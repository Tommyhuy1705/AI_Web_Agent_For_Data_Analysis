#!/usr/bin/env python3
"""
Quick Audio Diagnostic Tool
Run this to identify audio configuration and API issues
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def check_environment():
    """Check environment variables and configuration."""
    print("📋 ENVIRONMENT CHECK")
    print("=" * 60)
    
    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    
    print(f"🔑 API Key: {('Set (' + str(len(api_key)) + ' chars)') if api_key else '❌ NOT SET'}")
    print(f"🎙️  Voice ID: {voice_id}")
    print(f"🤖 Model ID: {model_id}")
    
    # Check .env file
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        try:
            with open(env_file, encoding='utf-8', errors='ignore') as f:
                content = f.read()
                has_key = "ELEVENLABS_API_KEY" in content
                print(f"📄 .env file: {'✅ Found' if has_key else '⚠️  ELEVENLABS_API_KEY not in .env'}")
        except Exception as e:
            print(f"📄 .env file: ⚠️  Could not read ({e})")
    else:
        print(f"📄 .env file: ❌ NOT FOUND")
    
    return api_key

def check_dependencies():
    """Check if required packages are installed."""
    print("\n📦 DEPENDENCIES CHECK")
    print("=" * 60)
    
    packages = {
        "elevenlabs": "Audio generation API client",
        "fastapi": "Web framework",
        "httpx": "HTTP client",
        "pydantic": "Data validation"
    }
    
    import importlib
    all_installed = True
    
    for package, description in packages.items():
        try:
            mod = importlib.import_module(package)
            version = getattr(mod, "__version__", "unknown")
            print(f"✅ {package:20} v{version:15} - {description}")
        except ImportError:
            print(f"❌ {package:20} {'NOT INSTALLED':15} - {description}")
            all_installed = False
    
    return all_installed

def check_api_configuration():
    """Check ElevenLabs API configuration."""
    print("\n🔐 API CONFIGURATION CHECK")
    print("=" * 60)
    
    try:
        from backend.services.audio_service import _validate_api_key, is_configured
        
        is_config = is_configured()
        is_valid, error_msg = _validate_api_key()
        
        print(f"Configured: {'✅ YES' if is_config else '❌ NO'}")
        print(f"Valid Key: {'✅ YES' if is_valid else '❌ NO'}")
        
        if error_msg:
            print(f"Error: {error_msg}")
        
        return is_valid
    except Exception as e:
        print(f"❌ Could not check configuration: {e}")
        return False

def check_service_status():
    """Check if audio service can be imported."""
    print("\n🎵 SERVICE STATUS CHECK")
    print("=" * 60)
    
    try:
        from backend.services import audio_service
        print("✅ Audio service module imported successfully")
        
        # Check key functions
        functions = [
            "is_configured",
            "text_to_speech_bytes",
            "text_to_speech_stream",
            "get_available_voices",
            "_validate_api_key"
        ]
        
        for func_name in functions:
            if hasattr(audio_service, func_name):
                print(f"✅ Function '{func_name}' available")
            else:
                print(f"❌ Function '{func_name}' NOT available")
        
        return True
    except Exception as e:
        print(f"❌ Error importing audio service: {e}")
        return False

def check_fastapi_route():
    """Check if audio router is properly configured."""
    print("\n🛣️  FASTAPI ROUTE CHECK")
    print("=" * 60)
    
    try:
        from backend.api.routes.audio_router import router
        
        routes = [route.path for route in router.routes]
        endpoints = ["/status", "/briefing", "/voices"]
        
        print(f"✅ Audio router imported successfully")
        print(f"📍 Routes available:")
        
        for endpoint in endpoints:
            full_path = f"/api/audio{endpoint}"
            if any(endpoint in route for route in routes):
                print(f"   ✅ {full_path}")
            else:
                print(f"   ❌ {full_path} NOT FOUND")
        
        return True
    except Exception as e:
        print(f"❌ Error importing audio router: {e}")
        return False

def print_recommendations(api_key, deps_ok, config_valid, service_ok, route_ok):
    """Print recommendations based on checks."""
    print("\n" + "=" * 60)
    print("📝 RECOMMENDATIONS")
    print("=" * 60)
    
    issues = []
    
    if not api_key:
        issues.append("1. Add ELEVENLABS_API_KEY to .env file")
    elif not config_valid:
        issues.append("2. Update ELEVENLABS_API_KEY with valid key from https://elevenlabs.io/")
    
    if not deps_ok:
        issues.append("3. Install missing packages: pip install -r backend/requirements.txt")
    
    if not service_ok:
        issues.append("4. Check Python path and module imports")
    
    if not route_ok:
        issues.append("5. Verify audio router configuration in FastAPI app")
    
    if not issues:
        print("✅ All checks passed! Audio service is ready.")
        print("\nNext steps:")
        print("1. Start the backend: python backend/main.py")
        print("2. Test audio: curl -X GET http://localhost:8000/api/audio/status")
        print("3. Create audio: POST to /api/audio/briefing with text")
    else:
        print("Issues found:\n")
        for issue in issues:
            print(f"  {issue}")

def run_diagnostic():
    """Run complete diagnostic check."""
    print("\n" + "=" * 60)
    print("🔧 AUDIO SERVICE DIAGNOSTIC TOOL")
    print("=" * 60 + "\n")
    
    # Run all checks
    api_key = check_environment()
    deps_ok = check_dependencies()
    config_valid = check_api_configuration()
    service_ok = check_service_status()
    route_ok = check_fastapi_route()
    
    # Print recommendations
    print_recommendations(api_key, deps_ok, config_valid, service_ok, route_ok)
    
    print("\n" + "=" * 60)
    print("Diagnostic complete!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        run_diagnostic()
    except Exception as e:
        print(f"\n❌ Diagnostic failed: {e}")
        sys.exit(1)
