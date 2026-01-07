from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "STATUS API"}

@app.get("/api/health")
def health():
    return {"status": "healthy"}

@app.post("/api/verify/email/request")
def email_request():
    return {"message": "Code sent"}

@app.post("/api/verify/email/confirm")
def email_confirm():
    return {"verified": True}

@app.post("/api/verify/id/upload")
def id_upload():
    return {"success": True}

@app.post("/api/verify/face")
def face_verify():
    return {"match": True, "confidence": 0.95}

@app.get("/api/search")
def search():
    return {"results": [], "total": 0}

@app.get("/api/stats")
def stats():
    return {"total": 0}
