from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
import os
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

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "Krisfer12@gmail.com")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
MONGODB_URI = os.environ.get("MONGODB_URI", "")
FRONTEND_URL = "https://vite-react-rouge-omega-62.vercel.app"

stripe.api_key = STRIPE_SECRET_KEY

client = None
db = None
couples_collection = None

if MONGODB_URI:
    try:
        client = MongoClient(MONGODB_URI)
        db = client.statusapp
        couples_collection = db.couples
        print("MongoDB initialized!")
    except Exception as e:
        print(f"MongoDB init error: {e}")

def get_collection():
    global client, db, couples_collection
    if couples_collection is not None:
        return couples_collection
    if MONGODB_URI:
        try:
            client = MongoClient(MONGODB_URI)
            db = client.statusapp
            couples_collection = db.couples
            return couples_collection
        except:
            pass
    return None

@app.get("/")
def root():
    coll = get_collection()
    return {"message": "STATUS API", "database": "connected" if coll is not None else "NOT CONNECTED"}

@app.get("/api/health")
def health():
    coll = get_collection()
    return {"status": "healthy", "database": "connected" if coll is not None else "NOT CONNECTED"}

@app.post("/api/verify/email/request")
def email_request(data: dict):
    return {"message": "Code sent", "success": True}

@app.post("/api/verify/email/confirm")
def email_confirm(data: dict):
    return {"verified": True}

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
                    "unit_amount": 99,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{FRONTEND_URL}/?paid=true",
            cancel_url=f"{FRONTEND_URL}/?paid=false",
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        return {"error": str(e)}

# NEW: Verified Badge Payment Endpoint ($4.99)
@app.post("/api/payment/create-verified")
def create_verified_payment(data: dict):
    if not STRIPE_SECRET_KEY:
        return {"error": "Payments not configured"}
    try:
        couple_id = data.get("couple_id", "")
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "STATUS - Verified Badge"},
                    "unit_amount": 499,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{FRONTEND_URL}/?verified=true&couple_id={couple_id}",
            cancel_url=f"{FRONTEND_URL}/",
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/couples")
def register_couple(data: dict):
    coll = get_collection()
    if coll is None:
        return {"error": "Database not available", "couple_id": None}
    
    data["registered_at"] = datetime.utcnow()
    data["status"] = "active"
    
    try:
        result = coll.insert_one(data)
        couple_id = str(result.inserted_id)
        
        email = data.get("person1", {}).get("email", "")
        p1 = data.get("person1", {}).get("name", "")
        p2 = data.get("person2", {}).get("name", "")
        anniversary = data.get("anniversary", "")
        
        if SENDGRID_API_KEY and email:
            try:
                ann_text = ""
                if anniversary:
                    ann_text = f"<p style='color:#10b981'>Together since {anniversary}</p>"
                html = f"<div style='font-family:Arial;max-width:600px;margin:0 auto'><div style='background:#10b981;padding:30px;text-align:center'><h1 style='color:white;margin:0'>STATUS</h1></div><div style='padding:30px;background:#f9fafb'><h2>Congratulations!</h2><p>Your relationship is now registered on STATUS!</p><div style='background:white;border:2px solid #10b981;border-radius:10px;padding:20px;margin:20px 0;text-align:center'><strong>{p1}</strong> and <strong>{p2}</strong>{ann_text}</div><p>Anyone can now search for your names and see you are in a registered relationship.</p></div></div>"
                requests.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "personalizations": [{"to": [{"email": email}]}],
                        "from": {"email": SENDER_EMAIL, "name": "STATUS"},
                        "subject": "STATUS - Registration Complete!",
                        "content": [{"type": "text/html", "value": html}]
                    },
                    timeout=10
                )
            except:
                pass
        
        return {"couple_id": couple_id, "message": "Registered successfully!"}
    except Exception as e:
        return {"error": str(e), "couple_id": None}

@app.get("/api/search")
def search(name: str = None):
    if not name:
        return {"results": [], "total": 0}
    
    coll = get_collection()
    if coll is None:
        return {"results": [], "total": 0, "error": "Database not available"}
    
    search_term = name.strip()
    
    try:
        query = {
            "$and": [
                {"status": {"$ne": "deleted"}},
                {"$or": [
                    {"person1.name": {"$regex": search_term, "$options": "i"}},
                    {"person2.name": {"$regex": search_term, "$options": "i"}}
                ]}
            ]
        }
        
        cursor = coll.find(query).limit(50)
        results = []
        
        for doc in cursor:
            results.append({
                "couple_id": str(doc.get("_id", "")),
                "person1": doc.get("person1"),
                "person2": doc.get("person2"),
                "anniversary": doc.get("anniversary"),
                "verified": doc.get("verified", False),
                "registered_at": doc.get("registered_at").isoformat() if doc.get("registered_at") else None
            })
        
        return {"results": results, "total": len(results)}
    except Exception as e:
        return {"results": [], "total": 0, "error": str(e)}

@app.get("/api/couple/{couple_id}")
def get_couple(couple_id: str):
    coll = get_collection()
    if coll is None:
        return {"error": "Database not available"}
    
    try:
        doc = coll.find_one({"_id": ObjectId(couple_id)})
        if doc:
            if doc.get("status") == "deleted":
                return {"error": "This registration has been deleted"}
            return {
                "couple_id": str(doc.get("_id")),
                "person1": doc.get("person1"),
                "person2": doc.get("person2"),
                "anniversary": doc.get("anniversary"),
                "verified": doc.get("verified", False),
                "registered_at": doc.get("registered_at").isoformat() if doc.get("registered_at") else None,
                "status": doc.get("status", "active")
            }
    except Exception as e:
        print(f"Error: {e}")
    
    return {"error": "Couple not found"}

@app.post("/api/delete/request")
def delete_request(data: dict):
    email = data.get("email", "").strip().lower()
    
    if not email:
        return {"success": False, "error": "Email required"}
    
    coll = get_collection()
    if coll is None:
        return {"success": False, "error": "Database not available"}
    
    try:
        couple = coll.find_one({
            "$and": [
                {"status": {"$ne": "deleted"}},
                {"$or": [
                    {"person1.email": {"$regex": f"^{email}$", "$options": "i"}},
                    {"person2.email": {"$regex": f"^{email}$", "$options": "i"}}
                ]}
            ]
        })
        
        if couple:
            return {"success": True, "message": "Registration found"}
        return {"success": False, "error": "No registration found with this email"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/delete/confirm")
def delete_confirm(data: dict):
    email = data.get("email", "").strip().lower()
    
    if not email:
        return {"success": False, "error": "Email required"}
    
    coll = get_collection()
    if coll is None:
        return {"success": False, "error": "Database not available"}
    
    try:
        result = coll.update_one(
            {"$or": [
                {"person1.email": {"$regex": f"^{email}$", "$options": "i"}},
                {"person2.email": {"$regex": f"^{email}$", "$options": "i"}}
            ]},
            {"$set": {"status": "deleted", "deleted_at": datetime.utcnow()}}
        )
        
        if result.modified_count > 0:
            return {"success": True, "message": "Registration deleted successfully"}
        return {"success": False, "error": "Could not delete registration"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/stats")
def stats():
    coll = get_collection()
    if coll is None:
        return {"total": 0, "database": "NOT CONNECTED"}
    
    try:
        total = coll.count_documents({"status": {"$ne": "deleted"}})
        return {"total": total, "database": "connected"}
    except:
        return {"total": 0, "database": "error"}

@app.get("/api/admin/all")
def admin_all(limit: int = 100):
    coll = get_collection()
    if coll is None:
        return {"registrations": [], "count": 0, "error": "Database not available"}
    
    try:
        cursor = coll.find().sort("registered_at", -1).limit(limit)
        results = []
        
        for doc in cursor:
            results.append({
                "couple_id": str(doc.get("_id", "")),
                "person1": doc.get("person1", {}).get("name", ""),
                "person2": doc.get("person2", {}).get("name", ""),
                "person1_email": doc.get("person1", {}).get("email", ""),
                "person1_city": doc.get("person1", {}).get("city", ""),
                "anniversary": doc.get("anniversary"),
                "status": doc.get("status", "active"),
                "verified": doc.get("verified", False),
                "registered_at": doc.get("registered_at").isoformat() if doc.get("registered_at") else None
            })
        
        return {"registrations": results, "count": len(results)}
    except Exception as e:
        return {"registrations": [], "count": 0, "error": str(e)}
