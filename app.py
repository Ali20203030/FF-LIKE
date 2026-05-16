from flask import Flask, request, jsonify
import asyncio, json, binascii, aiohttp, urllib3
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import DecodeError
import like_pb2, like_count_pb2, uid_generator_pb2
from config import URLS_INFO, URLS_LIKE, FILES

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

def load_tokens(server):
    filename = FILES.get(server, 'token_me.json')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "Token", filename)
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
        "X-Unity-Version": "2018.4.11f1",  # إصدار الكود الأول الأسرع والأضمن
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

# دالة إرسال سريعة تشارك نفس الجلسة المستمرة
async def send_like_fast(session, token, url, data):
    try:
        async with session.post(url, data=data, headers=get_headers(token), timeout=5) as r:
            return await r.read()
    except:
        return None

# دالة جلب معلومات مسرعة (Async) بديلة لـ requests البطيئة
async def get_info_async(session, url, enc, token):
    try:
        async with session.post(url, data=enc, headers=get_headers(token), timeout=5) as r:
            if r.status == 200:
                content = await r.read()
                p = like_count_pb2.Info()
                p.ParseFromString(content)
                return p
    except:
        pass
    return None

async def process_all_likes(uid, server, url_like, url_info):
    tokens = load_tokens(server)
    valid_tokens = [t['token'] for t in tokens if t and isinstance(t, dict) and 'token' in t]
    
    if not valid_tokens:
        return {"error": "No valid tokens"}, 404

    enc_uid = encrypt_message(create_uid(uid))
    enc_like = encrypt_message(create_like(uid, server))
    
    # فتح جلسة واحدة عملاقة لجميع الطلبات لتوفر وقت الـ Connection
    async with aiohttp.ClientSession() as session:
        # 1. جلب معلومات الحساب قبل الزيادة (باستخدام أول توكن شغال)
        before = None
        tok = None
        for t in valid_tokens[:5]:
            before = await get_info_async(session, url_info, enc_uid, t)
            if before:
                tok = t
                break
                
        if not before:
            return {"error": "Player not found or tokens blocked"}, 500
            
        before_like = int(json.loads(MessageToJson(before)).get('AccountInfo', {}).get('Likes', 0))
        
        # 2. إرسال اللايكات دفعة واحدة في نفس الملي ثانية لجميع التوكنات
        tasks = [send_like_fast(session, t, url_like, enc_like) for t in valid_tokens]
        await asyncio.gather(*tasks)
        
        # 3. جلب معلومات الحساب بعد الزيادة مباشرة بنفس الجلسة السريعة
        after_data = await get_info_async(session, url_info, enc_uid, tok)
        if not after_data:
            after_data = before
            
        after = json.loads(MessageToJson(after_data))
        after_like = int(after.get('AccountInfo', {}).get('Likes', 0))
        
        return {
            "credits": "Ali Maher 🌸",
            "likes_added": after_like - before_like,
            "likes_before": before_like,
            "likes_after": after_like,
            "player": after.get('AccountInfo', {}).get('PlayerNickname', ''),
            "uid": after.get('AccountInfo', {}).get('UID', 0),
            "region": after.get('AccountInfo', {}).get('region', ''),
            "status": 1 if after_like - before_like else 2,
        }, 200

@app.route("/like")
def like():
    uid = request.args.get("uid")
    server = (request.args.get("server") or request.args.get("region") or "").upper()
    
    if not uid or not server: 
        return jsonify(error="UID and server required"), 400
        
    url_info = URLS_INFO.get(server, "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow")
    url_like = URLS_LIKE.get(server, "https://clientbp.ggpolarbear.com/LikeProfile")
    
    # تشغيل المعالجة السريعة
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result, status_code = loop.run_until_complete(process_all_likes(uid, server, url_like, url_info))
    loop.close()
    
    return jsonify(result), status_code

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
