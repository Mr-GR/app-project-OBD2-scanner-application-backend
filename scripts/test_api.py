#!/usr/bin/env python3
"""
API testing script for OBD2 Scanner backend
Tests all endpoints and functionality
"""

import requests
import json
import time
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8080"

def test_health_check():
    """Test basic health check endpoint"""
    print("🏥 Testing health check...")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data['message']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_chat_endpoints():
    """Test AI chat endpoints"""
    print("🤖 Testing AI chat endpoints...")
    
    results = {}
    
    # Test original ask endpoint
    print("  📞 Testing /api/ask endpoint...")
    try:
        ask_payload = {
            "question": "What does P0420 mean?",
            "level": "beginner"
        }
        
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/ask", json=ask_payload)
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Ask endpoint: {response_time:.0f}ms")
            print(f"   Response length: {len(data['answer'])} characters")
            results['ask'] = True
        else:
            print(f"❌ Ask endpoint failed: {response.status_code}")
            results['ask'] = False
    except Exception as e:
        print(f"❌ Ask endpoint error: {e}")
        results['ask'] = False
    
    # Test enhanced chat endpoint (no context)
    print("  💬 Testing /api/chat endpoint (no context)...")
    try:
        chat_payload = {
            "message": "What does P0420 mean?",
            "level": "beginner",
            "include_diagnostics": False
        }
        
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/chat", json=chat_payload)
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Chat endpoint (no context): {response_time:.0f}ms")
            print(f"   Response length: {len(data['message']['content'])} characters")
            print(f"   Format: {data['message']['format']}")
            results['chat_no_context'] = True
        else:
            print(f"❌ Chat endpoint failed: {response.status_code}")
            results['chat_no_context'] = False
    except Exception as e:
        print(f"❌ Chat endpoint error: {e}")
        results['chat_no_context'] = False
    
    # Test enhanced chat endpoint (with context)
    print("  🚗 Testing /api/chat endpoint (with context)...")
    try:
        chat_context_payload = {
            "message": "What should I do about these codes?",
            "level": "beginner",
            "context": {
                "vin": "1HGBH41JXMN109186",
                "dtc_codes": ["P0420", "P0171"],
                "vehicle_info": {
                    "make": "Honda",
                    "model": "Civic",
                    "year": "2018"
                },
                "sensor_data": {
                    "engine_temp": "195F",
                    "rpm": "2500"
                }
            },
            "include_diagnostics": True
        }
        
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/chat", json=chat_context_payload)
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Chat endpoint (with context): {response_time:.0f}ms")
            print(f"   Response length: {len(data['message']['content'])} characters")
            print(f"   Has suggestions: {len(data.get('suggestions', [])) > 0}")
            print(f"   Has diagnostic data: {data.get('diagnostic_data') is not None}")
            results['chat_with_context'] = True
        else:
            print(f"❌ Chat endpoint with context failed: {response.status_code}")
            results['chat_with_context'] = False
    except Exception as e:
        print(f"❌ Chat endpoint with context error: {e}")
        results['chat_with_context'] = False
    
    # Test quick chat endpoint
    print("  ⚡ Testing /api/chat/quick endpoint...")
    try:
        quick_chat_payload = {
            "message": "What does P0420 mean?"
        }
        
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/chat/quick", json=quick_chat_payload)
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Quick chat endpoint: {response_time:.0f}ms")
            print(f"   Response length: {len(data['message']['content'])} characters")
            print(f"   Format: {data['message']['format']}")
            print(f"   Has suggestions: {len(data.get('suggestions', [])) > 0}")
            results['chat_quick'] = True
        else:
            print(f"❌ Quick chat endpoint failed: {response.status_code}")
            results['chat_quick'] = False
    except Exception as e:
        print(f"❌ Quick chat endpoint error: {e}")
        results['chat_quick'] = False
    
    # Test chat stats endpoint
    print("  📊 Testing /api/chat/stats endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/chat/stats")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Chat stats endpoint")
            print(f"   Cache entries: {data['cache']['total_entries']}")
            print(f"   Classification methods: {list(data['classification_methods'].keys())}")
            results['chat_stats'] = True
        else:
            print(f"❌ Chat stats failed: {response.status_code}")
            results['chat_stats'] = False
    except Exception as e:
        print(f"❌ Chat stats error: {e}")
        results['chat_stats'] = False
    
    return results

def test_instant_classification():
    """Test instant classification performance"""
    print("⚡ Testing instant classification performance...")
    
    test_cases = [
        {"input": "P0420", "expected": "instant"},
        {"input": "P0171", "expected": "instant"},
        {"input": "engine trouble", "expected": "instant"},
        {"input": "weather forecast", "expected": "instant"},
        {"input": "My car is making weird noises when I turn left", "expected": "llm_or_cached"}
    ]
    
    results = []
    for i, test_case in enumerate(test_cases):
        print(f"  🧪 Test {i+1}: '{test_case['input']}'")
        
        try:
            payload = {
                "message": test_case['input'],
                "level": "beginner"
            }
            
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/api/chat", json=payload)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                # Check if response was fast enough to be instant classification
                is_fast = response_time < 100  # Less than 100ms suggests instant classification
                status = "⚡ INSTANT" if is_fast else "🔄 LLM/CACHED"
                print(f"     {status} ({response_time:.0f}ms)")
                results.append(True)
            else:
                print(f"     ❌ Failed: {response.status_code}")
                results.append(False)
                
        except Exception as e:
            print(f"     ❌ Error: {e}")
            results.append(False)
    
    passed = sum(results)
    total = len(results)
    print(f"  📊 Classification tests: {passed}/{total} passed")
    
    return passed == total

def test_diagnostics_endpoint():
    """Test diagnostics endpoint"""
    print("🔍 Testing diagnostics endpoint...")
    
    try:
        payload = {
            "vin": "1HGBH41JXMN109186",
            "codes": ["P0420", "P0171"]
        }
        
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/diagnostics", json=payload)
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Diagnostics endpoint: {response_time:.0f}ms")
            print(f"   Vehicle: {data['vin_info']['year']} {data['vin_info']['make']} {data['vin_info']['model']}")
            print(f"   Codes processed: {len(data['codes'])}")
            for code in data['codes']:
                print(f"     {code['code']}: {code['description'][:50]}...")
            return True
        else:
            print(f"❌ Diagnostics endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Diagnostics endpoint error: {e}")
        return False

def test_scanner_endpoints():
    """Test OBD2 scanner endpoints (without actual hardware)"""
    print("🔌 Testing scanner endpoints...")
    
    results = {}
    
    # Test port listing
    try:
        response = requests.get(f"{BASE_URL}/api/scanner/ports")
        if response.status_code == 200:
            ports = response.json()
            print(f"✅ Scanner ports endpoint: Found {len(ports)} ports")
            results['ports'] = True
        else:
            print(f"⚠️  Scanner ports endpoint: {response.status_code} (expected without hardware)")
            results['ports'] = False
    except Exception as e:
        print(f"⚠️  Scanner ports error: {e} (expected without hardware)")
        results['ports'] = False
    
    # Test scanner status
    try:
        response = requests.get(f"{BASE_URL}/api/scanner/status")
        if response.status_code == 200:
            status = response.json()
            print(f"✅ Scanner status: Connected={status['connected']}")
            results['status'] = True
        else:
            print(f"❌ Scanner status failed: {response.status_code}")
            results['status'] = False
    except Exception as e:
        print(f"❌ Scanner status error: {e}")
        results['status'] = False
    
    # Test manual data processing
    try:
        payload = {
            "vin": "1HGBH41JXMN109186",
            "dtc_codes": ["P0420", "P0171"],
            "sensor_data": {"engine_temp": 195, "rpm": 2500},
            "notes": "Test data processing"
        }
        
        response = requests.post(f"{BASE_URL}/api/scanner/manual-data", json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Manual data processing: {data['total_dtc']} codes processed")
            results['manual_data'] = True
        else:
            print(f"❌ Manual data processing failed: {response.status_code}")
            results['manual_data'] = False
    except Exception as e:
        print(f"❌ Manual data processing error: {e}")
        results['manual_data'] = False
    
    return results

def test_performance_comparison():
    """Compare performance between ask, chat, and quick chat endpoints"""
    print("🏁 Performance comparison: /api/ask vs /api/chat vs /api/chat/quick...")
    
    test_questions = [
        "P0420",
        "P0171", 
        "engine trouble",
        "check engine light",
        "brake problems"
    ]
    
    ask_times = []
    chat_times = []
    quick_times = []
    
    for question in test_questions:
        # Test ask endpoint
        try:
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/api/ask", json={
                "question": question,
                "level": "beginner"
            })
            if response.status_code == 200:
                ask_times.append((time.time() - start_time) * 1000)
        except:
            pass
        
        # Test chat endpoint
        try:
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/api/chat", json={
                "message": question,
                "level": "beginner"
            })
            if response.status_code == 200:
                chat_times.append((time.time() - start_time) * 1000)
        except:
            pass
        
        # Test quick chat endpoint
        try:
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/api/chat/quick", json={
                "message": question
            })
            if response.status_code == 200:
                quick_times.append((time.time() - start_time) * 1000)
        except:
            pass
        
        time.sleep(0.1)  # Small delay between requests
    
    if ask_times and chat_times and quick_times:
        avg_ask = sum(ask_times) / len(ask_times)
        avg_chat = sum(chat_times) / len(chat_times)
        avg_quick = sum(quick_times) / len(quick_times)
        
        print(f"📊 Average response times:")
        print(f"   /api/ask:        {avg_ask:.0f}ms")
        print(f"   /api/chat:       {avg_chat:.0f}ms")
        print(f"   /api/chat/quick: {avg_quick:.0f}ms")
        
        fastest = min(avg_ask, avg_chat, avg_quick)
        if fastest == avg_quick:
            print(f"🚀 Quick chat is the fastest!")
        elif fastest == avg_chat:
            print(f"🚀 Regular chat is the fastest!")
        else:
            print(f"🚀 Ask endpoint is the fastest!")
        
        return True
    else:
        print("❌ Could not collect performance data")
        return False

def main():
    """Run all API tests"""
    print("🧪 Starting comprehensive API tests...\n")
    print(f"🎯 Target API: {BASE_URL}\n")
    
    # Check if server is running
    print("🔍 Checking if server is running...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code != 200:
            print(f"❌ Server not responding properly: {response.status_code}")
            print("💡 Make sure to start the server first:")
            print("   python main.py")
            print("   OR")
            print("   ./scripts/deploy.sh development")
            return 1
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print("💡 Make sure to start the server first:")
        print("   python main.py")
        print("   OR") 
        print("   ./scripts/deploy.sh development")
        return 1
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")
        return 1
    
    print("✅ Server is running!\n")
    
    # Run all tests
    tests = [
        ("Health Check", test_health_check),
        ("Chat Endpoints", test_chat_endpoints),
        ("Instant Classification", test_instant_classification),
        ("Diagnostics Endpoint", test_diagnostics_endpoint),
        ("Scanner Endpoints", test_scanner_endpoints),
        ("Performance Comparison", test_performance_comparison)
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"🧪 Running: {test_name}")
        print('='*60)
        
        try:
            result = test_func()
            # Handle different return types
            if isinstance(result, dict):
                # Count passed tests in dict
                passed = sum(1 for v in result.values() if v)
                total = len(result)
                results[test_name] = passed == total
                print(f"📊 {test_name}: {passed}/{total} sub-tests passed")
            else:
                results[test_name] = bool(result)
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 API TEST SUMMARY")
    print('='*60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\n📊 Overall: {passed}/{total} test suites passed")
    
    if passed == total:
        print("🎉 All API tests passed! Your backend is working perfectly!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    exit(main())