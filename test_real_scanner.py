#!/usr/bin/env python3
"""
Test script to verify real OBD2 scanner connection and DTC detection
This simulates connecting to a real scanner and getting actual DTC codes
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8080"

def test_scanner_connection():
    """Test connecting to a real OBD2 scanner"""
    print("🔌 Testing Scanner Connection...")
    
    # First, check available ports
    try:
        response = requests.get(f"{BASE_URL}/api/scanner/ports")
        if response.status_code == 200:
            ports = response.json()
            print(f"✅ Available ports: {ports}")
            return ports
        else:
            print(f"❌ Failed to get ports: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error getting ports: {e}")
        return []

def test_scanner_connect(port=None):
    """Test connecting to scanner"""
    print(f"\n🔗 Testing Scanner Connection to {port or 'default port'}...")
    
    connect_data = {
        "port": port or "/dev/cu.OBDII",  # Default Bluetooth port
        "baudrate": 38400,
        "fast_mode": False
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/scanner/connect",
            json=connect_data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Connection result: {result}")
            return result.get("connected", False)
        else:
            print(f"❌ Connection failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_real_dtc_scan():
    """Test scanning for real DTC codes"""
    print("\n🔍 Testing Real DTC Code Scanning...")
    
    try:
        # Test the DTC scan endpoint
        response = requests.get(f"{BASE_URL}/api/scanner/dtc/scan")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ DTC Scan Result: {result}")
            
            active_codes = result.get("active_codes", [])
            pending_codes = result.get("pending_codes", [])
            
            print(f"📊 Active codes: {len(active_codes)}")
            print(f"📊 Pending codes: {len(pending_codes)}")
            
            if active_codes:
                print("⚠️  Active DTC Codes Found:")
                for code in active_codes:
                    print(f"   - {code['code']}: {code['description']}")
            else:
                print("✅ No active DTC codes (vehicle is healthy)")
                
            return active_codes, pending_codes
        else:
            print(f"❌ DTC scan failed: {response.status_code}")
            return [], []
            
    except Exception as e:
        print(f"❌ DTC scan error: {e}")
        return [], []

def test_real_health_check():
    """Test real vehicle health check"""
    print("\n🏥 Testing Real Vehicle Health Check...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/scanner/health-check")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Health Check Result: {result}")
            
            # Check each system
            systems = [
                "engine", "transmission", "emissions", "fuel_system",
                "cooling_system", "electrical_system", "brake_system", "exhaust_system"
            ]
            
            print("\n🔧 System Health Status:")
            for system in systems:
                status = result.get(system, "unknown")
                emoji = "✅" if status == "good" else "⚠️" if status == "warning" else "❌" if status == "critical" else "❓"
                print(f"   {emoji} {system.replace('_', ' ').title()}: {status}")
                
            return result
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return {}
            
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return {}

def test_ai_analysis_with_real_data():
    """Test AI analysis with real scanner data"""
    print("\n🤖 Testing AI Analysis with Real Scanner Data...")
    
    # First get current scanner status
    try:
        status_response = requests.get(f"{BASE_URL}/api/scanner/status")
        scanner_status = status_response.json() if status_response.status_code == 200 else {}
        
        # Get live data
        live_response = requests.get(f"{BASE_URL}/api/scanner/live-data")
        live_data = live_response.json() if live_response.status_code == 200 else {}
        
        # Get DTC codes
        dtc_response = requests.get(f"{BASE_URL}/api/scanner/dtc/scan")
        dtc_data = dtc_response.json() if dtc_response.status_code == 200 else {}
        
        # Prepare AI analysis request
        analysis_request = {
            "message": "Analyze my vehicle diagnostics data",
            "vehicle_data": {
                "live_data": live_data,
                "trouble_codes": dtc_data.get("active_codes", []),
                "connection_status": scanner_status.get("connected", False),
                "device_name": scanner_status.get("device_name", "Unknown")
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/chat/analyze-vehicle",
            json=analysis_request
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ AI Analysis Result:")
            print(f"   Status: {result.get('status')}")
            print(f"   Response: {result.get('response')}")
            
            if result.get('metadata'):
                print(f"   Metadata: {result.get('metadata')}")
                
            return result
        else:
            print(f"❌ AI analysis failed: {response.status_code}")
            return {}
            
    except Exception as e:
        print(f"❌ AI analysis error: {e}")
        return {}

def main():
    """Main test function"""
    print("🚀 Testing Real OBD2 Scanner Integration")
    print("=" * 50)
    
    # Test 1: Get available ports
    ports = test_scanner_connection()
    
    # Test 2: Try to connect to scanner
    connected = False
    if ports:
        # Try the first available port
        first_port = ports[0].get("port") if ports else None
        connected = test_scanner_connect(first_port)
    
    # Test 3: Scan for real DTC codes
    active_codes, pending_codes = test_real_dtc_scan()
    
    # Test 4: Get real health check
    health_status = test_real_health_check()
    
    # Test 5: AI analysis with real data
    ai_result = test_ai_analysis_with_real_data()
    
    print("\n📊 Test Summary:")
    print("=" * 50)
    print(f"🔌 Scanner Connected: {'✅ Yes' if connected else '❌ No'}")
    print(f"🔍 Active DTC Codes: {len(active_codes)}")
    print(f"📋 Pending DTC Codes: {len(pending_codes)}")
    print(f"🏥 Health Systems Checked: {len([k for k, v in health_status.items() if v != 'unknown'])}")
    print(f"🤖 AI Analysis: {'✅ Available' if ai_result.get('status') == 'success' else '❌ Unavailable'}")
    
    if active_codes:
        print(f"\n⚠️  Your vehicle has {len(active_codes)} active trouble codes:")
        for code in active_codes:
            print(f"   - {code['code']}: {code['description']}")
        print("\n💡 The backend is correctly detecting real DTC codes!")
    else:
        print("\n✅ No active trouble codes detected")
        if connected:
            print("💡 Either your vehicle is healthy or needs engine to be running")
        else:
            print("❌ Scanner not connected - cannot detect real codes")
    
    print(f"\n🎯 Recommendations:")
    if not connected:
        print("   1. Connect your OBD2 scanner to the vehicle")
        print("   2. Turn on vehicle ignition (engine doesn't need to run)")
        print("   3. Ensure scanner is paired via Bluetooth")
    else:
        print("   1. ✅ Scanner is connected")
        print("   2. Test with engine running for live data")
        print("   3. Your Flutter app can now get real diagnostic data")

if __name__ == "__main__":
    main()