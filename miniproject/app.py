
import os, bcrypt
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from pymongo import MongoClient, errors
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_secret")

# ── MongoDB 연결 ──
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/miniproject")
try:
    mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    # 연결 테스트
    mongo.admin.command('ping')
    print("MongoDB 연결 성공")
except errors.ServerSelectionTimeoutError:
    print("MongoDB 연결 실패 - 서버를 찾을 수 없습니다")
    exit(1)
except Exception as e:
    print(f"MongoDB 연결 오류: {e}")
    exit(1)

db = mongo.get_default_database()
users = db["users"]

# 인덱스 생성
try:
    users.create_index("username", unique=True)
    print("사용자명 인덱스 생성 완료")
except errors.PyMongoError as e:
    print(f"인덱스 생성 중 오류: {e}")

# ── 헬퍼 함수 ──
def is_logged_in():
    """로그인 상태 확인"""
    return session.get("user") is not None

def require_login():
    """로그인이 필요한 라우트용 데코레이터"""
    if not is_logged_in():
        return redirect(url_for("login_page"))
    return None

# ── 페이지 라우트 ──
@app.route("/")
def main_page():
    user = session.get("user")
    print(f"세션 정보: {session}")
    print(f"사용자 정보: {user}")
    return render_template("main.html", user=user)

@app.route("/login")
def login_page():
    # 이미 로그인된 경우 메인으로 리다이렉트
    if is_logged_in():
        return redirect(url_for("main_page"))
    return render_template("login.html")

@app.route("/register")
def register_page():
    # 이미 로그인된 경우 메인으로 리다이렉트
    if is_logged_in():
        return redirect(url_for("main_page"))
    return render_template("register.html")

# ── API: 회원가입 ──
@app.route("/api/register", methods=["POST"])
def register_api():
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        confirm = data.get("confirm") or ""

        # 입력값 검증
        if not username or not password:
            return jsonify(success=False, msg="아이디/비밀번호를 입력해 주세요."), 400
        
        if len(username) < 3 or len(username) > 20:
            return jsonify(success=False, msg="아이디는 3~20자 사이여야 합니다."), 400
            
        if len(password) < 6:
            return jsonify(success=False, msg="비밀번호는 최소 6자 이상이어야 합니다."), 400
            
        if password != confirm:
            return jsonify(success=False, msg="비밀번호가 일치하지 않습니다."), 400

        # 비밀번호 해시화
        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12))
        
        # DB에 사용자 추가
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
@app.route("/api/login", methods=["POST"])
def login_api():
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        
        if not username or not password:
            return jsonify(success=False, msg="아이디와 비밀번호를 입력해 주세요."), 400

        # 사용자 조회
        user = users.find_one({"username": username})
        if not user:
            return jsonify(success=False, msg="존재하지 않는 아이디입니다."), 401

        # 비밀번호 검증
        if not bcrypt.checkpw(password.encode("utf-8"), user["passwordHash"]):
            return jsonify(success=False, msg="비밀번호가 일치하지 않습니다."), 401

        # 로그인 성공 → 세션 저장
        session["user"] = {"username": username}
        print(f"로그인 성공, 세션 저장: {session['user']}")
        return jsonify(success=True, msg="로그인 성공")
        
    except errors.PyMongoError as e:
        print(f"로그인 DB 오류: {e}")
        return jsonify(success=False, msg="서버 오류가 발생했습니다."), 500
    except Exception as e:
        print(f"로그인 오류: {e}")
        return jsonify(success=False, msg="처리 중 오류가 발생했습니다."), 500

# ── 로그아웃 ──
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main_page"))

# ── 계정 삭제 ──
@app.route("/account/delete", methods=["POST"])
def delete_account():
    # 로그인 여부 확인
    if not is_logged_in():
        return jsonify(success=False, msg="로그인이 필요합니다."), 401

    try:
        username = session["user"]["username"]

        # 사용자 삭제
        result = users.delete_one({"username": username})
        if result.deleted_count == 0:
            return jsonify(success=False, msg="사용자를 찾을 수 없습니다."), 404

        # (선택) 관련 데이터도 함께 삭제
        # db["posts"].delete_many({"author": username})

        # 세션 정리
        session.clear()
        return jsonify(success=True, msg="계정이 삭제되었습니다.")
        
    except errors.PyMongoError as e:
        print(f"계정 삭제 DB 오류: {e}")
        return jsonify(success=False, msg="삭제 중 오류가 발생했습니다."), 500
    except Exception as e:
        print(f"계정 삭제 오류: {e}")
        return jsonify(success=False, msg="처리 중 오류가 발생했습니다."), 500

# 에러 핸들러는 일단 주석 처리 (필요시 나중에 404.html, 500.html 파일 생성 후 사용)
# @app.errorhandler(404)
# def not_found(error):
#     return render_template("404.html"), 404

# @app.errorhandler(500)  
# def internal_error(error):
#     return render_template("500.html"), 500

# ── 앱 종료 시 MongoDB 연결 정리 ──
import atexit

def cleanup():
    if mongo:
        mongo.close()
        print("MongoDB 연결 정리 완료")

atexit.register(cleanup)

if __name__ == "__main__":
    print("Flask 앱 시작...")
    app.run(host="0.0.0.0", port=3000, debug=True)