# DataWrangler Operations Runbook

## Service Architecture

```
[Nginx :80/:443] → [Frontend :3000] (Next.js)
                  → [Backend :8000] (FastAPI + Uvicorn)
                  → [Worker] (Celery)
                  → [Flower :5555] (Celery Monitor)
                  ← [PostgreSQL :5432]
                  ← [Redis :6379]
```

## Log Locations

| Service | Command |
|---------|---------|
| Backend | `docker compose -f docker-compose.prod.yml logs backend` |
| Worker | `docker compose -f docker-compose.prod.yml logs worker` |
| Frontend | `docker compose -f docker-compose.prod.yml logs frontend` |
| Nginx | `docker compose -f docker-compose.prod.yml logs nginx` |
| All (tail) | `docker compose -f docker-compose.prod.yml logs -f --tail=100` |

Backend uses structured JSON logging (structlog). Parse with `jq`:
```bash
docker compose -f docker-compose.prod.yml logs backend | grep '"level":"error"'
```

## Common Issues

### Backend returns 503

**Symptom**: `/api/v1/health` returns `{"status": "unhealthy"}`

**Check**:
```bash
# Is PostgreSQL running?
docker compose -f docker-compose.prod.yml exec postgres pg_isready

# Is Redis running?
docker compose -f docker-compose.prod.yml exec redis redis-cli ping

# Backend logs
docker compose -f docker-compose.prod.yml logs --tail=50 backend
```

**Fix**: Restart the failed dependency, then restart backend:
```bash
docker compose -f docker-compose.prod.yml restart postgres redis backend
```

### Jobs stuck in "pending"

**Symptom**: Jobs created but never start processing.

**Check**:
```bash
# Is the Celery worker running?
docker compose -f docker-compose.prod.yml ps worker

# Worker logs
docker compose -f docker-compose.prod.yml logs --tail=50 worker

# Flower dashboard
open http://server:5555
```

**Fix**:
```bash
docker compose -f docker-compose.prod.yml restart worker
```

### SSO login fails

**Symptom**: Login redirects but callback returns error.

**Check**:
1. Verify OIDC_ISSUER_URL is reachable from the backend container:
   ```bash
   docker compose -f docker-compose.prod.yml exec backend curl -s $OIDC_ISSUER_URL/.well-known/openid-configuration
   ```
2. Verify OIDC_CLIENT_ID and OIDC_CLIENT_SECRET match the IdP configuration
3. Verify callback URL is registered in the IdP: `https://datawrangler.ameritas.com/api/v1/auth/callback`

### Frontend shows blank page

**Check**:
```bash
# Is the frontend container running?
docker compose -f docker-compose.prod.yml ps frontend

# Check Nginx proxy config
docker compose -f docker-compose.prod.yml exec nginx nginx -t
```

**Fix**: Rebuild frontend if Next.js build failed:
```bash
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml restart frontend nginx
```

### Out of memory

**Symptom**: Services crash with OOM errors.

**Check**:
```bash
docker stats --no-stream
```

**Fix**: Increase memory limits in `docker-compose.prod.yml` or add swap:
```bash
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

## Restart Procedures

### Single service restart
```bash
docker compose -f docker-compose.prod.yml restart <service>
```

### Full stack restart
```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Nuclear restart (rebuild everything)
```bash
docker compose -f docker-compose.prod.yml down -v  # WARNING: -v removes volumes (data)
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

## Backup and Restore

### PostgreSQL Backup
```bash
# Backup
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U datawrangler datawrangler > backup_$(date +%Y%m%d_%H%M%S).sql

# Automated daily backup (add to crontab)
# 0 2 * * * cd /opt/datawrangler && docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U datawrangler datawrangler | gzip > /opt/backups/dw_$(date +\%Y\%m\%d).sql.gz
```

### PostgreSQL Restore
```bash
docker compose -f docker-compose.prod.yml exec -T postgres psql -U datawrangler datawrangler < backup.sql
```

## Credential Rotation

### Fernet Key Rotation
```bash
# Generate new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Update .env.prod with new FERNET_KEY
# The backend supports key rotation — old credentials will be re-encrypted on next access

docker compose -f docker-compose.prod.yml restart backend worker
```

### JWT Secret Rotation
```bash
# Update SECRET_KEY in .env.prod with new random value
# WARNING: All active sessions will be invalidated

docker compose -f docker-compose.prod.yml restart backend
```

### Database Password Rotation
```bash
# 1. Update PostgreSQL password
docker compose -f docker-compose.prod.yml exec postgres psql -U datawrangler -c "ALTER USER datawrangler PASSWORD 'new-password';"

# 2. Update POSTGRES_PASSWORD in .env.prod

# 3. Restart backend and worker
docker compose -f docker-compose.prod.yml restart backend worker
```

## Monitoring

### Flower (Celery)
- URL: `http://server:5555`
- Shows: active workers, task queue depth, task success/failure rates
- Alert if: queue depth > 100 or failure rate > 10%

### Health Endpoints
- `/api/v1/health` — Overall system health (DB + Redis)
- `/api/v1/health/ready` — Readiness for traffic

### Key Metrics to Watch
| Metric | Warning | Critical |
|--------|---------|----------|
| API response time (p95) | > 2s | > 5s |
| Celery queue depth | > 50 | > 200 |
| PostgreSQL connections | > 80% max | > 95% max |
| Redis memory | > 75% | > 90% |
| Disk usage | > 80% | > 95% |
| Backend error rate | > 1% | > 5% |

## Contacts

| Role | Contact |
|------|---------|
| Platform team | datawrangler-ops@ameritas.com |
| Security/compliance | security@ameritas.com |
| Infrastructure | infrastructure@ameritas.com |
