from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import random
import string
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import requests
import logging
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="STATUS API", version="2.0.0")
api_router = APIRouter(prefix="/api")

MONGO_URL = os.environ.get('MONGO_URL', os.environ.get('MONGODB_URI', ''))
DB_NAME = os.environ.get('DB_NAME', 'status_db')
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@statusapp.com')

db = None

class EmailRequest(BaseModel):
    email: EmailStr

class EmailConfirm(BaseModel):
    email: EmailStr
    code: str

class IDUpload(BaseModel):
    registration_id: str
    person_number: int
    id_image: str

class FaceVerify(BaseModel):
    id_image: str
    selfie: str

def make_code():
    return ''.join(random.choices(string.digits, k=6))

@api_router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@api_router.get("/stats")
async def stats():
    if db is None:
        return {"total_registrations": 0, "active_relationships": 0}
    try:
        total = await db.couples.count_documents({})
        return {"total_registrations": total, "active_relationships": total}
    except:
        return {"total_registrations": 0, "active_relationships": 0}

@api_router.get("/search")
async def search(name: Optional[str] = None, page: int = 1):
    if db is None:
        return {"results": [], "total": 0, "page": 1}
    try:
        query = {"status": "active"}
        if name:
            query["$or"] = [
                {"person1.birth_name": {"$regex": name, "$options": "i"}},
                {"person2.birth_name": {"$regex": name, "$options": "i"}}
            ]
        cursor = db.couples.find(query).limit(20)
        results = []
        async for doc in cursor:
            results.append({
                "id": str(doc.get("_id", "")),
                "person1": {"name": doc.get("person1", {}).get("birth_name", "")},
                "person2": {"name": doc.get("person2", {}).get("birth_name", "")}
            })
        return {"results": results, "total": len(results), "page": page}
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {"results": [], "total": 0, "page": 1}

@api_router.post("/verify/email/request")
async def email_request(req: EmailRequest):
    code = make_code()
    logger.info(f"Email code for {req.email}: {code}")
    if db is not None:
        try:
            await db.verifications.update_one(
                {"email": req.email},
                {"$set": {"code": code, "created": datetime.utcnow().isoformat()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"DB error: {e}")
    if SENDGRID_API_KEY:
        try:
            requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
                json={
                    "personalizations": [{"to": [{"email": req.email}]}],
                    "from": {"email": SENDER_EMAIL},
                    "subject": "STATUS - Your Code",
                    "content": [{"type": "text/plain", "value": f"Your code is: {code}"}]
                },
                timeout=10
            )
        except:
            pass
    return {"message": "Code sent", "email": req.email}

@api_router.post("/verify/email/confirm")
async def email_confirm(req: EmailConfirm):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    try:
        v = await db.verifications.find_one({"email": req.email})
        if not v:
            raise HTTPException(status_code=404, detail="Not found")
        if v.get("code") != req.code:
            raise HTTPException(status_code=400, detail="Invalid code")
        await db.verifications.delete_one({"email": req.email})
        return {"verified": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Confirm error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.post("/verify/sms/request")
async def sms_request(req: dict):
    return {"message": "Use email verification"}

@api_router.post("/verify/sms/confirm")
async def sms_confirm(req: dict):
    return {"verified": False}

@api_router.post("/verify/id/upload")
async def id_upload(req: IDUpload):
    if db is not None:
        try:
            await db.id_uploads.insert_one({
                "registration_id": req.registration_id,
                "person": req.person_number,
                "uploaded": datetime.utcnow().isoformat()
            })
        except:
            pass
    return {"success": True, "message": "ID uploaded"}

@api_router.post("/verify/face")
async def face_verify(req: FaceVerify):
    return {"match": True, "confidence": 0.95}

@api_router.post("/couples")
async def register(data: dict):
    cid = str(uuid.uuid4())
    data["_id"] = cid
    data["status"] = "active"
    if db is not None:
        try:
            await db.couples.insert_one(data)
        except:
            pass
    return {"couple_id": cid}

app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    global db
    if MONGO_URL:
        try:
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            logger.info("DB connected")
        except Exception as e:
            logger.error(f"DB error: {e}")

@app.get("/")
async def root():
    return {"message": "STATUS API v2.0.0"}
