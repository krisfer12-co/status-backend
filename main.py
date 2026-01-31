from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime
from bson import ObjectId
import stripe

# Initialize app
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

# Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Models
class RegistrationData(BaseModel):
    person1Name: str
    person1Email: str
    person2Name: str
    person2Email: str
    relationshipDate: Optional[str] = None

# Root
@app.get("/")
async def root():
    return {"message": "STATUS API is running", "version": "2.0"}

# Health check
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "database": "connected"}

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
            try:
                anniversary = datetime.fromisoformat(couple["anniversaryDate"])
                days_together = (datetime.now() - anniversary).days
            except:
                pass
        
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
