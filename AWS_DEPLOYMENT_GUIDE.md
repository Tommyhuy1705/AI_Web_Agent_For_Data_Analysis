# AWS Deployment Guide for SIA (Sales Intelligence Agent)

## 🚀 Overview

This guide walks you through deploying the AI Web Agent to AWS using:
- **ECR** (Elastic Container Registry) for Docker images
- **EC2** for running containers
- **GitHub Actions** for CI/CD automation
- **RDS/Supabase** for database (already configured)

---

## 📋 Prerequisites

### 1. AWS Account & Credentials
- AWS Account with permissions for ECR, EC2, IAM
- AWS Access Key ID and Secret Access Key
- AWS Region (e.g., `ap-southeast-2`)

### 2. GitHub Repository
- Repository must be public or have actions enabled
- You're already using GitHub (verified ✓)

### 3. Tools Installed Locally
- AWS CLI (optional but recommended)
- SSH access to create keys

---

## 🎯 Step-by-Step Deployment

### STEP 1: Create AWS Resources

#### 1.1 Create ECR Repositories
```bash
# Set your AWS region
$AWS_REGION = "ap-southeast-2"  # or your preferred region

# Get AWS credentials via AWS Console
# Then run these commands:

aws ecr create-repository --repository-name sia-backend --region $AWS_REGION
aws ecr create-repository --repository-name sia-frontend --region $AWS_REGION
```

**Save the ECR Registry URL** (format: `123456789.dkr.ecr.ap-southeast-2.amazonaws.com`)

#### 1.2 Create EC2 Instance
1. Go to AWS Console → EC2 → Launch Instance
2. Select: **Ubuntu 22.04 LTS** (t3.medium minimum)
3. **Storage:** 30GB (gp3)
4. **Security Group:** Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS), 3000, 8000
5. Create/use SSH key pair and download `.pem` file
6. Launch instance and note the **Public IP**

#### 1.3 Install Docker on EC2
```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Run on EC2:
sudo apt update && sudo apt install -y docker.io git curl
sudo usermod -aG docker ubuntu
sudo systemctl enable docker
newgrp docker

# Create deployment directory
mkdir -p /opt/sia
cd /opt/sia

# Clone repository (or pull latest)
git clone https://github.com/YOUR_USERNAME/AI_Web_Agent_For_Data_Analysis.git .
# Or if already cloned:
git pull origin main
```

---

### STEP 2: Configure GitHub Secrets

Go to GitHub Repository → Settings → Secrets and Variables → Actions

Add the following secrets:

```
Name: AWS_REGION
Value: ap-southeast-2
```

```
Name: AWS_ACCESS_KEY_ID
Value: YOUR_AWS_ACCESS_KEY
```

```
Name: AWS_SECRET_ACCESS_KEY
Value: YOUR_AWS_SECRET_KEY
```

```
Name: ECR_REGISTRY
Value: 123456789.dkr.ecr.ap-southeast-2.amazonaws.com
```

```
Name: EC2_HOST
Value: XX.XX.XX.XX  (Your EC2 public IP)
```

```
Name: EC2_USER
Value: ubuntu
```

```
Name: EC2_SSH_KEY
Value: (paste contents of your-key.pem file here)
```

```
Name: BACKEND_ENV_BASE64
Value: (Generate in STEP 3)
```

---

### STEP 3: Generate Base64 Environment

This encodes your `.env` file for secure deployment:

**On Windows PowerShell:**
```powershell
# Read your .env file and encode it
$envContent = Get-Content ".env" -Raw
$envBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($envContent))
Set-Clipboard -Value $envBase64
Write-Host "Base64 env copied to clipboard!"
```

**On Mac/Linux:**
```bash
base64 < .env | tr -d '\n' | pbcopy
echo "Base64 env copied to clipboard!"
```

Then paste this value into GitHub secret `BACKEND_ENV_BASE64`

---

### STEP 4: Set EC2 Directory Permissions

SSH into EC2 and run:
```bash
# On EC2
mkdir -p /opt/sia
sudo chown ubuntu:ubuntu /opt/sia
chmod 755 /opt/sia
```

---

### STEP 5: Trigger Deployment

#### Option A: Automatic (via Git Push)
```bash
# Just push to main
git add .
git commit -m "Deploy to AWS"
git push origin main
```

#### Option B: Manual (via GitHub Actions)
1. Go to GitHub → Actions → "Build & Deploy to AWS"
2. Click "Run workflow"
3. Select "main" branch
4. Click "Run workflow"

**Monitor deployment:**
- Go to Actions tab and watch the workflow run
- Check EC2 logs: `ssh ... ubuntu@YOUR_IP && docker logs sia-backend`

---

## ✅ Verification

### 1. Check Deployment Status
```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Check running containers
docker ps

# Check backend logs
docker logs sia-backend --tail 50

# Check frontend logs
docker logs sia-frontend --tail 50

# Test backend
curl http://localhost:8000/health

# Test frontend
curl http://localhost:3000
```

### 2. Access Your System
- **Frontend:** `http://YOUR_EC2_IP:3000`
- **Backend API:** `http://YOUR_EC2_IP:8000/docs`

### 3. Troubleshooting
```bash
# View all logs
docker compose -f docker-compose.prod.yml logs -f

# Restart services
docker compose -f docker-compose.prod.yml restart

# Check resource usage
docker stats

# Check network connectivity
docker network ls
```

---

## 🔧 Environment Variables

Your `.env` file contains all these (already set up):

```env
# Already configured in your .env:
✅ SUPABASE_URL
✅ SUPABASE_ANON_KEY
✅ SUPABASE_SERVICE_ROLE_KEY
✅ DASHSCOPE_API_KEY
✅ OPENAI_API_KEY
✅ TINYFISH_API_KEY
✅ EXA_API_KEY
✅ ELEVENLABS_API_KEY
✅ ELEVENLABS_VOICE_ID
✅ SENDGRID_API_KEY
✅ SENDGRID_FROM_EMAIL
✅ ALERT_RECIPIENTS
```

All should be automatically deployed via `BACKEND_ENV_BASE64` secret.

---

## 📊 Current AWS Status

| Component | Status | Notes |
|-----------|--------|-------|
| ECR Repositories | ⏳ Needs setup | Create sia-backend, sia-frontend |
| EC2 Instance | ⏳ Needs setup | Ubuntu 22.04, t3.medium minimum |
| GitHub Secrets | ⏳ Needs setup | 10 secrets to configure |
| Docker Images | ✅ Ready | Dockerfiles already in place |
| CI/CD Pipeline | ✅ Ready | deploy.yml workflow ready |

---

## 🚨 Important Notes

### 1. Cost Optimization
- **EC2:** Use t3.medium (~$0.0416/hour) or smaller
- **ECR:** First 50GB free per month
- **Data Transfer:** Monitor to avoid egress charges

### 2. Security Best Practices
- Never commit `.env` or secrets to Git
- Use IAM role instead of access keys (when possible)
- Enable EC2 security group restrictions
- Use VPC for private networking
- Enable CloudWatch monitoring

### 3. Scaling for Production
- Load balancer (ALB) for multiple EC2 instances
- Auto-scaling groups for automatic scaling
- RDS for database (instead of managed Supabase)
- CloudFront for CDN
- Route53 for domain management

---

## 📞 Quick Reference

### Manual Deploy Commands (SSH to EC2)
```bash
# Pull latest code and redeploy
cd /opt/sia
git pull origin main
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f backend

# Restart specific service
docker compose -f docker-compose.prod.yml restart backend
```

### Useful Links
- AWS ECR: https://console.aws.amazon.com/ecr
- AWS EC2: https://console.aws.amazon.com/ec2
- GitHub Actions: https://github.com/YOUR_REPO/actions
- Docker Docs: https://docs.docker.com/
- Supabase: https://app.supabase.com

---

## 🎉 What Happens During Deployment

1. **GitHub Push** → Triggers workflow
2. **Build Backend** → Docker image built and pushed to ECR
3. **Build Frontend** → Next.js image built and pushed to ECR
4. **SSH to EC2** → Connect to your instance
5. **Pull from ECR** → Newest images downloaded
6. **Start Containers** → Backend and frontend start
7. **Health Check** → Verify services are running
8. **System Live** → Access at `http://YOUR_EC2_IP:3000`

---

## 🆘 Troubleshooting

### Problem: "ECR login failed"
**Error:** `Unable to parse response`  
**Fix:** Check AWS credentials are correct and have ECR permissions

### Problem: "Permission denied (publickey)"
**Error:** SSH key issue  
**Fix:** Ensure EC2_SSH_KEY secret contains the full private key content

### Problem: "Container exits immediately"
**Error:** Backend/frontend containers crash  
**Fix:** Check `docker logs` for errors, verify env vars are loaded

### Problem: "Backend env not loading"
**Error:** `BACKEND_ENV_BASE64 is empty`  
**Fix:** Regenerate and re-upload the secret, ensure base64 encoding is correct

---

## ✨ Next Steps

1. **Create AWS Resources** (15 minutes)
   - [ ] Create ECR repos
   - [ ] Create EC2 instance
   - [ ] Install Docker on EC2

2. **Configure GitHub** (10 minutes)
   - [ ] Add 10 GitHub secrets
   - [ ] Generate base64 env
   - [ ] Add BACKEND_ENV_BASE64 secret

3. **Deploy** (5 minutes)
   - [ ] Push to main or trigger workflow
   - [ ] Wait for GitHub Actions to complete
   - [ ] Verify EC2 dashboard is accessible

4. **Monitor** (ongoing)
   - [ ] Check logs regularly
   - [ ] Set up CloudWatch alarms
   - [ ] Monitor costs

---

**Ready to deploy? Start with STEP 1!** 🚀
