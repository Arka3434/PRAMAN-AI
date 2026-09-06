from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401
from app.api.v1 import api_router
from app.core.bootstrap import bootstrap_initial_admin, ensure_default_dev_users
from app.core.config import settings
from app.core.storage import ensure_upload_root, UPLOAD_ROOT
from app.db.session import SessionLocal


def run_database_migrations() -> None:
    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    alembic_cfg.set_main_option('sqlalchemy.url', settings.database_url)
    command.upgrade(alembic_cfg, 'head')


ensure_upload_root()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="PRAMAN AI Phase 2 backend foundation",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.mount('/storage', StaticFiles(directory=str(UPLOAD_ROOT.parent)), name='storage')
app.include_router(api_router)


@app.on_event('startup')
async def startup_event() -> None:
    run_database_migrations()
    with SessionLocal() as db:
        bootstrap_initial_admin(db)
        ensure_default_dev_users(db)


@app.get('/')
async def root() -> dict[str, str]:
    return {'message': 'PRAMAN AI backend is running'}
