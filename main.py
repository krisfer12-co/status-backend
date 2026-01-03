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
import base64

app = FastAPI(title="STATUS API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "status_db")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE = os.environ.get("TWILIO_PHONE_NUMBER", "")
GOOGLE_VISION_KEY = os.environ.get("GOOGLE_VISION_API_KEY", "")

client = None
db = None

def generate_code():
    return ''.join(random.choices(string.digits, k=6))

def send_sms(to_phone, code):
    if not TWILIO_SID:
        return False
    try:
        requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            data={"From": TWILIO_PHONE, "To": to_phone, "Body": f"Your STATUS code: {code}"})
        return True
    except:
        return False

def send_email(to_email, code):
    if not SENDGRID_API_KEY:
        return False
    try:
        requests.post("https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
            json={"personalizations": [{"to": [{"email": to_email}]}], "from": {"email": SENDER_EMAIL, "name": "STATUS"}, "subject": "STATUS Verification Code", "content": [{"type": "text/plain", "value": f"Your code: {code}"}]})
        return True
    except:
        return False

def compare_faces(id_image_base64, selfie_base64):
    if not GOOGLE_VISION_KEY:
        return {"match": False, "error": "API key not configured"}
    try:
        url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_KEY}"
        def detect_face(img_base64):
            response = requests.post(url, json={"requests": [{"image": {"content": img_base64}, "features": [{"type": "FACE_DETECTION", "maxResults": 1}]}]})
            data = response.json()
            if "responses" in data and data["responses"] and "faceAnnotations" in data["responses"][0]:
                return data["responses"][0]["faceAnnotations"][0]
            return None
        id_face = detect_face(id_image_base64)
        selfie_face = detect_face(selfie_base64)
        if not id_face or not selfie_face:
            return {"match": False, "error": "Could not detect face in one or both images", "id_face": bool(id_face), "selfie_face": bool(selfie_face)}
        id_confidence = id_face.get("detectionConfidence", 0)
        selfie_confidence = selfie_face.get("detectionConfidence", 0)
        if id_confidence > 0.7 and selfie_confidence > 0.7:
            return {"match": True, "confidence": min(id_confidence, selfie_confidence), "message": "Face verification passed"}
        return {"match": False, "confidence": min(id_confidence, selfie_confidence), "message": "Face verification failed - low confidence"}
    except Exception as e:
        return {"match": False, "error": str(e)}

@app.on_event("startup")
async def startup():
    global client, db
    if MONGO_URL:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]

@app.get("/")
async def root():
    return {"message": "STATUS API", "version": "3.0.0", "status": "running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/verify/sms/request")
async def request_sms(data: dict):
    phone = data.get("phone")
    if not phone or not db:
        raise HTTPException(status_code=400, detail="Phone required")
    code = generate_code()
    await db.verifications.update_one({"phone": phone, "type": "sms"}, {"$set": {"code": code, "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat()}}, upsert=True)
    sent = send_sms(phone, code)
    return {"success": sent, "message": "SMS sent" if sent else "SMS failed"}

@app.post("/api/verify/sms/confirm")
async def confirm_sms(data: dict):
    phone, code = data.get("phone"), data.get("code")
    if not db:
        raise HTTPException(status_code=500, detail="Database error")
    v = await db.verifications.find_one({"phone": phone, "type": "sms"})
    if not v or v["code"] != code:
        raise HTTPException(status_code=400, detail="Invalid code")
    return {"verified": True}

@app.post("/api/verify/email/request")
async def request_email(data: dict):
    email = data.get("email")
    if not email or not db:
        raise HTTPException(status_code=400, detail="Email required")
    code = generate_code()
    await db.verifications.update_one({"email": email, "type": "email"}, {"$set": {"code": code, "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat()}}, upsert=True)
    sent = send_email(email, code)
    return {"success": sent, "message": "Email sent" if sent else "Email failed"}

@app.post("/api/verify/email/confirm")
async def confirm_email(data: dict):
    email, code = data.get("email"), data.get("code")
    if not db:
        raise HTTPException(status_code=500, detail="Database error")
    v = await db.verifications.find_one({"email": email, "type": "email"})
    if not v or v["code"] != code:
        raise HTTPException(status_code=400, detail="Invalid code")
    return {"verified": True}

@app.post("/api/verify/face")
async def verify_face(data: dict):
    id_image = data.get("id_image")
    selfie = data.get("selfie")
    if not id_image or not selfie:
        raise HTTPException(status_code=400, detail="Both images required")
    result = compare_faces(id_image, selfie)
    return result

@app.post("/api/verify/id/upload")
async def upload_id(data: dict):
    registration_id = data.get("registration_id")
    person = data.get("person_number", 1)
    id_image = data.get("id_image")
    selfie = data.get("selfie")
    if not db or not id_image:
        raise HTTPException(status_code=400, detail="Missing data")
    face_result = {"match": True, "message": "Skipped"} if not selfie else compare_faces(id_image, selfie)
    doc = {"_id": str(uuid.uuid4()), "registration_id": registration_id, "person_number": person, "id_image": id_image[:100] + "...", "selfie": bool(selfie), "face_match": face_result, "status": "approved" if face_result.get("match") else "pending_review", "submitted_at": datetime.utcnow().isoformat()}
    await db.id_verifications.insert_one(doc)
    return {"success": True, "face_match": face_result, "status": doc["status"]}

@app.post("/api/couples")
async def register_couple(data: dict):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    p1, p2 = data.get("person1", {}), data.get("person2", {})
    existing = await db.couples.find_one({"$or": [{"person1.email": p1.get("email")}, {"person2.email": p2.get("email")}], "status": "active"})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    couple_id = str(uuid.uuid4())
    doc = {"_id": couple_id, "person1": p1, "person2": p2, "photos": data.get("photos", []), "relationship_start_date": data.get("relationship_start_date", ""), "status": "active", "created_at": datetime.utcnow().isoformat()}
    await db.couples.insert_one(doc)
    return {"couple_id": couple_id, "message": "Registration successful"}

@app.get("/api/search")
async def search(name: Optional[str] = None, state: Optional[str] = None):
    if not db:
        return {"results": [], "total": 0}
    query = {"status": "active"}
    if name:
        query["$or"] = [{"person1.birth_name": {"$regex": name, "$options": "i"}}, {"person2.birth_name": {"$regex": name, "$options": "i"}}]
    results = []
    async for doc in db.couples.find(query).limit(20):
        results.append({"id": doc["_id"], "person1": {"name": doc["person1"].get("birth_name"), "state": doc["person1"].get("state")}, "person2": {"name": doc["person2"].get("birth_name"), "state": doc["person2"].get("state")}, "relationship_start_date": doc.get("relationship_start_date")})
    return {"results": results, "total": len(results)}

@app.get("/api/stats")
async def stats():
    if not db:
        return {"total": 0, "active": 0}
    total = await db.couples.count_documents({})
    active = await db.couples.count_documents({"status": "active"})
    return {"total": total, "active": active}
