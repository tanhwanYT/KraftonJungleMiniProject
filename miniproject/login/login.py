import os
from flask import Flask, render_template, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ── Mongo 연결 ───────────────────────────
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/miniproject")
mongo = MongoClient(MONGODB_URI)
db = mongo.get_default_database()  # miniproject DB

# ── 로그인 페이지(기존) ───────────────────
@app.route("/login")
def login_page():
    return render_template("login.html")

# ── 헬스체크: Mongo 연결 확인 ─────────────
@app.route("/api/health")
def health():
    try:
        # 'ping'으로 연결 확인
        mongo.admin.command("ping")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # 외부 접속 필요 시 포트/보안그룹 확인
    app.run(host="0.0.0.0", port=3000, debug=True)
