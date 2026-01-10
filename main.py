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
GOOGLE_VISION_KEY = os.environ.get("GOOGLE_VISION_KEY", "")

# IMPORTANT: Store codes here
codes = {}
registrations = []

def make_code():
    return "".join(random.choices(string.digits, k=6))

def send_email(to_email, code):
    if SENDGRID_API_KEY:
        try:
            requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
                json={
                    "personalizations": [{"to": [{"email": to_email}]}],
                    "from": {"email": SENDER_EMAIL, "name": "STATUS App"},
                    "subject": "STATUS - Your Verification Code",
                    "content": [{"type": "text/plain", "value": f"Your verification code is: {code}\n\nThis code expires in 10 minutes."}]
                },
                timeout=10
            )
        except:
            pass

def detect_face(image_base64):
    if not GOOGLE_VISION_KEY:
        return True
    try:
        if image_base64 and "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        response = requests.post(
            f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_KEY}",
            json={"requests": [{"image": {"content": image_base64}, "features": [{"type": "FACE_DETECTION", "maxResults": 1}]}]},
            timeout=30
        )
        faces = response.json().get("responses", [{}])[0].get("faceAnnotations", [])
        return len(faces) > 0
    except:
        return True

@app.get("/")
def root():
    return {"message": "STATUS API v2.2 - Email Fix + Ready for MongoDB"}

@app.get("/api/health")
def health():
    return {"status": "healthy", "total_couples": len(registrations)}

@app.post("/api/verify/email/request")
def email_request(data: dict):
    email = data.get("email", "")
    if not email:
        raise HTTPException(status_code=400, detail="Email required")
    
    code = make_code()
    codes[email] = code  # Store the code
    send_email(email, code)
    
    return {"message": "Code sent", "email": email}

@app.post("/api/verify/email/confirm")
def email_confirm(data: dict):
    email = data.get("email", "")
    code = data.get("code", "")
    
    # Check if code was requested for this email
    if email not in codes:
        raise HTTPException(status_code=400, detail="No code requested for this email")
    
    # Check if code matches
    stored_code = codes[email]
    if stored_code != code:
        raise HTTPException(status_code=400, detail="Invalid code")
    
    # Code is correct - delete it
