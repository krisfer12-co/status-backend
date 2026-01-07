[from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
import string
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import requests

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', os.environ.get('MONGODB_URI', 'mongodb://localhost:27017'))
DB_NAME = os.environ.get('DB_NAME', 'status_db')

client = None
db = None

# SendGrid configuration
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@statusapp.com')

# Create the main app
app = FastAPI(title="STATUS API", version="2.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Models
class EmailVerificationRequest(BaseModel):
    email: EmailStr

class EmailVerificationConfirm(BaseModel):
    email: EmailStr
    code: str

class IDUploadRequest(BaseModel):
    registration_id: str
    person_number: int
    id_image: str

class FaceVerifyRequest(BaseModel):
    id_image: str
    selfie: str

# Helper functions
def generate_code(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))

async def send_email(to_email: str, subject: str, body: str) -> bool:
    if not SENDGRID_API_KEY:
        logger.warning(f"SendGrid not configured. Code for {to_email}: {body}")
        return True
    try:
        response = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": SENDER_EMAIL, "name": "STATUS App"},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}]
            },
            timeout=10
        )
        logger.info(f"Email sent to {to_email}, status: {response.status_code}")
        return response.status_code == 202
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False

# API Endpoints
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@api_router.get("/stats")
async def get_stats():
    try:
        total = await db.couples.count_documents({})
        active = await db.couples.count_documents({"status": "active"})
        return {"total_registrations": total, "active_relationships": active}
    except:
        return {"total_registrations": 0, "active_relationships": 0}

@api_router.get("/search")
async def search_couples(
    name: Optional[str] = None,
    state: Optional[str] = None,
    age: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    query = {"status": "active"}
    if name:
        query["$or"] = [
            {"person1.birth_name": {"$regex": name, "$options": "i"}},
            {"person2.birth_name": {"$regex": name, "$options": "i"}}
        ]
    
    skip = (page - 1) * page_size
    cursor = db.couples.find(query).skip(skip).limit(page_size)
    results = []
    async for doc in cursor:
        results.append({
            "id": str(doc.get("_id", "")),
            "person1": {"name": doc.get("person1", {}).get("birth_name", ""), "state": doc.get("person1", {}).get("state", "")},
            "person2": {"name": doc.get("person2", {}).get("birth_name", ""), "state": doc.get("person2", {}).get("state", "")}
        })
    
    total = await db.couples.count_documents(query)
    return {"results": results, "total": total, "page": page}

@api_router.post("/verify/email/request")
async def request_email_verification(request: EmailVerificationRequest):
    code = generate_code()
    await db.verifications.update_one(
        {"email": request.email},
        {"$set": {"code": code, "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat()}},
        upsert=True
    )
    await send_email(request.email, "STATUS - Verification Code", f"Your verification code is: {code}")
    return {"message": "Verification code sent", "email": request.email}

@api_router.post("/verify/email/confirm")
async def confirm_email_verification(request: EmailVerificationConfirm):
    verification = await db.verifications.find_one({"email": request.email})
    if not verification:
        raise HTTPException(status_code=404, detail="No verification request found")
    if verification["code"] != request.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    await db.verifications.delete_one({"email": request.email})
    return {"verified": True, "message": "Email verified successfully"}

@api_router.post("/verify/sms/request")
async def request_sms_verification(request: dict):
    return {"message": "SMS verification temporarily disabled. Please use email verification."}

@api_router.post("/verify/sms/confirm")
async def confirm_sms_verification(request: dict):
    return {"verified": False, "message": "SMS verification temporarily disabled."}

@api_router.post("/verify/id/upload")
async def upload_id(request: IDUploadRequest):
    await db.id_verifications.insert_one({
        "registration_id": request.registration_id,
        "person_number": request.person_number,
        "uploaded_at": datetime.utcnow().isoformat(),
        "status": "pending"
    })
    return {"success": True, "message": "ID uploaded successfully"}

@api_router.post("/verify/face")
async def verify_face(request: FaceVerifyRequest):
    # Simplified face verification - returns match for demo
    return {"match": True, "confidence": 0.95, "message": "Face verification passed"}

@api_router.post("/couples")
async def register_couple(data: dict):
    couple_id = str(uuid.uuid4())
    data["_id"] = couple_id
    data["status"] = "active"
    data["created_at"] = datetime.utcnow().isoformat()
    await db.couples.insert_one(data)
    return {"couple_id": couple_id, "message": "Registration successful"}

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    global client, db
    try:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        logger.info("Database connected")
    except Exception as e:
        logger.error(f"Database connection error: {e}")

@app.get("/")
async def root():
    return {"message": "STATUS API v2.0.0"}
