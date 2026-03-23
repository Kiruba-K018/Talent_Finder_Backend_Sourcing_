# Talent Finder - Backend Sourcing Service

## Project Overview

Backend microservice for automated candidate sourcing and recruitment pipeline orchestration. This service handles scheduled sourcing jobs, LinkedIn integration, candidate aggregation, and job matching workflows. It works in conjunction with the Core service to identify and source qualified candidates from multiple platforms.

### Key Features

- **Scheduled Sourcing Jobs**: Background job scheduling for automated candidate sourcing
- **Candidates Profile Platform Integration**: OAuth-based LinkedIn authentication and candidate extraction
- **Multi-Source Aggregation**: Aggregate candidates from multiple platforms
- **Candidate Matching**: Match candidates against job requirements
- **Event-Driven Architecture**: Async event processing for scalable sourcing
- **Observability**: Comprehensive logging, metrics, and tracing
- **Error Handling & Retry Logic**: Robust failure handling with exponential backoff
- **API Integration**: RESTful APIs for sourcing operations

### Technology Stack

- **Framework**: FastAPI (Python 3.10+)
- **Scheduler**: APScheduler for background jobs
- **Authentication**: OAuth 2.0 (LinkedIn)
- **Async**: AsyncIO with aiohttp for concurrent requests
- **Databases**: PostgreSQL (metadata), MongoDB (candidates)
- **Observability**: Structured logging, Prometheus metrics, Jaeger tracing

## Setup Instructions

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- MongoDB 5+
- Redis (optional, for caching and Celery)
- LinkedIn App credentials
- Git

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Talent_Finder_Backend/Talent_Finder_Backend_Sourcing_
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Verify setup**
   ```bash
   python -c "import src; print('Setup successful')"
   ```

## Environment Variables

### Database Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection for sourcing metadata | `postgresql://user:password@localhost:5432/sourcing_db` |
| `MONGODB_URL` | MongoDB for candidate data | `mongodb://localhost:27017/sourcing_db` |

### API Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `API_HOST` | Server host | `0.0.0.0` |
| `API_PORT` | Server port | `8001` |
| `CORE_SERVICE_URL` | URL to Core service for candidate creation | `http://localhost:8000` |

### Authentication & Security

| Variable | Description | Example |
|----------|-------------|---------|
| `JWT_SECRET_KEY` | JWT signing secret | `your-secret-key-min-32-chars` |
| `JWT_ALGORITHM` | Algorithm for JWT | `HS256` |

### LinkedIn Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `LINKEDIN_CLIENT_ID` | LinkedIn OAuth client ID | `123456789abcdef` |
| `LINKEDIN_CLIENT_SECRET` | LinkedIn OAuth client secret | `your-client-secret` |
| `LINKEDIN_REDIRECT_URI` | OAuth redirect URI | `http://localhost:8001/auth/linkedin/callback` |
| `LINKEDIN_API_VERSION` | LinkedIn API version | `v2` |

### Scheduler Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SCHEDULER_ENABLED` | Enable APScheduler | `true` |
| `SCHEDULER_TIMEZONE` | Scheduler timezone | `UTC` |
| `SOURCING_JOB_INTERVAL_MINUTES` | Interval between sourcing jobs | `60` |
| `BATCH_SIZE` | Candidates processed per batch | `100` |
| `MAX_RETRIES` | Retry attempts for failed jobs | `3` |

### Observability

| Variable | Description | Example |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_FORMAT` | Log format (json/text) | `json` |
| `PROMETHEUS_METRICS_ENABLED` | Enable Prometheus metrics | `true` |
| `JAEGER_ENABLED` | Enable distributed tracing | `false` |
| `JAEGER_AGENT_HOST` | Jaeger agent host | `localhost` |
| `JAEGER_AGENT_PORT` | Jaeger agent port | `6831` |

## Scheduler Configuration

### APScheduler Setup

The service uses APScheduler for background job scheduling. Configure schedules in `src/config/settings.py`:

```python
# Default scheduled jobs
SCHEDULED_JOBS = [
    {
        "id": "sourcing_job",
        "func": "src.core.services.sourcing_service:run_sourcing_job",
        "trigger": "interval",
        "minutes": 60,  # Run every hour
        "max_instances": 1,  # Prevent concurrent runs
    },
    {
        "id": "candidate_sync_job",
        "func": "src.core.services.sync_service:sync_candidates",
        "trigger": "cron",
        "hour": 2,  # Run at 2 AM daily
        "minute": 0,
    }
]
```

### Job Configuration Options

```env
# Enable/disable scheduler
SCHEDULER_ENABLED=true

# Scheduler type: memory, sqlalchemy, mongodb
SCHEDULER_TYPE=sqlalchemy

# Job execution parameters
SOURCING_JOB_INTERVAL_MINUTES=60
BATCH_SIZE=100
MAX_RETRIES=3
RETRY_BACKOFF_FACTOR=2

# Concurrency
MAX_CONCURRENT_JOBS=5
JOB_TIMEOUT_SECONDS=3600
```

### Available Scheduled Jobs

| Job ID | Purpose | Default Schedule | Parameters |
|--------|---------|-------------------|-----------|
| `sourcing_job` | Run candidate sourcing | Every 60 minutes | `batch_size`, `filters` |
| `candidate_sync_job` | Sync candidates with Core | Daily at 2 AM | `limit`, `date_range` |
| `linkedin_refresh_job` | Refresh LinkedIn tokens | Every 6 hours | `user_id` |
| `cleanup_job` | Clean up old logs/temp data | Weekly Sunday 3 AM | `days_retention` |

### Manual Job Triggering

```bash
# Trigger sourcing job manually
curl -X POST http://localhost:8001/api/v1/jobs/sourcing-job/run \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get job status
curl http://localhost:8001/api/v1/jobs/sourcing-job/status \
  -H "Authorization: Bearer YOUR_TOKEN"

# View scheduled jobs
curl http://localhost:8001/api/v1/jobs/scheduled \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Running the Service

### Start Development Server

```bash
python -m src.main
```

The API will be available at `http://localhost:8001`

### Access API Documentation

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

### Health Check

```bash
curl http://localhost:8001/health
```

### With Docker

```bash
docker build -t talent-finder-sourcing:latest .
docker run -p 8001:8001 \
  --env-file .env \
  talent-finder-sourcing:latest
```

### With Docker Compose

```bash
docker-compose up -d sourcing
docker-compose logs -f sourcing
```

### Start Specific Components

```bash
# Start API server only (no scheduler)
python -m src.main --no-scheduler

# Start scheduler only (no API)
python -m src.main --scheduler-only

# Run in debug mode
python -m src.main --debug
```

## LinkedIn Authentication Setup

### Prerequisites

1. **Create LinkedIn App**
   - Go to https://www.linkedin.com/developers/apps
   - Click "Create app"
   - Fill in app name, company, and app logo
   - Accept terms and create app

2. **Configure OAuth 2.0**
   - In app settings, go to "Auth" tab
   - Add Authorized redirect URLs:
     ```
     http://localhost:8001/auth/linkedin/callback
     https://your-domain.com/auth/linkedin/callback
     ```
   - Note your Client ID and Client Secret

### Environment Setup

Add to `.env`:

```env
LINKEDIN_CLIENT_ID=your-client-id
LINKEDIN_CLIENT_SECRET=your-client-secret
LINKEDIN_REDIRECT_URI=http://localhost:8001/auth/linkedin/callback
```

### Authentication Flow

1. **Request Authorization**
   ```bash
   curl -X GET "http://localhost:8001/api/v1/auth/linkedin/authorize" \
     -H "Authorization: Bearer YOUR_TOKEN"
   # Redirects to LinkedIn login
   ```

2. **Handle Callback**
   - LinkedIn redirects to `/auth/linkedin/callback` with authorization code
   - Service exchanges code for access token
   - Token stored securely in database

3. **Use Access Token**
   ```bash
   curl -X GET "http://localhost:8001/api/v1/candidates/search?job_id=123" \
     -H "Authorization: Bearer YOUR_TOKEN"
   # Uses stored LinkedIn token for API calls
   ```

### Token Management

```python
# Tokens are automatically refreshed
# Check token validity
GET /api/v1/auth/linkedin/status

# Refresh token manually
POST /api/v1/auth/linkedin/refresh

# Revoke access
POST /api/v1/auth/linkedin/revoke
```

### LinkedIn API Scope

Configure required scopes in `src/config/settings.py`:

```python
LINKEDIN_SCOPES = [
    "r_liteprofile",      # Basic profile access
    "r_emailaddress",     # Email permission
    "r_hiring_search",    # Hiring search capability
]
```

## Monitoring and Logging

### Structured Logging

Logs are structured in JSON format for easy parsing:

```json
{
  "timestamp": "2024-03-19T10:30:45.123Z",
  "level": "INFO",
  "service": "sourcing",
  "request_id": "req-123456",
  "user_id": "user-123",
  "message": "Sourcing job started",
  "context": {
    "job_id": "job-456",
    "batch_size": 100
  }
}
```

### Log Levels

```
DEBUG   - Development debugging
INFO    - General information
WARNING - Warning messages
ERROR   - Error conditions
CRITICAL - Critical failures
```

### View Logs

```bash
# Real-time logs
docker-compose logs -f sourcing

# Last 100 lines
docker-compose logs --tail=100 sourcing

# Filter by level
docker-compose logs sourcing | grep ERROR

# Export logs
docker-compose logs sourcing > logs.txt
```

### Metrics Collection

Prometheus metrics are exposed at `/metrics`:

```bash
curl http://localhost:8001/metrics
```

### Key Metrics

| Metric | Description | Type |
|--------|-------------|------|
| `sourcing_jobs_total` | Total sourcing jobs executed | Counter |
| `sourcing_jobs_failed` | Failed sourcing jobs | Counter |
| `candidates_sourced_total` | Total candidates sourced | Counter |
| `sourcing_job_duration_seconds` | Job execution duration | Histogram |
| `api_requests_total` | Total API requests | Counter |
| `api_request_duration_seconds` | API request latency | Histogram |

### Distributed Tracing

Enable Jaeger tracing for request tracing:

```env
JAEGER_ENABLED=true
JAEGER_AGENT_HOST=localhost
JAEGER_AGENT_PORT=6831
```

View traces at: http://localhost:16686

## Troubleshooting

### Service Won't Start

**Problem**: `ERROR: Service failed to start`

**Solution**:
```bash
# Check Python version
python --version  # Should be 3.10+

# Verify dependencies
pip check

# Check port availability
lsof -i :8001

# Kill process on port if needed
kill -9 $(lsof -t -i:8001)
```

### Scheduler Not Running

**Problem**: `Scheduled jobs not executing`

**Solution**:
```bash
# Check if scheduler is enabled
grep "SCHEDULER_ENABLED" .env

# Verify scheduler status
curl http://localhost:8001/api/v1/jobs/scheduler/status

# Check logs for scheduler errors
docker-compose logs sourcing | grep -i scheduler

# Restart with scheduler
python -m src.main --enable-scheduler
```

### LinkedIn Authentication Issues

**Problem**: `401 Unauthorized on LinkedIn API calls`

**Solution**:
```bash
# Verify credentials
grep "LINKEDIN_CLIENT_ID\|LINKEDIN_CLIENT_SECRET" .env

# Check token validity
curl -X GET "http://localhost:8001/api/v1/auth/linkedin/status" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Refresh token
curl -X POST "http://localhost:8001/api/v1/auth/linkedin/refresh" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check OAuth redirect URI matches
# App setting: https://www.linkedin.com/developers/apps
```

### Database Connection Issues

**Problem**: `Connection to PostgreSQL/MongoDB failed`

**Solution**:
```bash
# Test PostgreSQL
psql -U postgres -d sourcing_db -c "SELECT 1"

# Test MongoDB
mongosh --eval "db.adminCommand('ping')"

# Verify connection strings in .env
grep "DATABASE_URL\|MONGODB_URL" .env

# Check database exists
psql -U postgres -lqt | grep sourcing_db
```

### High Memory Usage

**Problem**: `Service consuming excessive memory`

**Solution**:
```bash
# Check process memory
ps aux | grep src.main

# Reduce batch size
BATCH_SIZE=50  # Decreased from 100

# Limit concurrent jobs
MAX_CONCURRENT_JOBS=2

# Monitor memory
docker stats sourcing
```

### API Rate Limiting

**Problem**: `429 Too Many Requests`

**Solution**:
```bash
# Check rate limit configuration
grep "RATE_LIMIT" .env

# Implement backoff in client
import time
time.sleep(2 ** retry_count)  # Exponential backoff
```

### Job Timeout Issues

**Problem**: `Job execution timeout`

**Solution**:
```bash
# Increase timeout
JOB_TIMEOUT_SECONDS=7200  # 2 hours

# Reduce batch size
BATCH_SIZE=50

# Monitor long-running jobs
curl http://localhost:8001/api/v1/jobs/running
```

### Common Errors Reference

| Error | Cause | Solution |
|-------|-------|----------|
| `Connection refused` | Service not running | Start service: `python -m src.main` |
| `Invalid credentials` | Wrong LinkedIn keys | Verify in `.env` and LinkedIn app settings |
| `Token expired` | OAuth token invalid | Refresh token: `POST /auth/linkedin/refresh` |
| `Database locked` | Concurrent write | Check other processes, restart service |
| `Memory error` | Out of memory | Reduce `BATCH_SIZE`, increase `MAX_CONCURRENT_JOBS` |
| `CORS error` | Origin not allowed | Update `CORS_ORIGINS` in `.env` |

### Getting Help

- **API Documentation**: http://localhost:8001/docs
- **Logs**: `docker-compose logs sourcing`
- **Health Status**: `curl http://localhost:8001/health`
- **Scheduler Status**: `curl http://localhost:8001/api/v1/jobs/scheduler/status`
- **Issues**: Create GitHub issue with logs and environment details

## Related Documentation

- [Core Service README](../Talent_Finder_Backend_Core/README.md)
- [API Documentation](http://localhost:8001/docs)
- [LinkedIn API Documentation](https://learn.microsoft.com/en-us/linkedin/shared/api-reference/api-reference)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
