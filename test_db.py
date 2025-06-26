#!/usr/bin/env python3
"""
Test database connection and create tables
"""
from db.database import test_connection, engine
from db.models import Base

def main():
    print("🔍 Testing database connection...")
    
    if test_connection():
        print("✅ Database connection successful!")
        
        print("🔨 Creating tables...")
        try:
            Base.metadata.create_all(bind=engine)
            print("✅ Tables created successfully!")
            
            # List created tables
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            print(f"📋 Created tables: {tables}")
            
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
    else:
        print("❌ Database connection failed!")
        print("Make sure PostgreSQL is running and database exists")

if __name__ == "__main__":
    main()