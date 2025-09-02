# miniproject/app.py
import os, bcrypt
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from pymongo import MongoClient, errors
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_secret")  # 세션/보호 라우트에 필요

# ── MongoDB 연결: 앱 시작 시 1번만 생성, 모든 라우트에서 재사용 ──
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27018/miniproject") #ec2에서 flask실행시 포트번호 27017로 반드시 변경 같은
mongo = MongoClient(MONGODB_URI)
db = mongo.get_default_database()
users = db["users"]
try:
    users.create_index("username", unique=True)
except errors.PyMongoError:
    pass

# ── 페이지 라우트 ──
@app.get("/")
def main_page():
    return render_template("main.html")  # 세션으로 로그인 여부 분기 가능

@app.get("/login")
def login_page():
    return render_template("login.html")

@app.get("/register")
def register_page():
    return render_template("register.html")

# ── API: 회원가입 (DB에 계정 추가) ──
@app.post("/api/register")
def register_api():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    confirm  = data.get("confirm") or ""

    if not username or not password:
        return jsonify(success=False, msg="아이디/비밀번호를 입력해 주세요."), 400
    if password != confirm:
        return jsonify(success=False, msg="비밀번호가 일치하지 않습니다."), 400

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12))
    try:
        users.insert_one({"username": username, "passwordHash": pw_hash})
    except errors.DuplicateKeyError:
        return jsonify(success=False, msg="이미 존재하는 아이디입니다."), 409
    return jsonify(success=True, msg="회원가입 완료")

# ── API: 로그인 (DB에서 검증) ──
@app.post("/api/login")
def login_api():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify(success=False), 400

    user = users.find_one({"username": username})
    if not user or not bcrypt.checkpw(password.encode("utf-8"), user["passwordHash"]):
        return jsonify(success=False)

    # 로그인 성공 → 세션 저장 (선택)
    session["user"] = {"username": username}
    return jsonify(success=True)

@app.get("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("main_page"))

if __name__ == "__main__":
    # print(app.url_map)  # 등록된 라우트 확인용
    app.run(host="0.0.0.0", port=3000, debug=True)

