# Talent Finder Backend Sourcing API Documentation

## Base URL

```
http://localhost:8001
https://sourcing.talentfinder.com
```

## Overview

The Talent Finder Backend Sourcing service handles automated candidate sourcing from LinkedIn and other platforms. This service is responsible for:

- Triggering candidate sourcing operations based on job requirements
- Performing dry-run operations to preview sourcing results
- Monitoring service health and readiness
- Scheduling and managing sourcing tasks

## Table of Contents

1. [Authentication](#authentication)
2. [Endpoints](#endpoints)
3. [Error Handling](#error-handling)
4. [Health & Monitoring](#health--monitoring)

## Authentication

The sourcing service requires JWT Bearer token authentication for protected endpoints. Include the token in the Authorization header:

```
Authorization: Bearer <access_token>
```

Tokens must be obtained from the Core Backend service `/api/v1/auth/login` endpoint.

## Endpoints

### Trigger Sourcing Job

```
POST /sourcing/trigger
```

**Description:** Manually trigger a sourcing job to search for candidates on LinkedIn and other platforms.

**Authentication:** Required (Admin or Recruiter)

**Request Body:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "config_id": "550e8400-e29b-41d4-a716-446655440300"
}
```

**Response:** `202 Accepted`
```json
{
  "message": "Sourcing job triggered successfully",
  "source_run_id": "550e8400-e29b-41d4-a716-446655440200",
  "status": "in_progress"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid job_id or config_id
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Job or configuration not found
- `409 Conflict`: Sourcing already in progress for this job
- `500 Internal Server Error`: LinkedIn API error or internal service error

**Process Flow:**
1. Validates job and configuration exist
2. Creates a source_run record with "pending" status
3. Initiates background sourcing task
4. Returns immediately with source_run_id for tracking
5. Client can poll the Core Backend `/api/v1/source-runs/{source_run_id}` endpoint for status updates

**Status Tracking:**
After triggering, monitor progress via Core Backend:
```
GET /api/v1/source-runs/{source_run_id}
```

---

### Dry-Run Sourcing

```
POST /sourcing/trigger/dry-run
```

**Description:** Preview sourcing results without actually creating candidate records. Useful for testing sourcing configurations before execution.

**Authentication:** Required (Admin)

**Request Body:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "config_id": "550e8400-e29b-41d4-a716-446655440300"
}
```

**Response:** `200 OK`
```json
{
  "message": "Dry-run completed successfully",
  "preview": {
    "total_candidates_found": 250,
    "candidates_matching_criteria": 45,
    "sample_candidates": [
      {
        "profile_id": "linkedin_profile_12345",
        "name": "Alice Johnson",
        "title": "Senior Software Engineer",
        "location": "San Francisco, CA",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "experience_years": 8,
        "match_score": 0.92
      },
      {
        "profile_id": "linkedin_profile_12346",
        "name": "Bob Smith",
        "title": "Backend Engineer",
        "location": "Austin, TX",
        "skills": ["Python", "Django", "MySQL"],
        "experience_years": 6,
        "match_score": 0.85
      }
    ],
    "matching_criteria": {
      "required_skills": ["Python", "FastAPI", "PostgreSQL"],
      "location": "United States",
      "experience_level": "senior",
      "min_experience_years": 5
    }
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid job_id or config_id
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: Only admins can run dry-runs
- `404 Not Found`: Job or configuration not found
- `500 Internal Server Error`: LinkedIn API error or internal service error

**Use Cases:**
- Preview number of candidates available before running full sourcing
- Test configuration accuracy before applying to multiple jobs
- Validate skill matching algorithms
- Review sample candidate profiles for quality

---

### Health Check

```
GET /health
```

**Description:** Check if the sourcing service is running and responding to requests.

**Authentication:** Not required

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "service": "Talent Finder Sourcing Service",
  "version": "1.0.0"
}
```

---

### Readiness Check

```
GET /health/ready
```

**Description:** Verify that the sourcing service is fully initialized and ready to handle sourcing requests. This includes database connectivity, external service availability, and scheduler readiness.

**Authentication:** Not required

**Response:** `200 OK`
```json
{
  "status": "ready",
  "database": "connected",
  "linkedin_service": "available",
  "scheduler": "running"
}
```

**When Not Ready:**

```
Status: 503 Service Unavailable
{
  "status": "not_ready",
  "database": "disconnected",
  "linkedin_service": "unavailable",
  "scheduler": "not_started"
}
```

---

## Error Handling

All error responses follow a standard format:

```json
{
  "detail": "Error description",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-03-19T10:30:00Z"
}
```

### Common Errors

#### Invalid Job ID
```
Status: 400 Bad Request
{
  "detail": "Invalid job_id format: must be a valid UUID",
  "error_code": "INVALID_JOB_ID"
}
```

#### Job Not Found
```
Status: 404 Not Found
{
  "detail": "Job with ID 550e8400-e29b-41d4-a716-446655440000 not found",
  "error_code": "JOB_NOT_FOUND"
}
```

#### Configuration Not Found
```
Status: 404 Not Found
{
  "detail": "Sourcing configuration not found",
  "error_code": "CONFIG_NOT_FOUND"
}
```

#### Sourcing Already In Progress
```
Status: 409 Conflict
{
  "detail": "Sourcing is already in progress for this job",
  "error_code": "SOURCING_IN_PROGRESS"
}
```

#### LinkedIn API Error
```
Status: 500 Internal Server Error
{
  "detail": "Failed to connect to LinkedIn API: rate limit exceeded",
  "error_code": "LINKEDIN_API_ERROR"
}
```

#### Database Error
```
Status: 500 Internal Server Error
{
  "detail": "Database connection failed",
  "error_code": "DATABASE_ERROR"
}
```

#### Authorization Error
```
Status: 403 Forbidden
{
  "detail": "You do not have permission to trigger sourcing",
  "error_code": "INSUFFICIENT_PERMISSIONS"
}
```

### Error Response Headers

Error responses may include additional information:
- `X-Error-ID`: Unique identifier for this error instance (useful for support tickets)
- `X-Retry-After`: Seconds to wait before retrying (for 503 errors)
- `X-Request-ID`: Correlation ID for request tracking

---

## Health & Monitoring

### Service Dependency Status

The `/health/ready` endpoint checks:

| Component | Status | Details |
|-----------|--------|---------|
| Database | Connected/Disconnected | PostgreSQL connection status |
| LinkedIn Service | Available/Unavailable | LinkedIn API connectivity |
| Message Queue | Running/Stopped | Background job queue status |
| Scheduler | Running/Stopped | Task scheduler status |
| Cache | Connected/Disconnected | Redis/cache connectivity |

### Monitoring Integration

The service exposes Prometheus metrics at:
```
GET /metrics
```

Key metrics monitored:
- `sourcing_jobs_total` - Total sourcing jobs triggered
- `sourcing_jobs_completed` - Successfully completed sourcing jobs
- `sourcing_jobs_failed` - Failed sourcing operations
- `sourcing_candidates_found` - Total candidates found across all jobs
- `linkedin_api_requests_total` - Calls made to LinkedIn API
- `linkedin_api_errors_total` - Failed LinkedIn API calls
- `sourcing_duration_seconds` - Histogram of sourcing operation durations

---

## Integration with Core Backend

The sourcing service integrates with the Core Backend service:

### Workflow

1. **Trigger Sourcing** (Sourcing Service)
   ```
   POST /sourcing/trigger
   ```
   Creates a source run record

2. **Track Progress** (Core Backend)
   ```
   GET /api/v1/source-runs/{source_run_id}
   ```
   Query status and candidate count

3. **Retrieve Results** (Core Backend)
   ```
   GET /api/v1/sourced-candidates/by-source-run/{source_run_id}
   ```
   Access sourced candidates

### Service-to-Service Communication

The sourcing service makes authenticated calls to the Core Backend:
- Creates/updates source run records
- Fetches job and configuration details
- Stores sourced candidate information
- Updates job posting with shortlist

All inter-service requests use the same JWT authentication mechanism.

---

## Configuration

The sourcing service behavior is controlled by the Sourcing Configuration resource in the Core Backend:

```json
{
  "config_id": "550e8400-e29b-41d4-a716-446655440300",
  "search_skills": ["Python", "FastAPI", "PostgreSQL"],
  "search_location": "United States",
  "search_salary_range": "120000-180000",
  "search_experience_level": "senior",
  "min_experience_years": 5,
  "is_active": true
}
```

Modify configuration via Core Backend:
```
PUT /api/v1/admin/sourcing-config/{config_id}
```

---

## Rate Limiting

The sourcing service implements rate limiting for fair resource usage:

- **Per Job**: Maximum 3 sourcing operations per job per 24 hours
- **Per Organization**: Maximum 10 concurrent sourcing jobs
- **LinkedIn API**: Respects LinkedIn's API rate limits (automatically queues excess requests)

Rate limit information in response headers:
- `X-RateLimit-Limit`: Total operations allowed
- `X-RateLimit-Remaining`: Operations remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Best Practices

1. **Check Health Before Triggering**: Always verify service is ready before triggering sourcing
   ```
   GET /health/ready
   ```

2. **Use Dry-Run First**: Test configurations with dry-run before full execution
   ```
   POST /sourcing/trigger/dry-run
   ```

3. **Poll for Completion**: Monitor source run status via Core Backend
   ```
   GET /api/v1/source-runs/{source_run_id}
   ```
   Poll every 5-10 seconds initially, then decrease frequency

4. **Handle Long Operations**: Sourcing can take 2-30 minutes depending on criteria. Use webhook notifications when available.

5. **Error Recovery**: Implement exponential backoff for retries
   - First retry: 10 seconds
   - Second retry: 30 seconds
   - Third retry: 2 minutes

6. **Monitor LinkedIn Quota**: Check available LinkedIn API quota before initiating sourcing

7. **Update Configurations Regularly**: Refresh sourcing configs based on hiring needs to improve relevance

---

## Examples

### Complete Sourcing Workflow

**Step 1: Check Service Health**
```bash
curl -X GET http://localhost:8001/health/ready
```

**Step 2: Get Job Details**
```bash
curl -X GET http://localhost:8000/api/v1/jobpost/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Step 3: Run Dry-Run**
```bash
curl -X POST http://localhost:8001/sourcing/trigger/dry-run \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "config_id": "550e8400-e29b-41d4-a716-446655440300"
  }'
```

**Step 4: Trigger Full Sourcing**
```bash
curl -X POST http://localhost:8001/sourcing/trigger \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "config_id": "550e8400-e29b-41d4-a716-446655440300"
  }'
```

**Step 5: Monitor Status**
```bash
curl -X GET http://localhost:8000/api/v1/source-runs/550e8400-e29b-41d4-a716-446655440200 \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Step 6: Retrieve Results**
```bash
curl -X GET http://localhost:8000/api/v1/sourced-candidates/by-source-run/550e8400-e29b-41d4-a716-446655440200 \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Status Codes

| Code | Description |
|------|-------------|
| 200 | OK - Request successful |
| 202 | Accepted - Async operation started |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid authentication |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Operation already in progress |
| 503 | Service Unavailable - Service not ready |
| 500 | Internal Server Error - Server error |

---

## Support

For issues or questions regarding the sourcing API:

1. Check `/health/ready` for service status
2. Review error_code in error response
3. Include X-Request-ID in support requests for faster resolution
4. Check sourcing job logs: `/logs/sourcing/<source_run_id>`
