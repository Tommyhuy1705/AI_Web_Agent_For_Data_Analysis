# Audio Error - Quick Reference Card

## 🚨 Quick Fix Checklist

When you get an audio error, follow this checklist in order:

### Step 1: Check Status
```powershell
curl http://localhost:8000/api/audio/status
```
This will tell you the exact problem.

### Step 2: Run Diagnostic
```powershell
.venv\Scripts\python diagnose_audio.py
```
Shows configuration issues and what to fix.

### Step 3: Fix Issues Based on Error

| Error Message | What to Do | Command |
|---------------|-----------|---------|
| "API key not set" | Add ELEVENLABS_API_KEY to .env | See below |
| "API key invalid" | Check key format, regenerate at elevenlabs.io | Regenerate & update .env |
| "elevenlabs not installed" | Install package | `pip install elevenlabs` |
| "Authentication failed" | Wrong/expired key | Go to elevenlabs.io → regenerate key |
| "Rate limit exceeded" | Wait a few minutes | Retry in 5-10 minutes |
| "Connection error" | Check internet or ElevenLabs status | https://status.elevenlabs.io/ |

### Step 4: Verify Fix
```powershell
.venv\Scripts\python test_audio_fix.py
```
Confirms fixes are working.

## 🔑 Add API Key to .env

1. Open `.env` file in project root
2. Find or add this line:
   ```
   ELEVENLABS_API_KEY=sk_your_key_here
   ```
3. Get actual key from: https://elevenlabs.io/ → Account Settings → API Keys
4. Restart backend:
   ```powershell
   python backend/main.py
   ```

## 📊 Error Messages Explained

### Missing Configuration
```json
{"error": "ELEVENLABS_API_KEY is not set in environment variables"}
```
**Fix:** Add API key to `.env` file

### Invalid Key Format
```json
{"error": "ELEVENLABS_API_KEY appears to be invalid (too short: 5 chars)"}
```
**Fix:** Verify API key format is correct (typically starts with `sk_`)

### Authentication Failed
```json
{"error": "ElevenLabs authentication failed: Invalid or expired API key"}
```
**Fix:** Regenerate API key from https://elevenlabs.io/

### Package Not Installed
```json
{"error": "elevenlabs package not installed. Run: pip install elevenlabs"}
```
**Fix:** Run `pip install elevenlabs`

### Rate Limiting
```json
{"error": "ElevenLabs rate limit exceeded. Please try again later"}
```
**Fix:** Wait 5-10 minutes before trying again

### Connection Issues
```json
{"error": "Connection error with ElevenLabs API"}
```
**Fix:** Check internet connection, verify ElevenLabs status

## 🧪 Test Audio Creation

### Test 1: Check service status
```bash
curl http://localhost:8000/api/audio/status
```
Expected: `"configured": true, "status": "ready"`

### Test 2: Create audio
```bash
curl -X POST http://localhost:8000/api/audio/briefing `
  -H "Content-Type: application/json" `
  -d '{"text": "Hello world test", "stream": false}'
```
Expected: MP3 file or clear error message

### Test 3: Get available voices
```bash
curl http://localhost:8000/api/audio/voices
```
Expected: List of voice IDs with names

## 🛠️ Install Missing Package

```powershell
# Activate virtual environment
.venv\Scripts\activate

# Install elevenlabs
pip install elevenlabs

# Optional: verify installation
python -m pip list | grep elevenlabs

# Restart backend
python backend/main.py
```

## 📋 .env Configuration Template

```bash
# Audio (ElevenLabs)
ELEVENLABS_API_KEY=sk_your_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
```

## 🔍 Debugging Commands

### View backend logs (Windows PowerShell)
```powershell
Get-Content logs/backend.log -Tail 20 -Wait
```

### View specific audio errors
```powershell
Get-Content logs/backend.log | Select-String "ElevenLabs" | Tail -10
```

### Check if package is installed
```powershell
python -c "import elevenlabs; print(elevenlabs.__version__)"
```

### Check environment variables
```powershell
echo $env:ELEVENLABS_API_KEY
```

## ❓ Common Questions

**Q: Where do I get the API key?**
A: https://elevenlabs.io/ → Sign up/Login → Account Settings → API Keys

**Q: Is there a free tier?**
A: Yes, ElevenLabs offers free credits. Check https://elevenlabs.io/pricing

**Q: Why do I need to restart after updating .env?**
A: The backend loads environment variables on startup. Restart to reload them.

**Q: What if I still get errors?**
A: Run `diagnose_audio.py` - it will tell you exactly what's wrong.

**Q: How do I check if my API key is valid?**
A: Run `curl http://localhost:8000/api/audio/status` - it validates automatically.

## 📞 Support Resources

- **Diagnosis Tool:** `python diagnose_audio.py`
- **Full Guide:** `AUDIO_FIX_GUIDE.md`
- **Error Summary:** `AUDIO_ERROR_FIX_SUMMARY.md`
- **Test Suite:** `python test_audio_fix.py`
- **ElevenLabs Status:** https://status.elevenlabs.io/
- **ElevenLabs Support:** https://support.elevenlabs.io/

---

**💡 Pro Tip:** The new error messages are designed to be self-explanatory. If you get an error, read it carefully - it tells you exactly what to fix!
