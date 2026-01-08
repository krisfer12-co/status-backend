from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registrations = []

@app.get("/")
def root():
    return {"message": "STATUS API"}

@app.get("/api/health")
def health():
    return {"status": "healthy"}

@app.post("/api/verify/email/request")
def email_request(data: dict):
    return {"message": "Code sent", "email": data.get("email")}

@app.post("/api/verify/email/confirm")
def email_confirm(data: dict):
    return {"verified": True}

@app.post("/api/verify/id/upload")
def id_upload(data: dict):
    return {"success": True}

@app.post("/api/verify/face")
def face_verify(data: dict):
    return {"match": True, "confidence": 0.95}

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
                results.append(r)
    return {"results": results, "total": len(results)}

@app.get("/api/stats")
def stats():
    return {"total": len(registrations)}
