#!/usr/bin/env python3
"""
Test script to verify Flutter app integration with FastAPI backend
This simulates what your Flutter app should do to send/receive OBD2 data
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8080"  # Your Flutter app's expected URL
# BASE_URL = "http://192.168.1.48:8080"  # For network testing

def test_scanner_status():
    """Test scanner status endpoint"""
    print("🔍 Testing Scanner Status...")
    try:
        response = requests.get(f"{BASE_URL}/api/scanner/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Scanner Status: {data}")
            return True
        else:
            print(f"❌ Status check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Status check error: {e}")
        return False

def test_live_data_flow():
    """Test live data send/receive flow"""
    print("\n📡 Testing Live Data Flow...")
    
    # 1. Send live data (simulate Flutter app sending OBD2 data)
    sample_data = {
        "rpm": 2500,
        "speed": 65,
        "engine_temp": 90,
        "fuel_level": 75,
        "throttle_position": 45,
        "vin": "1HGCM82633A123456",  # Sample VIN
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Send data to backend
        response = requests.post(
            f"{BASE_URL}/api/scanner/live-data",
            json=sample_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ Live data sent successfully")
            
            # Wait a moment then retrieve data
            time.sleep(0.5)
            
            # Get data from backend
            response = requests.get(f"{BASE_URL}/api/scanner/live-data")
            if response.status_code == 200:
                received_data = response.json()
                print(f"✅ Live data received: {received_data}")
                return True
            else:
                print(f"❌ Failed to retrieve live data: {response.status_code}")
                return False
        else:
            print(f"❌ Failed to send live data: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Live data test error: {e}")
        return False

def test_dtc_scan():
    """Test DTC scanning"""
    print("\n🔧 Testing DTC Scan...")
    try:
        response = requests.get(f"{BASE_URL}/api/scanner/dtc/scan")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ DTC Scan: {data}")
            return True
        else:
            print(f"❌ DTC scan failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ DTC scan error: {e}")
        return False

def test_health_check():
    """Test vehicle health check"""
    print("\n🏥 Testing Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/api/scanner/health-check")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health Check: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def generate_flutter_code():
    """Generate Flutter integration code"""
    print("\n📱 Flutter Integration Code:")
    print("="*50)
    
    flutter_code = '''
// Add this to your Flutter app's OBD2BluetoothService

import 'dart:convert';
import 'package:http/http.dart' as http;

class Config {
  static const String baseUrl = 'http://192.168.0.104:8080';
}

class OBD2BluetoothService {
  // Your existing Bluetooth parsing code...
  
  // Add this method to send data to backend
  Future<void> sendLiveDataToBackend(Map<String, dynamic> liveData) async {
    try {
      final response = await http.post(
        Uri.parse('${Config.baseUrl}/api/scanner/live-data'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'rpm': liveData['rpm'],
          'speed': liveData['speed'],
          'engine_temp': liveData['engine_temp'],
          'fuel_level': liveData['fuel_level'],
          'throttle_position': liveData['throttle_position'],
          'vin': liveData['vin'],  // Include VIN if available
          'timestamp': DateTime.now().toIso8601String(),
        }),
      );
      
      if (response.statusCode == 200) {
        print('✅ Live data sent to backend');
      } else {
        print('❌ Failed to send data: ${response.statusCode}');
      }
    } catch (e) {
      print('❌ Backend relay error: $e');
    }
  }
  
  // Add this method to get shared data from backend
  Future<Map<String, dynamic>?> getLiveDataFromBackend() async {
    try {
      final response = await http.get(
        Uri.parse('${Config.baseUrl}/api/scanner/live-data'),
      );
      
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        print('❌ Failed to get data: ${response.statusCode}');
        return null;
      }
    } catch (e) {
      print('❌ Backend get error: $e');
      return null;
    }
  }
  
  // Modify your existing _parseOBD2Response method
  void _parseOBD2Response(String response) {
    // Your existing parsing logic...
    Map<String, dynamic> parsedData = {
      'rpm': extractRPM(response),
      'speed': extractSpeed(response),
      'engine_temp': extractEngineTemp(response),
      'fuel_level': extractFuelLevel(response),
      'throttle_position': extractThrottlePosition(response),
      'vin': extractVIN(response),  // Include VIN extraction
    };
    
    // Send to backend after parsing
    sendLiveDataToBackend(parsedData);
  }
}

// In your DiagnosticsTabWidget, use this to get data:
class DiagnosticsTabWidget extends StatefulWidget {
  @override
  _DiagnosticsTabWidgetState createState() => _DiagnosticsTabWidgetState();
}

class _DiagnosticsTabWidgetState extends State<DiagnosticsTabWidget> {
  Map<String, dynamic>? liveData;
  
  @override
  void initState() {
    super.initState();
    // Poll for live data every 2 seconds
    Timer.periodic(Duration(seconds: 2), (timer) {
      _updateLiveData();
    });
  }
  
  Future<void> _updateLiveData() async {
    final data = await OBD2BluetoothService().getLiveDataFromBackend();
    if (data != null) {
      setState(() {
        liveData = data;
      });
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text('RPM: ${liveData?['rpm'] ?? 'N/A'}'),
        Text('Speed: ${liveData?['speed'] ?? 'N/A'}'),
        Text('Engine Temp: ${liveData?['engine_temp'] ?? 'N/A'}'),
        Text('Fuel Level: ${liveData?['fuel_level'] ?? 'N/A'}'),
        Text('Throttle: ${liveData?['throttle_position'] ?? 'N/A'}'),
        Text('VIN: ${liveData?['vin'] ?? 'N/A'}'),
      ],
    );
  }
}
'''
    print(flutter_code)

def main():
    """Main test function"""
    print("🚀 Testing Flutter-FastAPI Integration")
    print("="*50)
    
    # Test all endpoints
    tests = [
        test_scanner_status,
        test_live_data_flow,
        test_dtc_scan,
        test_health_check
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n📊 Test Results:")
    print("="*50)
    passed = sum(results)
    total = len(results)
    print(f"✅ Passed: {passed}/{total} tests")
    
    if passed == total:
        print("🎉 All tests passed! Your backend is ready for Flutter integration.")
        generate_flutter_code()
    else:
        print("❌ Some tests failed. Check your backend configuration.")

if __name__ == "__main__":
    main()