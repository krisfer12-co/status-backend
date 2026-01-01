from fastapi import FastAPI, HTTPException, UploadFile, File
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
import base64

app = FastAPI(title="STATUS API", version="2.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "status_db")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE = os.environ.get("TWILIO_PHONE_NUMBER", "")

client = None
db = None

class PersonInfo(BaseModel):
    birth_name: str
    email: EmailStr
    phone: str
    state: str
    age: int

class CoupleRegistration(BaseModel):
    person1: PersonInfo
    person2: PersonInfo
    photos: List[str] = []
    relationship_start_date: str

class VerifyRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    type: str = "email"

class VerifyConfirm(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    code: str
    type: str = "email"

class IDUpload(BaseModel):
    registration_id: str
    person_number: int
    id_image: str

def generate_code():
    return ''.join(random.choices(string.digits, k=6))

def send_email(to_email, code):
    if not SENDGRID_API_KEY:
        return False
    try:
        requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": SENDER_EMAIL, "name": "STATUS App"},
                "subject": "STATUS Verification Code",
                "content": [{"type": "text/plain", "value": f"Your STATUS verification code is: {code}\n\nThis code expires in 10 minutes."}]
            }
        )
        return True
    except:
        return False

def send_sms(to_phone, code):
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_PHONE:
        return False
    try:
        requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            data={
                "From": TWILIO_PHONE,
                "To": to_phone,
                "Body": f"Your STATUS verification code is: {code}"
            }
        )
        return True
    except:
        return False

@app.on_event("startup")
async def startup():
    global client, db
    if MONGO_URL:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]

@app.get("/")
async def root():
    return {"message": "STATUS API", "version": "2.0.0", "status": "running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/verify/email/request")
async def request_email_verification(data: dict):
    email = data.get("email")
    if not email or not db:
        raise HTTPException(status_code=400, detail="Email required")
    code = generate_code()
    await db.verifications.update_one(
        {"email": email, "type": "email"},
        {"$set": {"code": code, "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat()}},
        upsert=True
    )
    sent = send_email(email, code)
    return {"message": "Verification code sent", "success": sent}

@app.post("/api/verify/email/confirm")
async def confirm_email_verification(data: dict):
    email = data.get("email")
    code = data.get("code")
    if not db:
        raise HTTPException(status_code=500, detail="Database error")
    v = await db.verifications.find_one({"email": email, "type": "email"})
    if not v or v["code"] != code:
        raise HTTPException(status_code=400, detail="Invalid code")
    await db.verifications.update_one({"email": email, "type": "email"}, {"$set": {"verified": True}})
    return {"verified": True}

@app.post("/api/verify/sms/request")
async def request_sms_verification(data: dict):
    phone = data.get("phone")
    if not phone or not db:
        raise HTTPException(status_code=400, detail="Phone required")
    code = generate_code()
    await db.verifications.update_one(
        {"phone": phone, "type": "sms"},
        {"$set": {"code": code, "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat()}},
        upsert=True
    )
    sent = send_sms(phone, code)
    return {"message": "Verification code sent", "success": sent}

@app.post("/api/verify/sms/confirm")
async def confirm_sms_verification(data: dict):
    phone = data.get("phone")
    code = data.get("code")
    if not db:
        raise HTTPException(status_code=500, detail="Database error")
    v = await db.verifications.find_one({"phone": phone, "type": "sms"})
    if not v or v["code"] != code:
        raise HTTPException(status_code=400, detail="Invalid code")
    await db.verifications.update_one({"phone": phone, "type": "sms"}, {"$set": {"verified": True}})
    return {"verified": True}

@app.post("/api/verify/id/upload")
async def upload_id(data: dict):
    registration_id = data.get("registration_id")
    person_number = data.get("person_number")
    id_image = data.get("id_image")
    if not db or not registration_id or not id_image:
        raise HTTPException(status_code=400, detail="Missing data")
    await db.id_verifications.insert_one({
        "_id": str(uuid.uuid4()),
        "registration_id": registration_id,
        "person_number": person_number,
        "id_image": id_image,
        "status": "pending_review",
        "submitted_at": datetime.utcnow().isoformat()
    })
    return {"message": "ID uploaded for review", "status": "pending_review"}

@app.get("/api/admin/pending-ids")
async def get_pending_ids():
    if not db:
        return {"pending": []}
    pending = []
    async for doc in db.id_verifications.find({"status": "pending_review"}):
        pending.append({
            "id": doc["_id"],
            "registration_id": doc["registration_id"],
            "person_number": doc["person_number"],
            "submitted_at": doc["submitted_at"]
        })
    return {"pending": pending}

@app.post("/api/admin/approve-id")
async def approve_id(data: dict):
    id_verification_id = data.get("id")
    approved = data.get("approved", False)
    if not db:
        raise HTTPException(status_code=500, detail="Database error")
    status = "approved" if approved else "rejected"
    await db.id_verifications.update_one(
        {"_id": id_verification_id},
        {"$set": {"status": status, "reviewed_at": datetime.utcnow().isoformat()}}
    )
    return {"message": f"ID {status}", "status": status}

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
        "status": "pending_verification",
        "verification": {
            "person1_email": False,
            "person1_phone": False,
            "person1_id": False,
            "person2_email": False,
            "person2_phone": False,
            "person2_id": False
        },
        "created_at": datetime.utcnow().isoformat()
    }
    await db.couples.insert_one(doc)
    return {"couple_id": couple_id, "message": "Registration started - verification required", "status": "pending_verification"}

@app.get("/api/couples/{couple_id}")
async def get_couple(couple_id: str):
    if not db:
        raise HTTPException(status_code=500, detail="Database error")
    couple = await db.couples.find_one({"_id": couple_id})
    if not couple:
        raise HTTPException(status_code=404, detail="Not found")
    return couple

@app.post("/api/couples/{couple_id}/verify")
async def update_couple_verification(couple_id: str, data: dict):
    if not db:
        raise HTTPException(status_code=500, detail="Database error")
    field = data.get("field")
    if field:
        await db.couples.update_one(
            {"_id": couple_id},
            {"$set": {f"verification.{field}": True}}
        )
    couple = await db.couples.find_one({"_id": couple_id})
    if couple:
        v = couple.get("verification", {})
        all_verified = all([
            v.get("person1_email"), v.get("person1_phone"), v.get("person1_id"),
            v.get("person2_email"), v.get("person2_phone"), v.get("person2_id")
        ])
        if all_verified:
            await db.couples.update_one({"_id": couple_id}, {"$set": {"status": "active"}})
    return {"message": "Verification updated"}

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

@app.get("/api/stats")
async def stats():
    if not db:
        return {"total_registrations": 0, "active_relationships": 0, "pending_verifications": 0}
    total = await db.couples.count_documents({})
    active = await db.couples.count_documents({"status": "active"})
    pending = await db.couples.count_documents({"status": "pending_verification"})
    return {"total_registrations": total, "active_relationships": active, "pending_verifications": pending}
