#!/bin/bash
# Setup Keycloak realm and client for DataWrangler development
# Run after Keycloak is healthy: ./docker/keycloak/setup-realm.sh

set -e

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
ADMIN_USER="${KEYCLOAK_ADMIN:-admin}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-admin}"
REALM="datawrangler"
CLIENT_ID="datawrangler-app"
CLIENT_SECRET="dev-secret"
REDIRECT_URI="http://localhost:8000/api/v1/auth/sso/callback"

echo "Waiting for Keycloak to be ready..."
# Keycloak 24 dev mode doesn't expose /health/ready — poll master realm instead
until curl -sf "${KEYCLOAK_URL}/realms/master" > /dev/null 2>&1; do
    sleep 2
done
echo "Keycloak is ready."

# Get admin token
TOKEN=$(curl -sf -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
    -d "username=${ADMIN_USER}" \
    -d "password=${ADMIN_PASS}" \
    -d "grant_type=password" \
    -d "client_id=admin-cli" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Admin token obtained."

# Create realm
curl -sf -X POST "${KEYCLOAK_URL}/admin/realms" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"realm\": \"${REALM}\",
        \"enabled\": true,
        \"registrationAllowed\": true
    }" && echo "Realm '${REALM}' created." || echo "Realm may already exist."

# Create client
curl -sf -X POST "${KEYCLOAK_URL}/admin/realms/${REALM}/clients" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"clientId\": \"${CLIENT_ID}\",
        \"enabled\": true,
        \"protocol\": \"openid-connect\",
        \"publicClient\": false,
        \"secret\": \"${CLIENT_SECRET}\",
        \"redirectUris\": [\"${REDIRECT_URI}\", \"http://localhost:3000/*\"],
        \"webOrigins\": [\"http://localhost:3000\", \"http://localhost:8000\"],
        \"standardFlowEnabled\": true,
        \"directAccessGrantsEnabled\": true
    }" && echo "Client '${CLIENT_ID}' created." || echo "Client may already exist."

# Create a test user
curl -sf -X POST "${KEYCLOAK_URL}/admin/realms/${REALM}/users" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"username\": \"testuser\",
        \"email\": \"testuser@ameritas.com\",
        \"firstName\": \"Test\",
        \"lastName\": \"User\",
        \"enabled\": true,
        \"emailVerified\": true,
        \"credentials\": [{
            \"type\": \"password\",
            \"value\": \"testpass\",
            \"temporary\": false
        }]
    }" && echo "Test user 'testuser@ameritas.com' created (password: testpass)." || echo "User may already exist."

echo ""
echo "Keycloak setup complete!"
echo "  Admin console: ${KEYCLOAK_URL}/admin (admin/admin)"
echo "  OIDC discovery: ${KEYCLOAK_URL}/realms/${REALM}/.well-known/openid-configuration"
echo "  Test user: testuser@ameritas.com / testpass"
