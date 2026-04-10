from flask import Flask, request, jsonify
import asyncio, json, binascii, requests, aiohttp, urllib3
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import DecodeError
import like_pb2, like_count_pb2, uid_generator_pb2
from config import URLS_INFO ,URLS_LIKE,FILES
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

def load_tokens(server):
    filename = FILES.get(server, 'token_me.json')

    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "Tokens", filename)

    print("Trying path:", path)  # 👈 مهم جدًا

    if not os.path.exists(path):
        raise FileNotFoundError(f"❌ الملف مش موجود هنا: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_headers(token):
    return {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Expect": "100-continue",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB53",
        }
key = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
iv = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
def encrypt_message(data):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(data, AES.block_size))

def create_like(uid, region):
    m = like_pb2.LikeRequest()
    m.target_uid = int(uid)
    m.action = region
    return m.SerializeToString()

def create_uid(uid):
    m = uid_generator_pb2.uid_generator(); m.saturn_, m.garena = int(uid), 1
    return m.SerializeToString()

async def send(token, url, data):
    headers = get_headers(token)
    async with aiohttp.ClientSession() as s:
        async with s.post(url, data=data, headers=headers) as r:
            return await r.text() if r.status == 200 else None

async def multi(uid, server, url):
    enc = encrypt_message(create_like(uid, server))
    tokens = load_tokens(server)
    return await asyncio.gather(
    *[send(t['token'], url, enc) for t in tokens]
)

def get_info(enc, server, token):
    urls =URLS_INFO
    r = requests.post(urls.get(server,"https://clientbp.ggblueshark.com/GetPlayerPersonalShow"),
                      data=enc, headers=get_headers(token), verify=False)
    try: p = like_count_pb2.Info(); p.ParseFromString(r.content); return p
    except DecodeError: return None

@app.route("/like")
def like():
    uid, server = request.args.get("uid"), request.args.get("server","").upper()
    if not uid or not server: return jsonify(error="UID and server required"),400
    tokens = load_tokens(server); enc = encrypt_message(create_uid(uid))
    before, tok = None, None
    for t in tokens[:10]:
        before = get_info(enc, server, t["token"])
        if before: tok = t["token"]; break
    if not before: return jsonify(error="Player not found"),500
    before_like = int(json.loads(MessageToJson(before)).get('AccountInfo',{}).get('Likes',0))
    urls =URLS_LIKE
    asyncio.run(multi(uid, server, urls.get(server,"https://clientbp.ggpolarbear.com/LikeProfile")))
    after = json.loads(MessageToJson(get_info(enc, server, tok)))
    after_like = int(after.get('AccountInfo',{}).get('Likes',0))
    return jsonify({
        
        
        "credits":"Ali Maher 🌸",
        "likes_added": after_like - before_like,
        "likes_before": before_like,
        "likes_after": after_like,
        "player": after.get('AccountInfo',{}).get('PlayerNickname',''),
        "uid": after.get('AccountInfo',{}).get('UID',0),
        "status": 1 if after_like-before_like else 2,
        
       
    })

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)









    
#URL_ENPOINTS ="http://127.0.0.1:5000/like?uid=13002831333&server=me"
#credits : "Ali Maher 🌸/"
