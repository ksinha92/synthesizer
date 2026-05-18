# DataWrangler Deployment Guide

## Prerequisites

- Docker 24+ and Docker Compose v2
- Linux VM (Ubuntu 22.04+ recommended) with 8GB+ RAM, 4+ CPU cores
- Domain name with DNS pointing to server IP
- TLS certificate (Let's Encrypt or corporate CA)
- OIDC/SAML provider configured (Okta, Azure AD, or Keycloak)
- PostgreSQL 16 (included in Docker Compose, or use external RDS)

## 1. Clone and Configure

```bash
git clone <repo-url> /opt/datawrangler
cd /opt/datawrangler

# Copy and edit production environment
cp .env.example .env.prod
```

### Required `.env.prod` Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | Database password | `<strong random 32+ chars>` |
| `SECRET_KEY` | JWT signing key | `<strong random 64+ chars>` |
| `FERNET_KEY` | Credential encryption key | Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `OIDC_CLIENT_ID` | OIDC provider client ID | From your IdP |
| `OIDC_CLIENT_SECRET` | OIDC provider client secret | From your IdP |
| `OIDC_ISSUER_URL` | OIDC issuer URL | `https://ameritas.okta.com/oauth2/default` |
| `CLAUDE_API_KEY` | Anthropic API key (optional) | `sk-ant-...` |
| `ALLOWED_ORIGINS` | CORS origins | `https://datawrangler.ameritas.com` |

## 2. TLS Setup

Place your TLS certificate and key in the nginx directory:

```bash
cp /path/to/cert.pem docker/nginx/ssl/cert.pem
cp /path/to/key.pem docker/nginx/ssl/key.pem
```

Update `docker/nginx/nginx.conf` to enable the SSL server block.

## 3. Build and Deploy

```bash
# Build all images
docker compose -f docker-compose.prod.yml build

# Run database migrations
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# Start all services
docker compose -f docker-compose.prod.yml up -d

# Verify all services are healthy
docker compose -f docker-compose.prod.yml ps
```

All services should show "healthy" status within 30 seconds.

## 4. Keycloak Setup (if using local Keycloak)

```bash
# Run the realm setup script
docker compose -f docker-compose.prod.yml exec keycloak /opt/keycloak/setup-realm.sh
```

Skip this step if using Okta or Azure AD.

## 5. Verify Deployment

```bash
# Health check
curl -s https://datawrangler.ameritas.com/api/v1/health | jq .

# Expected: {"status": "healthy", "database": "ok", "redis": "ok"}

# Readiness check
curl -s https://datawrangler.ameritas.com/api/v1/health/ready | jq .

# Frontend loads
curl -s -o /dev/null -w "%{http_code}" https://datawrangler.ameritas.com
# Expected: 200
```

## 6. Post-Deployment Checklist

- [ ] All 7 services running and healthy (`docker compose ps`)
- [ ] Health endpoint returns 200
- [ ] Frontend loads with correct theme
- [ ] SSO login redirects to identity provider
- [ ] SSO callback creates session
- [ ] Can create a project
- [ ] Can add a connection and test it
- [ ] Celery worker processes jobs (check Flower at :5555)
- [ ] Nginx serves HTTPS correctly

## Updating

```bash
cd /opt/datawrangler
git pull origin main
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
```

## Rollback

```bash
# Stop current version
docker compose -f docker-compose.prod.yml down

# Checkout previous version
git checkout <previous-tag>

# Rebuild and restart
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend alembic downgrade -1
docker compose -f docker-compose.prod.yml up -d
```
