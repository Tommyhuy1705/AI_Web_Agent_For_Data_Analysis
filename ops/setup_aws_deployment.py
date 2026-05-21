#!/usr/bin/env python3
"""
AWS Deployment Setup Helper
Helps generate and configure secrets for AWS deployment
"""
import base64
import json
import sys
from pathlib import Path


def generate_env_base64(env_file=".env"):
    """Generate base64-encoded environment for GitHub secrets."""
    try:
        with open(env_file, "r", encoding='utf-8', errors='ignore') as f:
            env_content = f.read()
        
        env_base64 = base64.b64encode(env_content.encode('utf-8')).decode('utf-8')
        return env_base64
    except FileNotFoundError:
        print(f"❌ Error: {env_file} not found")
        return None


def validate_secrets():
    """Check if all required secrets are populated."""
    # Read .env
    try:
        with open(".env", encoding='utf-8', errors='ignore') as f:
            env_vars = {}
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    env_vars[key] = val
    except FileNotFoundError:
        print("❌ .env file not found")
        return False
    
    # Check critical keys
    required_keys = [
        "SUPABASE_URL",
        "DASHSCOPE_API_KEY",
        "ELEVENLABS_API_KEY",
        "SENDGRID_API_KEY"
    ]
    
    missing = []
    for key in required_keys:
        if not env_vars.get(key):
            missing.append(key)
    
    if missing:
        print(f"⚠️  Missing env variables: {', '.join(missing)}")
        return False
    
    print("✅ All critical env variables present")
    return True


def print_github_secrets_guide(env_base64):
    """Print guide for adding GitHub secrets."""
    print("\n" + "="*70)
    print("📌 GITHUB SECRETS TO ADD")
    print("="*70)
    print("\nGo to: GitHub Repository → Settings → Secrets and Variables → Actions\n")
    
    secrets = {
        "AWS_REGION": "ap-southeast-2",
        "AWS_ACCESS_KEY_ID": "YOUR_AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY": "YOUR_AWS_SECRET_ACCESS_KEY",
        "ECR_REGISTRY": "123456789.dkr.ecr.ap-southeast-2.amazonaws.com",
        "EC2_HOST": "XX.XXX.XXX.XXX",
        "EC2_USER": "ubuntu",
        "EC2_SSH_KEY": "[Contents of your .pem key file]",
        "BACKEND_ENV_BASE64": env_base64[:50] + "..."
    }
    
    for i, (key, value) in enumerate(secrets.items(), 1):
        print(f"{i}. Secret Name: {key}")
        if key == "BACKEND_ENV_BASE64":
            print(f"   Value: [See below - Copy from file]")
        elif key in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "EC2_SSH_KEY"]:
            print(f"   Value: [Get from AWS Console / your-key.pem file]")
        else:
            print(f"   Value: {value}")
        print()


def save_env_base64(env_base64, output_file="BACKEND_ENV_BASE64.txt"):
    """Save base64 env to file for easy copying."""
    with open(output_file, "w") as f:
        f.write(env_base64)
    print(f"✅ Base64 env saved to {output_file}")
    print(f"   → Open this file and copy the entire content to GitHub secret BACKEND_ENV_BASE64")


def print_aws_setup_checklist():
    """Print AWS setup checklist."""
    print("\n" + "="*70)
    print("📋 AWS SETUP CHECKLIST")
    print("="*70)
    
    steps = [
        ("Create ECR Repository (sia-backend)", "aws ecr create-repository --repository-name sia-backend --region ap-southeast-2"),
        ("Create ECR Repository (sia-frontend)", "aws ecr create-repository --repository-name sia-frontend --region ap-southeast-2"),
        ("Create EC2 Instance", "AWS Console → EC2 → Launch Instance (Ubuntu 22.04 LTS, t3.medium)"),
        ("Note EC2 Public IP", "Copy from EC2 Dashboard"),
        ("Create SSH Key Pair", "AWS Console → EC2 → Key Pairs → Create key pair"),
        ("Save .pem file", "Download and save in safe location"),
        ("Install Docker on EC2", "SSH to EC2 and run: sudo apt update && sudo apt install -y docker.io"),
        ("Create /opt/sia directory", "SSH to EC2 and run: mkdir -p /opt/sia && sudo chown ubuntu:ubuntu /opt/sia"),
    ]
    
    for i, (step, command) in enumerate(steps, 1):
        print(f"\n{i}. {step}")
        if command.startswith("aws") or command.startswith("SSH"):
            print(f"   Command: {command}")
        else:
            print(f"   Action: {command}")


def print_deployment_commands():
    """Print deployment commands."""
    print("\n" + "="*70)
    print("🚀 DEPLOYMENT COMMANDS")
    print("="*70)
    
    commands = {
        "Manual Deploy (via Git)": [
            "git add .",
            "git commit -m 'Deploy to AWS'",
            "git push origin main",
            "# Watch GitHub Actions tab for deployment progress"
        ],
        "Manual Deploy (via GitHub UI)": [
            "Go to GitHub → Actions → 'Build & Deploy to AWS'",
            "Click 'Run workflow'",
            "Select 'main' branch",
            "Click 'Run workflow'"
        ],
        "SSH to EC2 for Manual Control": [
            "ssh -i your-key.pem ubuntu@YOUR_EC2_IP",
            "cd /opt/sia",
            "docker ps",
            "docker logs sia-backend",
            "docker compose -f docker-compose.prod.yml restart backend"
        ]
    }
    
    for section, cmds in commands.items():
        print(f"\n{section}:")
        for cmd in cmds:
            print(f"  {cmd}")


def main():
    """Main execution."""
    print("\n" + "="*70)
    print("🔧 AWS DEPLOYMENT SETUP HELPER")
    print("="*70)
    
    # Step 1: Validate environment
    print("\n📋 Step 1: Validating environment...")
    if not validate_secrets():
        print("⚠️  Cannot proceed with deployment without required secrets")
        return 1
    
    # Step 2: Generate base64 env
    print("\n📋 Step 2: Generating base64 environment...")
    env_base64 = generate_env_base64()
    if not env_base64:
        return 1
    
    print(f"✅ Base64 env generated ({len(env_base64)} characters)")
    
    # Step 3: Save to file
    print("\n📋 Step 3: Saving base64 env...")
    save_env_base64(env_base64)
    
    # Step 4: Print setup guides
    print_aws_setup_checklist()
    print_github_secrets_guide(env_base64)
    print_deployment_commands()
    
    # Final summary
    print("\n" + "="*70)
    print("✨ NEXT STEPS")
    print("="*70)
    print("""
1. Create AWS resources (5-10 minutes):
   ✓ Create 2 ECR repositories
   ✓ Create EC2 instance (Ubuntu, t3.medium)
   ✓ Create SSH key pair
   ✓ Install Docker on EC2

2. Configure GitHub Secrets (5 minutes):
   ✓ Add all 8 secrets from checklist above
   ✓ Get BACKEND_ENV_BASE64 from file just created
   ✓ Get EC2_SSH_KEY from your downloaded .pem file

3. Deploy (2 minutes):
   ✓ Push to main OR trigger workflow manually
   ✓ Monitor GitHub Actions for deployment progress
   ✓ Wait ~5 minutes for deployment to complete

4. Verify (1 minute):
   ✓ Open http://YOUR_EC2_IP:3000 in browser
   ✓ Check backend at http://YOUR_EC2_IP:8000/docs
   ✓ Start using your system!

📖 Full guide: See AWS_DEPLOYMENT_GUIDE.md
🆘 Issues? Check Troubleshooting section in deployment guide
""")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
