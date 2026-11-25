# CryptoPulse ⚡

[![Telegram Bot](https://img.shields.io/badge/Telegram-@cryptopulse10__bot-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/cryptopulse10_bot)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React_18-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/Neon_PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

**CryptoPulse** is an ultra-low-latency real-time cryptocurrency telemetry and market intelligence engine. It streams high-frequency trade ticks directly from the Binance WebSocket exchange feed, calculates sliding-window metrics in $O(1)$ time, evaluates user-defined alert rules in RAM, and pushes real-time market snapshots and notifications to a **Telegram Mini App (TMA)** and bot.

🤖 **Live Telegram Bot:** [@cryptopulse10_bot](https://t.me/cryptopulse10_bot)  
📊 **Benchmark & Performance Report:** [docs/BENCHMARK_REPORT.md](docs/BENCHMARK_REPORT.md)

---

## 🌟 Key Features

* **High-Throughput $O(1)$ Sliding-Window Engine:**
  * Incremental rolling accumulators and dual monotonic deques replace repeated $O(N)$ full-window scans.
  * Computes 5m VWAP, rolling percentage price changes (1m, 5m, 15m), volume spike ratios against 1-hour rolling baselines, taker-buy order flow ratios, and online sample variance volatility in sub-35 microseconds.
  * Sustains **53,000+ trades/sec** in steady-state with **p95 latency under 34 µs** and scales up to **1M events** with zero numerical drift.
* **In-Memory Edge-Triggered Alert Engine:**
  * Evaluates price levels, breakouts, percentage changes, volume surges, and taker buy ratios against streaming ticks.
  * Hysteresis and cooldown state machine eliminates notification spam and false flapping.
  * Supports both recurring and one-shot alerts (automatically unregisters and deactivates fired alerts in real time).
  * Validated across 10 labeled scenario tests (177 total tick evaluations) achieving **100% precision and recall**.
* **Telegram Mini App (TMA) & Web Dashboard:**
  * Built with React 18, Vite, TypeScript, TailwindCSS, and shadcn/ui.
  * Real-time Server-Sent Events (SSE) stream delivering 1-second market intelligence updates.
  * Paginated active alerts and audit history logs with pause/resume toggles and history purging.
  * Built-in Browser Preview Mode with direct bot deep-linking for external desktop visitors.
* **Asynchronous Database Architecture:**
  * Fully asynchronous PostgreSQL persistence using SQLAlchemy 2.0 and `asyncpg` with Alembic schema migrations.

---

## 🏗️ Architecture Overview

```
                      +-----------------------------+
                      |   Binance WebSocket Feed    |
                      +--------------+--------------+
                                     | (Raw Trades @trade)
                                     v
                  +---------------------------------------+
                  |       Binance Ingestion Worker        |
                  | (Watchdog, Exponential Backoff, Ping) |
                  +-------------------+-------------------+
                                     |
                                     v
                  +---------------------------------------+
                  |    O(1) Sliding-Window Engine (RAM)   |
                  |  (VWAP, Monotonic High/Low, Variance) |
                  +-------------------+-------------------+
                                     |
                      +---------------+---------------+
                      |                               |
                      v                               v
        +----------------------------+  +----------------------------+
        |   Rule Evaluator Engine    |  | Server-Sent Events (SSE)   |
        |  (Edge Hysteresis & CD)    |  |   (/api/v1/stream/overview)|
        +-------------+--------------+  +-------------+--------------+
                      |                               |
                      v                               v
        +----------------------------+  +----------------------------+
        |   Async Alert Dispatcher   |  |     Telegram Mini App      |
        | (aiogram Telegram Bot API) |  | (React + Vite + shadcn/ui) |
        +-------------+--------------+  +----------------------------+
                      |
                      v
        +----------------------------+
        |   Neon PostgreSQL (Async)  |
        |  (Rules, Users & History)  |
        +----------------------------+
```

---

## ⚡ Performance & Correctness Highlights

All benchmarks were independently measured and verified on an AMD 8-Core / 16-Thread workstation running Python 3.11. Full methodology and raw JSON/CSV data are published in [docs/BENCHMARK_REPORT.md](docs/BENCHMARK_REPORT.md).

| Workload Configuration | Baseline Throughput | Optimized Engine | Speedup | Latency Reduction (p95) |
| :--- | :---: | :---: | :---: | :---: |
| **Window Ingestion Only (100k)** | — | **274,275 eps** | — | **4.4 µs** (p95) |
| **Window + Metrics (Steady-State)** | 585 eps | **53,127 eps** | **90.8x** | **-98.8%** (2,715 µs ➔ 33.7 µs) |
| **Full Pipeline (25 Alert Rules)** | 504 eps | **22,998 eps** | **45.7x** | **-97.9%** (3,409 µs ➔ 71.7 µs) |
| **Full Pipeline (100 Alert Rules)**| 577 eps | **11,700 eps** | **20.3x** | **-94.6%** (2,891 µs ➔ 156.5 µs)|
| **Rule Engine Precision / Recall** | — | **100.0% / 100.0%** | — | **0 False Positives / Negatives** |
| **Concurrent SSE Clients (TCP)**   | — | **100 Clients** | — | **100% Success, 0% Loss** |

---

## 📁 Repository Structure

```
CryptoPulse/
├── backend/                      # FastAPI async backend
│   ├── app/
│   │   ├── api/                  # REST & SSE endpoints (rules, history, stream, analytics)
│   │   ├── bot/                  # aiogram Telegram Bot handlers & dispatcher
│   │   ├── core/                 # Config, security, logging
│   │   ├── db/                   # SQLAlchemy async engine & Base
│   │   ├── models/               # Database ORM models (User, AlertRule, AlertHistory)
│   │   ├── rules/                # In-memory rule engine, caching & cooldown hysteresis
│   │   ├── schemas/              # Pydantic v2 schemas
│   │   ├── stream/               # O(1) Sliding-window analytics & Binance ingestion
│   │   └── main.py               # FastAPI entrypoint & lifespan
│   ├── alembic/                  # Database migration scripts
│   ├── tests/                    # 48 unit, differential, and integration tests
│   └── requirements.txt          # Backend dependencies
├── frontend/                     # Telegram Mini App (TMA)
│   ├── src/
│   │   ├── components/           # UI components (market cards, rule modals, tabs)
│   │   ├── hooks/                # Custom React hooks (SSE streaming, rules, history)
│   │   ├── lib/                  # Telegram WebApp SDK helpers
│   │   └── App.tsx               # Main SPA entrypoint
│   └── package.json              # Frontend dependencies
├── benchmarks/                   # Reproducible benchmarking suite
│   ├── correctness/              # 10 labeled correctness scenarios (177 ticks)
│   ├── data/                     # Deterministic trade event replay generator
│   ├── performance/              # Ingestion throughput, SSE concurrency, dispatcher latency
│   ├── results/                  # Raw benchmark JSON/CSV datasets
│   └── run_all.py                # Master benchmark runner
├── docs/
│   └── BENCHMARK_REPORT.md       # Comprehensive performance & optimization report
└── README.md
```

---

## 🚀 Getting Started

### 1. Prerequisites
* Python 3.11+
* Node.js 18+ & npm
* PostgreSQL (or free cloud tier via [Neon](https://neon.tech))
* Telegram Account & Bot Token (via [@BotFather](https://t.me/BotFather))

---

### 2. Backend Setup

```bash
# 1. Clone the repository
git clone https://github.com/Student9876/CryptoPulse.git
cd CryptoPulse

# 2. Create and activate a Python virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Configure environment variables
cp backend/.env.example backend/.env
# Edit backend/.env and populate your TELEGRAM_BOT_TOKEN and DATABASE_URL

# 5. Run database migrations
cd backend
alembic upgrade head

# 6. Launch the FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://127.0.0.1:8000` (Swagger docs at `http://127.0.0.1:8000/docs`).

---

### 3. Frontend Setup (Telegram Mini App)

```bash
cd frontend

# Install npm packages
npm install

# Start Vite development server
npm run dev
```

The frontend will run at `http://localhost:5173`. When accessed outside Telegram, the built-in **Browser Preview Mode** will guide you to [@cryptopulse10_bot](https://t.me/cryptopulse10_bot).

---

### 4. Running Tests & Benchmarks

```bash
# Run the full automated test suite (48 tests passing)
pytest backend/tests -v

# Run differential analytics tests (Baseline vs. O(1) Engine)
pytest backend/tests/test_differential_analytics.py -v

# Run the full reproducible benchmark suite (throughput, latencies, SSE, profiler)
python -m benchmarks.run_all
```

---

## 🤖 Telegram Bot Integration

Launch the bot directly in Telegram:  
👉 **[@cryptopulse10_bot](https://t.me/cryptopulse10_bot)**

### Bot Commands:
* `/start` — Launches the CryptoPulse Telegram Mini App with a single click.
* `/alerts` — Views and manages active user alerts.
* `/status` — Displays live WebSocket feed connection health and sliding-window statistics.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
