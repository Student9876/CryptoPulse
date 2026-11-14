# CryptoPulse — Cloud Deployment Guide

This guide walks you through deploying **CryptoPulse** to production for **$0/month** using modern serverless and cloud hosting platforms.

---

## Architecture Overview

```
                      ┌────────────────────────────────┐
                      │ Binance Vision Market Gateway  │
                      │ (Public WebSocket Data Stream) │
                      └───────────────┬────────────────┘
                                      │ Live Trade Ticks
                                      ▼
┌────────────────────────┐    ┌────────────────────────────────┐
│   Telegram Bot Client  │    │     CryptoPulse Backend        │
│    (Mobile / Desktop)  │◄───┤  (FastAPI + In-Memory Deque)   │
└───────────┬────────────┘    │ Hosted on: Koyeb / Render      │
            │                 └───────────────┬────────────────┘
            │ Launch Mini App                 │
            ▼                                 │ REST & SSE
┌────────────────────────┐                    │
│ Telegram Mini App (TMA)│                    │
│ (React + shadcn/ui)    │◄───────────────────┘
│ Hosted on: Vercel      │
└────────────────────────┘
            │
            ▼
┌────────────────────────┐
│   Serverless Database  │
│  (Neon PostgreSQL)     │
└────────────────────────┘
```

---

## Step 1: Free Cloud Database (Neon PostgreSQL)

1. Go to [neon.tech](https://neon.tech) and sign up for a free account.
2. Create a new project named `cryptopulse`.
3. Copy the provided connection string. It will look like:
   ```text
   postgresql://alex:AbC123xyz@ep-cool-fog-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
4. *Note:* CryptoPulse automatically sanitizes this connection string to use the asynchronous `postgresql+asyncpg://` driver prefix.

---

## Step 2: Deploy Backend (Koyeb or Render)

### Option A: Deploy to Koyeb (Recommended — Frankfurt / Zero Timeout)
1. Fork or push this repository to GitHub.
2. Sign in to [koyeb.com](https://www.koyeb.com).
3. Click **Create App** → **GitHub**.
4. Select your `CryptoPulse` repository.
5. In **Builder**:
   - Choose **Dockerfile**.
   - Set **Dockerfile location** to: `backend/Dockerfile`.
   - Set **Work directory** to: `backend`.
6. Under **Environment variables**, add:
   - `DATABASE_URL`: `<your-neon-database-url>`
   - `TELEGRAM_BOT_TOKEN`: `<your-bot-token-from-botfather>`
   - `BINANCE_WS_URL`: `wss://data-stream.binance.vision/stream`
   - `DEBUG`: `false`
   - `CORS_ORIGINS`: `["*"]`
   - `ENABLE_INGESTION`: `true`
7. Click **Deploy**. Koyeb will build the image, start the WebSocket ingestion, and give you a public URL (e.g. `https://cryptopulse-backend-yourname.koyeb.app`).

### Option B: Deploy to Render
1. Sign in to [render.com](https://render.com) → **New** → **Web Service**.
2. Connect your repository.
3. Choose **Docker**, set Docker context directory to `./backend`, Dockerfile to `Dockerfile`.
4. Add the same environment variables as above.
5. Click **Deploy**.

---

## Step 3: Run Database Migrations in Cloud

From your local machine, run Alembic migrations pointing to your Neon database:

```powershell
$env:DATABASE_URL="your-neon-database-url"
.venv\Scripts\alembic -c backend\alembic.ini upgrade head
```

This will create the `users`, `alert_rules`, and `alert_history` tables on Neon in seconds.

---

## Step 4: Deploy Frontend (Vercel)

1. Sign in to [vercel.com](https://vercel.com) → **Add New** → **Project**.
2. Select your repository.
3. Configure the project:
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
4. Under **Environment Variables**, add:
   - `BACKEND_URL`: `https://your-backend-app.onrender.com` (or Koyeb URL)
5. Click **Deploy**. You will receive a production URL (e.g. `https://cryptopulse.vercel.app`).

---

## Step 5: Telegram Bot & Mini App Integration

1. Open Telegram and message **[@BotFather](https://t.me/BotFather)**.
2. If you haven't created your bot yet, send `/newbot` and follow the prompts to get your `TELEGRAM_BOT_TOKEN`.
3. Configure the Mini App launch button:
   - Send: `/setmenubutton`
   - Select your bot.
   - Enter button title: `Open CryptoPulse`
   - Enter your Vercel URL: `https://cryptopulse.vercel.app`
4. Test inside Telegram:
   - Search for your bot in Telegram and start a chat.
   - You will see the **"Open CryptoPulse"** menu button in the bottom-left corner!
   - Tapping it opens the live Mini App with real-time Binance ticks and native Telegram haptic feedback.
