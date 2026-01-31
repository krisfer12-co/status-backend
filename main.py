# ==========================================
# NEW ROUTES FOR PHOTO GALLERY & CUSTOMIZATION
# ==========================================

from pydantic import BaseModel
from typing import List, Optional

class CoupleCustomization(BaseModel):
    customColor: Optional[str] = "#667eea"
    loveStory: Optional[str] = ""
    anniversaryDate: Optional[str] = None
    tips: Optional[List[dict]] = []

@app.put("/api/couples/{couple_id}/customize")
async def customize_profile(couple_id: str, customization: CoupleCustomization):
    """Update couple profile customization"""
    try:
        result = db.couples.update_one(
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
        return {"message": "Profile customized successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/couples/{couple_id}/profile")
async def get_couple_profile(couple_id: str):
    """Get full couple profile"""
    try:
        couple = db.couples.find_one({"_id": ObjectId(couple_id)})
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
            "stats": {"daysTogether": days_together, "photosCount": 0}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

6. **Click "Commit changes"** (green button)
7. **Click "Commit changes"** again in the popup

---

### **STEP 2: Update requirements.txt**

1. **Still on GitHub, click "Go back"** or go to: https://github.com/krisfer12-co/status-backend
2. **Click on `requirements.txt`**
3. **Click the pencil icon** (Edit)
4. **Add these two lines** at the end:
```
cloudinary
python-multipart
```

5. **Click "Commit changes"**

---

### **STEP 3: Get Cloudinary Account (Free)**

1. **Go to:** https://cloudinary.com/users/register_free
2. **Sign up for free** (takes 2 minutes)
3. **After signing up, you'll see a Dashboard**
4. **Copy these 3 things** (write them down):
   - Cloud Name
   - API Key
   - API Secret

---

### **STEP 4: Add Cloudinary to Render**

1. **Go to:** https://dashboard.render.com
2. **Click on your `status-api` service**
3. **Click "Environment"** (left sidebar)
4. **Click "Add Environment Variable"**
5. **Add 3 variables** (one at a time):
```
Key: CLOUDINARY_CLOUD_NAME
Value: [paste your cloud name]

Key: CLOUDINARY_API_KEY  
Value: [paste your api key]

Key: CLOUDINARY_API_SECRET
Value: [paste your api secret]
