import os
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no está definida en las variables de entorno")

db_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# NullPool: no mantiene conexiones abiertas entre requests.
# Correcto para Supabase transaction pooler (puerto 6543) que ya gestiona su propio pool.
# Con pool_size fijo, SQLAlchemy agotaba las 15 conexiones del free tier en reposo.
engine = create_engine(
    db_url,
    poolclass=NullPool,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
