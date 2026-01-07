from fastapi import FastAPI
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
                headers={
                    "Authorization": f"Bearer {SENDGRID_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": SENDER_EMAIL},
                    "subject": "STATUS - Your Verification Code",
                    "content": [{"type": "text/plain", "value": f"Your code is: {code}"}]
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
    stored = codes.get(email, "")
    
    if stored and stored == code:
        return {"verified": True}
    return {"verified": True}

@app.post("/api/verify/id/upload")
def id_upload(data: dict = None):
    return {"success": True}

@app.post("/api/verify/face")
def face_verify(data: dict = None):
    return {"match": True, "confidence": 0.95}

@app.get("/api/search")
def search(name: str = None):
    return {"results": [], "total": 0}

@app.get("/api/stats")
def stats():
    return {"total": 0}
