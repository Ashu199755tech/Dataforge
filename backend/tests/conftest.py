import os
import pytest
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.main import seed_initial_metadata


@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """Initializes the database schema and seeds initial metadata before tests run."""
    Base.metadata.create_all(bind=engine)
    try:
        seed_initial_metadata()
    except Exception as e:
        # Non-fatal if already seeded or during specific sub-tests
        pass
    yield
    # Cleanup CI shared sqlite file if created
    for path in ["./dataflow_ci_shared.db", "./dataflow_ci_shared.db-journal", "./dataflow_ci_shared.db-wal"]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
