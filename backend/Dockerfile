FROM python:3.11-slim

WORKDIR /app

# System dependencies:
#   - gcc / libpq-dev      → asyncpg/psycopg2 (PostgreSQL/Redshift)
#   - unixodbc-dev + msodbcsql18 → pyodbc (SQL Server SQL auth + Azure AD)
#   - libkrb5-dev + krb5-user → asyncpg GSSAPI, motor GSSAPI, ibm_db Kerberos
#   - libgssapi-krb5-2     → motor[gssapi] runtime
#   - curl, gnupg, apt-transport-https → Microsoft repo bootstrap
# Microsoft repo registration is wrapped in an ACCEPT_EULA env so the
# msodbcsql18 install is non-interactive.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
        unixodbc-dev \
        libkrb5-dev \
        krb5-user \
        libgssapi-krb5-2 \
        curl \
        gnupg \
        apt-transport-https \
        ca-certificates \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && DEBIAN_RELEASE=$(awk -F'=' '/^VERSION_CODENAME=/ {print $2}' /etc/os-release) \
    && DEBIAN_VERSION_ID=$(awk -F'=' '/^VERSION_ID=/ {gsub(/"/, ""); print $2}' /etc/os-release) \
    && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/${DEBIAN_VERSION_ID}/prod ${DEBIAN_RELEASE} main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and setuptools first
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Motor GSSAPI extras (pykerberos) need libkrb5-dev at build time — install
# after the apt layer so build deps are present.
RUN pip install --no-cache-dir 'motor[gssapi]' || \
    echo "pykerberos build failed — Mongo GSSAPI auth will surface a clear ImportError at use time"

# Copy application code
COPY . .

# Install the package
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
