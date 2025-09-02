from flask import Flask, request, jsonify
from pymongo import MongoClient

app = Flask(__name__)

# 로컬 MongoDB (기본 포트 27017)
client = MongoClient("mongodb://localhost:27017/")

# 만약 MongoDB Atlas(클라우드) 사용 시
# client = MongoClient("mongodb+srv://<username>:<password>@cluster0.mongodb.net/")

# db = client['mydatabase'] 
# users = db['users']    

db = client['MiniTest']
test_collection = db['test']

test_collection.insert_one({"name": "test_user2", "age": 21})

user = test_collection.find_one({"name": "test_user2"})
print(user)
