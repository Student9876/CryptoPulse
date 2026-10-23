# CryptoPulse

**CryptoPulse** is an asynchronous real-time market intelligence and alerting engine for cryptocurrencies. It ingests high-frequency trade data directly from exchange WebSocket streams, calculates rolling statistics across custom time windows, evaluates user-defined alert rules, and delivers instantaneous notifications via a Telegram Bot paired with a Telegram Mini App.

---

## Architecture Overview

```
                      +-----------------------------+
                      |   Binance WebSocket Feed    |
                      +--------------+--------------+
                                     | (Raw Trades)
                                     v
                 +---------------------------------------+
                 |       Binance Ingestion Worker        |
                 | (Reconnects, Heartbeat, Normalization)|
                 +-------------------+-------------------+
                                     |
                                     v
                 +---------------------------------------+
                 |     In-Memory Sliding Window Engine   |
                 |   (Rolling % Chg, Volume Spike, Vol)  |
                 +-------------------+-------------------+
                                     |
                     +---------------+---------------+
                     |                               |
                     v                               v
       +----------------------------+  +----------------------------+
       |   Rule Evaluator Engine    |  | Broadcast Manager (1-to-N) |
       |    (Thresholds & Cooldown) |  |   (SSE / WebSockets Push)  |
       +-------------+--------------+  +-------------+--------------+
                     |                               |
                     v                               v
       +----------------------------+  +----------------------------+
       |  Telegram Bot Dispatcher   |  |     Telegram Mini App      |
       |  (Instant Push Alerts)     |  | (Vite + React + shadcn/ui) |
       +----------------------------+  +----------------------------+
                     |
                     v
       +----------------------------+
       |   Neon PostgreSQL (Async)  |
       |  (Users, Rules & History)  |
       +----------------------------+
```

---

## Directory Structure

```
CryptoPulse/
├── backend/                  # FastAPI backend and async stream engine
│   ├── app/
│   │   ├── core/             # Configuration, logging, settings
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   └── main.py           # FastAPI entrypoint and lifecycle
│   ├── tests/                # Automated pytest suite
│   ├── requirements.txt      # Python dependencies
│   └── .env.example          # Environment variable template
├── frontend/                 # Telegram Mini App (React + Vite + shadcn/ui)
└── README.md
```

---

## Getting Started (Backend)

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Setup Virtual Environment
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Configuration
Copy `.env.example` to `.env`:
```bash
cp backend/.env.example backend/.env
```

### 5. Run the Server
```bash
cd backend
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. You can visit `http://127.0.0.1:8000/docs` for the interactive Swagger documentation.

