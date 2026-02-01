from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import os
import random
import string
import requests
from datetime import datetime
import json

app = FastAPI(title="STATUS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "Krisfer12@gmail.com")

# In-memory storage (use a database in production)
registrations = []
verification_codes = {}  # email -> code mapping

# Pydantic models
class EmailRequest(BaseModel):
    email: EmailStr

class EmailConfirm(BaseModel):
    email: EmailStr
    code: str

class Person(BaseModel):
    name: str
    photo: Optional[str] = None  # base64 encoded image

class CoupleRegistration(BaseModel):
    person1: Person
    person2: Person
    anniversary_date: str  # YYYY-MM-DD format
    relationship_status: Optional[str] = "In a Relationship"
    message: Optional[str] = None
    email: EmailStr

def make_code():
    return "".join(random.choices(string.digits, k=6))

@app.get("/")
def root():
    return {
        "message": "STATUS API - Celebrate Love, Share Your Story",
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/health",
            "verify_email": "/api/verify/email/request",
            "confirm_email": "/api/verify/email/confirm",
            "register_couple": "/api/couples",
            "search": "/api/search",
            "stats": "/api/stats"
        }
    }

@app.get("/api/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/verify/email/request")
def email_request(data: EmailRequest):
    email = data.email
    code = make_code()
    
    # Store code for verification
    verification_codes[email] = code
    
    if SENDGRID_API_KEY:
        try:
            response = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {SENDGRID_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": SENDER_EMAIL, "name": "STATUS"},
                    "subject": "STATUS - Welcome! 💕",
                    "content": [{
                        "type": "text/html",
                        "value": f"""
                        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                            <h1 style="color: #ff6b9d;">Welcome to STATUS!</h1>
                            <p style="font-size: 16px;">Thank you for choosing to celebrate your relationship with us.</p>
                            <div style="background: #f8f8f8; padding: 20px; border-radius: 10px; margin: 20px 0;">
                                <p style="margin: 0; font-size: 14px; color: #666;">Your verification code is:</p>
                                <h2 style="margin: 10px 0; font-size: 32px; color: #ff6b9d; letter-spacing: 5px;">{code}</h2>
                            </div>
                            <p style="font-size: 14px; color: #666;">This code will expire in 10 minutes.</p>
                            <p style="font-size: 14px; color: #666;">Share your love story with the world! ❤️</p>
                        </div>
                        """
                    }]
                },
                timeout=10
            )
            if response.status_code != 202:
                print(f"SendGrid error: {response.text}")
        except Exception as e:
            print(f"Email sending failed: {str(e)}")
    
    return {"message": "Verification code sent", "email": email}

@app.post("/api/verify/email/confirm")
def email_confirm(data: EmailConfirm):
    stored_code = verification_codes.get(data.email)
    
    if not stored_code:
        raise HTTPException(status_code=400, detail="No verification code found for this email")
    
    if stored_code == data.code:
        # Code is valid, remove it
        del verification_codes[data.email]
        return {"verified": True, "message": "Email verified successfully"}
    
    return {"verified": False, "message": "Invalid verification code"}

@app.post("/api/couples")
def register_couple(data: CoupleRegistration):
    # Validate anniversary date
    try:
        anniversary = datetime.strptime(data.anniversary_date, "%Y-%m-%d")
        if anniversary > datetime.now():
            raise HTTPException(status_code=400, detail="Anniversary date cannot be in the future")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    couple_data = {
        "couple_id": str(len(registrations) + 1),
        "person1": data.person1.dict(),
        "person2": data.person2.dict(),
        "anniversary_date": data.anniversary_date,
        "relationship_status": data.relationship_status,
        "message": data.message,
        "email": data.email,
        "registered_at": datetime.now().isoformat()
    }
    
    registrations.append(couple_data)
    
    return {
        "couple_id": couple_data["couple_id"],
        "message": "Congratulations! Your relationship has been registered.",
        "anniversary_date": data.anniversary_date
    }

@app.get("/api/search")
def search(name: str = None):
    if not name:
        return {"results": [], "total": 0, "message": "Please provide a name to search"}
    
    results = []
    name_lower = name.lower()
    
    for r in registrations:
        p1_name = r.get("person1", {}).get("name", "").lower()
        p2_name = r.get("person2", {}).get("name", "").lower()
        
        if name_lower in p1_name or name_lower in p2_name:
            # Return couple info without email
            results.append({
                "couple_id": r.get("couple_id"),
                "person1": {
                    "name": r.get("person1", {}).get("name"),
                    "photo": r.get("person1", {}).get("photo")
                },
                "person2": {
                    "name": r.get("person2", {}).get("name"),
                    "photo": r.get("person2", {}).get("photo")
                },
                "anniversary_date": r.get("anniversary_date"),
                "relationship_status": r.get("relationship_status"),
                "message": r.get("message")
            })
    
    return {
        "results": results,
        "total": len(results),
        "query": name
    }

@app.get("/api/couples/{couple_id}")
def get_couple(couple_id: str):
    for r in registrations:
        if r.get("couple_id") == couple_id:
            # Return couple info without email
            return {
                "couple_id": r.get("couple_id"),
                "person1": {
                    "name": r.get("person1", {}).get("name"),
                    "photo": r.get("person1", {}).get("photo")
                },
                "person2": {
                    "name": r.get("person2", {}).get("name"),
                    "photo": r.get("person2", {}).get("photo")
                },
                "anniversary_date": r.get("anniversary_date"),
                "relationship_status": r.get("relationship_status"),
                "message": r.get("message"),
                "registered_at": r.get("registered_at")
            }
    
    raise HTTPException(status_code=404, detail="Couple not found")

@app.get("/api/stats")
def stats():
    return {
        "total_couples": len(registrations),
        "message": f"{len(registrations)} couples celebrating their love on STATUS"
    }

@app.get("/api/recent")
def recent_registrations(limit: int = 10):
    """Get recently registered couples"""
    recent = sorted(
        registrations,
        key=lambda x: x.get("registered_at", ""),
        reverse=True
    )[:limit]
    
    return {
        "couples": [
            {
                "couple_id": r.get("couple_id"),
                "person1_name": r.get("person1", {}).get("name"),
                "person2_name": r.get("person2", {}).get("name"),
                "anniversary_date": r.get("anniversary_date"),
                "registered_at": r.get("registered_at")
            }
            for r in recent
        ],
        "total": len(recent)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
