from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DB_TYPE         = os.getenv("DB_TYPE", "postgresql")
DB_USERNAME     = os.getenv("DB_USERNAME", "derms")
DB_PASSWORD     = os.getenv("DB_PASSWORD", "derms123")
DB_SERVER_URL   = os.getenv("DB_SERVER_URL", "localhost")
DB_SERVER_PORT  = os.getenv("DB_SERVER_PORT", "5432")
DB_NAME         = os.getenv("DB_NAME", "dermsdb")
ENGINE_ECHO     = os.getenv("ENGINE_ECHO", "false").lower() == "true"

DATABASE_URL = f"{DB_TYPE}://{DB_USERNAME}:{DB_PASSWORD}@{DB_SERVER_URL}:{DB_SERVER_PORT}/{DB_NAME}"

engine = create_engine(url=DATABASE_URL, echo=ENGINE_ECHO)

SessionLocal = sessionmaker(bind=engine)

def get_db():
    session = SessionLocal()
    try:
        yield session
    except:
        session.rollback()
        raise
    finally:
        session.close()