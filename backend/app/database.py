from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Create database engine with connection timeouts
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
    connect_args={
        'connect_timeout': 30,  # 30 second connection timeout
        'read_timeout': 60,     # 60 second read timeout
        'write_timeout': 60     # 60 second write timeout
    }
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables"""
    # Import Base from models to ensure all models are registered
    from app.models import Base
    Base.metadata.create_all(bind=engine)
