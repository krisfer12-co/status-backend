from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import os
import uuid
from datetime import datetime, timedelta
import random
import string
import requests

app = FastAPI(title="STATUS API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "status_db")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")

client = None
db = None

class PersonInfo(BaseModel):
    birth_name: str
    email: EmailStr
    state: str
    age: int

class CoupleRegistration(BaseModel):
    person1: PersonInfo
    person2: PersonInfo
    photos: List[str] = []
    relationship_start_date: str

@app.on_event("startup")
async def startup():
    global client, db
    if MONGO_URL:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]

@app.get("/")
async def root():
    return {"message": "STATUS API", "version": "1.0.0", "status": "running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/couples")
async def register_couple(couple: CoupleRegistration):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    existing = await db.couples.find_one({
        "$or": [
            {"person1.email": couple.person1.email},
            {"person2.email": couple.person2.email}
        ],
        "status": "active"
    })
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    couple_id = str(uuid.uuid4())
    doc = {
        "_id": couple_id,
        "person1": couple.person1.dict(),
        "person2": couple.person2.dict(),
        "photos": couple.photos,
        "relationship_start_date": couple.relationship_start_date,
        "status": "active",
        "created_at": datetime.utcnow().isoformat()
    }
    await db.couples.insert_one(doc)
    return {"couple_id": couple_id, "message": "Registration successful"}

@app.get("/api/search")
async def search(name: Optional[str] = None, state: Optional[str] = None, age: Optional[int] = None):
    if not db:
        return {"results": [], "total": 0}
    query = {"status": "active"}
    if name:
        query["$or"] = [
            {"person1.birth_name": {"$regex": name, "$options": "i"}},
            {"person2.birth_name": {"$regex": name, "$options": "i"}}
        ]
    results = []
    async for doc in db.couples.find(query).limit(20):
        results.append({
            "id": doc["_id"],
            "person1": {"name": doc["person1"]["birth_name"], "state": doc["person1"]["state"], "age": doc["person1"]["age"]},
            "person2": {"name": doc["person2"]["birth_name"], "state": doc["person2"]["state"], "age": doc["person2"]["age"]},
            "relationship_start_date": doc.get("relationship_start_date"),
            "has_photos": len(doc.get("photos", [])) > 0
        })
    return {"results": results, "total": len(results)}

@app.post("/api/verify/email/request")
async def request_verification(data: dict):
    email = data.get("email")
    if not email or not db:
        raise HTTPException(status_code=400, detail="Email required")
    code = ''.join(random.choices(string.digits, k=6))
    await db.verifications.update_one(
        {"email": email},
        {"$set": {"code": code, "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat()}},
        upsert=True
    )
    if SENDGRID_API_KEY:
        requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": email}]}],
                "from": {"email": SENDER_EMAIL},
                "subject": "STATUS Verification Code",
                "content": [{"type": "text/plain", "value": f"Your code: {code}"}]
            }
        )
    return {"message": "Code sent", "success": True}

@app.post("/api/verify/email/confirm")
async def confirm_verification(data: dict):
    email = data.get("email")
    code = data.get("code")
    if not db:
        raise HTTPException(status_code=500, detail="Database error")
    v = await db.verifications.find_one({"email": email})
    if not v or v["code"] != code:
        raise HTTPException(status_code=400, detail="Invalid code")
    return {"verified": True}

@app.get("/api/stats")
async def stats():
    if not db:
        return {"total_registrations": 0, "active_relationships": 0}
    total = await db.couples.count_documents({})
    active = await db.couples.count_documents({"status": "active"})
    return {"total_registrations": total, "active_relationships": active}
