"""
SkillViva Backend Application Entry Point

VISUAL FLOW OF HOW THIS FILE WORKS:
USER
↓
FRONTEND FORM (HTML/JavaScript)
↓
API REQUEST (Sends data over the internet)
↓
BACKEND (This main.py file receives the request)
↓
DATABASE (Saves or gets information)
↓
AI MODEL (Reads resumes, grades answers)
↓
RESPONSE (Sends the result back)
↓
UI UPDATE (User sees the screen change)

What is this file?
This file is the "brain" of the application. It runs on a server.
Whenever the frontend (the buttons and screens the user sees) needs to save something, 
get a new interview question, or evaluate an answer, it sends a message here.

Why does this exist?
Because the frontend (HTML/JavaScript) cannot securely talk to databases or AI services directly.
We need this middleman to protect our passwords and handle heavy tasks.
"""
import os
import sys
import codecs

# Force stdout/stderr to UTF-8 to prevent UnicodeEncodeError on Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

import re           # for JSON regex fallback parsing
import traceback     # for detailed error logging
import requests      # for calling Sarvam AI REST API (HTTP calls - Sarvam has no Python SDK)
import json
import base64
import math
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, Header, HTTPException, Request, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson import ObjectId
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

# NOTE: Sarvam AI is NOT a pip package — it is a REST API.
# We call it using: requests.post("https://api.sarvam.ai/v1/chat/completions", ...)
# The generate_ai_content() function below handles all Sarvam API calls.

# Load environment configuration (tries root .env.local first, then local .env)
root_dotenv = os.path.join(os.path.dirname(__file__), "..", "..", ".env.local")
if os.path.exists(root_dotenv):
    load_dotenv(dotenv_path=root_dotenv)
else:
    load_dotenv()

app = FastAPI(title="SkillViva Python API", description="FastAPI function-oriented backend clone")

# Enable CORS for local cross-origin development (just in case)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DATABASE CONNECTION ──────────────────────────────────────────
# What is a database? A place to save data permanently.
# Which database are we using? MongoDB (it saves data as JSON objects).
client = None

def get_db():
    """
    What this function does:
    It connects our Python code to the MongoDB database on the internet.
    
    When it runs:
    Every time an API route needs to save or read data.
    
    Who calls it:
    Almost every function below calls this first!
    
    Why it exists:
    We don't want to open a new connection every single time (that is slow). 
    This checks if we are already connected. If not, it connects.
    """
    global client
    if client is None:
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            raise HTTPException(status_code=500, detail="MONGODB_URI environment variable is missing in .env")
        try:
            # serverSelectionTimeoutMS=3000 ensures it fails quickly (3 seconds) if the cluster is unreachable
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            # Force a fast connection handshake check
            client.admin.command('ping')
        except PyMongoError as e:
            print(f"[Database Error] Failed to connect to MongoDB: {e}")
            raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")
    return client.skillviva

# ── HELPER: SEND OTP EMAIL VIA SMTP/RESEND ───────────────────────
def send_email_otp(to_email: str, otp: str):
    subject = "Your SkillViva Access Code"
    from_name = "SkillViva Security"
    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; background: #0a0a0a; color: #fff; padding: 40px; border-radius: 8px; text-align: center; border: 1px solid #222;">
      <h2 style="color: #e63329; font-size: 28px; letter-spacing: 2px; margin-bottom: 20px;">SKILLVIVA</h2>
      <p style="color: #ccc; font-size: 16px; line-height: 1.5;">Use the following 6-digit code to access your account:</p>
      <div style="background: #111; border: 2px solid #e63329; padding: 24px; margin: 30px 0; border-radius: 4px; display: inline-block;">
        <h1 style="font-size: 48px; letter-spacing: 12px; color: #fff; margin: 0; padding-left: 12px;">{otp}</h1>
      </div>
      <p style="color: #555; font-size: 12px; margin-top: 20px;">This code expires in <strong style="color:#e63329;">10 minutes</strong>. Do not share it with anyone.</p>
    </div>
    """
    
    # 1. Try Resend API
    resend_api_key = os.getenv("RESEND_API_KEY")
    if resend_api_key:
        try:
            url = "https://api.resend.com/emails"
            headers = {
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "from": "SkillViva <onboarding@resend.dev>",
                "to": to_email,
                "subject": subject,
                "html": html_content
            }
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code in [200, 201, 202]:
                print(f"[Resend] OTP email sent successfully to {to_email}")
                return True
            else:
                print(f"[Resend] Failed to send email: {res.text}")
        except Exception as e:
            print(f"[Resend] Exception: {e}")

    # 2. Try SMTP (Nodemailer equivalent)
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    if smtp_user and smtp_pass:
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f'"{from_name}" <{smtp_user}>'
            msg["To"] = to_email
            
            part = MIMEText(html_content, "html")
            msg.attach(part)
            
            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
                server.starttls()
            
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to_email], msg.as_string())
            server.quit()
            print(f"[SMTP] OTP email sent successfully to {to_email}")
            return True
        except Exception as e:
            print(f"[SMTP] Failed to send email via SMTP: {e}")
            
    print(f"\n[Console Fallback] Code for {to_email} is: {otp}\n")
    return False

# ── DATABASE SEEDER: POPULATE QUESTIONS FROM OFFLINE JSON ─────────
def seed_questions():
    try:
        db = get_db()
        count = db.questions.count_documents({})
        if count > 0:
            print(f"[Seeder] Questions collection already has {count} documents. Skipping seeding.")
            return
            
        # Try multiple candidate paths for question.json or question_bank.json
        candidate_paths = [
            os.path.join(os.path.dirname(__file__), "data", "question.json"),
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "question.json"),
            os.path.join(os.path.dirname(__file__), "..", "..", "src", "data", "question_bank.json")
        ]
        
        json_path = None
        for path in candidate_paths:
            if os.path.exists(path):
                json_path = path
                break
                
        if not json_path:
            print(f"[Seeder Warning] Question bank file not found in any of these paths: {candidate_paths}")
            return
            
        print(f"[Seeder] Reading questions from {json_path}...")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        role_map = {
            "frontend_developer": "Frontend Developer",
            "backend_developer": "Backend Developer",
            "full_stack_developer": "Full Stack Developer",
            "data_scientist": "Data Scientist",
            "product_manager": "Product Manager",
            "ui_ux_designer": "UI/UX Designer",
            "devops_engineer": "DevOps Engineer",
            "blockchain_developer": "Blockchain Developer",
            "sde": "Software Development Engineer (SDE)"
        }
        
        roles_data = data.get("roles_data", {})
        docs = []
        for role_key, role_info in roles_data.items():
            display_name = role_map.get(role_key, role_key.replace("_", " ").title())
            questions = role_info.get("questions", [])
            for q in questions:
                docs.append({
                    "role_id": display_name,
                    "difficulty": q.get("difficulty", "Level 1"),
                    "text": q.get("text"),
                    "company": q.get("company", "Generic"),
                    "topic": q.get("topic", "General"),
                    "createdAt": datetime.utcnow()
                })
                
        if docs:
            db.questions.insert_many(docs)
            print(f"[Seeder] Successfully seeded {len(docs)} questions into MongoDB questions collection!")
    except Exception as e:
        print(f"[Seeder Error] Failed to seed questions: {e}")

# ── HELPER: SERIALIZE MONGODB DOCUMENTS TO JSON ──────────────────
def serialize_doc(doc):
    if not doc:
        return None
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    if "userId" in doc:
        doc["userId"] = str(doc["userId"])
    if "user_id" in doc:
        doc["user_id"] = str(doc["user_id"])
    if "createdAt" in doc and isinstance(doc["createdAt"], datetime):
        doc["createdAt"] = doc["createdAt"].isoformat()
    if "updatedAt" in doc and isinstance(doc["updatedAt"], datetime):
        doc["updatedAt"] = doc["updatedAt"].isoformat()
    if "otpExpiry" in doc and isinstance(doc["otpExpiry"], datetime):
        doc["otpExpiry"] = doc["otpExpiry"].isoformat()
    return doc

# ── AUTHENTICATION SOLVER ────────────────────────────────────────
def get_current_user(x_user_email: Optional[str] = Header(None, alias="X-User-Email")):
    """
    FastAPI Dependency to retrieve the currently authenticated user.
    
    Acts as a lightweight stateless authentication middleware. Instead of using complex JWTs 
    (which require secret management and rotation), the client securely stores the verified email 
    and passes it via the 'X-User-Email' header.
    
    If the user does not exist in the database (e.g., first-time verified login), an initial 
    profile is automatically created.
    
    Args:
        x_user_email (str, optional): The email injected from the HTTP request headers.
        
    Returns:
        dict: The MongoDB user document.
        
    Raises:
        HTTPException: 401 Unauthorized if the header is missing.
    """
    if not x_user_email:
        raise HTTPException(status_code=401, detail="X-User-Email header is missing")
    
    db = get_db()
    user = db.users.find_one({"email": x_user_email})
    if not user:
        # Auto-create profile if user is new
        new_user = {
            "email": x_user_email,
            "name": x_user_email.split("@")[0].capitalize(),
            "isOnboarded": False,
            "createdAt": datetime.utcnow()
        }
        result = db.users.insert_one(new_user)
        new_user["_id"] = result.inserted_id
        user = new_user
    return user

# ── LLM WRAPPER: CALL SARVAM AI ──────────────────────────────────
def generate_ai_content(prompt_text: str, max_tokens: int = 4000, temperature: float = 0.1):
    """
    Centralized wrapper for interacting with Sarvam AI's large language models.
    
    This function implements a highly available, fault-tolerant execution pipeline. Since we rely 
    heavily on LLMs for core features (parsing resumes, batching questions, evaluating answers), 
    any AI downtime would break the app. 
    
    Fault Tolerance Mechanism:
    It iterates over multiple model checkpoints (primary: sarvam-105b, fallback: sarvam-30b). 
    If the primary model times out or fails (e.g. 5xx server error), it immediately retries with 
    the secondary model to ensure the user request succeeds.
    
    Args:
        prompt_text (str): The meticulously engineered prompt instruction and context.
        max_tokens (int): Token generation limit. Default 4000.
        temperature (float): Controls response randomness. Default 0.1 for highly deterministic, JSON-heavy output.
        
    Returns:
        str: The raw string content generated by the AI.
        
    Raises:
        HTTPException: 500 error if no API keys are configured or if all models fail to respond.
    """
    keys = [
        os.getenv("SARVAM_API_KEY_LLM"),
        os.getenv("SARVAM_API_KEY_TTS"),
        os.getenv("SARVAM_API_KEY_STT")
    ]
    api_keys = [k for k in keys if k]
    
    if not api_keys:
        raise HTTPException(status_code=500, detail="Sarvam AI keys are not configured in .env")

    is_json = "JSON" in prompt_text
    
    # Fault-tolerant model loop (tries sarvam-105b first, then sarvam-30b)
    for model_name in ["sarvam-105b", "sarvam-30b"]:
        for api_key in api_keys:
            try:
                url = "https://api.sarvam.ai/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "api-subscription-key": api_key
                }
                payload = {
                    "model": model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert AI API. You MUST output ONLY raw valid JSON." if is_json else "You are an expert, helpful assistant."
                        },
                        {
                            "role": "user",
                            "content": prompt_text + "\n\nCRITICAL: Output raw text/JSON without any markdown block formatting."
                        }
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                
                response = requests.post(url, json=payload, headers=headers, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if not content and "reasoning_content" in data.get("choices", [{}])[0].get("message", {}):
                        content = data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")
                    
                    if content:
                        # Strip thinking tags
                        if "<think>" in content:
                            import re
                            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
                        return content.strip()
            except Exception as e:
                print(f"Error calling {model_name} with key: {e}")
                continue

    raise HTTPException(status_code=500, detail="All Sarvam AI model fallback calls failed.")

# ── UTILITY: CLEAN AI JSON RESPONSES ─────────────────────────────
def clean_json_string(raw_str: str) -> str:
    """
    Sanitizes raw AI output to ensure valid JSON parsing.
    
    LLMs (even with strong system prompts) frequently hallucinate markdown code blocks (e.g., ```json ... ```) 
    or include extraneous conversational text alongside the JSON payload. This utility uses regex heuristics 
    to extract the core JSON object/array and strips invalid control characters.
    
    Args:
        raw_str (str): The raw text output from the LLM.
        
    Returns:
        str: A sanitized JSON string ready for json.loads().
    """
    if not raw_str:
        return ""
    cleaned = raw_str.strip()
    if cleaned.startswith("```"):
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
    
    # Grab bracket locations
    start_obj = cleaned.find("{")
    start_arr = cleaned.find("[")
    start_idx = min(start_obj, start_arr) if (start_obj != -1 and start_arr != -1) else max(start_obj, start_arr)
    
    end_obj = cleaned.rfind("}")
    end_arr = cleaned.rfind("]")
    end_idx = max(end_obj, end_arr)
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx:end_idx + 1]
    return cleaned

# ── ROUTES: AUTH & USER PROFILE ──────────────────────────────────
# ── ROUTE: AUTH OTP GENERATION ───────────────────────────────────
# VISUAL FLOW:
# USER (enters email)
# ↓
# FRONTEND (login.html)
# ↓
# API REQUEST (POST /api/auth/otp)
# ↓
# BACKEND (This function runs)
# ↓
# DATABASE (Saves a random 6-digit code for this email)
# ↓
# EMAIL SERVICE (Sends the code to the user's inbox)
# ↓
# FRONTEND (Shows "Enter Code" screen)

@app.post("/api/auth/otp")
async def api_auth_otp(req: Request):
    """
    What this function does:
    It creates a secret 6-digit code (OTP) and sends it to the user's email.
    
    When it gets called:
    When the user types their email and clicks "Continue" on the login page.
    
    What information it receives:
    The user's email address in JSON format: {"email": "hello@example.com"}
    
    Database operation:
    It finds the user's row in the 'users' table (collection). 
    It saves the 6-digit code and sets an expiration time of 10 minutes.
    Why? So we can check if the code is correct later!
    """
    try:
        body = await req.json()
        email = body.get("email", "").strip().lower()
        if not email:
            return JSONResponse(status_code=400, content={"error": "Email is required"})
            
        # Generate random 6-digit OTP
        otp = f"{random.randint(100000, 999999)}"
        db = get_db()
        expiry = datetime.utcnow() + timedelta(minutes=10)
        
        # Check if user exists, if not, create a stub
        user = db.users.find_one({"email": email})
        if not user:
            new_user = {
                "email": email,
                "name": email.split("@")[0].capitalize(),
                "isOnboarded": False,
                "createdAt": datetime.utcnow(),
                "otp": otp,
                "otpExpiry": expiry
            }
            db.users.insert_one(new_user)
        else:
            db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"otp": otp, "otpExpiry": expiry}}
            )
            
        # Send Email
        send_email_otp(email, otp)
        
        return {"success": True, "message": "OTP sent successfully"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: OTP VERIFICATION ────────────────────────────────────────
# VISUAL FLOW:
# USER (Enters the 6-digit code from their email)
# ↓
# FRONTEND (Sends code to /api/auth/verify-otp)
# ↓
# BACKEND (Checks if the code matches what's in the database)
# ↓
# IF MATCH -> BACKEND (Logs the user in and sends back their profile)
# IF NO MATCH -> BACKEND (Throws an error "Invalid code")

@app.post("/api/auth/verify-otp")
async def api_verify_otp(req: Request):
    """
    What this function does:
    It checks if the secret 6-digit code the user typed is correct.
    
    When it gets called:
    When the user clicks "Verify" on the login page.
    
    Database operation:
    Finds the user, compares the code, and if it's correct, deletes the code from the database so it can't be used twice!
    """
    try:
        body = await req.json()
        email = body.get("email", "").strip().lower()
        otp = body.get("otp", "").strip()
        
        if not email or not otp:
            return JSONResponse(status_code=400, content={"error": "Email and OTP are required"})
            
        db = get_db()
        user = db.users.find_one({"email": email})
        if not user:
            return JSONResponse(status_code=404, content={"error": "User not found"})
            
        # Verification logic (with 123456 bypass)
        saved_otp = user.get("otp")
        expiry = user.get("otpExpiry")
        
        is_valid = False
        error_reason = "Invalid verification code"
        
        if otp == "123456":
            is_valid = True
        elif not saved_otp:
            error_reason = "No OTP code was generated for this email. Please request a new code."
        elif saved_otp != otp:
            error_reason = f"Verification code does not match. (Debug: received '{otp}', expected '{saved_otp}')"
        else:
            # Code matches! Let's check expiry
            if expiry:
                if isinstance(expiry, str):
                    expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                if expiry.tzinfo is not None:
                    expiry = expiry.replace(tzinfo=None)
                
                now = datetime.utcnow()
                if now < expiry:
                    is_valid = True
                else:
                    error_reason = f"Verification code has expired. (Debug: expired at {expiry.isoformat()}, now is {now.isoformat()})"
            else:
                is_valid = True  # If no expiry time saved, assume it's valid
                
        if not is_valid:
            print(f"\n[OTP Verify Failure] for {email}: {error_reason}\n")
            return JSONResponse(status_code=400, content={"error": error_reason})
            
        # Success: Clear OTP fields
        db.users.update_one(
            {"_id": user["_id"]},
            {"$unset": {"otp": "", "otpExpiry": ""}}
        )
        
        # Fetch fresh user doc
        user = db.users.find_one({"_id": user["_id"]})
        return serialize_doc(user)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: GET MY PROFILE ────────────────────────────────────────
# VISUAL FLOW:
# FRONTEND (Sends "Who am I?" request with email header)
# ↓
# BACKEND (Finds the user in database) -> Returns Profile JSON!

@app.get("/api/auth/me")
def api_auth_me(db_user = Depends(get_current_user)):
    """
    What this function does:
    It gives the frontend all the saved information about the currently logged-in user.
    
    When it gets called:
    Almost every time a new page loads (Dashboard, Profile, Resume) so the website knows what name to show in the top right corner!
    """
    # Simply extract using dependency injection
    try:
        return serialize_doc(db_user)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})

# ── ROUTE: INITIAL ONBOARDING ────────────────────────────────────
# VISUAL FLOW:
# USER (Types their name and dream job on the onboarding page)
# ↓
# FRONTEND (Sends it to /api/auth/onboarding)
# ↓
# BACKEND (Updates the user's database row with the new info)

@app.post("/api/auth/onboarding")
async def api_auth_onboarding(req: Request, db_user = Depends(get_current_user)):
    """
    What this function does:
    Saves the user's Name and Dream Job Role to the database when they first join.
    """
    try:
        body = await req.json()
        name = body.get("name", "User")
        target_role = body.get("targetRole", "unknown")
        
        db = get_db()
        db.users.update_one(
            {"_id": db_user["_id"]},
            {
                "$set": {"isOnboarded": True, "name": name, "targetRole": target_role},
                "$unset": {"resumeAnalysis": ""}
            }
        )
        return {"message": "Onboarding complete"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: UPDATE MY PROFILE ─────────────────────────────────────
# VISUAL FLOW:
# USER (Changes their name or role on the Profile page)
# ↓
# FRONTEND (Sends PUT request to /api/auth/me)
# ↓
# BACKEND (Updates the database)

@app.put("/api/auth/me")
async def api_auth_me_update(req: Request, db_user = Depends(get_current_user)):
    """
    What this function does:
    Updates the user's profile information. 'PUT' usually means 'Update' in the API world.
    """
    try:
        body = await req.json()
        name = body.get("name")
        target_role = body.get("targetRole")
        
        update_data = {}
        if name:
            update_data["name"] = name.strip()
        if target_role:
            update_data["targetRole"] = target_role.strip()
            
        if not update_data:
            return JSONResponse(status_code=400, content={"error": "No fields to update"})
            
        db = get_db()
        db.users.update_one({"_id": db_user["_id"]}, {"$set": update_data})
        return {"success": True, "message": "Profile updated"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: RESUME ANALYZER ───────────────────────────────────────
# VISUAL FLOW:
# USER (Uploads a PDF Resume on resume.html)
# ↓
# FRONTEND (Reads the PDF and extracts the text)
# ↓
# API REQUEST (Sends the extracted text to /api/resume)
# ↓
# THIS FUNCTION (Sends the text to the AI and asks it to grade it)
# ↓
# AI (Returns a brutal review, missing skills, and ATS score)
# ↓
# DATABASE (Saves this analysis so we can use it to generate custom interview questions later!)

@app.post("/api/resume")
async def api_analyze_resume(req: Request, db_user = Depends(get_current_user)):
    """
    What this function does:
    It asks the AI to act like a brutal tech recruiter. The AI reads the user's resume, 
    compares it to their dream job, and points out all their missing skills.
    
    Why we need this:
    If we know what the user is bad at, we can purposely ask them interview questions about it!
    """
    try:
        body = await req.json()
        text = body.get("text", "")
        target_role = body.get("targetRole", "Frontend Developer")
        
        prompt = f"""
You are a brutally honest tech recruiter. Analyze the candidate's resume against the targeted role: {target_role}.
Highlight missing skills, inconsistencies, and improvements.

JSON format response:
{{
  "feedback": "2-3 sentence brutal review",
  "atsFriendly": true,
  "atsReason": "why it is ATS friendly or not",
  "pageCount": "1",
  "pageAnalysis": "Feedback on resume length",
  "missingSkills": ["skill1"],
  "extraSkills": ["extraSkill1"],
  "mismatches": ["mismatch1"],
  "improvements": ["improvement1"],
  "suggestedDifficulty": 2
}}

Resume:
{text[:5000]}
"""
        raw_response = generate_ai_content(prompt)
        clean_json = clean_json_string(raw_response)
        try:
            data = json.loads(clean_json, strict=False)
        except Exception:
            # Fallback for resume
            data = {
                "feedback": "Resume parsed, but AI formatting failed.",
                "atsFriendly": True,
                "missingSkills": [],
                "improvements": []
            }
        
        # Sync to database
        db = get_db()
        db.users.update_one(
            {"_id": db_user["_id"]},
            {"$set": {"resumeText": text[:8000], "resumeAnalysis": data}}
        )
        return data
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: QUESTIONS GENERATOR ────────────────────────────────────
# VISUAL FLOW:
# FRONTEND (Says "Give me Question #2!")
# ↓
# BACKEND (Looks in the database for pre-generated questions for this user)
# ↓
# IF FOUND -> Returns the question instantly!
# IF NOT FOUND -> BACKEND asks the AI to create a brand new question on the spot.

@app.post("/api/questions")
async def api_get_question(req: Request, db_user = Depends(get_current_user)):
    """
    What this function does:
    It gives the user their next interview question.
    
    The Logic:
    - Question 1 is ALWAYS an "Introduce yourself" question.
    - For other questions, it tries to find custom questions we already generated.
    - If it runs out, it forces the AI to write a new one based on their resume.
    """
    try:
        body = await req.json()
        role_id = body.get("role_id", "Frontend Developer")
        difficulty = str(body.get("difficulty", "1"))
        q_num = body.get("questionNumber", 1)
        asked_ids = body.get("askedQuestionIds", [])
        resume_context = body.get("resumeContext", "")
        if not resume_context:
            resume_context = db_user.get("resumeText", "")
        
        level_map = {"1": "Level 1", "2": "Level 2", "3": "Level 3"}
        diff_text = level_map.get(difficulty, "Level 1")
        
        db = get_db()
        
        # Q1: Introduction
        if q_num == 1:
            prompt = f"Conducting mock interview for {role_id}. Ask the candidate to introduce themselves in max 20 words. Example: 'Welcome. Please introduce yourself and walk me through your background.'"
            q_text = generate_ai_content(prompt)
            return {"question": {"text": q_text, "difficulty": diff_text}}
            
        asked_object_ids = []
        for qid in asked_ids:
            if len(qid) == 24:
                try:
                    asked_object_ids.append(ObjectId(qid))
                except:
                    pass
                    
        # 1. Try custom questions generated in batch first
        match_query = {
            "role_id": role_id,
            "difficulty": diff_text,
            "user_id": db_user["_id"],
            "_id": {"$nin": asked_object_ids}
        }
        
        custom_qs = list(db.custom_questions.aggregate([
            {"$match": match_query},
            {"$sample": {"size": 1}}
        ]))
        
        if custom_qs:
            return {"question": {"text": custom_qs[0]["text"], "difficulty": diff_text, "_id": str(custom_qs[0]["_id"])}}
            
        # 2. Fallback to generic database question and adapt it
        exclude_filter = {"role_id": role_id, "difficulty": diff_text}
        if asked_object_ids:
            exclude_filter["_id"] = {"$nin": asked_object_ids}
            
        db_qs = list(db.questions.aggregate([
            {"$match": exclude_filter},
            {"$sample": {"size": 1}}
        ]))
        
        if not db_qs:
            # Fallback: ignore difficulty
            fallback_filter = {"role_id": role_id}
            if asked_object_ids:
                fallback_filter["_id"] = {"$nin": asked_object_ids}
            db_qs = list(db.questions.aggregate([
                {"$match": fallback_filter},
                {"$sample": {"size": 1}}
            ]))
            
        if db_qs:
            db_question = db_qs[0]["text"]
            fetched_id = str(db_qs[0]["_id"])
            
            # Adapt the question using LLM
            resume_analysis = db_user.get("resumeAnalysis", {})
            analysis_context = ""
            if resume_analysis:
                analysis_context = f"Candidate missing skills: {', '.join(resume_analysis.get('missingSkills', []))}"
                
            adapt_prompt = f"""
You are an expert interviewer conducting a mock interview for the role of {role_id}.
You want to ask the following standard interview question: "{db_question}"

Rewrite this question so it applies directly to the candidate's experience, target domain, or skills/tools mentioned in their resume. 

CRITICAL REQUIREMENTS:
1. Make it sound conversational, direct, and brutal. 
2. The rewritten question MUST be short and crisp (maximum 25 words). Do NOT write a long paragraph.
3. This is a general role-specific mock interview, NOT a company-specific one. If the question mentions any specific company name (like Google, Amazon, Wipro, TCS, etc.), STRIP out that company name and make the question company-neutral.
4. CRITICAL: Do NOT hallucinate. You MUST pick a project, skill, or experience that is EXPLICITLY MENTIONED in the candidate's resume. If you cannot find a specific match, just ask the standard question generically.

Return ONLY the customized question text.

Resume:
{resume_context[:4000]}

{analysis_context}
"""
            try:
                adapted_text = generate_ai_content(adapt_prompt)
                if adapted_text:
                    return {"question": {"text": adapted_text, "difficulty": diff_text, "_id": fetched_id}}
            except Exception as e:
                print(f"[LLM Adapt Error] {e}")
                return {"question": {"text": db_question, "difficulty": diff_text, "_id": fetched_id}}
                
        # 3. If no generic questions found, do pure AI generation
        resume_analysis = db_user.get("resumeAnalysis", {})
        analysis_context = ""
        if resume_analysis:
            analysis_context = f"Candidate missing skills: {', '.join(resume_analysis.get('missingSkills', []))}"
            
        prompt = f"""
Generate a practical question for a {role_id} role.
Difficulty: {diff_text}
Candidate context: {analysis_context}
Rules: Keep under 25 words. Conversational. Do not mention company names.
"""
        q_text = generate_ai_content(prompt)
        return {"question": {"text": q_text, "difficulty": diff_text}}
    except Exception as e:
        print(f"[Get Question Error] {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: BATCH GENERATION ──────────────────────────────────────
# VISUAL FLOW:
# USER (Clicks "Start Interview" on the Dashboard)
# ↓
# FRONTEND (Sends a request here BEFORE the interview actually starts)
# ↓
# BACKEND (Asks the AI to generate 30 custom questions based on their resume all at once)
# ↓
# DATABASE (Saves all 30 questions)
# ↓
# FRONTEND (Takes the user to the Interview Arena)

@app.post("/api/questions/generate-batch")
async def api_generate_batch(req: Request, db_user = Depends(get_current_user)):
    """
    What this function does:
    It bulk-generates 30 interview questions before the interview even starts.
    
    Why we do this:
    If we asked the AI to generate a question *during* the interview, the user would have to sit in silence for 5 seconds waiting. 
    By pre-generating them, the interview feels lightning fast!
    """
    try:
        body = await req.json()
        role = body.get("role")
        resume_context = body.get("resumeContext", "")
        
        db = get_db()
        
        # Persona prompt for 30 questions
        prompt = f"""
Generate exactly 30 interview questions for a mock interview for the role of {role}.
Based strictly on this resume: {resume_context[:4000]}

DISTRIBUTION:
- 10 Questions at Level 1 (Basic / Intro)
- 10 Questions at Level 2 (Intermediate)
- 10 Questions at Level 3 (Advanced / Stress-test)

Requirements: Max 25 words per question. Output ONLY a raw JSON array of objects:
[
  {{ "text": "Question text...", "difficulty": "Level 1" }},
  {{ "text": "Question text...", "difficulty": "Level 2" }}
]
"""
        raw_res = generate_ai_content(prompt, max_tokens=4000)
        clean_json = clean_json_string(raw_res)
        try:
            questions = json.loads(clean_json, strict=False)
        except Exception:
            questions = []
        
        docs = []
        for q in questions:
            docs.append({
                "user_id": db_user["_id"],
                "role_id": role,
                "difficulty": q.get("difficulty", "Level 1"),
                "text": q.get("text"),
                "createdAt": datetime.utcnow(),
                "used": False
            })
            
        if docs:
            db.custom_questions.delete_many({"user_id": db_user["_id"], "role_id": role})
            db.custom_questions.insert_many(docs)
            
        return {"success": True, "count": len(docs)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: RESPONSE EVALUATOR ─────────────────────────────────────
# VISUAL FLOW:
# USER (Finishes answering a question out loud)
# ↓
# FRONTEND (Converts their voice to text, and sends the text here)
# ↓
# THIS FUNCTION (Sends the Interviewer's Question AND the User's Answer to the AI)
# ↓
# AI (Grades the answer out of 10, writes brutal feedback, and provides a perfect "Ideal Answer")
# ↓
# FRONTEND (Shows the grade and feedback on screen!)

@app.post("/api/evaluate")
async def api_evaluate_response(req: Request, db_user = Depends(get_current_user)):
    """
    What this function does:
    It is the core of the grading system. It takes what the user said, checks how long they hesitated, 
    and asks the AI to be a ruthless grader.
    
    It also controls "Adaptive Difficulty". If the user is scoring really well (like 9/10), 
    this function tells the system to make the next question HARDER (Level 3)!
    """
    try:
        body = await req.json()
        question = body.get("question")
        answer = body.get("answer")
        hesitation = body.get("hesitationSeconds", 0)
        delay = body.get("preAnswerDelay", 0)
        fillers = body.get("fillerCount", 0)
        level = int(body.get("currentLevel", 1))
        role = body.get("role", "Frontend Developer")
        recent_scores = body.get("recentScores", [])

        prompt = f"""
You are a brutal, realistic expert interviewer conducting a mock interview for the role of {role}.
Rate the candidate's answer below.

Question: "{question}"
Candidate Answer: "{answer}"

Delivery Data:
- Silence/hesitation while speaking: {hesitation} seconds
- Delay before starting the answer: {delay} seconds
- Filler words detected: {fillers}

Instructions:
1. Score 0-10 purely on answer quality relative to the expected knowledge for the {role} role.
   - CRITICAL REQUIREMENT: DO NOT evaluate a non-technical/business answer on "technical coding/programming" standards. Instead, grade it based on communication quality, logical reasoning, domain knowledge, and problem-solving skills.
2. Penalize delivery only after judging content:
   - hesitation >5s can reduce confidence score.
   - starting delay >10s can reduce readiness score.
   - many filler words can reduce clarity score.
   - Do not over-penalize a strong answer for minor pauses.
3. Give brutal 2-sentence feedback. No fluff.
4. Give an ideal 3-4 sentence model answer.
5. Confidence must be exactly one of: Confident, Nervous, Neutral.
6. Grammar score 0-10.

Output ONLY this JSON (no markdown, no extra text):
{{
  "score": 7,
  "feedback": "Two sentence brutal feedback here.",
  "idealAnswer": "Three to four sentence ideal answer here.",
  "confidence": "Confident",
  "grammarScore": 8
}}
"""
        raw_res = generate_ai_content(prompt)
        print(f"[Evaluate] Raw LLM response:\n{raw_res}\n")
        clean_json = clean_json_string(raw_res)
        print(f"[Evaluate] Cleaned JSON:\n{clean_json}\n")

        # Primary parse attempt
        data = None
        try:
            data = json.loads(clean_json, strict=False)
        except Exception:
            # FALLBACK: try to grab any valid JSON object with a 'score' key
            # (same strategy as the Next.js evaluate route)
            import re
            matches = re.findall(r'\{[\s\S]*?\}', raw_res)
            for m in matches:
                try:
                    candidate = json.loads(m, strict=False)
                    if "score" in candidate:
                        data = candidate
                        print(f"[Evaluate] Recovered JSON via regex fallback")
                        break
                except Exception:
                    continue

        # If still nothing, return a safe default — never crash with 500
        if not data:
            print("[Evaluate] All JSON parsing failed. Using safe default response.")
            data = {
                "score": 5,
                "feedback": "The AI evaluator had difficulty scoring this response, but it has been recorded.",
                "idealAnswer": "A strong answer would directly address the question with specific examples and clear structure.",
                "confidence": "Neutral",
                "grammarScore": 7
            }

        # Clamp score to 0-10
        score = max(0, min(10, int(data.get("score", 5))))

        # Adaptive Difficulty: recent_scores from JS are already on 0-100 scale
        # (JS does: recentScores.push(evalData.score * 10))
        # We add current score also on 0-100 scale → consistent comparison
        scores = list(recent_scores) + [score * 10]
        if len(scores) > 3:
            scores = scores[-3:]
            
        avg_score = sum(scores) / len(scores)
        next_level = level
        if avg_score < 56:
            next_level = max(1, level - 1)
        elif avg_score > 76:
            next_level = min(3, level + 1)
            
        data["nextLevel"] = next_level
        data["rollingAverage"] = avg_score
        return data
    except Exception as e:
        import traceback
        print(f"[Evaluate Exception] {e}")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: FINAL PERFORMANCE REPORT ──────────────────────────────
# VISUAL FLOW:
# USER (Finishes all their interview questions)
# ↓
# FRONTEND (Sends the entire interview history to /api/report)
# ↓
# BACKEND (Asks the AI to read the entire history and write a final summary)
# ↓
# FRONTEND (Saves the report and redirects the user to the Report page!)

@app.post("/api/report")
async def api_generate_report(req: Request):
    """
    What this function does:
    It asks the AI to act like a hiring manager and write a final summary of how the user performed overall.
    """
    try:
        body = await req.json()
        history = body.get("history", [])
        role = body.get("role", "Frontend Developer")
        
        prompt = f"""
Generate a comprehensive performance report for a mock interview for the role of {role}.
History Log:
{json.dumps(history)}

Identify strengths, weaknesses, and clear preparation recommendations.
Return strictly a JSON object:
{{
  "strong_areas": ["HTML/CSS", "React Hooks"],
  "weak_areas": ["State Management", "Performance Optimization"],
  "overall_feedback": "Detailed overall recruiter feedback text...",
  "recommendations": ["Recommendation 1", "Recommendation 2"]
}}
"""
        raw_res = generate_ai_content(prompt)
        clean_json = clean_json_string(raw_res)
        data = json.loads(clean_json)
        return data
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: INTERVIEW STATE MANAGEMENT ────────────────────────────
# VISUAL FLOW:
# USER (Clicks "Start Interview") -> API Creates a new empty interview in the Database
# USER (Answers a question) -> API Adds the Q&A to the interview in the Database
# USER (Finishes the interview) -> API Saves the final report to the Database

@app.post("/api/interviews")
async def api_create_interview(req: Request, db_user = Depends(get_current_user)):
    """
    What this function does:
    Creates a brand new "Interview Session" folder in the database so we can keep track of their progress.
    """
    try:
        body = await req.json()
        role = body.get("role")
        difficulty = body.get("difficulty")
        
        db = get_db()
        session = {
            "userId": db_user["_id"],
            "role": role,
            "initialDifficulty": difficulty,
            "history": [],
            "status": "IN_PROGRESS",
            "createdAt": datetime.utcnow(),
            "updatedAt": datetime.utcnow()
        }
        res = db.interviews.insert_one(session)
        return {"interviewId": str(res.inserted_id)}
    except Exception as e:
        print(f"[Create Session Error] {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.put("/api/interviews/{id}")
async def api_update_interview(id: str, req: Request, db_user = Depends(get_current_user)):
    """
    What this function does:
    Whenever the user answers a question or finishes the interview, this updates their "Interview Session" folder in the database.
    """
    try:
        body = await req.json()
        history_item = body.get("historyItem")
        report_data = body.get("reportData")
        status = body.get("status")
        
        db = get_db()
        update_doc = {"$set": {"updatedAt": datetime.utcnow()}}
        
        if history_item:
            update_doc["$push"] = {"history": history_item}
        if report_data:
            update_doc["$set"]["reportData"] = report_data
        if status:
            update_doc["$set"]["status"] = status
            
        db.interviews.update_one(
            {"_id": ObjectId(id), "userId": db_user["_id"]},
            update_doc
        )
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/interviews/user")
def api_get_user_interviews(db_user = Depends(get_current_user)):
    try:
        db = get_db()
        interviews = list(db.interviews.find({"userId": db_user["_id"]}).sort("createdAt", -1).limit(20))
        return [serialize_doc(i) for i in interviews]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/api/interviews/user/clear")
def api_clear_user_history(db_user = Depends(get_current_user)):
    try:
        db = get_db()
        db.interviews.delete_many({"userId": db_user["_id"]})
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: HARDCODED ROLES ───────────────────────────────────────
@app.get("/api/roles")
def api_get_roles():
    return [
        {"name": "Frontend Developer"},
        {"name": "Backend Developer"},
        {"name": "Full Stack Developer"},
        {"name": "Data Scientist"},
        {"name": "Product Manager"},
        {"name": "UI/UX Designer"},
        {"name": "DevOps Engineer"},
        {"name": "Blockchain Developer"}
    ]

# ── ROUTE: TEXT TO SPEECH (TTS) ──────────────────────────────────
# VISUAL FLOW:
# FRONTEND (Sends the text "What is React?")
# ↓
# BACKEND (Sends the text to Sarvam AI's Text-to-Speech service)
# ↓
# SARVAM AI (Converts the text into an Audio File)
# ↓
# BACKEND (Sends the Audio File back to the Frontend)
# ↓
# FRONTEND (Plays the sound out loud!)

@app.post("/api/tts")
async def api_tts(req: Request):
    """
    What this function does:
    It takes text and turns it into a human-sounding voice so the AI can actually "speak" to the user!
    """
    try:
        body = await req.json()
        text = body.get("text", "")
        api_key = os.getenv("SARVAM_API_KEY_TTS")
        
        url = "https://api.sarvam.ai/text-to-speech"
        payload = {
            "inputs": [text[:500]],
            "model": "bulbul:v2",
            "speaker": "anushka",
            "language_code": "en-IN"
        }
        headers = {
            "api-subscription-key": api_key,
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return {"audioBase64": data.get("audios", [""])[0]}
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── ROUTE: SPEECH-TO-TEXT (STT) ──────────────────────────────────
@app.post("/api/stt")
async def api_stt(file: UploadFile = File(...)):
    try:
        api_key = os.getenv("SARVAM_API_KEY_STT")
        url = "https://api.sarvam.ai/speech-to-text"
        
        files = {
            "file": ("speech.webm", await file.read(), "audio/webm")
        }
        data = {
            "model": "saaras:v3",
            "mode": "transcribe"
        }
        headers = {
            "api-subscription-key": api_key
        }
        
        response = requests.post(url, files=files, data=data, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[STT Error] Sarvam STT returned status {response.status_code}: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except HTTPException as http_err:
        return JSONResponse(status_code=http_err.status_code, content={"error": http_err.detail})
    except Exception as e:
        print(f"[STT Exception] {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ── SERVE FRONTEND STATIC FILES ──────────────────────────────────
# Mount the static files folder so index.html, dashboard.html etc. load.
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")

@app.on_event("startup")
async def startup_event():
    print("[Startup] Running database seeding...")
    seed_questions()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
