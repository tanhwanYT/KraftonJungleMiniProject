import os
import atexit
from functools import wraps
from datetime import datetime, timezone

import bcrypt
from dotenv import load_dotenv
from bson import ObjectId
from pymongo import MongoClient, errors
from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, send_from_directory
)
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_secret")
# 끝 슬래시 혼동 방지 (/comments vs /comments/)
app.url_map.strict_slashes = False

# ──────────────────────────────────────────────────────────────────────────
# MongoDB 연결
# ──────────────────────────────────────────────────────────────────────────
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27018/miniproject")
try:
    mongo = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    mongo.admin.command("ping")
    print("MongoDB 연결 성공")
except errors.ServerSelectionTimeoutError:
    print("MongoDB 연결 실패 - 서버를 찾을 수 없습니다")
    raise
except Exception as e:
    print(f"MongoDB 연결 오류: {e}")
    raise

db = mongo.get_default_database()
users = db["users"]
posts = db["posts"]
comments = db["comments"]

# 인덱스 생성
try:
    users.create_index("username", unique=True)
    posts.create_index([("board", 1), ("created_at", -1)])
    posts.create_index([("author", 1), ("created_at", -1)])
    comments.create_index([("post_id", 1), ("created_at", -1)])
    print("인덱스 생성 완료")
except errors.PyMongoError as e:
    print(f"인덱스 생성 중 오류: {e}")

# ──────────────────────────────────────────────────────────────────────────
# 업로드/보안 설정
# ──────────────────────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(app.instance_path, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_FILE_MB = 5  # 파일당 5MB 제한

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,  # HTTPS 환경이면 True 권장
)

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTS

# ──────────────────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────────────────
def is_logged_in() -> bool:
    return session.get("user") is not None

def login_required_json(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return jsonify(success=False, msg="로그인이 필요합니다."), 401
        return f(*args, **kwargs)
    return wrapper

def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

def post_doc_to_json(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "title": doc["title"],
        "content": doc["content"],
        "board": doc["board"],
        "author": doc["author"],
        "created_at": to_iso(doc["created_at"]),
        # 프런트에서 그대로 <img src="{url}"> 로 사용 가능한 절대경로 저장
        "images": doc.get("images", []),  # e.g. ["/uploads/660a..._image.png"]
        # 좋아요 정보(권장)
        "likes_count": doc.get("likes_count", 0),
        "liked_by": doc.get("liked_by", []),
    }

def is_author(doc) -> bool:
    return is_logged_in() and session["user"]["username"] == doc["author"]

# ──────────────────────────────────────────────────────────────────────────
# 페이지 라우트
# ──────────────────────────────────────────────────────────────────────────
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

# 글쓰기 페이지
@app.get("/write", endpoint="write_page")
def write_page():
    return render_template("PostWrite.html")

# 글 상세 페이지(템플릿 고정; 추후 /post/<id> 로 변경 가능)
@app.get("/post/view", endpoint="post_view_page")
def post_view_page():
    user = session.get("user")
    # 템플릿은 비어 있는 상태로 렌더 → JS(PostView.js)가 API로 채움
    return render_template("PostView.html", post=None, comments=[], user=user)

# 업로드 파일 제공
@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ──────────────────────────────────────────────────────────────────────────
# API: 댓글
# ──────────────────────────────────────────────────────────────────────────
@app.get("/api/posts/<id>/comments")  # 댓글 목록 조회
def list_comments_api(id):
    try:
        oid = ObjectId(id)
        cur = comments.find({"post_id": oid}).sort([("created_at", -1)])
        items = []
        for c in cur:
            items.append({
                "id": str(c["_id"]),
                "author": c.get("author", "익명"),
                "content": c.get("content", ""),
                "created_at": to_iso(c["created_at"]),
            })
        return jsonify(success=True, data={"items": items})
    except Exception as e:
        print("comments list error:", e)
        return jsonify(success=False, msg="서버 오류가 발생했습니다."), 500

@app.post("/api/posts/<id>/comments")  # 댓글 작성
@login_required_json
def create_comment_api(id):
    try:
        data = request.get_json(silent=True) or {}
        content = (data.get("content") or "").strip()
        if not content:
            return jsonify(success=False, msg="댓글 내용을 입력해 주세요."), 400

        oid = ObjectId(id)
        post = posts.find_one({"_id": oid})
        if not post:
            return jsonify(success=False, msg="게시글을 찾을 수 없습니다."), 404

        doc = {
            "post_id": oid,
            "author": session["user"]["username"],
            "content": content,
            "created_at": datetime.utcnow(),
        }
        res = comments.insert_one(doc)
        return jsonify(success=True, data={
            "id": str(res.inserted_id),
            "author": doc["author"],
            "content": doc["content"],
            "created_at": to_iso(doc["created_at"]),
        }), 201
    except Exception as e:
        print("comment create error:", e)
        return jsonify(success=False, msg="서버 오류가 발생했습니다."), 500

# ──────────────────────────────────────────────────────────────────────────
# API: 좋아요
# ──────────────────────────────────────────────────────────────────────────
@app.post("/api/posts/<id>/like")
@login_required_json
def like_post_api(id):
    try:
        username = session["user"]["username"]
        oid = ObjectId(id)
        doc = posts.find_one({"_id": oid})
        if not doc:
            return jsonify(success=False, msg="게시글을 찾을 수 없습니다."), 404

        liked_by = set(doc.get("liked_by", []))
        if username in liked_by:
            liked_by.remove(username)
        else:
            liked_by.add(username)

        likes_count = len(liked_by)
        posts.update_one(
            {"_id": oid},
            {"$set": {"liked_by": list(liked_by), "likes_count": likes_count}}
        )
        return jsonify(success=True, data={"likes_count": likes_count, "liked": username in liked_by})
    except Exception as e:
        print("like error:", e)
        return jsonify(success=False, msg="서버 오류가 발생했습니다."), 500

# ──────────────────────────────────────────────────────────────────────────
# API: 회원가입 / 로그인 / 로그아웃 / 계정 삭제
# ──────────────────────────────────────────────────────────────────────────
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

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("main_page"))

@app.post("/account/delete")
def delete_account():
    if not is_logged_in():
        return redirect(url_for("login_page"))
    try:
        username = session["user"]["username"]
        users.delete_one({"username": username})
        # (선택) 본인 게시글/이미지 삭제 로직은 필요 시 추가
    except errors.PyMongoError as e:
        print(f"계정 삭제 DB 오류: {e}")
        return "삭제 중 오류가 발생했습니다.", 500
    session.clear()
    return redirect(url_for("main_page"))

# ──────────────────────────────────────────────────────────────────────────
# API: 게시글
# ──────────────────────────────────────────────────────────────────────────
@app.post("/api/posts")
@login_required_json
def create_post_api():
    """
    multipart/form-data:
      - title, content, board (text)
      - images (파일, 여러 개)
    """
    try:
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        board = (request.form.get("board") or "").strip()
        author = session["user"]["username"]

        if not title or not content or not board:
            return jsonify(success=False, msg="필수 항목이 누락되었습니다."), 400

        # 문서 우선 생성
        doc = {
            "title": title,
            "content": content,
            "board": board,
            "author": author,
            "created_at": datetime.utcnow(),
            "images": [],
            "likes_count": 0,   # 초기화
            "liked_by": [],     # 초기화
        }
        result = posts.insert_one(doc)
        post_id = result.inserted_id

        # 파일 저장
        files = request.files.getlist("images")
        saved_urls = []
        for file in files:
            if not file or file.filename == "":
                continue
            if not allowed_file(file.filename):
                return jsonify(success=False, msg="허용되지 않은 파일 형식입니다."), 400

            # 용량 체크
            file.seek(0, os.SEEK_END)
            size_mb = file.tell() / (1024 * 1024)
            file.seek(0)
            if size_mb > MAX_FILE_MB:
                return jsonify(success=False, msg=f"파일 용량은 {MAX_FILE_MB}MB 이하여야 합니다."), 400

            safe_name = secure_filename(file.filename)
            save_name = f"{post_id}_{safe_name}"
            save_path = os.path.join(UPLOAD_FOLDER, save_name)
            file.save(save_path)

            # 프런트에서 바로 사용 가능한 URL
            url_path = f"/uploads/{save_name}"
            saved_urls.append(url_path)

        if saved_urls:
            posts.update_one({"_id": post_id}, {"$set": {"images": saved_urls}})

        created = posts.find_one({"_id": post_id})
        return jsonify(success=True, data=post_doc_to_json(created)), 201

    except Exception as e:
        print(f"게시글 생성 오류: {e}")
        return jsonify(success=False, msg="서버 오류가 발생했습니다."), 500

@app.get("/api/posts")
def list_posts_api():
    """
    쿼리:
      - board: Cafeteria | Outside | Delivery (선택)
      - page, per_page
    """
    try:
        board = request.args.get("board")
        page = max(int(request.args.get("page", 1)), 1)
        per_page = min(max(int(request.args.get("per_page", 10)), 1), 50)

        query = {}
        if board:
            query["board"] = board

        cursor = (
            posts.find(query)
                 .sort([("_id", -1)])  # 최신순
                 .skip((page - 1) * per_page)
                 .limit(per_page)
        )
        items = [post_doc_to_json(doc) for doc in cursor]
        total = posts.count_documents(query)
        pages = (total + per_page - 1) // per_page

        return jsonify(success=True, data={
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages
        })
    except Exception as e:
        print(f"게시글 목록 오류: {e}")
        return jsonify(success=False, msg="서버 오류가 발생했습니다."), 500

@app.get("/api/posts/<id>")
def get_post_api(id):
    try:
        doc = posts.find_one({"_id": ObjectId(id)})
        if not doc:
            return jsonify(success=False, msg="게시글을 찾을 수 없습니다."), 404
        return jsonify(success=True, data=post_doc_to_json(doc))
    except Exception as e:
        print(f"게시글 조회 오류: {e}")
        return jsonify(success=False, msg="서버 오류가 발생했습니다."), 500

@app.delete("/api/posts/<id>")
@login_required_json
def delete_post_api(id):
    try:
        doc = posts.find_one({"_id": ObjectId(id)})
        if not doc:
            return jsonify(success=False, msg="게시글이 존재하지 않습니다."), 404
        if not is_author(doc):
            return jsonify(success=False, msg="권한이 없습니다."), 403

        # 이미지 파일 삭제
        for url_path in doc.get("images", []):
            if url_path.startswith("/uploads/"):
                filename = url_path.split("/uploads/", 1)[1]
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

        posts.delete_one({"_id": doc["_id"]})
        return jsonify(success=True, msg="삭제되었습니다.")
    except Exception as e:
        print(f"게시글 삭제 오류: {e}")
        return jsonify(success=False, msg="서버 오류가 발생했습니다."), 500

@app.get("/Cafeteria")
def cafeteria_page():
    user = session.get("user")
    return render_template("Cafateria.html", user=user, board="Cafeteria")

@app.get("/Outside")
def outside_page():
    user = session.get("user")
    return render_template("Outside.html", user=user, board="Outside")

@app.get("/Delivery")
def delivery_page():
    user = session.get("user")
    return render_template("Delivery.html", user=user, board="Delivery")
# ──────────────────────────────────────────────────────────────────────────
# 헬스 체크
# ──────────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    try:
        db.command("ping")
        return {"ok": True, "users": db["users"].count_documents({})}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

# API 에러는 JSON으로
@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith("/api/"):
        return jsonify(success=False, msg="리소스를 찾을 수 없습니다."), 404
    return render_template("404.html"), 404

@app.errorhandler(500)
def handle_500(e):
    if request.path.startswith("/api/"):
        return jsonify(success=False, msg="서버 내부 오류가 발생했습니다."), 500
    return render_template("500.html"), 500

# (선택) 405도 JSON으로 받고 싶다면 주석 해제
# @app.errorhandler(405)
# def handle_405(e):
#   if request.path.startswith("/api/"):
#       return jsonify(success=False, msg="허용되지 않은 메서드입니다."), 405
#   return "Method Not Allowed", 405

# ──────────────────────────────────────────────────────────────────────────
# 종료 시 Mongo 연결 정리
# ──────────────────────────────────────────────────────────────────────────
def cleanup():
    if mongo:
        mongo.close()
        print("MongoDB 연결 정리 완료")

atexit.register(cleanup)

if __name__ == "__main__":
    print("Flask 앱 시작...")
    print(app.url_map)
    app.run(host="0.0.0.0", port=3000, debug=True)
