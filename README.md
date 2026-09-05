# PRAMAN AI

Phase 0 foundation for PRAMAN AI.

This repository includes:
- React + Vite frontend
- FastAPI backend
- PostgreSQL configuration
- Docker setup for local development
- Alembic migration scaffolding

## Stack
- Frontend: React, TypeScript, Vite, Tailwind CSS, shadcn/ui foundation
- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic
- Database: PostgreSQL
- Containerization: Docker + Docker Compose
- Testing: Pytest + Playwright

## Quick start

1. Copy `.env.example` to `.env` and adjust values as needed.
2. Start the stack:

```bash
docker compose up --build
```

3. Open the frontend at http://localhost:5173
4. Open the backend at http://localhost:8000/docs

## Local development without Docker

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Database

The default configuration points to PostgreSQL with the values in `.env.example`.

## Health check

- Frontend: http://localhost:5173
- Backend: http://localhost:8000/health
- Backend API: http://localhost:8000/api/v1/health

## Notes

This repository intentionally implements the project foundation only. The core inspection workflow and AI/CV features are not part of this Phase 0 implementation.
