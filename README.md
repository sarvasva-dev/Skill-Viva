# 🎙️ SkillViva: AI-Powered Resume-Targeted Interview Trainer

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-v0.110.0-green.svg)](https://fastapi.tiangolo.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-darkgreen.svg)](https://www.mongodb.com/atlas)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

SkillViva is a brutally realistic, high-pressure, voice-driven AI mock interviewer that dynamically targets gaps explicitly found in your uploaded resume. By analyzing your resume text client-side, the AI detects missing skills or weak points and structures an interactive oral exam tailored specifically to grill you on them.

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python**: Version 3.10 or higher.
- **MongoDB**: A running MongoDB Atlas cluster or local MongoDB instance.
- **Sarvam AI API Keys**: Access keys for Sarvam's LLM, Text-to-Speech (TTS), and Speech-to-Text (STT) services.

### 1. Clone & Setup Backend
First, navigate into the project workspace directory:

```powershell
# Navigate to backend directory
cd backend

# Create a Python virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (CMD):
.\venv\Scripts\activate.bat
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy the env template to `.env`:
```powershell
cp .env.example .env
```
Open `backend/.env` and replace the placeholder values with your actual database and API credentials:
```env
MONGODB_URI="mongodb+srv://your-user:your-pass@cluster.mongodb.net/dbname"
SARVAM_API_KEY_LLM="your_sarvam_llm_key"
SARVAM_API_KEY_TTS="your_sarvam_tts_key"
SARVAM_API_KEY_STT="your_sarvam_stt_key"
PORT=8000
```

### 3. Run the Backend Server
Start the FastAPI monolith using `uvicorn` from inside the `backend` folder:
```powershell
uvicorn main:app --reload --port 8000
```
The backend API documentation will be available locally at `http://localhost:8000/docs`.

### 4. Run the Frontend
Since the frontend is built using Vanilla JS and HTML files, you can:
1. Direct-run by double-clicking `frontend/index.html` to open it in your browser.
2. Or use a simple HTTP server to avoid CORS/origin issues when making local network requests:
   ```powershell
   # Using Python's built-in HTTP server from the root directory:
   python -m http.server 3000
   ```
   Then open `http://localhost:3000/frontend/index.html` in your browser.

---

## 📑 Project Overview

* **What problem this project solves**: Traditional mock interviews are scripted and static. Candidates memorize answers and struggle under live pressure. SkillViva solves this by providing a voice-driven AI interviewer that dynamically targets gaps explicitly found in your uploaded resume.
* **Why AI is used**: AI mimics human unpredictability. Static question banks are easy to game. AI generates contextual questions, evaluates answers on technical accuracy dynamically, and simulates the pressure of a seasoned recruiter.

### Main Features
- 🎙️ **Live Voice Interviews**: Real-time microphone input with Voice Activity Detection (VAD). You speak, the AI listens.
- 📄 **Resume-Targeted Grilling**: The AI reads your resume locally and attacks your missing skills or claimed expertise.
- ⚡ **Adaptive Difficulty**: The interview dynamically gets harder if you answer well, and easier if you struggle.
- 📊 **Brutal Feedback**: After every answer, you receive a 0-10 score, an ideal answer, and a grammar check.

---

## 📐 Architecture

Our architecture is a serverless-ready, decoupled monolith designed for extreme speed of execution during a 24-hour hackathon.

```text
[User Microphone]
       ↓
[Vanilla JS Frontend] -> (Converts Voice to Base64)
       ↓
[FastAPI Backend]     -> (Monolithic Python Server handling logic)
       ↓
[MongoDB Atlas]       -> (Saves Q&A history and User Profiles)
       ↓
[Sarvam AI Services]  -> (Grades transcript, converts Text-to-Speech)
       ↓
[Vanilla JS Frontend] -> (Updates UI, Plays Audio)
```

**Why this architecture wins:**
Zero build times for the frontend (no React hydration errors), synchronous thread pools in Python for heavy ML tasks, and asynchronous routing for web calls in a single, predictable file.

---

## 📂 Folder Structure

```text
Skill-Viva/
├── backend/
│   ├── main.py              # Monolithic FastAPI server (API routes, DB connectivity, AI wrapper)
│   ├── requirements.txt     # Python project dependencies
│   ├── .env                 # Local secrets configuration (ignored by Git)
│   ├── .env.example         # Template for environment configuration
│   └── data/
│       └── question.json    # Offline generic question fallback pool
├── frontend/
│   ├── index.html           # Landing page with animated statistics
│   ├── login.html           # Passwordless credentials-free OTP login page
│   ├── onboarding.html      # Name and target role onboarding form
│   ├── dashboard.html       # Candidate hub showing past interview attempts
│   ├── resume.html          # PDF extractor client-side scanner interface
│   ├── interview.html       # The voice interview arena (mic + voice loop)
│   ├── report.html          # Dynamic post-interview analytics reporting
│   ├── profile.html         # User settings modification form
│   └── style.css            # Custom CSS styles complementing Tailwind CDN
├── .gitignore               # Configured to ignore pycache, venv, and local env configs
└── README.md                # Project README handbook
```

---

## 📂 File By File Explanation

### 1. `backend/main.py`
- **Purpose**: The absolute core engine. A monolithic FastAPI server.
- **When It Runs**: Continuously running on the server (`uvicorn main:app`).
- **Important Functions**: `get_current_user()` (auth), `clean_json_string()` (sanitization), `generate_ai_content()` (AI wrapper).
- **Database Usage**: Heavy. Reads/writes to `users`, `interviews`, `custom_questions`, and `questions`.
- **AI Usage**: Orchestrates calls to Sarvam LLM, TTS, and STT.

### 2. `backend/.env`
- **Purpose**: Secure credential storage (`MONGODB_URI`, `SARVAM_API_KEY_...`).
- **When It Runs**: Loaded into memory when `main.py` starts.

### 3. `backend/data/question.json`
- **Purpose**: Offline generic question bank.
- **When It Runs**: Called by `/api/questions` if the AI bulk generation cache is empty.

### 4. `frontend/login.html`
- **Purpose**: Passwordless auth.
- **When It Runs**: User tries to log in.
- **Important Functions**: `handleRequestOTP()`, `handleVerifyOTP()`.
- **Important APIs**: `POST /api/auth/otp`, `POST /api/auth/verify-otp`.

### 5. `frontend/dashboard.html`
- **Purpose**: The main hub for the user.
- **Important Functions**: `fetchData()` (Parallel promise execution for speed).
- **Important APIs**: `GET /api/auth/me`, `GET /api/interviews/user`, `POST /api/questions/generate-batch`.

### 6. `frontend/resume.html`
- **Purpose**: PDF processing.
- **Important Functions**: `extractTextFromPDF()` (Uses `pdf.js` worker client-side).
- **Important APIs**: `POST /api/resume`.

### 7. `frontend/interview.html`
- **Purpose**: The live Q&A arena.
- **Important Functions**: `startListening()` (AudioContext VAD logic), `stopListening()`, `speakText()`.
- **Important APIs**: `/api/tts`, `/api/stt`, `/api/evaluate`, `/api/questions`.

### 8. `frontend/report.html` & `profile.html` & `index.html`
- **Purpose**: Post-interview analysis, user settings, and the landing page with animated stats (`useCountUp()`).

---

## 🔄 Lifecycle Flows

### Frontend Live-Mic Loop
1. **Start**: The UI pings `/api/tts` to make the AI speak the first question.
2. **Listening**: `startListening()` executes. The `AudioContext` and `AnalyserNode` begin measuring the microphone's RMS (energy level) every 100ms.
3. **Silence Detection (VAD)**: If the RMS drops below 0.015 for 3 continuous seconds, the JS automatically stops the `mediaRecorder`.
4. **Processing**: The Audio Blob is sent to `/api/stt` (Speech-to-Text).
5. **Grading**: The returned transcript is sent to `/api/evaluate` along with calculated hesitation times.
6. **Feedback**: The UI displays the score and pings `/api/tts` to speak the feedback.

### Backend Request Cycle
1. **Request Received**: FastAPI parses the JSON body and extracts the `X-User-Email` header.
2. **Auth Injection**: The `get_current_user` dependency automatically fetches the user from MongoDB.
3. **Regex Sanitization**: For AI routes, `main.py` calls Sarvam. The raw response is passed through `clean_json_string()` to strip markdown blocks (like ` ```json `).
4. **Database Update**: The sanitized JSON is appended to the `interviews` collection.
5. **Response Sent**: The formatted JSON is returned to the frontend.

### Authentication Flow
```text
[User] enters email
  ↓
[Backend] generates a 6-digit code, saves it in MongoDB with a 10m expiry, and emails it.
  ↓
[User] enters the 6-digit code.
  ↓
[Backend] verifies the code against MongoDB. If true, the code is deleted.
  ↓
[Frontend] saves the email in `localStorage`.
  ↓
[Protected Routes] Frontend attaches the `X-User-Email` header to every future API call.
```
> [!TIP]
> *Hackathon Bypass*: Entering `123456` bypasses the email phase instantly for live demo environments.

---

## 🗄️ Database Schema Details

**MongoDB Atlas** stores all documents natively:
1. **`users` Collection**: Stores identity (`email`, `name`, `targetRole`). Crucially, it embeds the `resumeAnalysis` directly into the document so the backend doesn't have to re-evaluate the resume to generate questions.
2. **`custom_questions` Collection**: An ephemeral cache. When an interview starts, we bulk-generate 30 questions into this table to eliminate latency during the live Q&A.
3. **`interviews` Collection**: A permanent ledger. It stores the `userId`, `status`, `reportData`, and an array of Q&A `history`.
4. **`questions` Collection**: Offline static fallback questions seeded from `question.json`.

---

## 🤖 AI Workflow & Parameterization

- **Models**: Sarvam `105b` (heavy reasoning), `30b` (fast fallback), `bulbul:v3` (TTS), `saaras:v1` (STT).
- **Parameters**: `Temperature = 0.7` is used for reasoning tasks to balance creativity with accuracy.
- **Prompt Strategy**: Constraint-focused. We inject database context: *"Generate a question for {role}. The candidate is missing these skills: {missingSkills}. Be brutal."*
- **Fallback Handling**: If `105b` times out or throws a 504 Gateway Error, the `try/except` block instantly redirects the exact prompt to the `30b` model.
- **Error Recovery**: `clean_json_string()` prevents JSONDecodeErrors. If parsing fails entirely, hardcoded fallback objects are returned to prevent the app from crashing during a demo.

---

## 🔌 API Documentation

### Auth & Profile
* `POST /api/auth/otp`: Generates and emails a 6-digit login code.
* `POST /api/auth/verify-otp`: Verifies the code and returns the user object.
* `GET /api/auth/me`: Retrieves the currently logged-in user's profile data via `X-User-Email`.
* `PUT /api/auth/me`: Updates the user's name or target role.
* `POST /api/auth/onboarding`: Sets `isOnboarded = True` and saves the user's name/role.

### Interview Preparation
* `POST /api/resume`: Analyzes extracted resume text (client-side PDF parsed) to find missing skills and ATS friendliness. Uses `sarvam-105b`.
* `POST /api/questions/generate-batch`: Bulk-generates 30 customized questions *before* the interview starts to ensure zero latency during the live session. Saves to `custom_questions`.
* `GET /api/roles`: Returns a hardcoded list of supported job roles.

### Live Interview Engine
* `POST /api/interviews`: Initializes a new interview session record in MongoDB.
* `POST /api/questions`: Fetches the next interview question. Mostly used for Q1 (intro) or if the bulk cache runs out.
* `POST /api/evaluate`: The core grading engine. Grades the candidate's voice answer, penalizing for hesitation and filler words. Dictates adaptive difficulty for the next round.
* `POST /api/tts`: Sarvam Text-to-Speech wrapper. Returns Base64 Audio.
* `POST /api/stt`: Sarvam Speech-to-Text wrapper. Converts audio blobs to text transcripts.
* `PUT /api/interviews/{id}`: Appends Q&A history to an active interview or updates the final report.

### Post-Interview Analytics
* `POST /api/report`: Analyzes the entire interview transcript block and generates a final post-interview performance summary JSON.
* `GET /api/interviews/user`: Fetches the user's past 20 interviews for the dashboard history view.
* `DELETE /api/interviews/user/clear`: Wipes the user's interview history.

---

## 👩‍⚖️ Evaluator Defense & Technical QA Guide

### 1. Why did you choose a monolithic Python architecture over Next.js?
* **Short (20s)**: Execution speed. Python dominates AI integrations.
* **Detailed (2m)**: During a 24-hour hackathon, we needed to eliminate build times and hydration errors. FastAPI gave us synchronous thread pools for heavy ML tasks and async routing for web calls.
* **Deep Tech**: Python allows us to utilize advanced regex pipelines (`re.sub`) for JSON sanitization and synchronous standard libraries (`requests`) which are more resilient for raw AI fallback loops than JS fetch promises.

### 2. [TRAP] Isn't having everything in `main.py` bad practice?
* **Short (20s)**: For production, yes. For a prototype, it's optimal.
* **Detailed (2m)**: It violates the Single Responsibility Principle, but we explicitly chose monolithic procedural code to avoid module resolution bugs and circular imports.
* **Deep Tech**: In V2, we would refactor this into an MVC pattern using FastAPI Routers.

### 3. Why use Vanilla JS instead of React?
* **Short (20s)**: Zero build steps. Direct DOM manipulation.
* **Detailed (2m)**: It proves we understand underlying browser APIs. The Voice Activity Detection (VAD) requires raw `AudioContext` control, which React's synthetic event system complicates.
* **Deep Tech**: By skipping the Virtual DOM, we achieve true 60FPS UI updates when polling the microphone RMS levels every 100ms.

### 4. Where is the PDF uploaded?
* **Short (20s)**: It isn't. It's read in the browser.
* **Detailed (2m)**: We use the `pdf.js` worker to parse the binary ArrayBuffer locally. Only the extracted raw text string is sent to the FastAPI backend.

### 5. [TRAP] Is your `X-User-Email` header authentication secure?
* **Short (20s)**: No, it's a hackathon shortcut.
* **Detailed (2m)**: Anyone can spoof the header via Postman. We did this to save 4 hours of debugging JWT rotation.
* **Deep Tech**: In a real environment, the `/verify-otp` route would generate an HS256 signed JWT containing the `user_id`, attach it to a `Secure; HttpOnly; SameSite=Strict` cookie.

### 6. How do you prevent OTP Brute Forcing?
* **Short (20s)**: A strict 10-minute expiry window.
* **Detailed (2m)**: The OTP is only valid for 600 seconds. After that, the `users` document query rejects it.
* **Deep Tech**: Currently, we lack rate-limiting. Before launch, we would use Redis to implement a Token Bucket algorithm.

### 7. Why MongoDB over PostgreSQL?
* **Short (20s)**: Unstructured nested JSON.
* **Detailed (2m)**: Our interview history contains arrays of objects (questions, answers, scores). In SQL, this requires complex foreign key relationships and JOINs. In Mongo, we just `$push` to the history array.
* **Deep Tech**: MongoDB allows us to embed the `resumeAnalysis` directly into the `users` document, saving an expensive disk seek on every request.

### 8. [TRAP] What happens if your LLM returns invalid JSON?
* **Short (20s)**: Our regex pipeline sanitizes it.
* **Detailed (2m)**: LLMs often hallucinate markdown formatting like ` ```json `. If we just ran `json.loads()`, the server would crash. We wrote `clean_json_string()` to strip these anomalies.
* **Deep Tech**: We execute `re.sub(r"```json\n?|```", "", raw_response)` and strip control characters. We then parse it with `json.loads(strict=False)`.

### 9. What if the Sarvam AI 105b model times out?
* **Short (20s)**: We instantly fall back to the 30b model.
* **Detailed (2m)**: We wrap the API call in a `try/except` block. If we receive a 504 Gateway Error, we instantly fire the payload to the `sarvam-30b` endpoint.

### 10. How do you handle Cross-Origin Resource Sharing (CORS)?
* **Short (20s)**: We use FastAPI's `CORSMiddleware`.
* **Detailed (2m)**: We allow `*` origins for the hackathon because we serve the frontend via `file://` protocols locally.
* **Deep Tech**: In production, we would restrict `allow_origins` to our exact Vercel/Netlify domain.

### 11. [TRAP] If your app goes viral, what crashes first?
* **Short (20s)**: The synchronous AI polling.
* **Detailed (2m)**: The `generate-batch` route holds the HTTP request open for 10-15 seconds. 1,000 concurrent users would exhaust our server's thread pool, leading to 502 Bad Gateway errors.
* **Deep Tech**: We would fix this by migrating to an Event-Driven Architecture (Celery + Redis) and notifying the frontend via WebSockets.

---

## 🛡️ Judge Survival & Demo Checklist

- **If they find a bug**: Do NOT panic or make excuses. Say: *"Great catch. We actually identified that as a limitation in our architecture phase. Given the 24-hour limit, we prioritized X over Y. In production, we would fix this by implementing [insert solution here]."*
- **Own your tech debt**: Don't pretend `X-User-Email` is secure. Highlighting your own flaws proves seniority.

### 2-Minute Demo Pitch
> "Traditional interview prep is broken. You memorize LeetCode, but freeze under live pressure. Meet SkillViva. It’s a brutal, AI-driven mock interviewer. Watch this: I upload my resume... it detects I'm missing 'System Design' skills. I click start. The AI immediately attacks that weakness and asks me a tough System Design question via live voice. Our custom browser-engine detects when I stop speaking, grades my hesitation, and gives me a brutal 0-10 score. It’s built on a Python FastAPI monolith with extreme fault-tolerance."

### Key Hackathon Revision Points
1. **Frontend**: Vanilla HTML/JS, Tailwind CSS via CDN.
2. **Backend**: Python 3, FastAPI, Uvicorn.
3. **Database**: MongoDB Atlas (`users`, `interviews`, `custom_questions`).
4. **LLM Engine**: Sarvam AI (`sarvam-105b` & `sarvam-30b`).
5. **Speech AI**: Sarvam `bulbul:v3` (TTS) & `saaras:v1` (STT).
6. **VAD**: Voice Activity Detection runs locally in browser via `AudioContext` RMS (< 0.015).
7. **Privacy Feature**: Resume PDFs are parsed entirely client-side using `pdf.js`.
8. **Auth Model**: Passwordless OTP via email (10m expiry).
9. **Hackathon Shortcut**: Universal OTP `123456` bypasses email latency during demos.
10. **State Management**: `localStorage` (auth) and `sessionStorage` (reports).
11. **Performance Hack**: We bulk-generate 30 questions *before* the interview to eliminate live latency.
12. **Adaptive Difficulty**: AI adjusts difficulty +/- 1 level based on rolling score average.
13. **Fault Tolerance**: Regex `clean_json_string()` prevents JSON crashes.
14. **STT Fallback**: Browser `webkitSpeechRecognition` kicks in if Sarvam API fails.
15. **Delivery Scoring**: JavaScript calculates hesitation seconds; LLM deducts points for it.
16. **Data Storage**: Resume text is embedded in the `users` table to avoid JOIN queries.
17. **Security Debt**: Header-based auth (`X-User-Email`) instead of secure JWTs.
18. **Scaling Debt**: Synchronous REST polling instead of WebSockets.
19. **Architecture Tradeoff**: Monolithic `main.py` over modular structure for speed of execution.
20. **Selling Point**: Brutally realistic evaluation—it doesn't just ask questions, it explicitly grills your resume gaps.

---

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
