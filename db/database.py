import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment-specific .env file
environment = os.getenv("ENVIRONMENT", "development")
env_file = f"environments/{environment}/.env"

if os.path.exists(env_file):
    load_dotenv(env_file, override=True)  # Force override existing env vars
    print(f"📁 Loaded {environment} environment from {env_file}")
else:
    load_dotenv()  # Fallback to root .env
    print(f"⚠️  Could not find {env_file}, using default .env")

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://obd2_user:obd2_password@localhost:5432/obd2_scanner"  # Use localhost as fallback
)

print(f"🔍 Using DATABASE_URL: {DATABASE_URL}")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
    echo=os.getenv("ENVIRONMENT") == "development"  # Log SQL in dev
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Test connection function
def test_connection():
    try:
        from sqlalchemy import text
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print(f"✅ Database connected successfully: {DATABASE_URL}")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False