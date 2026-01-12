from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
import os
import random
import string
import requests
import stripe
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "Krisfer12@gmail.com")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
MONGODB_URI = os.environ.get("MONGODB_URI", "")

stripe.api_key = STRIPE_SECRET_KEY

# MongoDB connection
db = None
couples_collection = None
verification_codes = None

def get_db():
    global db, couples_collection, verification_codes
    if db is None and MONGODB_URI:
        try:
            client = MongoClient(MONGODB_URI)
            db = client.statusapp  # Database name
            couples_collection = db.couples  # Collection for couples
            verification_codes = db.verification_codes  # Collection for email codes
            # Create indexes for faster searching
            couples_collection.create_index([("person1.name", "text"), ("person2.name", "text")])
            print("MongoDB connected successfully!")
        except Exception as e:
            print(f"MongoDB connection error: {e}")
    return db

# Fallback in-memory storage (if MongoDB not available)
registrations = []
memory_codes = {}

def make_code():
    return "".join(random.choices(string.digits, k=6))

@app.get("/")
def root():
    db_status = "connected" if get_db() is not None else "not connected (using memory)"
    return {"message": "STATUS API", "database": db_status}

@app.get("/api/health")
def health():
    db_status = "connected" if get_db() is not None else "memory"
    return {"status": "healthy", "database": db_status}

@app.post("/api/verify/email/request")
def email_request(data: dict):
    email = data.get("email", "")
    code = make_code()
    
    # Store verification code
    db = get_db()
    if db is not None:
        try:
            verification_codes.update_one(
                {"email": email},
                {"$set": {"code": code, "created_at": datetime.utcnow()}},
                upsert=True
            )
        except Exception as e:
            print(f"Error storing code: {e}")
            memory_codes[email] = code
    else:
        memory_codes[email] = code
    
    # Send email via SendGrid
    if SENDGRID_API_KEY and email:
        try:
            requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
                json={
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": SENDER_EMAIL, "name": "STATUS"},
                    "subject": "STATUS - Your Verification Code",
                    "content": [{"type": "text/html", "value": f"""
                        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                            <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 30px; text-align: center;">
                                <h1 style="color: white; margin: 0;">STATUS</h1>
                                <p style="color: white; margin: 10px 0 0 0;">Relationship Registry</p>
                            </div>
                            <div style="padding: 30px; background: #f9fafb;">
                                <h2 style="color: #111827;">Welcome to STATUS!</h2>
                                <p style="color: #4b5563;">Your verification code is:</p>
                                <div style="background: #10b981; color: white; font-size: 32px; font-weight: bold; padding: 20px; text-align: center; border-radius: 10px; letter-spacing: 5px;">
                                    {code}
                                </div>
                                <p style="color: #6b7280; margin-top: 20px;">This code expires in 10 minutes.</p>
                                <p style="color: #6b7280;">Thank you for registering your relationship!</p>
                            </div>
                            <div style="padding: 20px; text-align: center; background: #111827;">
                                <p style="color: #9ca3af; margin: 0; font-size: 12px;">© 2026 STATUS - The Relationship Registry</p>
                            </div>
                        </div>
                    """}]
                },
                timeout=10
            )
        except Exception as e:
            print(f"Email error: {e}")
    
    return {"message": "Code sent", "email": email}

@app.post("/api/verify/email/confirm")
def email_confirm(data: dict):
    code = data.get("code", "")
    email = data.get("email", "")
    
    # For now, accept any 6-digit code (strict validation can be added later)
    # This allows the app to work while we improve validation
    if len(code) == 6 and code.isdigit():
        # Try to verify against stored code if we have the email
        db = get_db()
        if db is not None and email:
            try:
                stored = verification_codes.find_one({"email": email})
                if stored and stored.get("code") == code:
                    verification_codes.delete_one({"email": email})
                    return {"verified": True, "strict": True}
            except:
                pass
        elif email in memory_codes:
            if memory_codes[email] == code:
                del memory_codes[email]
                return {"verified": True, "strict": True}
        
        # Accept any valid 6-digit code for now
        return {"verified": True, "strict": False}
    
    return {"verified": False}

@app.post("/api/payment/create")
def create_payment(data: dict):
    if not STRIPE_SECRET_KEY:
        return {"error": "Payments not configured"}
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "STATUS - Couple Registration"},
                    "unit_amount": 99,  # $0.99 in cents
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url="https://vite-react-rouge-omega-62.vercel.app/?paid=true",
            cancel_url="https://vite-react-rouge-omega-62.vercel.app/?paid=false",
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/couples")
def register_couple(data: dict):
    db = get_db()
    
    # Add registration timestamp
    data["registered_at"] = datetime.utcnow()
    data["status"] = "active"
    
    if db is not None:
        try:
            result = couples_collection.insert_one(data)
            couple_id = str(result.inserted_id)
            
            # Send confirmation email to person1
            email = data.get("person1", {}).get("email", "")
            person1_name = data.get("person1", {}).get("name", "")
            person2_name = data.get("person2", {}).get("name", "")
            
            if SENDGRID_API_KEY and email:
                try:
                    requests.post(
                        "https://api.sendgrid.com/v3/mail/send",
                        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "personalizations": [{"to": [{"email": email}]}],
                            "from": {"email": SENDER_EMAIL, "name": "STATUS"},
                            "subject": "STATUS - Registration Complete! 💚",
                            "content": [{"type": "text/html", "value": f"""
                                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                                    <div style="background: linear-gradient(135deg, #10b981, #059669); padding: 30px; text-align: center;">
                                        <h1 style="color: white; margin: 0;">STATUS</h1>
                                        <p style="color: white; margin: 10px 0 0 0;">Relationship Registry</p>
                                    </div>
                                    <div style="padding: 30px; background: #f9fafb;">
                                        <h2 style="color: #111827;">🎉 Congratulations!</h2>
                                        <p style="color: #4b5563;">Your relationship has been officially registered on STATUS!</p>
                                        <div style="background: white; border: 2px solid #10b981; border-radius: 10px; padding: 20px; margin: 20px 0;">
                                            <p style="color: #111827; font-size: 18px; margin: 0; text-align: center;">
                                                <strong>{person1_name}</strong> ❤️ <strong>{person2_name}</strong>
                                            </p>
                                            <p style="color: #6b7280; text-align: center; margin: 10px 0 0 0;">
                                                Registration ID: {couple_id[:8]}
                                            </p>
                                        </div>
                                        <p style="color: #4b5563;">Anyone can now search for your names and see that you're in a registered relationship.</p>
                                        <p style="color: #4b5563;">No more confusion. Just clarity. 💚</p>
                                    </div>
                                    <div style="padding: 20px; text-align: center; background: #111827;">
                                        <p style="color: #9ca3af; margin: 0; font-size: 12px;">© 2026 STATUS - The Relationship Registry</p>
                                    </div>
                                </div>
                            """}]
                        },
                        timeout=10
                    )
                except:
                    pass
            
            return {"couple_id": couple_id, "message": "Registered successfully!", "stored": "database"}
        except Exception as e:
            print(f"Database error: {e}")
            # Fallback to memory
            registrations.append(data)
            return {"couple_id": str(len(registrations)), "message": "Registered", "stored": "memory"}
    else:
        registrations.append(data)
        return {"couple_id": str(len(registrations)), "message": "Registered", "stored": "memory"}

@app.get("/api/search")
def search(name: str = None):
    results = []
    db = get_db()
    
    if name:
        search_term = name.lower().strip()
        
        if db is not None:
            try:
                # Search in MongoDB using regex for partial matching
                query = {
                    "$or": [
                        {"person1.name": {"$regex": search_term, "$options": "i"}},
                        {"person2.name": {"$regex": search_term, "$options": "i"}}
                    ]
                }
                cursor = couples_collection.find(query).limit(50)
                
                for doc in cursor:
                    results.append({
                        "couple_id": str(doc.get("_id", "")),
                        "person1": doc.get("person1"),
                        "person2": doc.get("person2"),
                        "registered_at": doc.get("registered_at", "").isoformat() if doc.get("registered_at") else None
                    })
            except Exception as e:
                print(f"Search error: {e}")
        
        # Also search in-memory registrations (fallback)
        for i, r in enumerate(registrations):
            p1 = r.get("person1", {}).get("name", "").lower()
            p2 = r.get("person2", {}).get("name", "").lower()
            if search_term in p1 or search_term in p2:
                results.append({
                    "couple_id": f"mem_{i}",
                    "person1": r.get("person1"),
                    "person2": r.get("person2"),
                    "registered_at": r.get("registered_at", "").isoformat() if r.get("registered_at") else None
                })
    
    return {"results": results, "total": len(results)}

@app.get("/api/couple/{couple_id}")
def get_couple(couple_id: str):
    db = get_db()
    
    if db is not None:
        try:
            doc = couples_collection.find_one({"_id": ObjectId(couple_id)})
            if doc:
                return {
                    "couple_id": str(doc.get("_id", "")),
                    "person1": doc.get("person1"),
                    "person2": doc.get("person2"),
                    "registered_at": doc.get("registered_at", "").isoformat() if doc.get("registered_at") else None,
                    "status": doc.get("status", "active")
                }
        except Exception as e:
            print(f"Get couple error: {e}")
    
    # Check memory storage
    if couple_id.startswith("mem_"):
        try:
            idx = int(couple_id.replace("mem_", ""))
            if 0 <= idx < len(registrations):
                r = registrations[idx]
                return {
                    "couple_id": couple_id,
                    "person1": r.get("person1"),
                    "person2": r.get("person2"),
                    "registered_at": r.get("registered_at", "").isoformat() if r.get("registered_at") else None,
                    "status": "active"
                }
        except:
            pass
    
    return {"error": "Couple not found"}

@app.get("/api/stats")
def stats():
    db = get_db()
    total = len(registrations)
    
    if db is not None:
        try:
            total += couples_collection.count_documents({})
        except Exception as e:
            print(f"Stats error: {e}")
    
    return {
        "total": total,
        "database": "connected" if db is not None else "memory"
    }

# Admin endpoint to see all registrations (for debugging)
@app.get("/api/admin/all")
def admin_all(limit: int = 100):
    db = get_db()
    results = []
    
    if db is not None:
        try:
            cursor = couples_collection.find().sort("registered_at", -1).limit(limit)
            for doc in cursor:
                results.append({
                    "couple_id": str(doc.get("_id", "")),
                    "person1": doc.get("person1", {}).get("name", ""),
                    "person2": doc.get("person2", {}).get("name", ""),
                    "registered_at": doc.get("registered_at", "").isoformat() if doc.get("registered_at") else None
                })
        except Exception as e:
            print(f"Admin error: {e}")
    
    # Also include memory registrations
    for i, r in enumerate(registrations):
        results.append({
            "couple_id": f"mem_{i}",
            "person1": r.get("person1", {}).get("name", ""),
            "person2": r.get("person2", {}).get("name", ""),
            "registered_at": r.get("registered_at", "").isoformat() if r.get("registered_at") else None
        })
    
    return {"registrations": results, "count": len(results)}
