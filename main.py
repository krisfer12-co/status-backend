# STATUS BACKEND - PYTHON/FASTAPI - FIXED VERSION
# Missing /api/payment/create route added

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
import stripe
import os
from typing import Optional

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

class PaymentConfirm(BaseModel):
    paymentIntentId: str

# ===================================
# ROUTES
# ===================================

@app.get("/")
async def root():
    return {
        "message": "STATUS API v1.0",
        "status": "running",
        "endpoints": [
            "GET /api/health",
            "GET /api/search",
            "POST /api/payment/create",
            "GET /api/couples/{id}"
        ]
    }

@app.get("/api/health")
async def health_check():
    try:
        await client.admin.command('ping')
        return {"status": "healthy", "database": "connected"}
    except:
        return {"status": "healthy", "database": "disconnected"}

@app.get("/api/search")
async def search_couples(name: str):
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    
    couples = await couples_collection.find({
        "$or": [
            {"person1Name": {"$regex": name, "$options": "i"}},
            {"person2Name": {"$regex": name, "$options": "i"}}
        ]
    }).limit(10).to_list(10)
    
    # Convert ObjectId to string
    for couple in couples:
        couple["_id"] = str(couple["_id"])
    
    return {"couples": couples}

# ===================================
# PAYMENT ROUTE - THIS WAS MISSING!
# ===================================

@app.post("/api/payment/create")
async def create_payment(payment: PaymentRequest):
    try:
        print(f"Payment request: {payment.person1Name} & {payment.person2Name}, ${payment.amount}")
        
        # Create Stripe payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=int(payment.amount * 100),  # Convert to cents
            currency="usd",
            metadata={
                "person1Name": payment.person1Name,
                "person2Name": payment.person2Name,
                "relationshipDate": payment.relationshipDate,
                "email": payment.email
            }
        )
        
        print(f"Payment intent created: {payment_intent.id}")
        
        # Save couple to database
        couple_data = {
            "person1Name": payment.person1Name,
            "person2Name": payment.person2Name,
            "relationshipDate": datetime.fromisoformat(payment.relationshipDate.replace('Z', '+00:00')),
            "email": payment.email,
            "phone": payment.phone,
            "stripePaymentId": payment_intent.id,
            "verified": payment.amount >= 4.99,
            "createdAt": datetime.utcnow()
        }
        
        result = await couples_collection.insert_one(couple_data)
        
        return {
            "success": True,
            "clientSecret": payment_intent.client_secret,
            "coupleId": str(result.inserted_id)
        }
        
    except Exception as e:
        print(f"Payment creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Payment creation failed: {str(e)}")

@app.post("/api/payment/confirm")
async def confirm_payment(confirm: PaymentConfirm):
    try:
        payment_intent = stripe.PaymentIntent.retrieve(confirm.paymentIntentId)
        
        if payment_intent.status == "succeeded":
            await couples_collection.update_one(
                {"stripePaymentId": confirm.paymentIntentId},
                {"$set": {"verified": True}}
            )
            return {"success": True, "message": "Payment confirmed!"}
        else:
            raise HTTPException(status_code=400, detail="Payment not successful")
            
    except Exception as e:
        print(f"Payment confirmation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Confirmation failed")

@app.get("/api/couples/{couple_id}")
async def get_couple(couple_id: str):
    try:
        couple = await couples_collection.find_one({"_id": ObjectId(couple_id)})
        
        if not couple:
            raise HTTPException(status_code=404, detail="Couple not found")
        
        couple["_id"] = str(couple["_id"])
        return {"couple": couple}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get couple")

@app.get("/api/couples/{couple_id}/profile")
async def get_couple_profile(couple_id: str):
    try:
        couple = await couples_collection.find_one({"_id": ObjectId(couple_id)})
        
        if not couple:
            raise HTTPException(status_code=404, detail="Couple not found")
        
        return {
            "person1Name": couple.get("person1Name"),
            "person2Name": couple.get("person2Name"),
            "relationshipDate": couple.get("relationshipDate"),
            "verified": couple.get("verified", False),
            "createdAt": couple.get("createdAt")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Profile not found")

# Run with: uvicorn main:app --host 0.0.0.0 --port $PORT
