import os, bcrypt, atexit
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from pymongo import MongoClient, errors
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_secret")

# ── MongoDB 연결 ──
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27018/miniproject")
try:
    mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    mongo.admin.command("ping")  # 연결 테스트
    print("MongoDB 연결 성공")
except errors.ServerSelectionTimeoutError:
    print("MongoDB 연결 실패 - 서버를 찾을 수 없습니다")
    raise
except Exception as e:
    print(f"MongoDB 연결 오류: {e}")
    raise

db = mongo.get_default_database()
users = db["users"]

# 인덱스 생성
try:
    users.create_index("username", unique=True)
    print("사용자명 인덱스 생성 완료")
except errors.PyMongoError as e:
    print(f"인덱스 생성 중 오류: {e}")

# ── 유틸 ──
def is_logged_in() -> bool:
    return session.get("user") is not None

# ── 페이지 라우트 ──
@app.get("/")
def main_page():
    user = session.get("user")
    return render_template("main.html", user=user)

@app.get("/login")
def login_page():
    if is_logged_in():
        return redirect(url_for("main_page"))
    return render_template("login.html")

@app.get("/register")
def register_page():
    if is_logged_in():
        return redirect(url_for("main_page"))
    return render_template("register.html")

# 글쓰기 페이지(템플릿: templates/PostWrite.html)
@app.get("/write", endpoint="write_page")
def write_page():
    return render_template("PostWrite.html")

# 글 상세 페이지(임시: 고정 템플릿 렌더)
# 추후 DB 연동 시 /post/<post_id> 로 바꾸면 됩니다.
@app.get("/post/view", endpoint="post_view_page")
def post_view_page():
    return render_template("PostView.html")

# ── API: 회원가입 ──
@app.post("/api/register")
def register_api():
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        confirm  = data.get("confirm")  or ""

        if not username or not password:
            return jsonify(success=False, msg="아이디/비밀번호를 입력해 주세요."), 400
        if not (3 <= len(username) <= 20):
            return jsonify(success=False, msg="아이디는 3~20자 사이여야 합니다."), 400
        if len(password) < 6:
            return jsonify(success=False, msg="비밀번호는 최소 6자 이상이어야 합니다."), 400
        if password != confirm:
            return jsonify(success=False, msg="비밀번호가 일치하지 않습니다."), 400

        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12))
        users.insert_one({"username": username, "passwordHash": pw_hash})
        return jsonify(success=True, msg="회원가입이 완료되었습니다.")
    except errors.DuplicateKeyError:
        return jsonify(success=False, msg="이미 존재하는 아이디입니다."), 409
    except errors.PyMongoError as e:
        print(f"회원가입 DB 오류: {e}")
        return jsonify(success=False, msg="서버 오류가 발생했습니다."), 500
    except Exception as e:
        print(f"회원가입 오류: {e}")
        return jsonify(success=False, msg="처리 중 오류가 발생했습니다."), 500

# ── API: 로그인 ──
@app.post("/api/login")
def login_api():
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify(success=False, msg="아이디와 비밀번호를 입력해 주세요."), 400

        user = users.find_one({"username": username})
        if not user:
            return jsonify(success=False, msg="존재하지 않는 아이디입니다."), 401

        if not bcrypt.checkpw(password.encode("utf-8"), user["passwordHash"]):
            return jsonify(success=False, msg="비밀번호가 일치하지 않습니다."), 401

        session["user"] = {"username": username}
        return jsonify(success=True, msg="로그인 성공")
    except errors.PyMongoError as e:
        print(f"로그인 DB 오류: {e}")
        return jsonify(success=False, msg="서버 오류가 발생했습니다."), 500
    except Exception as e:
        print(f"로그인 오류: {e}")
        return jsonify(success=False, msg="처리 중 오류가 발생했습니다."), 500

# ── 로그아웃 ──
@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("main_page"))

# ── 계정 삭제(POST) ──
@app.post("/account/delete")
def delete_account():
    if not is_logged_in():
        return redirect(url_for("login_page"))
    try:
        username = session["user"]["username"]
        res = users.delete_one({"username": username})
        # (선택) 게시글도 함께 삭제: db["posts"].delete_many({"author": username})
    except errors.PyMongoError as e:
        print(f"계정 삭제 DB 오류: {e}")
        return "삭제 중 오류가 발생했습니다.", 500
    session.clear()
    return redirect(url_for("main_page"))

# ── (선택) 헬스 체크 ──
@app.get("/api/health")
def health():
    try:
        db.command("ping")
        return {"ok": True, "users": db["users"].count_documents({})}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

# ── 종료 시 Mongo 연결 정리 ──
def cleanup():
    if mongo:
        mongo.close()
        print("MongoDB 연결 정리 완료")
atexit.register(cleanup)

if __name__ == "__main__":
    print("Flask 앱 시작...")
    print(app.url_map)  # 등록된 라우트 확인용
    app.run(host="0.0.0.0", port=3000, debug=True)
