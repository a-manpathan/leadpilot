"""
Database connection, engine initialization, and session management for LeadPilot.
"""
import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from config.settings import DATABASE_URL, IS_SQLITE, IS_POSTGRES
from database.models import Base

logger = logging.getLogger("leadpilot.db")

_engine = None
_SessionFactory = None


def get_engine():
    """Returns singleton SQLAlchemy engine configured for SQLite or PostgreSQL."""
    global _engine
    if _engine is None:
        if IS_SQLITE:
            _engine = create_engine(
                DATABASE_URL,
                connect_args={"check_same_thread": False},
                echo=False,
            )
        else:
            _engine = create_engine(
                DATABASE_URL,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False,
            )
        logger.info(f"Database engine initialized with URI: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    return _engine


def get_session_factory():
    """Returns singleton sessionmaker."""
    global _SessionFactory
    if _SessionFactory is None:
        engine = get_engine()
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionFactory


def init_db():
    """Initializes all database tables automatically on startup."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema verified and tables created if not existing.")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager for safe transactional database sessions."""
    SessionFactory = get_session_factory()
    session: Session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        session.close()


def reset_engine():
    """Disposes the cached engine so a new process-like connection can be opened."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None


def test_connection() -> tuple[bool, str]:
    """Tests current database connection and returns (success, message)."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_type = "PostgreSQL" if IS_POSTGRES else "SQLite"
        return True, f"Successfully connected to {db_type} database."
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"
