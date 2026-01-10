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
    
    # Code is correct - delete it and return success
    del codes[email]
    return {"success": True, "message": "Email verified", "email": email}
