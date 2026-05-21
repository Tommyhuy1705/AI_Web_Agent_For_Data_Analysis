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

... (content truncated for brevity) ...
