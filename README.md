# GAME STORE — Telegram Mini App

PlayStation game store as a Telegram Mini App.  
Prices from 4 regions (UA/TR/IN/PL) converted to BYN.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite |
| Backend | FastAPI, SQLite (aiosqlite) |
| Bot | aiogram 3 |
| Parser | httpx, PS Store API |
| Backend Deploy | Railway |
| Frontend Deploy | Vercel |

---

## Project Structure

```
tg-shop/
├── backend/          # FastAPI REST API
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── schemas.py
│   └── routers/
├── frontend/         # React Mini App
│   ├── src/
│   ├── index.html
│   ├── vite.config.ts
│   └── vercel.json
├── bot/              # Telegram Bot (aiogram 3)
│   └── bot.py
├── parser/           # PS Store price parser
│   ├── ps_parser.py
│   └── sale_import.py
├── database/
│   └── schema.sql
├── requirements.txt
├── railway.json
└── Procfile
```

---

## Local Development

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/tg-shop.git
cd tg-shop
cp .env.example .env
# Fill in .env with your values
```

`.env` variables:
```env
BOT_TOKEN=your_telegram_bot_token
WEBAPP_URL=https://your-frontend.vercel.app
ADMIN_ID=your_telegram_user_id
ADMIN_PASSWORD=your_admin_password
DB_PATH=database/shop.db
CORS_ORIGINS=http://localhost:3001,https://your-frontend.vercel.app
```

### 2. Backend

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8001
# API: http://localhost:8001
# Docs: http://localhost:8001/docs
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# App: http://localhost:3001
```

### 4. Bot

```bash
python bot/bot.py
```

### 5. Import games (optional)

```bash
# Main catalog
python parser/ps_parser.py --run-once

# Spring sale games
python parser/sale_import.py
```

---

## Deploy Backend → Railway

### 1. Create project on Railway

- Go to [railway.app](https://railway.app)
- **New Project** → Deploy from GitHub repo
- Select `tg-shop` repository

### 2. Set environment variables in Railway

In the **Variables** tab:

```
BOT_TOKEN=your_token
WEBAPP_URL=https://your-frontend.vercel.app
ADMIN_ID=123456789
ADMIN_PASSWORD=strong_password
DB_PATH=database/shop.db
CORS_ORIGINS=https://your-frontend.vercel.app
PORT=8000
```

### 3. Railway will automatically:

- Detect `requirements.txt` and install dependencies
- Run the command from `Procfile` / `railway.json`
- Provide a public URL: `https://tg-shop-production.up.railway.app`

### 4. Verify deployment

```
GET https://your-app.up.railway.app/health
→ {"status": "ok"}
```

---

## Deploy Frontend → Vercel

### 1. Import project

- Go to [vercel.com](https://vercel.com)
- **New Project** → Import from GitHub
- **Framework**: Vite
- **Root Directory**: `frontend`
- **Build Command**: `npm run build`
- **Output Directory**: `dist`

### 2. Set environment variable

```
VITE_API_URL=https://your-app.up.railway.app
```

### 3. After deploy — update API URL

In `frontend/src/api.ts`, set the Railway backend URL.

---

## Telegram Bot Setup

```
1. Create bot via @BotFather → get BOT_TOKEN
2. /newapp → set WEBAPP_URL (your Vercel URL)
3. /setmenubutton → add Menu button pointing to WEBAPP_URL
4. /setdomain → allow your Vercel domain
```

---

## Admin Panel

URL: `https://your-frontend.vercel.app/admin`  
Password: value of `ADMIN_PASSWORD` from `.env`

Features:
- Manage products (add / edit / delete)
- View orders
- Manage categories

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/products` | List products (filters: category_id, sort, section) |
| GET | `/api/v1/products/{id}` | Single product |
| GET | `/api/v1/categories` | List categories |
| GET | `/api/v1/cart` | User cart |
| POST | `/api/v1/cart` | Add to cart |
| DELETE | `/api/v1/cart/{id}` | Remove from cart |
| POST | `/api/v1/orders` | Create order |
| GET | `/api/v1/favourites` | User favourites |
| POST | `/api/v1/favourites/{id}` | Add to favourites |

All `/cart` and `/favourites` requests require header `X-User-Id: <telegram_user_id>`.

---

## Price Regions

| Region | Code | Currency | DB Column |
|--------|------|----------|-----------|
| Ukraine | UA | UAH | price_uah |
| Turkey | TR | TRY | price_try |
| India | IN | INR | price_inr |
| Poland | PL | PLN | price_pln |

All prices are converted to BYN for display.
