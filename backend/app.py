# backend/app.py
import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from openai import OpenAI
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ------------------------
# Streamlit Session State
# ------------------------
for key in [
    "logged_in", "sender_email", "sender_password",
    "generated_subject", "generated_body"
]:
    if key not in st.session_state:
        st.session_state[key] = "" if "email" in key or "password" in key else False

# ------------------------
# FastAPI Setup
# ------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for local dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# Utility Functions
# ------------------------
def create_message(sender, to, subject, text, attachments):
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))
    for path in attachments:
        part = MIMEBase("application", "octet-stream")
        with open(path, "rb") as f:
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(path)}")
        msg.attach(part)
    return msg

def send_email(sender, password, to, msg):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        return "✅ Sent"
    except Exception as e:
        return f"❌ {e}"

def generate_email_via_openrouter(prompt):
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=st.secrets["openrouter"]["api_key"]
        )
        completion = client.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct:free",
            messages=[
                {"role": "system", "content": "You are a professional email writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=400
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error generating email: {e}"

# ------------------------
# API ENDPOINTS
# ------------------------
@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(email, password)
        server.quit()
        st.session_state.logged_in = True
        st.session_state.sender_email = email
        st.session_state.sender_password = password
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/generate")
async def generate_email(description: str = Form(...)):
    prompt = f"Description: {description}\nReturn as: Subject: <subject>\nBody: <body>"
    ai_response = generate_email_via_openrouter(prompt)
    if "Subject:" in ai_response and "Body:" in ai_response:
        subject = ai_response.split("Subject:")[1].split("Body:")[0].strip()
        body = ai_response.split("Body:")[1].strip()
    else:
        subject = "Generated Subject"
        body = ai_response
    st.session_state.generated_subject = subject
    st.session_state.generated_body = body
    return {"subject": subject, "body": body}

@app.post("/send")
async def send_emails(
    subject: str = Form(...),
    body: str = Form(...),
    files: list[UploadFile] = File(None),
    contacts_file: UploadFile = File(...)
):
    contacts = pd.read_csv(contacts_file.file)
    attachment_paths = []
    if files:
        for f in files:
            path = f.name
            with open(path, "wb") as out:
                out.write(f.file.read())
            attachment_paths.append(path)
    logs = []
    for _, row in contacts.iterrows():
        text_to_send = body.replace("{{name}}", str(row.get("name", "")))
        msg = create_message(st.session_state.sender_email, row["email"], subject, text_to_send, attachment_paths)
        status = send_email(st.session_state.sender_email, st.session_state.sender_password, row["email"], msg)
        logs.append({"email": row["email"], "status": status})
    return {"logs": logs}

# ------------------------
# Run FastAPI inside Streamlit
# ------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
