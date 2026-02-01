from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os

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

@app.get("/api/couples/{couple_id}/profile")
async def get_profile(couple_id: str):
    try:
        couple = await couples_collection.find_one({"_id": ObjectId(couple_id)})
        if not couple:
            raise HTTPException(status_code=404, detail="Not found")
        
        return {
            "person1Name": couple.get("person1Name"),
            "person2Name": couple.get("person2Name"),
            "relationshipDate": couple.get("relationshipDate"),
            "verified": couple.get("verified", False)
        }
    except:
        raise HTTPException(status_code=404, detail="Not found")
