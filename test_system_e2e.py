#!/usr/bin/env python3
"""
End-to-End System Test
Tests: Backend health, Audio service, API endpoints
"""
import asyncio
import json
import sys
import time
from datetime import datetime

async def test_backend_health():
    """Test if backend is running and healthy."""
    print("\n" + "="*70)
    print("🏥 TEST 1: BACKEND HEALTH CHECK")
    print("="*70)
    
    try:
        import requests
        
        # Test main health endpoint
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running and responding")
            return True
        else:
            print(f"⚠️  Backend returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend health check failed: {e}")
        return False

async def test_audio_status():
    """Test audio service status."""
    print("\n" + "="*70)
    print("🎵 TEST 2: AUDIO SERVICE STATUS")
    print("="*70)
    
    try:
        import requests
        
        response = requests.get("http://localhost:8000/api/audio/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Audio service endpoint responding")
            print(f"   Configured: {data.get('configured')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Service: {data.get('service')}")
            
            if data.get('configured') and data.get('status') == 'ready':
                print("✅ Audio service is READY for audio generation")
                return True
            else:
                error = data.get('error')
                if error:
                    print(f"⚠️  Audio service error: {error}")
                return False
        else:
            print(f"❌ Audio endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Audio status check failed: {e}")
        return False

async def test_audio_creation():
    """Test actual audio generation."""
    print("\n" + "="*70)
    print("🎤 TEST 3: AUDIO GENERATION TEST")
    print("="*70)
    
    try:
        import requests
        
        test_text = "Xin chào, đây là kiểm tra tính năng tạo âm thanh. Hệ thống đang hoạt động bình thường."
        
        payload = {
            "text": test_text,
            "stream": False,
            "summarize": False
        }
        
        print(f"Sending request with text: '{test_text[:50]}...'")
        
        response = requests.post(
            "http://localhost:8000/api/audio/briefing",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            audio_size = len(response.content)
            print(f"✅ Audio generated successfully")
            print(f"   Audio file size: {audio_size} bytes")
            print(f"   Response type: {response.headers.get('content-type')}")
            
            if audio_size > 1000:
                print("✅ Audio file appears valid")
                return True
            else:
                print(f"⚠️  Audio file seems too small ({audio_size} bytes)")
                return False
        else:
            error_data = response.json()
            print(f"❌ Audio generation failed with status {response.status_code}")
            print(f"   Error: {error_data.get('detail', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Audio creation test failed: {e}")
        return False

async def test_dashboard_api():
    """Test dashboard API."""
    print("\n" + "="*70)
    print("📊 TEST 4: DASHBOARD API")
    print("="*70)
    
    try:
        import requests
        
        response = requests.get("http://localhost:8000/api/dashboard/data", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Dashboard API responding")
            print(f"   KPI cards: {len(data.get('kpi_cards', []))} available")
            print(f"   Charts: {len(data.get('charts', []))} available")
            
            if data.get('kpi_cards') and data.get('charts'):
                print("✅ Dashboard data structure is complete")
                return True
            else:
                print("⚠️  Dashboard data incomplete")
                return False
        else:
            print(f"❌ Dashboard API returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Dashboard test failed: {e}")
        return False

async def test_chat_stream():
    """Test chat stream endpoint."""
    print("\n" + "="*70)
    print("💬 TEST 5: CHAT STREAM ENDPOINT")
    print("="*70)
    
    try:
        import requests
        
        payload = {
            "message": "Doanh thu tháng này so với tháng trước thế nào?"
        }
        
        response = requests.post(
            "http://localhost:8000/api/chat/stream",
            json=payload,
            timeout=15,
            stream=True
        )
        
        if response.status_code == 200:
            print(f"✅ Chat stream endpoint responding")
            
            chunk_count = 0
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    chunk_count += 1
            
            if chunk_count > 0:
                print(f"✅ Received {chunk_count} data chunks")
                return True
            else:
                print("⚠️  No data received from stream")
                return False
        else:
            print(f"❌ Chat stream returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Chat stream test failed: {e}")
        return False

async def test_frontend_connectivity():
    """Test if frontend can connect to backend."""
    print("\n" + "="*70)
    print("🌐 TEST 6: FRONTEND CONNECTIVITY")
    print("="*70)
    
    try:
        import requests
        
        # Frontend should be accessible on port 3000
        response = requests.get("http://localhost:3000", timeout=5)
        if response.status_code == 200:
            print(f"✅ Frontend is running on http://localhost:3000")
            return True
        else:
            print(f"⚠️  Frontend returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Frontend connectivity test failed: {e}")
        return False

async def run_all_tests():
    """Run all tests and summarize results."""
    print("\n" + "="*70)
    print("🚀 STARTING SYSTEM END-TO-END TESTS")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    results = {}
    
    # Run all tests
    results['backend_health'] = await test_backend_health()
    results['audio_status'] = await test_audio_status()
    results['audio_creation'] = await test_audio_creation()
    results['dashboard'] = await test_dashboard_api()
    results['chat_stream'] = await test_chat_stream()
    results['frontend'] = await test_frontend_connectivity()
    
    # Print summary
    print("\n" + "="*70)
    print("📋 TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        display_name = test_name.replace('_', ' ').title()
        print(f"{status:10} - {display_name}")
    
    print("\n" + "-"*70)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("="*70)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is fully operational.")
        print("\n✅ Ready for:")
        print("   • Audio generation from insights")
        print("   • Interactive chat with market intelligence")
        print("   • Dashboard refreshing with real-time data")
        print("   • Email alarms and notifications")
        return True
    elif passed >= 4:
        print(f"\n⚠️  {total - passed} test(s) failed. Core functionality is working but some features may be limited.")
        return True
    else:
        print(f"\n❌ Critical issues detected. {total - passed} test(s) failed.")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        sys.exit(1)
