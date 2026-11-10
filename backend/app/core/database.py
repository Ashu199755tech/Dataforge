from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import StaticPool
from backend.app.core.config import settings

# SQLite compatibility argument
connect_args = {}
engine_kwargs = {"pool_pre_ping": True}

# Normalize Postgres URL prefix (e.g. Supabase or Heroku postgres:// -> postgresql://)
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    if ":memory:" in db_url or db_url == "sqlite://" or db_url == "sqlite":
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(
    db_url,
    connect_args=connect_args,
    **engine_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
