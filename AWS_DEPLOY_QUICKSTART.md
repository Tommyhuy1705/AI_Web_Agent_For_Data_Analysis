# 🚀 AWS DEPLOYMENT - QUICK START (5 Steps)

Your environment is ready to deploy to AWS! Follow these 5 steps to get live.

---

## ✅ STEP 1: Create AWS Resources (10 minutes)

### 1.1 Create ECR Repositories
```bash
# Run in Terminal (with AWS CLI configured)
aws ecr create-repository --repository-name sia-backend --region ap-southeast-2
aws ecr create-repository --repository-name sia-frontend --region ap-southeast-2
```

**Save these URLs:**
- Backend ECR: `123456789.dkr.ecr.ap-southeast-2.amazonaws.com/sia-backend`
- Frontend ECR: `123456789.dkr.ecr.ap-southeast-2.amazonaws.com/sia-frontend`
- Registry: `123456789.dkr.ecr.ap-southeast-2.amazonaws.com`

### 1.2 Create EC2 Instance
1. Go to AWS Console → EC2 → Instances → Launch Instance
2. Configure:
   - **Name:** SIA-Server
   - **OS:** Ubuntu 22.04 LTS (Free tier eligible)
   - **Type:** t3.medium (production) or t3.micro (testing)
   - **Storage:** 30GB gp3
   - **Port 22, 80, 443, 3000, 8000** open in Security Group
3. Create new SSH key pair and download `.pem` file
4. Launch instance and note **Public IP** (e.g., `13.211.236.68`)

### 1.3 Install Docker on EC2
```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# On EC2:
sudo apt update && sudo apt install -y docker.io git curl
sudo usermod -aG docker ubuntu
newgrp docker
mkdir -p /opt/sia && cd /opt/sia
git clone https://github.com/YOUR_USERNAME/AI_Web_Agent_For_Data_Analysis.git .
```

---

## ✅ STEP 2: Generate Base64 Environment (1 minute)

Already done! ✅

**File created:** `BACKEND_ENV_BASE64.txt` (6500 characters)

This file contains your complete `.env` encoded for secure deployment.

---

## ✅ STEP 3: Add GitHub Secrets (5 minutes)

🔗 Go to: **GitHub → Your Repo → Settings → Secrets and variables → Actions**

### Add These 8 Secrets:

| Secret Name | Value | Source |
|-------------|-------|--------|
| `AWS_REGION` | `ap-southeast-2` | Fixed |
| `AWS_ACCESS_KEY_ID` | `AKIA...` | AWS IAM Console |
| `AWS_SECRET_ACCESS_KEY` | `wJal...` | AWS IAM Console |
| `ECR_REGISTRY` | `123456789.dkr.ecr.ap-southeast-2.amazonaws.com` | From Step 1.1 |
| `EC2_HOST` | `13.211.236.68` | From Step 1.2 |
| `EC2_USER` | `ubuntu` | Fixed |
| `EC2_SSH_KEY` | `-----BEGIN RSA PRIVATE KEY-----...` | Your .pem file |
| `BACKEND_ENV_BASE64` | `IyA9PT09PT...` | File: BACKEND_ENV_BASE64.txt |

**Getting AWS credentials:**
1. Go to AWS Console
2. Click your username → Security credentials
3. Create access key (if needed)
4. Copy Key ID and Secret Access Key

**Getting SSH key for GitHub:**
1. Open your `.pem` file in text editor
2. Copy entire contents (including `-----BEGIN RSA PRIVATE KEY-----`)
3. Paste into `EC2_SSH_KEY` secret

**Getting base64 env:**
1. Open `BACKEND_ENV_BASE64.txt`
2. Copy entire contents
3. Paste into `BACKEND_ENV_BASE64` secret

---

## ✅ STEP 4: Trigger Deployment (2 minutes)

### Option A: Automatic via Git Push
```bash
git add .
git commit -m "Deploy to AWS"
git push origin main
```

### Option B: Manual via GitHub UI
1. Go to GitHub → Actions
2. Find "Build & Deploy to AWS"
3. Click "Run workflow"
4. Select "main" branch
5. Click "Run workflow"

**Monitor deployment:**
- Watch the Actions tab in GitHub
- Workflow runs in ~5 minutes
- Check for ✅ mark when complete

---

## ✅ STEP 5: Verify Deployment (2 minutes)

### Check EC2 Deployment
```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Check containers
docker ps

# Check logs
docker logs sia-backend --tail 20
docker logs sia-frontend --tail 20

# Test backend
curl http://localhost:8000/health
```

### Access Your System
- **Frontend:** `http://YOUR_EC2_IP:3000`
- **Backend API:** `http://YOUR_EC2_IP:8000/docs`
- **Backend Health:** `http://YOUR_EC2_IP:8000/health`

### Example
If EC2 IP is `13.211.236.68`:
- Frontend: `http://13.211.236.68:3000`
- Backend: `http://13.211.236.68:8000/docs`

---

## 📊 What Gets Deployed

✅ **Backend (FastAPI)**
- Chat API with market intelligence
- All integrations (DashScope, TinyFish, Exa, etc.)
- Email alerts (SendGrid)

✅ **Frontend (Next.js)**
- Dashboard UI
- Real-time chat interface
- Responsive design

✅ **Database**
- Already using Supabase (no action needed)

✅ **Environment**
- All your `.env` variables securely deployed
- API keys for all services

---

## 🆘 Troubleshooting

### Backend won't start
```bash
# SSH to EC2
ssh -i your-key.pem ubuntu@YOUR_EC2_IP
docker logs sia-backend
# Look for error messages
```

### Can't access http://EC2_IP:3000
- Check Security Group allows port 3000
- Wait 30 seconds after deployment
- Check frontend is running: `docker ps | grep sia-frontend`

### ECR login failed in GitHub Actions
- Verify AWS credentials are correct
- Check IAM user has ECR permissions
- Recreate access keys if needed

### SSH key not working
- Ensure EC2_SSH_KEY secret has full key including:
  ```
  -----BEGIN RSA PRIVATE KEY-----
  [contents]
  -----END RSA PRIVATE KEY-----
  ```

---

## 📞 Useful Commands

### Monitor Deployment
```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Real-time logs
docker compose -f docker-compose.prod.yml logs -f

# Just backend
docker compose -f docker-compose.prod.yml logs -f backend

# Just frontend
docker compose -f docker-compose.prod.yml logs -f frontend

# Check resource usage
docker stats

# Restart services
docker compose -f docker-compose.prod.yml restart backend
```

### Manual Troubleshoot
```bash
# Stop everything
docker compose -f docker-compose.prod.yml down

# Pull latest images
docker compose -f docker-compose.prod.yml pull

# Start fresh
docker compose -f docker-compose.prod.yml up -d

# Check health
curl http://localhost:8000/health
```

---

## 🎯 Summary

```
Step 1: Create AWS Resources (10 min) ✓
Step 2: Generate Base64 Env (1 min) ✓ DONE
Step 3: Add GitHub Secrets (5 min)
Step 4: Deploy (2 min)
Step 5: Verify (2 min)
───────────────────────────
Total time: ~20 minutes

Result: Live system at http://YOUR_EC2_IP:3000 🚀
```

---

## 📁 Files You Have

- ✅ `BACKEND_ENV_BASE64.txt` - Ready to paste into GitHub secret
- ✅ `AWS_DEPLOYMENT_GUIDE.md` - Full detailed guide
- ✅ `setup_aws_deployment.py` - Setup script (already ran)
- ✅ `docker-compose.prod.yml` - Production Docker config
- ✅ `.github/workflows/deploy.yml` - CI/CD pipeline

---

## 🎉 Next Action

**Right now:**
1. Complete AWS resource setup (Step 1)
2. Get GitHub secrets from AWS Console (Step 3)
3. Add secrets to GitHub (Step 3)
4. Push to deploy or trigger manually (Step 4)

**Then:**
Access at `http://YOUR_EC2_IP:3000` and start using your AI system! 🚀

---

**Questions?** See `AWS_DEPLOYMENT_GUIDE.md` for detailed explanations
