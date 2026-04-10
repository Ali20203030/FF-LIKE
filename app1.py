from flask import Flask, request, jsonify
import asyncio, json, requests, aiohttp, urllib3
import os, random
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import DecodeError
import random
import like_pb2, like_count_pb2, uid_generator_pb2
from config import URLS_INFO, URLS_LIKE, FILES

import random

def random_device():
    devices = [
        "Dalvik/2.1.0 (Linux; U; Android 10; SM-G975F Build/QP1A.190711.020)",
        "Dalvik/2.1.0 (Linux; U; Android 11; Redmi Note 10 Pro Build/RKQ1.200826.002)",
        "Dalvik/2.1.0 (Linux; U; Android 12; M2012K11AG Build/SKQ1.211006.001)",
        "Dalvik/2.1.0 (Linux; U; Android 13; Pixel 6 Build/TQ3A.230805.001)",
        "Dalvik/2.1.0 (Linux; U; Android 10; Poco X3 Pro Build/QKQ1.200512.002)"
    ]
    return random.choice(devices)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ================= LOAD TOKENS =================

def load_tokens(server):
    filename = FILES.get(server, "token_me.json")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "tokens", filename)

    print("Trying path:", path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"❌ الملف مش موجود هنا: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ================= HEADERS =================
DEVICE_CACHE = {}
def device_for_token(token):

    if token in DEVICE_CACHE:
        return DEVICE_CACHE[token]

    models = [
        "SM-G973F",
        "Redmi Note 8",
        "MI 9T",
        "POCO X3",
        "SM-A505F",
        "Vivo 1901"
    ]

    android_versions = ["8.1.0", "9", "10", "11"]

    model = random.choice(models)
    android = random.choice(android_versions)

    ua = f"Dalvik/2.1.0 (Linux; U; Android {android}; {model} Build/PKQ1)"

    DEVICE_CACHE[token] = ua
    return ua
def get_headers(token):
    return {
        "User-Agent": random_device(),
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": f"2018.4.{random.randint(10,25)}f1",
        "X-GA": f"v1 1 {random.randint(1000,9999)}",
        "ReleaseVersion": "OB52",
    }

# ================= ENCRYPTION =================

key = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
iv  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

def encrypt_message(data):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(data, AES.block_size))

# ================= PROTO =================

def create_like(uid, region):
    m = like_pb2.LikeRequest()
    m.target_uid = int(uid)
    m.action = region
    return m.SerializeToString()

def create_uid(uid):
    m = uid_generator_pb2.uid_generator()
    m.saturn_ = int(uid)
    m.garena = 1
    return m.SerializeToString()

# ================= SEND LIKE =================

async def send(session, token, url, data):
    try:
        # delay عشوائي لتجنب spam detection
        await asyncio.sleep(random.uniform(0.25, 0.8))

        headers = get_headers(token)

        async with session.post(url, data=data, headers=headers) as r:
            if r.status == 200:
                return await r.text()
            return None

    except Exception as e:
        print("Send error:", e)
        return None

# ================= MULTI LIKE =================

async def multi(uid, server, url):

    enc = encrypt_message(create_like(uid, server))
    tokens = load_tokens(server)

    print(f"Using {len(tokens)} tokens")

    async with aiohttp.ClientSession() as session:

        tasks = [
            send(session, t["token"], url, enc)
            for t in tokens
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

    success = sum(1 for r in results if r)
    print("Success requests:", success)

    return results

# ================= GET INFO =================

def get_info(enc, server, token):
    urls = URLS_INFO

    r = requests.post(
        urls.get(server, "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"),
        data=enc,
        headers=get_headers(token),
        verify=False,
    )

    try:
        p = like_count_pb2.Info()
        p.ParseFromString(r.content)
        return p
    except DecodeError:
        return None

# ================= ROUTE =================

@app.route("/like")
def like():

    uid = request.args.get("uid")
    server = request.args.get("server", "").upper()

    if not uid or not server:
        return jsonify(error="UID and server required"), 400

    tokens = load_tokens(server)

    enc = encrypt_message(create_uid(uid))

    before = None
    tok = None

    # نجيب حساب صالح لقراءة اللايكات
    for t in tokens[:10]:
        before = get_info(enc, server, t["token"])
        if before:
            tok = t["token"]
            break

    if not before:
        return jsonify(error="Player not found"), 500

    before_like = int(
        json.loads(MessageToJson(before))
        .get("AccountInfo", {})
        .get("Likes", 0)
    )

    urls = URLS_LIKE

    # ارسال اللايكات
    asyncio.run(
        multi(uid, server,
              urls.get(server,
              "https://clientbp.ggpolarbear.com/LikeProfile"))
    )

    after_proto = get_info(enc, server, tok)
    after = json.loads(MessageToJson(after_proto))

    after_like = int(after.get("AccountInfo", {}).get("Likes", 0))

    return jsonify({
        "credits": "Ali Maher 🌸",
        "likes_added": after_like - before_like,
        "likes_before": before_like,
        "likes_after": after_like,
        "player": after.get("AccountInfo", {}).get("PlayerNickname", ""),
        "uid": after.get("AccountInfo", {}).get("UID", 0),
        "status": 1 if after_like - before_like else 2,
    })

# ================= RUN =================

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)