# Prism

A self-hosted, bring-your-own-model (BYOM) AI chat platform.  
**Backend**: FastAPI (Python 3.14) · **Frontend**: Next.js 15 (React 19)

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.14 |
| Node.js | 20 LTS |
| npm | 10 |
| Git | any |

---

## Project Structure

```
prism/
├── backend/       # FastAPI API server
└── frontend/      # Next.js UI
```

---

## Backend Setup

```bash
cd backend

# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -e ".[llm,dev]"

# 3. Configure environment
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
```

Edit `backend/.env` and set at minimum:

```env
# Generate with:
# python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
MASTER_KEY=<your-generated-key>

JWT_SECRET=<at-least-32-random-chars>
```

```bash
# 4. Run database migrations
python -m app.dev_migrate

# 5. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API is available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

## Frontend Setup

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Configure environment
copy .env.local.example .env.local   # Windows
# cp .env.local.example .env.local   # macOS / Linux
```

If `.env.local` does not exist, create it:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
# 3. Start the dev server
npm run dev
```

The UI is available at `http://localhost:3000`.

### Production build

```bash
npm run build
npm start
```

---

## Running Tests (Backend)

```bash
cd backend
.venv\Scripts\activate
pytest
```

With coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

---

## Environment Variables Reference

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `dev` | Environment (`dev` / `prod`) |
| `APP_PORT` | `8000` | Port the API listens on |
| `MASTER_KEY` | *(required)* | Base64 32-byte Fernet key |
| `JWT_SECRET` | *(required)* | Secret for signing JWTs |
| `JWT_ACCESS_TTL_MIN` | `15` | Access token lifetime (minutes) |
| `JWT_REFRESH_TTL_DAYS` | `30` | Refresh token lifetime (days) |
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLAlchemy DB URL |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | Logging level |
| `UPLOAD_DIR` | `./uploads` | Directory for file uploads |
| `UPLOAD_MAX_IMAGE_MB` | `10` | Max image upload size |
| `UPLOAD_MAX_FILE_MB` | `25` | Max file upload size |

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |

---

## Adding an AI Provider

1. Log in to the UI at `http://localhost:3000`
2. Go to **Settings → Providers**
3. Add a provider (OpenAI, Azure OpenAI, Anthropic, Google, or Ollama) with your API key
4. Models from that provider will be available in the chat model selector

---

## License

Private repository — all rights reserved.
