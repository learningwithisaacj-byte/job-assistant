# 🚀 Job Assistant AI

> **AI-powered job search + ATS resume generator**
> Find jobs → match to your profile → auto-generate tailored resumes → download PDF/DOCX

Built with **FastAPI · Streamlit · Claude (Anthropic) · python-jobspy · SQLAlchemy**

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔍 **Multi-source Job Scraping** | LinkedIn, Indeed, Naukri via `python-jobspy` |
| 🧠 **AI Job Matching** | Claude scores each job vs your resume (0–100%) |
| ✍️ **ATS Resume Generator** | Full resume rewrite per JD with action verbs & keywords |
| 💌 **Cover Letter Generator** | Tailored, human-sounding cover letter per job |
| 📄 **PDF + DOCX Export** | Clean ATS-friendly format, both formats |
| 📊 **ATS Score + Gap Analysis** | Keyword density score + missing skill suggestions |
| 🖥️ **Streamlit UI** | Upload, search, generate, download – all in-browser |
| 🐘 **PostgreSQL / SQLite** | SQLite for dev, swap URL for Postgres in prod |

---

## 📁 Folder Structure

```
job_assistant/
├── backend/
│   ├── __init__.py
│   ├── config.py            ← Settings (reads from .env)
│   ├── database.py          ← SQLAlchemy models + async session
│   ├── scraper.py           ← LinkedIn / Indeed / Naukri scrapers
│   ├── matcher.py           ← TF-IDF + Claude job scoring
│   ├── resume_generator.py  ← JD parser + resume rewriter + cover letter
│   ├── pdf_generator.py     ← ReportLab PDF + python-docx DOCX
│   └── main.py              ← FastAPI app (all endpoints)
├── frontend/
│   └── app.py               ← Streamlit UI
├── utils/
│   ├── __init__.py
│   ├── resume_parser.py     ← PDF/DOCX text extraction
│   └── ats_scorer.py        ← Keyword density + ATS audit
├── sample_transformation.py ← Before/after resume example
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── render.yaml              ← Render.com deployment config
└── README.md
```

---

## ⚡ Quick Start (Local)

### 1. Clone & Install

```bash
git clone https://github.com/your-username/job-assistant.git
cd job-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...    # ← Required (get from console.anthropic.com)
DATABASE_URL=sqlite+aiosqlite:///./job_assistant.db   # default = SQLite
OUTPUT_DIR=./outputs
MATCH_THRESHOLD=65
```

### 3. Start the Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

Open: http://localhost:8000/docs (FastAPI Swagger UI)

### 4. Start the Frontend

In a **new terminal**:

```bash
streamlit run frontend/app.py
```

Open: http://localhost:8501

---

## 🐳 Docker Compose (Recommended)

```bash
# Copy env
cp .env.example .env
# Fill in ANTHROPIC_API_KEY in .env

# Start everything (API + Streamlit + PostgreSQL)
docker-compose up --build
```

Services:
- Frontend: http://localhost:8501
- API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

---

## ☁️ Deploy on Render.com (Free)

### Option A – Using render.yaml (Blueprint)

1. Fork this repo to your GitHub
2. Go to https://render.com → New → Blueprint
3. Connect your GitHub repo
4. Render auto-reads `render.yaml` and creates:
   - `job-assistant-api` (FastAPI web service)
   - `job-assistant-ui` (Streamlit web service)
   - `job-assistant-db` (PostgreSQL database)
5. Set `ANTHROPIC_API_KEY` in the Environment Variables for `job-assistant-api`

### Option B – Manual Render Deploy

**Backend (FastAPI):**
```
Build Command:  pip install -r requirements.txt
Start Command:  uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Frontend (Streamlit):**
```
Build Command:  pip install -r requirements.txt
Start Command:  streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
```

**Environment Variables (both services):**
```
ANTHROPIC_API_KEY  = sk-ant-...
DATABASE_URL       = <from Render PostgreSQL>
ENVIRONMENT        = production
OUTPUT_DIR         = /tmp/outputs
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload-resume` | Upload PDF/DOCX, get `user_id` |
| `POST` | `/api/search-jobs` | Scrape + match jobs |
| `POST` | `/api/generate-resume` | Generate tailored resume for a job |
| `GET` | `/api/download/pdf/{id}` | Download PDF |
| `GET` | `/api/download/docx/{id}` | Download DOCX |
| `GET` | `/api/download/cover-letter/{id}` | Download cover letter |
| `GET` | `/api/jobs` | List stored jobs |
| `GET` | `/api/health` | Health check |

Full interactive docs: `http://localhost:8000/docs`

---

## 📊 Sample Transformation (Before → After)

Run the demo:
```bash
python sample_transformation.py
```

**Before (typical resume):**
```
- Worked on backend systems using Python
- Helped with the API development
- Did some database work
```

**After (AI-tailored):**
```
• Architected a FastAPI-based microservices platform handling 50K+ daily API
  requests, reducing latency by ~35% through Redis caching and async query
  optimisation.
• Developed and deployed 4 PyTorch ML models to production using Docker and
  Kubernetes, cutting inference time by 28% via batching and quantisation.
```

---

## 🔑 Getting Your Anthropic API Key

1. Go to https://console.anthropic.com
2. Sign up / log in
3. Settings → API Keys → Create Key
4. Copy to `.env` as `ANTHROPIC_API_KEY=sk-ant-...`

---

## ⚠️ Important Notes

- **Job scraping rate limits**: LinkedIn and Indeed rate-limit aggressively. Use proxies or add delays for large batches.
- **AI costs**: Each resume generation uses ~3,000–5,000 tokens (≈ $0.01–0.03 per resume on Claude Sonnet).
- **No fabrication**: The AI strictly preserves your actual experience. It only improves wording and adds keywords.
- **Naukri scraping**: Works via their internal API. May break if Naukri updates their endpoint.

---

## 🚀 Bonus Features Included

- ✅ **Resume Score vs JD** – ATS keyword density score after generation
- ✅ **Keyword Gap Suggestions** – Shows which JD keywords are missing
- ✅ **Skill Overlap Report** – Matched vs missing skills per job
- 💡 **Chrome Extension Idea** – See `CHROME_EXTENSION_IDEA.md` for architecture

---

## 🧩 Chrome Extension Architecture (Bonus Idea)

```
chrome-extension/
├── manifest.json        ← MV3, permissions: activeTab, storage
├── content.js           ← Detects LinkedIn job pages, extracts JD
├── popup.html           ← "Apply with Job Assistant" button
└── background.js        ← Calls your API: POST /api/generate-resume
                            then opens PDF download
```

Flow:
1. User browses LinkedIn job → extension detects JD
2. Clicks "Generate ATS Resume" in popup
3. Extension POSTs JD to your API (needs your hosted URL)
4. API returns download links → extension opens PDF

---

## 📜 License

MIT – use freely, attribution appreciated.
