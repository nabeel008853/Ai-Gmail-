import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from openai import OpenAI

st.set_page_config(page_title="AI Gmail Sender", page_icon="📧", layout="wide")

# -------------------------
# Session State
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "email" not in st.session_state:
    st.session_state.email = ""
if "password" not in st.session_state:
    st.session_state.password = ""

# -------------------------
# Helper: Load HTML
# -------------------------
def load_html(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# -------------------------
# API: Login
# -------------------------
def api_login():
    email = st.experimental_get_query_params().get("email", [""])[0]
    password = st.experimental_get_query_params().get("password", [""])[0]

    if not email or not password:
        return {"success": False, "message": "Missing credentials"}

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(email, password)
        server.quit()

        st.session_state.logged_in = True
        st.session_state.email = email
        st.session_state.password = password

        return {"success": True, "message": "Login successful!"}

    except Exception as e:
        return {"success": False, "message": str(e)}

# -------------------------
# API: Upload CSV Contacts
# -------------------------
def api_upload_csv():
    uploaded_file = st.file_uploader("file", type=["csv"])

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        df.to_csv("contacts.csv", index=False)
        return {"success": True, "message": "Contacts uploaded!"}

    return {"success": False, "message": "No file received"}

# -------------------------
# API: AI Email Generation
# -------------------------
def api_generate_email():
    desc = st.experimental_get_query_params().get("description", [""])[0]

    if not desc:
        return {"subject": "", "body": ""}

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=st.secrets["openrouter"]["api_key"]
        )

        completion = client.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct:free",
            messages=[
                {"role": "system", "content": "Write a professional email"},
                {"role": "user", "content": desc}
            ],
            max_tokens=200
        )

        output = completion.choices[0].message.content

        subject = "Generated Subject"
        body = output

        return {"subject": subject, "body": body}

    except Exception as e:
        return {"subject": "", "body": f"Error: {e}"}

# -------------------------
# API: Send Emails
# -------------------------
def api_send_email():
    subject = st.experimental_get_query_params().get("subject", [""])[0]
    body = st.experimental_get_query_params().get("body", [""])[0]

    if not st.session_state.logged_in:
        return {"success": False, "message": "Not logged in"}

    if not os.path.exists("contacts.csv"):
        return {"success": False, "message": "No contacts uploaded"}

    df = pd.read_csv("contacts.csv")

    sender = st.session_state.email
    password = st.session_state.password

    logs = []

    for _, row in df.iterrows():
        try:
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = row["email"]
            msg["Subject"] = subject
            msg.attach(MIMEText(body.replace("{{name}}", str(row.get("name", ""))), "plain"))

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()

            logs.append({"email": row["email"], "status": "Sent"})

        except Exception as e:
            logs.append({"email": row["email"], "status": str(e)})

    return {"success": True, "logs": logs}

# -------------------------
# Router
# -------------------------

query = st.experimental_get_query_params()

if "api" in query:
    if query["api"][0] == "login":
        st.json(api_login())
    elif query["api"][0] == "upload_csv":
        st.json(api_upload_csv())
    elif query["api"][0] == "generate_email":
        st.json(api_generate_email())
    elif query["api"][0] == "send_email":
        st.json(api_send_email())

else:
    if not st.session_state.logged_in:
        st.components.v1.html(load_html("../frontend/login.html"), height=720, scrolling=True)
    else:
        st.components.v1.html(load_html("../frontend/dashboard.html"), height=900, scrolling=True)
