code = make_code()
codes[email] = code  # Store the code for this email

if SENDGRID_API_KEY:
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
