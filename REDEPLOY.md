# Survey API - Redeployment Guide

## New EC2 Instance URL
**Base URL:** `http://ec2-15-223-192-87.ca-central-1.compute.amazonaws.com:3000`

---

## Quick Redeployment Steps

### Option 1: Automated Deployment (Recommended)

**From your local Windows machine:**

1. Open PowerShell in the project directory (`E:\surveyProj`)
2. Run:
   ```powershell
   .\deploy.ps1
   ```

This script will:
- Test SSH connection
- Transfer all project files to EC2
- Run the redeployment script on EC2
- Show deployment status

---

### Option 2: Manual Deployment

#### Step 1: Transfer Files to EC2

**From your local machine (PowerShell):**
```powershell
cd E:\surveyProj
scp -i "E:\aws-services-stage.pem" -r . ubuntu@ec2-15-223-192-87.ca-central-1.compute.amazonaws.com:~/surveyProj/
```

#### Step 2: Connect to EC2

```powershell
ssh -i "E:\aws-services-stage.pem" ubuntu@ec2-15-223-192-87.ca-central-1.compute.amazonaws.com
```

#### Step 3: Run Redeployment on EC2

**On the EC2 instance:**
```bash
cd ~/surveyProj

# Make redeploy script executable
chmod +x redeploy.sh

# Run redeployment
./redeploy.sh
```

**OR manually:**
```bash
cd ~/surveyProj

# Stop existing containers
docker-compose down

# Build new images
docker-compose build --no-cache

# Start containers
docker-compose up -d

# Check status
docker ps

# View logs
docker-compose logs -f
```

---

## Verify Deployment

### Test API Endpoint
```bash
curl http://ec2-15-223-192-87.ca-central-1.compute.amazonaws.com:3000/api/test
```

**Expected Response:**
```json
{"message":"API is working!"}
```

### Check Container Status
```bash
docker ps
```

You should see the `survey-api` container running.

---

## Troubleshooting

### If SSH connection fails:
1. Check EC2 instance is running in AWS Console
2. Verify Security Group allows SSH (port 22) from your IP
3. Check the key file path: `E:\aws-services-stage.pem`

### If deployment fails:
1. Check Docker is installed: `docker --version`
2. Check Docker Compose: `docker-compose --version`
3. View logs: `docker-compose logs -f`
4. Check `.env` file exists and has correct database credentials

### If API doesn't respond:
1. Check Security Group allows port 3000 from 0.0.0.0/0
2. Check container logs: `docker-compose logs survey-api`
3. Verify database connection in logs

---

## Useful Commands

### View Logs
```bash
docker-compose logs -f
docker-compose logs -f survey-api
```

### Restart Service
```bash
docker-compose restart
```

### Stop Service
```bash
docker-compose down
```

### Rebuild and Restart
```bash
docker-compose up -d --build
```

### Access Container Shell
```bash
docker exec -it surveyproj-survey-api-1 sh
```

### Clean Up Old Images
```bash
docker image prune -f
docker system prune -f
```

---

## Environment Variables

Make sure your `.env` file on EC2 has all required variables:

```env
# Database Configuration
DB_HOST=your-database-host
DB_PORT=3306
DB_DATABASE=your-database-name
DB_USERNAME=your-database-user
DB_PASSWORD=your-database-password
DB_DIALECT=mysql

# Server Configuration
PORT=3000
NODE_ENV=production
```

---

## Security Group Configuration

Ensure your EC2 Security Group has these rules:

| Type | Protocol | Port Range | Source |
|------|----------|-------------|--------|
| SSH | TCP | 22 | Your IP / 0.0.0.0/0 |
| Custom TCP | TCP | 3000 | 0.0.0.0/0 |

---

## Post-Deployment Checklist

- [ ] API test endpoint responds: `/api/test`
- [ ] Database connection successful (check logs)
- [ ] All routes accessible
- [ ] Security Group configured correctly
- [ ] Environment variables set correctly
- [ ] Container running and healthy

---

**Last Updated:** December 2024  
**EC2 Instance:** ec2-15-223-192-87.ca-central-1.compute.amazonaws.com
