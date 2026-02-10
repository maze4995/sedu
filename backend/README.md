# SEDU Backend

Minimal FastAPI backend for the SEDU project.

## Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Server starts at http://localhost:8000

## Endpoints

| Method | Path       | Description          |
|--------|------------|----------------------|
| GET    | /health    | Health check         |
| POST   | /uploads   | Upload a file        |
| GET    | /docs      | Swagger UI (auto)    |

## Test

```bash
curl http://localhost:8000/health
```
