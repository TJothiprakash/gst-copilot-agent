# 🧾 GST Copilot — AI-powered GST Filing Assistant

> Helping small businesses in India file GST returns effortlessly using AI agents.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2.0-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-red)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🎯 Problem

Small business owners in India — especially in textile hubs like Tiruppur — drown in GST compliance paperwork. They can't afford accountants for every invoice. Mistakes lead to penalties.

**GST Copilot solves this.**

---

## 🚀 What it does

Upload any GST invoice (PDF or image) and the AI agent:

1. **Extracts** all invoice data using Gemini multimodal AI
2. **Classifies** invoice as B2B / B2C / Export / RCM
3. **Validates** GSTIN format, HSN codes, GST rates
4. **Computes** CGST / SGST / IGST automatically
5. **Generates** GSTR-1 draft ready for filing
6. **Explains** everything in plain English

Human-in-the-loop ensures nothing gets filed without user confirmation.

---

## 🏗️ Architecture
User uploads invoice
↓
Ingest node (Gemini multimodal)
↓
Classify node (B2B/B2C/Export/RCM)
↓
Validate node (GSTIN, HSN, rates)
↓
── HUMAN CHECKPOINT ── (errors flagged)
↓
Compute node (CGST/SGST/IGST)
↓
Draft GSTR node (GSTR-1 summary)
↓
Explain node (plain English)
↓
Output to user + saved to DB

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | LangGraph |
| LLM | Google Gemini 2.5 Flash |
| API | FastAPI |
| Frontend | Streamlit |
| Database | Supabase (PostgreSQL + pgvector) |
| LLM Tracing | Langfuse |
| Metrics | Prometheus + Grafana Cloud |
| CI/CD | GitHub Actions |
| Deployment | Render |
| Packaging | uv |

---

## 📁 Project Structure
gst-copilot/
├── agent/
│   ├── graph.py          # LangGraph state machine
│   ├── state.py          # TypedDict state schema
│   ├── gemini.py         # Raw Gemini API client
│   ├── prompts.py        # Prompt templates
│   ├── parsers.py        # Pydantic output parsers
│   └── nodes/
│       ├── ingest.py     # File ingestion + extraction
│       ├── classify.py   # Invoice classification
│       ├── validate.py   # Validation + error detection
│       ├── compute.py    # GST computation
│       ├── draft_gstr.py # GSTR-1 draft generation
│       └── explain.py    # Plain English explanation
├── api/
│   └── main.py           # FastAPI endpoints
├── ui/
│   └── app.py            # Streamlit frontend
├── db/
│   └── client.py         # Supabase client
├── evals/
│   └── test_cases.py     # 24 unit tests
├── .github/
│   └── workflows/
│       └── ci.yml        # GitHub Actions CI/CD
├── Dockerfile
├── pyproject.toml
└── .env.example

---

## ⚙️ Local Setup

### Prerequisites
- Python 3.11+
- uv package manager
- Docker (optional)

### Installation

```bash
# Clone the repo
git clone https://github.com/TJothiprakash/gst-copilot-agent.git
cd gst-copilot-agent

# Create virtual environment
uv venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Install dependencies
uv sync

# Copy env file and fill in your keys
cp .env.example .env
```

### Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `GRAFANA_PROMETHEUS_URL` | Grafana Cloud push URL |
| `GRAFANA_PROMETHEUS_USERNAME` | Grafana username |
| `GRAFANA_PROMETHEUS_PASSWORD` | Grafana API token |

### Run locally

```bash
# Terminal 1 - API
uvicorn api.main:app --reload --port 8000

# Terminal 2 - UI
streamlit run ui/app.py
```

Open http://localhost:8501

---

## 🧪 Tests

```bash
pytest evals/test_cases.py -v
# 24 passed
```

---

## 📊 Observability

| Tool | What it tracks |
|------|---------------|
| Langfuse | Every Gemini API call, latency, input/output |
| Prometheus | Invoice processing time, success/failure rates |
| Grafana | Visual dashboards for all metrics |

---

## 🌐 Deployment

Auto-deploys to Render on every push to `main` via GitHub Actions:
Push → Tests → Docker build → Deploy

---

## 🤝 Contributing

This is an open source project. PRs welcome!

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a PR

---

## 📄 License

MIT License — free to use, modify and distribute.

---

## 👨‍💻 Author

Built with ❤️ for small businesses in Tiruppur, Tamil Nadu.