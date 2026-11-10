from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.core.config import settings

# Normalize Postgres URL prefix (e.g. Supabase or Heroku postgres:// -> postgresql://)
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# SQLite compatibility
engine_kwargs = {"pool_pre_ping": True}
if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    # When in-memory SQLite is requested in CI, route to a shared file to enable safe multi-threaded concurrency
    if ":memory:" in db_url or db_url == "sqlite://" or db_url == "sqlite":
        db_url = "sqlite:///./dataflow_ci_shared.db"

engine = create_engine(
    db_url,
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
