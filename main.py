from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
from typing import List, Optional
import stripe
import os
import uuid

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB
MONGODB_URL = os.getenv("MONGODB_URL")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.status_db
couples_collection = db.couples
photos_collection = db.photos

# Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# ===================================
# MODELS
# ===================================

class PaymentRequest(BaseModel):
    person1Name: str
    person2Name: str
    relationshipDate: str
    email: str
    phone: str
    amount: float

class CoupleCustomization(BaseModel):
    customColor: Optional[str] = "#667eea"
    loveStory: Optional[str] = ""
    anniversaryDate: Optional[str] = None
    tips: Optional[List[dict]] = []

# ===================================
# BASIC ROUTES
# ===================================

@app.get("/")
async def root():
    return {"message": "STATUS API", "status": "running"}

@app.get("/api/health")
async def health_check():
    try:
        await client.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except:
        return {"status": "healthy", "database": "disconnected"}

# ===================================
# SEARCH
# ===================================

@app.get("/api/search")
async def search_couples(name: str):
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    
    couples = await couples_collection.find({
        "$or": [
            {"person1Name": {"$regex": name, "$options": "i"}},
            {"person2Name": {"$regex": name, "$options": "i"}}
        ]
    }).limit(10).to_list(10)
    
    for couple in couples:
        couple["_id"] = str(couple["_id"])
    
    return {"couples": couples}

# ===================================
# PAYMENT
# ===================================

@app.post("/api/payment/create")
async def create_payment(payment: PaymentRequest):
    try:
        print(f"💳 Payment: {payment.person1Name} & {payment.person2Name}")
        
        # Create Stripe payment
        payment_intent = stripe.PaymentIntent.create(
            amount=int(payment.amount * 100),
            currency="usd",
            metadata={
                "person1Name": payment.person1Name,
                "person2Name": payment.person2Name,
                "email": payment.email
            }
        )
        
        # Save couple
        couple_data = {
            "person1Name": payment.person1Name,
            "person2Name": payment.person2Name,
            "relationshipDate": payment.relationshipDate,
            "email": payment.email,
            "phone": payment.phone,
            "stripePaymentId": payment_intent.id,
            "verified": payment.amount >= 4.99,
            "customColor": "#667eea",
            "loveStory": "",
            "tips": [],
            "createdAt": datetime.utcnow()
        }
        
        result = await couples_collection.insert_one(couple_data)
        
        return {
            "success": True,
            "clientSecret": payment_intent.client_secret,
            "coupleId": str(result.inserted_id)
        }
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ===================================
# PHOTO UPLOAD
# ===================================

@app.post("/api/photos/upload")
async def upload_photos(
    photos: List[UploadFile] = File(...),
    coupleId: str = None
):
    """Upload photos for a couple"""
    if not coupleId:
        raise HTTPException(status_code=400, detail="Couple ID required")
    
    uploaded_photos = []
    
    for photo in photos:
        # Generate filename
        file_ext = photo.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        
        # Save locally (for development)
        file_path = f"./uploads/{unique_filename}"
        os.makedirs("./uploads", exist_ok=True)
        
        with open(file_path, "wb") as buffer:
            content = await photo.read()
            buffer.write(content)
        
        # Create photo record
        photo_record = {
            "id": str(uuid.uuid4()),
            "url": f"/uploads/{unique_filename}",
            "thumbnail": f"/uploads/{unique_filename}",
            "coupleId": coupleId,
            "uploadedAt": datetime.utcnow().isoformat()
        }
        
        await photos_collection.insert_one(photo_record)
        uploaded_photos.append(photo_record)
    
    return {"photos": uploaded_photos, "count": len(uploaded_photos)}

@app.get("/api/photos/{couple_id}")
async def get_couple_photos(couple_id: str):
    """Get all photos for a couple"""
    photos = await photos_collection.find({"coupleId": couple_id}).to_list(100)
    
    for photo in photos:
        photo["_id"] = str(photo["_id"])
    
    return {"photos": photos, "count": len(photos)}

@app.delete("/api/photos/{photo_id}")
async def delete_photo(photo_id: str):
    """Delete a photo"""
    result = await photos_collection.delete_one({"id": photo_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    return {"message": "Photo deleted"}

# ===================================
# PROFILE & CUSTOMIZATION
# ===================================

@app.get("/api/couples/{couple_id}/profile")
async def get_couple_profile(couple_id: str):
    """Get full couple profile"""
    try:
        couple = await couples_collection.find_one({"_id": ObjectId(couple_id)})
        
        if not couple:
            raise HTTPException(status_code=404, detail="Not found")
        
        # Get photos
        photos = await photos_collection.find({"coupleId": couple_id}).to_list(100)
        
        couple["_id"] = str(couple["_id"])
        for photo in photos:
            photo["_id"] = str(photo["_id"])
        
        # Calculate days together
        days_together = 0
        if couple.get("relationshipDate"):
            try:
                rel_date = datetime.fromisoformat(couple["relationshipDate"].replace('Z', '+00:00'))
                days_together = (datetime.utcnow() - rel_date).days
            except:
                pass
        
        return {
            "couple": couple,
            "photos": photos,
            "stats": {
                "daysTogether": days_together,
                "photosCount": len(photos)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/api/couples/{couple_id}/customize")
async def customize_profile(couple_id: str, customization: CoupleCustomization):
    """Update couple profile customization"""
    try:
        result = await couples_collection.update_one(
            {"_id": ObjectId(couple_id)},
            {"$set": {
                "customColor": customization.customColor,
                "loveStory": customization.loveStory,
                "anniversaryDate": customization.anniversaryDate,
                "tips": customization.tips,
                "updatedAt": datetime.utcnow().isoformat()
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Couple not found")
        
        return {
            "message": "Profile updated",
            "customization": customization.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run with: uvicorn main:app --host 0.0.0.0 --port $PORT
