from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import List, Optional
import os
from datetime import datetime
from bson import ObjectId
import stripe
import cloudinary
import cloudinary.uploader
import uuid

# Initialize FastAPI app
app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB setup
MONGODB_URL = os.getenv("MONGODB_URL")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.status_db

# Stripe setup
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Cloudinary setup
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Pydantic Models
class RegistrationData(BaseModel):
    person1Name: str
    person1Email: str
    person2Name: str
    person2Email: str
    relationshipDate: Optional[str] = None

class VerificationData(BaseModel):
    coupleId: str

class CoupleCustomization(BaseModel):
    customColor: Optional[str] = "#667eea"
    loveStory: Optional[str] = ""
    anniversaryDate: Optional[str] = None
    tips: Optional[List[dict]] = []

# Root route
@app.get("/")
async def root():
    return {"message": "STATUS API is running", "version": "2.0"}

# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "database": "connected"}

# Register couple
@app.post("/api/register")
async def register_couple(data: RegistrationData):
    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=99,
            currency="usd",
            metadata={
                "person1_name": data.person1Name,
                "person2_name": data.person2Name,
            }
        )
        
        couple = {
            "person1Name": data.person1Name,
            "person1Email": data.person1Email,
            "person2Name": data.person2Name,
            "person2Email": data.person2Email,
            "relationshipDate": data.relationshipDate,
            "verified": False,
            "registeredAt": datetime.now().isoformat(),
            "customColor": "#667eea",
            "loveStory": "",
            "anniversaryDate": data.relationshipDate,
            "tips": [],
            "stripePaymentId": payment_intent.id
        }
        
        result = await db.couples.insert_one(couple)
        couple_id = str(result.inserted_id)
        
        return {
            "success": True,
            "coupleId": couple_id,
            "clientSecret": payment_intent.client_secret
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Purchase verified badge
@app.post("/api/verify-badge")
async def purchase_verified_badge(data: VerificationData):
    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=499,
            currency="usd",
            metadata={
                "couple_id": data.coupleId,
                "product": "verified_badge"
            }
        )
        
        return {
            "success": True,
            "clientSecret": payment_intent.client_secret
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Confirm verification
@app.post("/api/confirm-verification/{couple_id}")
async def confirm_verification(couple_id: str):
    try:
        result = await db.couples.update_one(
            {"_id": ObjectId(couple_id)},
            {"$set": {"verified": True}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Couple not found")
        
        return {"success": True, "message": "Couple verified successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Search couples
@app.get("/api/search")
async def search_couples(name: str = ""):
    try:
        if not name:
            return {"results": [], "total": 0}
        
        couples = await db.couples.find({
            "$or": [
                {"person1Name": {"$regex": name, "$options": "i"}},
                {"person2Name": {"$regex": name, "$options": "i"}}
            ]
        }).to_list(length=100)
        
        for couple in couples:
            couple["_id"] = str(couple["_id"])
        
        return {"results": couples, "total": len(couples)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Delete couple
@app.delete("/api/couples/{couple_id}")
async def delete_couple(couple_id: str):
    try:
        result = await db.couples.delete_one({"_id": ObjectId(couple_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Couple not found")
        
        return {"success": True, "message": "Couple deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Upload photos
@app.post("/api/photos/upload")
async def upload_photos(photos: List[UploadFile] = File(...), coupleId: str = Form(...)):
    if not coupleId:
        raise HTTPException(status_code=400, detail="Couple ID required")
    
    uploaded_photos = []
    
    for photo in photos:
        try:
            result = cloudinary.uploader.upload(
                photo.file,
                folder=f"couples/{coupleId}",
                transformation=[
                    {"width": 800, "height": 800, "crop": "limit"},
                    {"quality": "auto"},
                    {"fetch_format": "auto"}
                ]
            )
            
            photo_record = {
                "id": str(uuid.uuid4()),
                "url": result["secure_url"],
                "thumbnail": result["secure_url"].replace("/upload/", "/upload/c_thumb,w_200,h_200/"),
                "coupleId": coupleId,
                "uploadedAt": datetime.now().isoformat()
            }
            
            uploaded_photos.append(photo_record)
            
        except Exception as e:
            print(f"Error uploading photo: {e}")
            continue
    
    return {"photos": uploaded_photos, "count": len(uploaded_photos)}

# Get couple photos
@app.get("/api/photos/{couple_id}")
async def get_couple_photos(couple_id: str):
    return {"photos": [], "count": 0}

# Customize profile
@app.put("/api/couples/{couple_id}/customize")
async def customize_profile(couple_id: str, customization: CoupleCustomization):
    try:
        result = await db.couples.update_one(
            {"_id": ObjectId(couple_id)},
            {"$set": {
                "customColor": customization.customColor,
                "loveStory": customization.loveStory,
                "anniversaryDate": customization.anniversaryDate,
                "tips": customization.tips,
                "updatedAt": datetime.now().isoformat()
            }}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Couple not found")
        
        return {
            "message": "Profile customized successfully",
            "customization": customization.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get couple profile
@app.get("/api/couples/{couple_id}/profile")
async def get_couple_profile(couple_id: str):
    try:
        couple = await db.couples.find_one({"_id": ObjectId(couple_id)})
        
        if not couple:
            raise HTTPException(status_code=404, detail="Couple not found")
        
        couple["_id"] = str(couple["_id"])
        
        days_together = 0
        if couple.get("anniversaryDate"):
            anniversary = datetime.fromisoformat(couple["anniversaryDate"])
            days_together = (datetime.now() - anniversary).days
        
        return {
            "couple": couple,
            "photos": [],
            "stats": {
                "daysTogether": days_together,
                "photosCount": 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
