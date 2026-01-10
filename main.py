from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import random
import string
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "Krisfer12@gmail.com")

codes = {}
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
    codes[email] = code
    
    if SENDGRID_API_KEY and email:
        try:
            requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
                json={
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": SENDER_EMAIL, "name": "STATUS"},
                    "subject": "STATUS - Your Verification Code",
                    "content": [{"type": "text/plain", "value": f"Your verification code is: {code}"}]
                },
                timeout=10
            )
        except:
            pass
    return {"message": "Code sent", "email": email}

@app.post("/api/verify/email/confirm")
def email_confirm(data: dict):
    email = data.get("email", "")
    code = data.get("code", "")
    stored = codes.get(email)
    
    if not stored:
        raise HTTPException(status_code=400, detail="No code sent to this email")
    if stored != code:
        raise HTTPException(status_code=400, detail="Wrong code")
    
    del codes[email]
    return {"verified": True}

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
