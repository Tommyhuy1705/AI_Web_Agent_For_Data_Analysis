# Audio Creation Error Fix - Troubleshooting Guide

## What Was Fixed

The audio creation error "Không thể tạo audio. ElevenLabs API có thể bị lỗi hoặc API key không hợp lệ" was being raised too generically without clear indication of the actual problem. The fix implements:

### 1. **API Key Validation**
- Checks if `ELEVENLABS_API_KEY` is set in environment variables
- Validates key format (minimum length check)
- Returns specific error message if key is missing or invalid

### 2. **Enhanced Error Detection**
The system now distinguishes between different failure types:

| Error Type | Error Message | Solution |
|-----------|---------------|----------|
| Missing API Key | "ELEVENLABS_API_KEY is not set" | Add key to `.env` |
| Invalid API Key | "ELEVENLABS_API_KEY appears to be invalid (too short)" | Check key format |
| Authentication Failed | "ElevenLabs authentication failed: Invalid or expired API key" | Regenerate key |
| Rate Limited | "ElevenLabs rate limit exceeded. Please try again later" | Wait and retry |
| Invalid Voice ID | "Invalid voice ID 'xxx'" | Verify voice ID exists |
| Package Not Installed | "elevenlabs package not installed. Run: pip install elevenlabs" | Install package |
| Network Error | "Connection error with ElevenLabs API" | Check internet connection |
| Empty Response | "ElevenLabs returned empty audio stream" | Try again later |

### 3. **Improved Code Changes**

#### Backend Service (`backend/services/audio_service.py`)
- Added `_validate_api_key()` function that returns both validity status and error message
- Modified `text_to_speech_bytes()` to return tuple: `(audio_bytes, error_message)`
- Added specific error type detection for authentication, rate limits, invalid voices, connections
- Better import error handling with installation instructions
- Functions now return detailed error context for debugging

#### Backend Router (`backend/api/routes/audio_router.py`)
- Updated `/api/audio/briefing` endpoint to capture and propagate error details
- Enhanced `/api/audio/status` endpoint to show configuration validation results
- Updated `/api/audio/voices` endpoint with error handling
- Improved HTTP error responses with specific error details instead of generic messages

### 4. **Detailed Error Messages**
When errors occur, the API now returns specific information:
```json
{
  "detail": "Không thể tạo audio. ElevenLabs authentication failed: Invalid or expired API key (Detail: 401 Invalid API key)"
}
```

Instead of just:
```json
{
  "detail": "Không thể tạo audio. ElevenLabs API có thể bị lỗi hoặc API key không hợp lệ. Kiểm tra logs backend để biết chi tiết."
}
```

## How to Troubleshoot Audio Issues

### Step 1: Check Configuration Status
```bash
curl http://localhost:8000/api/audio/status
```

**Expected response:**
```json
{
  "configured": true,
  "service": "ElevenLabs TTS",
  "purpose": "Convert AI insights to MP3 audio briefings",
  "status": "ready",
  "error": null
}
```

**Error response:**
```json
{
  "configured": false,
  "status": "error",
  "error": "ELEVENLABS_API_KEY is not set in environment variables"
}
```

### Step 2: Verify API Key in .env
```bash
cat .env | grep ELEVENLABS_API_KEY
```

Should output something like:
```
ELEVENLABS_API_KEY=sk_1234567890abcdef1234567890
```

If missing:
1. Go to https://elevenlabs.io/
2. Sign up or log in
3. Generate API key from account settings
4. Add to `.env`: `ELEVENLABS_API_KEY=your_key_here`

### Step 3: Verify elevenlabs Package
```bash
python -m pip list | grep elevenlabs
```

If not installed:
```bash
pip install elevenlabs
```

### Step 4: Check Backend Logs
When creating audio fails, check backend logs for specific error:
```bash
# Linux/Mac
tail -f logs/backend.log

# Windows (in backend terminal)
Get-Content logs/backend.log -Tail 20 -Wait
```

Look for lines like:
```
ERROR - ElevenLabs authentication failed: Invalid or expired API key
ERROR - ElevenLabs returned empty audio stream
ERROR - Connection error with ElevenLabs API
```

### Step 5: Test API Directly
```bash
curl -X POST http://localhost:8000/api/audio/briefing \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is test text for audio generation",
    "stream": false,
    "summarize": false
  }'
```

This will return MP3 file if successful, or error message if it fails.

## Common Issues & Solutions

### Issue: "API key not set"
**Cause:** `ELEVENLABS_API_KEY` not in `.env`
**Solution:**
1. Open `.env` in project root
2. Add: `ELEVENLABS_API_KEY=sk_your_key_here`
3. Restart backend: `python backend/main.py`

### Issue: "Invalid or expired API key"
**Cause:** API key is wrong or expired
**Solution:**
1. Log into https://elevenlabs.io/
2. Go to account settings → API Keys
3. Regenerate API key or create new one
4. Update `.env` with new key
5. Restart backend

### Issue: "Rate limit exceeded"
**Cause:** Too many API calls in short time
**Solution:** Wait a few minutes before retrying

### Issue: "elevenlabs not installed"
**Cause:** Package not in virtual environment
**Solution:**
```bash
# Activate venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install
pip install elevenlabs

# Restart backend
python backend/main.py
```

### Issue: "Connection error"
**Cause:** Network issue or ElevenLabs API down
**Solution:**
1. Check internet connection
2. Check if ElevenLabs API is up (https://status.elevenlabs.io/)
3. Try again in a few moments

## Testing the Fix

Run the test suite to verify all error handling works:
```bash
.venv\Scripts\python test_audio_fix.py
```

This tests:
- API key validation with missing/invalid keys
- Error message clarity
- Edge cases in audio processing
- Voice list retrieval errors

## Architecture Changes

### Before
```
text_to_speech_bytes() → Optional[bytes]
└─ Exception occurs → None (silent failure)
└─ Router can't tell why it failed
└─ Generic error returned to frontend
```

### After
```
text_to_speech_bytes() → Tuple[Optional[bytes], Optional[str]]
├─ Success → (audio_bytes, None)
├─ API Key Missing → (None, "ELEVENLABS_API_KEY is not set...")
├─ Auth Failed → (None, "ElevenLabs authentication failed...")
├─ Rate Limited → (None, "ElevenLabs rate limit exceeded...")
└─ Router captures error details
   └─ Frontend receives specific error message
      └─ User can troubleshoot effectively
```

## Backend Logging

All audio operations are now logged with detailed information:

```
INFO - Audio briefing request: 234 chars, stream=False, summarize=True
DEBUG - API validation passed
INFO - ElevenLabs TTS completed: 234 chars → 45678 bytes
```

or

```
ERROR - ElevenLabs configuration error: ELEVENLABS_API_KEY is not set
ERROR - ElevenLabs TTS error: Invalid voice ID 'xxx'
ERROR - ElevenLabs TTS error (type=APIError): 401 Unauthorized
```

## Environment Configuration

Required for production:
```bash
# Required for audio feature
ELEVENLABS_API_KEY=sk_1234567890abcdef1234567890
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Default: Rachel
ELEVENLABS_MODEL_ID=eleven_multilingual_v2  # Default model
```

Optional (will use defaults if not set):
- `ELEVENLABS_VOICE_ID` - uses Rachel (multilingual) by default
- `ELEVENLABS_MODEL_ID` - uses eleven_multilingual_v2 by default

## Next Steps

1. **Verify your .env** has `ELEVENLABS_API_KEY` set correctly
2. **Restart your backend**: `python backend/main.py`
3. **Test audio creation** via the UI (Request → Response button)
4. **Check logs** if any errors occur
5. **Use `/api/audio/status`** endpoint to verify configuration

## Support

If issues persist:
1. Run: `.venv\Scripts\python test_audio_fix.py` to verify fixes are loaded
2. Check backend logs for specific error details
3. Verify API key at https://elevenlabs.io/
4. Check API status at https://status.elevenlabs.io/
