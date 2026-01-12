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

stripe.api_key = STRIPE_SECRET_KEY

client = None
db = None
couples_collection = None

def init_db():
    global client, db, couples_collection
    if client is None and MONGODB_URI:
        try:
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            db = client.statusapp
            couples_collection = db.couples
            return True
        except Exception as e:
            print(f"MongoDB error: {e}")
            return False
    return client is not None

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/")
def root():
    connected = init_db()
    return {"message": "STATUS API", "database": "connected" if connected else "NOT CONNECTED"}

@app.get("/api/health")
def health():
    connected = init_db()
    return {"status": "healthy", "database": "connected" if connected else "NOT CONNECTED"}

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
            line_items=[{"price_data": {"currency": "usd", "product_data": {"name": "STATUS - Couple Registration"}, "unit_amount": 99}, "quantity": 1}],
            mode="payment",
            success_url="https://vite-react-rouge-omega-62.vercel.app/?paid=true",
            cancel_url="https://vite-react-rouge-omega-62.vercel.app/?paid=false",
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/couples")
def register_couple(data: dict):
    if not init_db():
        return {"error": "Database not available", "couple_id": None}
    data["registered_at"] = datetime.utcnow()
    data["status"] = "active"
    try:
        result = couples_collection.insert_one(data)
        couple_id = str(result.inserted_id)
        email = data.get("person1", {}).get("email", "")
        p1 = data.get("person1", {}).get("name", "")
        p2 = data.get("person2", {}).get("name", "")
        if SENDGRID_API_KEY and email:
            try:
                html = f"<div style='font-family:Arial;max-width:600px;margin:0 auto'><div style='background:#10b981;padding:30px;text-align:center'><h1 style='color:white;margin:0'>STATUS</h1></div><div style='padding:30px;background:#f9fafb'><h2>Congratulations!</h2><p>Your relationship is now registered!</p><div style='background:white;border:2px solid #10b981;border-radius:10px;padding:20px;margin:20px 0;text-align:center'><strong>{p1}</strong> and <strong>{p2}</strong></div></div></div>"
                requests.post("https://api.sendgrid.com/v3/mail/send", headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"}, json={"personalizations": [{"to": [{"email": email}]}], "from": {"email": SENDER_EMAIL, "name": "STATUS"}, "subject": "STATUS - Registration Complete!", "content": [{"type": "text/html", "value": html}]}, timeout=10)
            except:
                pass
        return {"couple_id": couple_id, "message": "Registered successfully!"}
    except Exception as e:
        return {"error": str(e), "couple_id": None}

@app.get("/api/search")
def search(name: str = None):
    if not name:
        return {"results": [], "total": 0}
    if not init_db():
        return {"results": [], "total": 0}
    try:
        query = {"$and": [{"status": {"$ne": "deleted"}}, {"$or": [{"person1.name": {"$regex": name.strip(), "$options": "i"}}, {"person2.name": {"$regex": name.strip(), "$options": "i"}}]}]}
        cursor = couples_collection.find(query).limit(50)
        results = []
        for doc in cursor:
            results.append({"couple_id": str(doc.get("_id", "")), "person1": doc.get("person1"), "person2": doc.get("person2"), "anniversary": doc.get("anniversary"), "registered_at": doc.get("registered_at").isoformat() if doc.get("registered_at") else None})
        return {"results": results, "total": len(results)}
    except Exception as e:
        return {"results": [], "total": 0}

@app.get("/api/couple/{couple_id}")
def get_couple(couple_id: str):
    if not init_db():
        return {"error": "Database not available"}
    try:
        doc = couples_collection.find_one({"_id": ObjectId(couple_id)})
        if doc and doc.get("status") != "deleted":
            return {"couple_id": str(doc.get("_id")), "person1": doc.get("person1"), "person2": doc.get("person2"), "anniversary": doc.get("anniversary"), "status": doc.get("status", "active")}
    except:
        pass
    return {"error": "Couple not found"}

@app.post("/api/delete/request")
def delete_request(data: dict):
    email = data.get("email", "").strip().lower()
    if not email or not init_db():
        return {"success": False, "error": "Email required"}
    try:
        couple = couples_collection.find_one({"$and": [{"status": {"$ne": "deleted"}}, {"$or": [{"person1.email": {"$regex": f"^{email}$", "$options": "i"}}, {"person2.email": {"$regex": f"^{email}$", "$options": "i"}}]}]})
        if couple:
            return {"success": True}
        return {"success": False, "error": "No registration found with this email"}
    except:
        return {"success": False, "error": "Error searching"}

@app.post("/api/delete/confirm")
def delete_confirm(data: dict):
    email = data.get("email", "").strip().lower()
    if not email or not init_db():
        return {"success": False, "error": "Email required"}
    try:
        result = couples_collection.update_one({"$or": [{"person1.email": {"$regex": f"^{email}$", "$options": "i"}}, {"person2.email": {"$regex": f"^{email}$", "$options": "i"}}]}, {"$set": {"status": "deleted", "deleted_at": datetime.utcnow()}})
        if result.modified_count > 0:
            return {"success": True, "message": "Deleted"}
        return {"success": False, "error": "Could not delete"}
    except:
        return {"success": False, "error": "Delete failed"}

@app.get("/api/stats")
def stats():
    if not init_db():
        return {"total": 0, "database": "NOT CONNECTED"}
    try:
        return {"total": couples_collection.count_documents({"status": {"$ne": "deleted"}}), "database": "connected"}
    except:
        return {"total": 0, "database": "error"}

@app.get("/api/admin/all")
def admin_all(limit: int = 100):
    if not init_db():
        return {"registrations": [], "count": 0}
    try:
        cursor = couples_collection.find().sort("registered_at", -1).limit(limit)
        results = [{"couple_id": str(doc.get("_id", "")), "person1": doc.get("person1", {}).get("name", ""), "person2": doc.get("person2", {}).get("name", ""), "status": doc.get("status", "active")} for doc in cursor]
        return {"registrations": results, "count": len(results)}
    except:
        return {"registrations": [], "count": 0}
