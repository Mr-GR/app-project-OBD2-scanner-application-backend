#!/usr/bin/env python3
"""
Comprehensive database testing script
Tests connection, table creation, CRUD operations, and relationships
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import engine, SessionLocal, Base, test_connection
from db.models import User, UserVehicle, DiagnosticSession, ChatHistory
from sqlalchemy import text
import json
from datetime import datetime

def test_connection_detailed():
    """Test database connection with detailed info"""
    print("🔗 Testing database connection...")
    
    if not test_connection():
        return False
    
    try:
        with engine.connect() as conn:
            # Test PostgreSQL version
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"📋 PostgreSQL Version: {version.split(',')[0]}")
            
            # Test current database
            result = conn.execute(text("SELECT current_database()"))
            db_name = result.fetchone()[0]
            print(f"🗄️  Current Database: {db_name}")
            
            # Test connection count
            result = conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"))
            connections = result.fetchone()[0]
            print(f"🔌 Active Connections: {connections}")
            
        return True
    except Exception as e:
        print(f"❌ Detailed connection test failed: {e}")
        return False

def create_tables():
    """Create all database tables"""
    print("🔨 Creating database tables...")
    
    try:
        Base.metadata.create_all(bind=engine)
        
        # List created tables
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            
        print(f"✅ Created tables: {', '.join(tables)}")
        return True
    except Exception as e:
        print(f"❌ Table creation failed: {e}")
        return False

def test_crud_operations():
    """Test Create, Read, Update, Delete operations"""
    print("📝 Testing CRUD operations...")
    
    db = SessionLocal()
    try:
        # CREATE - Add test user
        test_user = User(
            email="test@obd2scanner.com",
            name="Test User"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        print(f"✅ Created user: {test_user.email} (ID: {test_user.id})")
        
        # CREATE - Add test vehicle
        test_vehicle = UserVehicle(
            user_id=test_user.id,
            vin="1HGBH41JXMN109186",
            make="Honda",
            model="Civic",
            year=2018,
            vehicle_type="Passenger Car",
            is_primary=True
        )
        db.add(test_vehicle)
        db.commit()
        db.refresh(test_vehicle)
        print(f"✅ Created vehicle: {test_vehicle.year} {test_vehicle.make} {test_vehicle.model}")
        
        # CREATE - Add diagnostic session
        test_session = DiagnosticSession(
            user_id=test_user.id,
            vehicle_id=test_vehicle.id,
            dtc_codes=["P0420", "P0171"],
            sensor_data={"engine_temp": "195F", "rpm": "2500"},
            session_name="Test Diagnostic Session",
            notes="Testing database functionality"
        )
        db.add(test_session)
        db.commit()
        db.refresh(test_session)
        print(f"✅ Created diagnostic session: {test_session.session_name}")
        
        # CREATE - Add chat history
        test_chat = ChatHistory(
            user_id=test_user.id,
            vehicle_id=test_vehicle.id,
            message="What does P0420 mean?",
            response="P0420 indicates catalyst system efficiency below threshold.",
            level="beginner",
            context_data={"vin": test_vehicle.vin, "dtc_codes": ["P0420"]},
            response_time_ms=150,
            classification_method="instant_dtc_code_detected",
            endpoint_used="/api/chat"
        )
        db.add(test_chat)
        db.commit()
        db.refresh(test_chat)
        print(f"✅ Created chat history entry")
        
        # READ - Test queries with relationships
        print("\n🔍 Testing relationship queries...")
        
        # User with vehicles
        user_with_vehicles = db.query(User).filter(User.id == test_user.id).first()
        print(f"📊 User {user_with_vehicles.email} has {len(user_with_vehicles.vehicles)} vehicle(s)")
        
        # Vehicle with diagnostic sessions
        vehicle_with_sessions = db.query(UserVehicle).filter(UserVehicle.id == test_vehicle.id).first()
        print(f"📊 Vehicle {vehicle_with_sessions.make} {vehicle_with_sessions.model} has {len(vehicle_with_sessions.diagnostic_sessions)} session(s)")
        
        # UPDATE - Update user name
        test_user.name = "Updated Test User"
        db.commit()
        print(f"✅ Updated user name to: {test_user.name}")
        
        # UPDATE - Update vehicle mileage (add custom field)
        test_vehicle.is_primary = False
        db.commit()
        print(f"✅ Updated vehicle primary status")
        
        # READ - Count records
        user_count = db.query(User).count()
        vehicle_count = db.query(UserVehicle).count()
        session_count = db.query(DiagnosticSession).count()
        chat_count = db.query(ChatHistory).count()
        
        print(f"\n📊 Record counts:")
        print(f"   Users: {user_count}")
        print(f"   Vehicles: {vehicle_count}")
        print(f"   Diagnostic Sessions: {session_count}")
        print(f"   Chat History: {chat_count}")
        
        # DELETE - Clean up test data
        db.delete(test_chat)
        db.delete(test_session)
        db.delete(test_vehicle)
        db.delete(test_user)
        db.commit()
        print("🗑️  Cleaned up test data")
        
        return True
        
    except Exception as e:
        print(f"❌ CRUD operations failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def test_json_fields():
    """Test JSON field functionality"""
    print("🧪 Testing JSON field operations...")
    
    db = SessionLocal()
    try:
        # Create test user and vehicle
        user = User(email="json_test@test.com", name="JSON Test User")
        db.add(user)
        db.commit()
        db.refresh(user)
        
        vehicle = UserVehicle(
            user_id=user.id,
            vin="TEST123456789",
            make="Test",
            model="Vehicle",
            year=2023
        )
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)
        
        # Test complex JSON data
        complex_dtc_data = [
            {"code": "P0420", "description": "Catalyst System Efficiency Below Threshold Bank 1"},
            {"code": "P0171", "description": "System Too Lean Bank 1"}
        ]
        
        complex_sensor_data = {
            "engine": {
                "temperature": {"value": 195, "unit": "F"},
                "rpm": {"value": 2500, "unit": "rpm"}
            },
            "vehicle": {
                "speed": {"value": 45, "unit": "mph"},
                "fuel_level": {"value": 75, "unit": "%"}
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Create diagnostic session with complex JSON
        session = DiagnosticSession(
            user_id=user.id,
            vehicle_id=vehicle.id,
            dtc_codes=complex_dtc_data,
            sensor_data=complex_sensor_data,
            session_name="JSON Test Session"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Test JSON queries
        print("✅ Stored complex JSON data")
        print(f"📊 DTC codes: {len(session.dtc_codes)} entries")
        print(f"📊 Sensor data keys: {list(session.sensor_data.keys())}")
        
        # Test JSON field access
        engine_temp = session.sensor_data['engine']['temperature']['value']
        print(f"🌡️  Engine temperature: {engine_temp}°F")
        
        # Clean up
        db.delete(session)
        db.delete(vehicle)
        db.delete(user)
        db.commit()
        print("🗑️  Cleaned up JSON test data")
        
        return True
    except Exception as e:
        print(f"❌ JSON field test failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def test_performance():
    """Test database performance with bulk operations"""
    print("⚡ Testing database performance...")
    
    db = SessionLocal()
    try:
        start_time = datetime.now()
        
        # Create test user
        user = User(email="perf_test@test.com", name="Performance Test User")
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Bulk insert vehicles
        vehicles = []
        for i in range(100):
            vehicle = UserVehicle(
                user_id=user.id,
                vin=f"TESTVIN{i:010d}",
                make="TestMake",
                model="TestModel",
                year=2020 + (i % 5)
            )
            vehicles.append(vehicle)
        
        db.add_all(vehicles)
        db.commit()
        
        bulk_insert_time = datetime.now() - start_time
        print(f"✅ Bulk inserted 100 vehicles in {bulk_insert_time.total_seconds():.2f}s")
        
        # Test bulk query
        query_start = datetime.now()
        all_vehicles = db.query(UserVehicle).filter(UserVehicle.user_id == user.id).all()
        query_time = datetime.now() - query_start
        print(f"✅ Queried {len(all_vehicles)} vehicles in {query_time.total_seconds():.3f}s")
        
        # Test filtered query
        filter_start = datetime.now()
        recent_vehicles = db.query(UserVehicle).filter(
            UserVehicle.user_id == user.id,
            UserVehicle.year >= 2022
        ).all()
        filter_time = datetime.now() - filter_start
        print(f"✅ Filtered query returned {len(recent_vehicles)} vehicles in {filter_time.total_seconds():.3f}s")
        
        # Clean up
        for vehicle in all_vehicles:
            db.delete(vehicle)
        db.delete(user)
        db.commit()
        
        total_time = datetime.now() - start_time
        print(f"⚡ Total performance test completed in {total_time.total_seconds():.2f}s")
        
        return True
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def main():
    """Run all database tests"""
    print("🧪 Starting comprehensive database tests...\n")
    
    tests = [
        ("Connection Test", test_connection_detailed),
        ("Table Creation", create_tables),
        ("CRUD Operations", test_crud_operations),
        ("JSON Fields", test_json_fields),
        ("Performance Test", test_performance)
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"🧪 Running: {test_name}")
        print('='*50)
        
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 TEST SUMMARY")
    print('='*50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\n📊 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Database is working perfectly!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    exit(main())