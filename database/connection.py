# ============================================================
# Database Connection Manager
# ============================================================
# PURPOSE:
#   Creates and manages the connection to our database.
#   Every file that needs to talk to the database imports from here:
#       from database.connection import get_db, engine
#
# HOW IT WORKS:
#   1. Reads DATABASE_URL from settings (e.g., "sqlite:///./data/jobsearch.db")
#   2. Creates a SQLAlchemy "engine" (the connection pool)
#   3. Creates a "session factory" (produces database sessions on demand)
#   4. Provides get_db() — a function that gives you a session and
#      automatically closes it when you're done
#
# ANALOGY:
#   Think of the engine as the PIPE to the database.
#   Think of a session as a CONVERSATION through that pipe.
#   get_db() starts a conversation, lets you talk, then hangs up.
# ============================================================

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from config.settings import settings
import os


# ---- Step 1: Ensure the data directory exists ----
# SQLite stores the database as a file (e.g., ./data/jobsearch.db)
# We need to make sure the "data" folder exists before SQLite tries to create the file
if settings.DATABASE_URL.startswith("sqlite"):
    # Extract the file path from the URL
    # "sqlite:///./data/jobsearch.db" → "./data/jobsearch.db"
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)  # Create directory if it doesn't exist


# ---- Step 2: Create the database engine ----
# The engine is the core interface to the database.
# It maintains a pool of connections that get reused.

# SQLite needs a special setting to work with multiple threads
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        # SQLite by default only allows one thread. This setting removes that restriction.
        connect_args={"check_same_thread": False},
        # Echo SQL queries to console when LOG_LEVEL is DEBUG (helpful for learning)
        echo=(settings.LOG_LEVEL == "DEBUG"),
    )
else:
    # PostgreSQL (or other databases) don't need the check_same_thread hack
    engine = create_engine(
        settings.DATABASE_URL,
        echo=(settings.LOG_LEVEL == "DEBUG"),
    )


# ---- Step 3: Create a session factory ----
# A "session factory" is a function that creates new database sessions.
# Each session is like opening a conversation with the database:
#   - You can query data (SELECT)
#   - You can insert/update/delete data
#   - You "commit" to save changes, or "rollback" to undo
#   - You "close" when you're done

SessionLocal = sessionmaker(
    bind=engine,          # Connect sessions to our engine
    autocommit=False,     # Don't auto-save — we control when to commit
    autoflush=False,      # Don't auto-push changes — we control when to flush
)


# ---- Step 4: Create the base class for all our database models ----
# Every table we define (UserProfile, JobPosting, etc.) will inherit from this.
# This is how SQLAlchemy knows "this Python class represents a database table."

class Base(DeclarativeBase):
    """
    Base class for all database models.
    
    Every model (table) inherits from this:
        class UserProfile(Base):
            __tablename__ = "user_profiles"
            ...
    """
    pass


# ---- Step 5: Provide a clean way to get database sessions ----
def get_db() -> Session:
    """
    Creates a new database session and returns it.
    
    USAGE (in API routes):
        @app.post("/api/resume/upload")
        def upload_resume(db: Session = Depends(get_db)):
            # Use 'db' to query/insert data
            # Session is automatically closed after the request
    
    USAGE (in agents/scripts):
        db = get_db()
        try:
            # do database work
            db.commit()
        finally:
            db.close()
    """
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def init_database() -> None:
    """
    Creates all database tables if they don't exist yet.
    
    Call this ONCE when the app starts:
        from database.connection import init_database
        init_database()
    
    This reads all the model classes (from models.py) and creates
    the corresponding tables in the database. If a table already
    exists, it's left alone (no data loss).
    """
    # Import models so SQLAlchemy knows about them
    # (they register themselves with Base when imported)
    import database.models  # noqa: F401 — imported for side effect

    # Create all tables that don't exist yet
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created/verified successfully")
