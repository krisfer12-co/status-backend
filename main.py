from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import random
import string
import requests
import stripe

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
stripe.api_key = STRIPE_SECRET_KEY

registrations = []

def make_code():
    return "".join(random.choices(string.digits, k=6))

@app.get("/")
def root():
    return {"message": "STATUS API"}

@app.get("/api/health")
def health():
    return {"status": "healthy"}

@app.post("/api/verify/email/request")
def email_request(data: dict):
    email = data.get("email", "")
    code = make_code()
    
    if SENDGRID_API_KEY and email:
        try:
            requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
                json={
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": SENDER_EMAIL, "name": "STATUS"},
                    "subject": "STATUS - Welcome!",
                    "content": [{"type": "text/plain", "value": f"Welcome to STATUS!\n\nYour verification code is: {code}\n\nThank you for registering your relationship!"}]
                },
                timeout=10
            )
        except:
            pass
    return {"message": "Code sent", "email": email}

@app.post("/api/verify/email/confirm")
def email_confirm(data: dict):
    code = data.get("code", "")
    if len(code) == 6 and code.isdigit():
        return {"verified": True}
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
                    "unit_amount": 99,
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
    registrations.append(data)
    return {"couple_id": str(len(registrations)), "message": "Registered"}

@app.get("/api/search")
def search(name: str = None):
    results = []
    if name:
        for r in registrations:
            p1 = r.get("person1", {}).get("name", "").lower()
            p2 = r.get("person2", {}).get("name", "").lower()
            if name.lower() in p1 or name.lower() in p2:
                results.append({"person1": r.get("person1"), "person2": r.get("person2")})
    return {"results": results, "total": len(results)}

@app.get("/api/stats")
def stats():
    return {"total": len(registrations)}
