# Add these routes to your main.py backend file

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import boto3
import os
from datetime import datetime
import uuid

app = FastAPI()

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class CoupleCustomization(BaseModel):
    customColor: Optional[str] = "#667eea"
    loveStory: Optional[str] = ""
    anniversaryDate: Optional[str] = None
    tips: Optional[List[dict]] = []

class Photo(BaseModel):
    id: str
    url: str
    thumbnail: str
    coupleId: str
    uploadedAt: str
    caption: Optional[str] = None

# ==========================================
# PHOTO UPLOAD ROUTES
# ==========================================

@app.post("/api/photos/upload")
async def upload_photos(
    photos: List[UploadFile] = File(...),
    coupleId: str = None
):
    """
    Upload multiple photos for a couple
    Note: This example saves to local storage
    For production, use AWS S3 or Cloudinary
    """
    if not coupleId:
        raise HTTPException(status_code=400, detail="Couple ID required")
    
    uploaded_photos = []
    
    for photo in photos:
        # Generate unique filename
        file_extension = photo.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # Save file locally (for development)
        # In production, upload to S3/Cloudinary
        file_path = f"./uploads/{unique_filename}"
        os.makedirs("./uploads", exist_ok=True)
        
        with open(file_path, "wb") as buffer:
            content = await photo.read()
            buffer.write(content)
        
        # Create photo record
        photo_record = {
            "id": str(uuid.uuid4()),
            "url": f"/uploads/{unique_filename}",
            "thumbnail": f"/uploads/{unique_filename}",  # In production, create thumbnail
            "coupleId": coupleId,
            "uploadedAt": datetime.now().isoformat(),
            "caption": None
        }
        
        # Save to database
        # db.photos.insert_one(photo_record)
        
        uploaded_photos.append(photo_record)
    
    return {"photos": uploaded_photos, "count": len(uploaded_photos)}


@app.get("/api/photos/{couple_id}")
async def get_couple_photos(couple_id: str):
    """Get all photos for a couple"""
    # Query from database
    # photos = list(db.photos.find({"coupleId": couple_id}))
    
    # Example response
    photos = []
    return {"photos": photos, "count": len(photos)}


@app.delete("/api/photos/{photo_id}")
async def delete_photo(photo_id: str):
    """Delete a photo"""
    # Delete from database and storage
    # db.photos.delete_one({"id": photo_id})
    # Also delete file from S3/local storage
    
    return {"message": "Photo deleted successfully"}


# ==========================================
# PROFILE CUSTOMIZATION ROUTES
# ==========================================

@app.put("/api/couples/{couple_id}/customize")
async def customize_profile(couple_id: str, customization: CoupleCustomization):
    """Update couple profile customization"""
    
    # Update in database
    # db.couples.update_one(
    #     {"_id": couple_id},
    #     {"$set": {
    #         "customColor": customization.customColor,
    #         "loveStory": customization.loveStory,
    #         "anniversaryDate": customization.anniversaryDate,
    #         "tips": customization.tips,
    #         "updatedAt": datetime.now().isoformat()
    #     }}
    # )
    
    return {
        "message": "Profile customized successfully",
        "customization": customization.dict()
    }


@app.get("/api/couples/{couple_id}/profile")
async def get_couple_profile(couple_id: str):
    """Get full couple profile with customization and photos"""
    
    # Query from database
    # couple = db.couples.find_one({"_id": couple_id})
    # photos = list(db.photos.find({"coupleId": couple_id}))
    
    # Example response
    return {
        "couple": {
            "id": couple_id,
            "person1Name": "John",
            "person2Name": "Jane",
            "verified": True,
            "customColor": "#667eea",
            "loveStory": "We met at a coffee shop...",
            "anniversaryDate": "2023-01-15",
            "tips": [],
            "registeredAt": "2024-01-20T10:00:00"
        },
        "photos": [],
        "stats": {
            "daysTogether": 380,
            "photosCount": 0
        }
    }


# ==========================================
# ALTERNATIVE: Using Cloudinary for Images
# ==========================================
"""
Install: pip install cloudinary

import cloudinary
import cloudinary.uploader

# Configure Cloudinary
cloudinary.config(
    cloud_name = "your_cloud_name",
    api_key = "your_api_key",
    api_secret = "your_api_secret"
)

@app.post("/api/photos/upload-cloudinary")
async def upload_to_cloudinary(
    photos: List[UploadFile] = File(...),
    coupleId: str = None
):
    uploaded_photos = []
    
    for photo in photos:
        # Upload to Cloudinary
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
    
    return {"photos": uploaded_photos, "count": len(uploaded_photos)}
"""
