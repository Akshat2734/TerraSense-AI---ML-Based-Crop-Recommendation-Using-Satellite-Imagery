import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Writes: Point to PgBouncer (Port 6432)
# We use os.getenv to allow Docker to override this, but default to our PgBouncer setup
# 1. Writes: Point to PgBouncer (Port 6432)
PRIMARY_URL = os.getenv(
    "DATABASE_WRITE_URL", 
    "postgresql://terrasense:secretpassword@pgbouncer:6432/terrasense_db"
)

# 2. Reads: Point directly to the official Storage Node (Port 5432)
REPLICA_URL = os.getenv(
    "DATABASE_READ_URL",
    "postgresql://terrasense:secretpassword@db:5432/terrasense_db"
)

# Create the Engines
engine_primary = create_engine(PRIMARY_URL)
engine_replica = create_engine(REPLICA_URL)

# Create the Session Factories
SessionLocalPrimary = sessionmaker(autocommit=False, autoflush=False, bind=engine_primary)
SessionLocalReplica = sessionmaker(autocommit=False, autoflush=False, bind=engine_replica)

# Dependency for background Celery Tasks (Writes)
def get_db():
    db = SessionLocalPrimary()
    try:
        yield db
    finally:
        db.close()

# Dependency for FastAPI Map Queries (Reads)
def get_read_db():
    db = SessionLocalReplica()
    try:
        yield db
    finally:
        db.close()