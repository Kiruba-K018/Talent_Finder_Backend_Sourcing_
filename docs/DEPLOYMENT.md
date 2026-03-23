# Backend Sourcing Deployment Guide

## Overview

The Talent Finder Backend Sourcing service handles automated candidate sourcing from LinkedIn and other platforms. It runs as a FastAPI application on Python 3.12 with Chromium/Playwright for web automation and includes background task scheduling.

## Quick Start - Local Docker Compose

### Prerequisites

- Docker and Docker Compose installed
- 4GB RAM minimum available
- Port availability: 8001 (API), 9001 (Metrics)
- Backend Core service running on configured URL

### Local Deployment

1. Navigate to Backend Core directory and start services:
```bash
cd Talent_Finder_Backend/Talent_Finder_Backend_Core
docker-compose up -d
```

This starts PostgreSQL, MongoDB, and ChromaDB required by sourcing service.

2. Navigate to Sourcing service directory:
```bash
cd ../Talent_Finder_Backend_Sourcing_
```

3. Create environment file:
```bash
cp .env.example .env
```

4. Update `.env` with configuration:
```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=talentfinder
MONGO_USER=mongo
MONGO_PASSWORD=your_secure_password
MONGO_DB=talentfinder
GROQ_API_KEY=your_groq_key
LINKEDIN_EMAIL=your_linkedin_email
LINKEDIN_PASSWORD=your_linkedin_password
CORE_SERVICE_URL=http://core-backend:8000
```

5. Start sourcing service:
```bash
docker-compose -f docker-compose.yml up -d sourcing
```

6. Verify deployment:
```bash
curl http://localhost:8001/health
curl http://localhost:8001/health/ready
```

The API will be available at `http://localhost:8001` with metrics at `http://localhost:9001/metrics`.

## Docker Configuration

### Image Details

**Base Image:** `python:3.12-slim`

**System Dependencies:**
- Chromium and ChromeDriver for web scraping
- Playwright for browser automation
- Font libraries for rendering
- libasound2 for audio support in headless mode

**Python Dependencies:**
- FastAPI web framework
- SQLAlchemy for database access
- Motor for MongoDB async driver
- Playwright for automation
- Pydantic for validation

### Dockerfile

The provided `Dockerfile` creates an optimized image with web automation support:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    chromium chromium-driver curl wget gnupg unzip \
    fonts-liberation libnss3 libgbm1 libasound2 libxss1 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install and cache Python packages
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN pip install --no-cache-dir playwright && \
    playwright install chromium && \
    playwright install-deps chromium

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Copy application
COPY src/ ./src/
COPY .env* ./

EXPOSE 8001 9001

CMD ["python", "-m", "src.main"]
```

**Key Features:**
- Multi-stage build eliminates unnecessary layers
- Cache invalidation optimized for requirements
- Playwright browsers cached in image layer
- Chrome and ChromeDriver pre-installed

### Resource Requirements

**Minimum:**
- CPU: 1 core
- Memory: 1GB
- Disk: 500MB (for Playwright cache)

**Recommended:**
- CPU: 2 cores
- Memory: 2GB
- Disk: 1GB

## Docker Compose Services

### Service Configuration

The sourcing service is defined in the Backend Core's docker-compose.yml:

```yaml
sourcing:
  build:
    context: ../Talent_Finder_Backend_Sourcing_
    dockerfile: Dockerfile
  container_name: talentfinder_sourcing
  environment:
    POSTGRES_HOST: postgres
    MONGO_HOST: mongodb
    CORE_SERVICE_URL: http://app:8000
    PROMETHEUS_PORT: 9001
  ports:
    - "8001:8001"
    - "9001:9001"
  depends_on:
    postgres:
      condition: service_healthy
    mongodb:
      condition: service_healthy
    app:
      condition: service_started
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G
```

**Dependencies:**
- PostgreSQL: Configuration and source run storage
- MongoDB: Sourced candidates storage
- PgVector: Vector embeddings for candidate matching
- Backend Core: Job details and configuration retrieval

**Port Mapping:**
- 8001: FastAPI application
- 9001: Prometheus metrics

## Environment Configuration

### Core Settings

```
APP_ENV=development             # development | production | staging
APP_HOST=0.0.0.0               # Bind address
APP_PORT=8001                  # Service port
LOG_LEVEL=INFO                 # DEBUG | INFO | WARNING | ERROR
```

### PostgreSQL Settings

```
POSTGRES_USER=postgres         # Database user
POSTGRES_PASSWORD=             # User password (required)
DB_HOST=postgres               # Connection host
DB_PORT=5432                   # Connection port
DB_NAME=talentfinder           # Database name
POSTGRES_POOL_SIZE=2           # Max connections (reduced for Cloud SQL)
POSTGRES_MAX_OVERFLOW=1        # Overflow connections
```

**Connection URL:** `postgresql+psycopg://user:password@host:port/dbname`

### MongoDB Settings

```
MONGO_USER=mongo               # MongoDB user
MONGO_PASSWORD=                # User password (required)
MONGO_HOST=mongodb             # Connection host
MONGO_PORT=27017               # Connection port
MONGO_DB=talentfinder          # Database name
MONGO_AUTHSOURCE=admin         # Authentication database
MONGO_CANDIDATES_COLLECTION=sourced_candidates

# Optional: MongoDB Atlas
ATLAS_CONNECTION_STRING=       # mongodb+srv://... URI for Atlas
```

**Local Connection:** `mongodb://user:password@mongodb:27017/talentfinder?authSource=admin`

**Atlas Connection:** Provide full URI to `ATLAS_CONNECTION_STRING`

### Core Service Settings

```
CORE_SERVICE_URL=http://app:8000           # Backend Core URL
CORE_SERVICE_TIMEOUT=30                    # Request timeout (seconds)
CORE_SERVICE_MAX_RETRIES=3                 # Retry on failure
```

### LinkedIn Scraping Settings

```
LINKEDIN_EMAIL=your@email.com              # LinkedIn account email
LINKEDIN_PASSWORD=                         # LinkedIn password (required)
LINKEDIN_SESSION_COOKIE=                   # Optional: Direct session cookie
LINKEDIN_HEADLESS_LOGIN=true               # Attempt headless login
CHROME_BIN=/usr/bin/chromium               # Chromium binary path
CHROMEDRIVER_PATH=/usr/bin/chromedriver    # ChromeDriver path
SCRAPER_HEADLESS=true                      # Run browser headless
SCRAPER_MIN_DELAY=2                        # Min delay between requests (seconds)
SCRAPER_MAX_DELAY=7                        # Max delay between requests (seconds)
SCRAPER_PAGE_TIMEOUT=60                    # Page load timeout (seconds)
PROXY_URL=                                 # Optional: Proxy URL for scraping
```

### PostJobFree Scraping Settings

```
PLAYWRIGHT_HEADLESS=true                   # Run browser headless
PLAYWRIGHT_TIMEOUT=60000                   # Page timeout (milliseconds)
SERPAPI_KEY=                               # SerpAPI key for search
POSTJOBFREE_PLATFORM_ID=22000015-0000...  # Platform identifier
POSTJOBFREE_MAX_PROFILES=20                # Max profiles to scrape per run
```

### API Keys

```
GROQ_API_KEY=                  # Groq API key for LLM
GROQ_API_KEY_SECONDARY=        # Secondary Groq API key
```

### Scheduling Settings

```
SCHEDULER_POLL_INTERVAL=60     # Poll interval for background jobs (seconds)
```


## Google Cloud Run Deployment

### Prerequisites

- Google Cloud account with active project
- `gcloud` CLI installed and configured
- Docker credential helper configured
- Service account with Cloud Run and Cloud SQL permissions

### Deployment Script

Use the provided `deploy.sh`:

```bash
#!/bin/bash

PROJECT_ID="gwx-internship-01"
REGION="us-east1"
SERVICE_NAME="talentfinder-backend-sourcing"
GAR_REPO="us-east1-docker.pkg.dev/$PROJECT_ID/gwx-gar-intern-01"
IMAGE="$GAR_REPO/talentfinder-backend-sourcing:latest"

# Cloud SQL connection
DB_URL="postgresql+psycopg://user:password@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE"

# MongoDB Atlas
MONGODB_ATLAS_URI="mongodb+srv://user:password@cluster.mongodb.net/dbname"

# Build and push image
docker build -t $IMAGE .
docker push $IMAGE

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image=$IMAGE \
  --region=$REGION \
  --platform=managed \
  --port=8001 \
  --memory=2Gi \
  --max-instances=2 \
  --min-instances=0 \
  --timeout=600 \
  --no-cpu-throttling \
  --service-account=SERVICE_ACCOUNT_EMAIL \
  --set-env-vars="DB_URL=$DB_URL,ATLAS_CONNECTION_STRING=$MONGODB_ATLAS_URI"
```

### Deployment Configuration

**Memory & CPU:**
- Memory: 2Gi (2GB) for Chromium and processing
- CPU: Fully allocated
- Timeout: 600 seconds (sourcing can take 5-30 minutes)

**Scaling:**
- Min instances: 0 (cost optimization)
- Max instances: 2 (prevent runaway costs)

Note: Cloud Run request timeout is 3600 seconds (1 hour), but Talent Finder sourcing applies 600-second timeout for Cloud Run compatibility. Long sourcing jobs should use async polling.

### Environment Variables for Cloud Run

```
DB_URL=postgresql+psycopg://user:password@/database?host=/cloudsql/PROJECT:REGION:INSTANCE
ATLAS_CONNECTION_STRING=mongodb+srv://user:password@cluster.mongodb.net/database
CORE_SERVICE_URL=https://talentfinder-backend-core-URL
LINKEDIN_EMAIL=your_email@company.com
LINKEDIN_PASSWORD=your_password
GROQ_API_KEY=your_groq_key
PROMETHEUS_PORT=9001
LOG_LEVEL=INFO
```

### Post-Deployment Verification

```bash
# Get service URL
gcloud run services describe talentfinder-backend-sourcing \
  --region=us-east1 \
  --format='value(status.url)'

# Test health endpoints
curl https://YOUR_SERVICE_URL/health
curl https://YOUR_SERVICE_URL/health/ready

# View logs
gcloud run services logs read talentfinder-backend-sourcing \
  --region=us-east1 \
  --limit=100
```

## Backup and Recovery

### PostgreSQL Configuration Backup

```bash
# Backup sourcing-related schema
docker-compose exec postgres pg_dump -U postgres talentfinder \
  -t source_runs \
  -t sourcing_config > sourcing_config_backup.sql
```

### MongoDB Sourced Candidates Backup

```bash
# Backup sourced_candidates collection
docker-compose exec mongo mongodump \
  --username mongo \
  --password mongo \
  --authenticationDatabase admin \
  --db talentfinder \
  --collection sourced_candidates \
  --out=/backups
```

### Recovery Procedures

**Restore PostgreSQL:**

```bash
docker-compose stop sourcing
docker-compose exec -T postgres psql -U postgres talentfinder < sourcing_config_backup.sql
docker-compose up -d sourcing
```

**Restore MongoDB:**

```bash
docker-compose stop sourcing
docker-compose exec -T mongo mongorestore \
  --username mongo \
  --password mongo \
  --authenticationDatabase admin \
  /backups
docker-compose up -d sourcing
```


### Database Connection Management

**Settings:**
```
POSTGRES_POOL_SIZE=2           # Reduced for Cloud SQL
POSTGRES_MAX_OVERFLOW=1        # Allow overflow
```

**Total Connections = Replicas × POSTGRES_POOL_SIZE**

Example: 3 replicas × 2 pool size = 6 connections (typical PostgreSQL: 100 total)

## Monitoring and Logging

### Health Endpoints

**Liveness Check:**
```bash
curl http://localhost:8001/health
```

**Readiness Check:**
```bash
curl http://localhost:8001/health/ready
```

Checks database connectivity and core service availability.

### Logs

**Docker:**
```bash
docker-compose logs -f sourcing
```

**Cloud Run:**
```bash
gcloud run services logs read talentfinder-backend-sourcing --limit=100
```

**Kubernetes:**
```bash
kubectl logs -f deployment/backend-sourcing -n talentfinder
```

### Metrics (Prometheus)

```
GET /metrics
```

Metrics include:
- sourcing_jobs_total: Total jobs triggered
- sourcing_jobs_completed: Successful completions
- sourcing_jobs_failed: Failed jobs
- sourcing_candidates_found: Total candidates
- linkedin_api_requests_total: API calls
- linkedin_api_errors: API failures
- sourcing_duration_seconds: Operation duration histogram

## Troubleshooting

### Browser Automation Issues

**Symptom:** "Chromium not found" error

**Solution:**
```bash
# Verify Chromium installation in container
docker-compose exec sourcing which chromium
docker-compose exec sourcing which chromedriver

# Recreate image if issue persists
docker-compose down sourcing
docker rmi talentfinder_sourcing
docker-compose up -d sourcing
```

### LinkedIn Authentication Failed

**Symptom:** "Invalid LinkedIn credentials" or "Captcha detected"

**Solution:**
1. Verify email and password in `.env`
2. Check LinkedIn account for security alerts
3. Try session cookie: `LINKEDIN_SESSION_COOKIE=value`
4. Disable headless mode temporarily for debugging: `LINKEDIN_HEADLESS_LOGIN=false`

### Database Connection Timeout

**Symptom:** "Connection timeout to PostgreSQL"

**Solution:**
1. Verify database is running: `docker-compose ps postgres`
2. Check connection string in `.env`
3. Verify network: `docker network ls`
4. Test connectivity: `docker-compose exec sourcing psql -h postgres -U postgres -d talentfinder -c "SELECT 1"`

### Memory Issues

**Symptom:** Container killed with "OOMKilled" or memory errors

**Solution:**
1. Increase memory in kubernetes/docker-compose
2. Reduce POSTJOBFREE_MAX_PROFILES
3. Monitor memory: `docker stats talentfinder_sourcing`
4. Implement periodic pod restart in Kubernetes

## Production Checklist

- [ ] LinkedIn credentials secured in secret management
- [ ] Database credentials rotated and secured
- [ ] Core service URL correctly configured (https in production)
- [ ] Sourcing job concurrency limited to 1 per pod
- [ ] Database backup automated and tested
- [ ] Memory limits set to prevent OOMKilled
- [ ] Health checks passing consistently
- [ ] Logging level appropriate (INFO for production)
- [ ] Metrics collection enabled
- [ ] Alerting configured for job failures
- [ ] Rate limiting considerations documented
- [ ] Proxy configured if in restricted network
