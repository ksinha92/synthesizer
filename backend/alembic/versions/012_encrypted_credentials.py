"""Encrypt existing plaintext credentials with Fernet.

Revision ID: 012
Revises: 011

IMPORTANT: Set FERNET_KEY env var before running. Back up database first.
This migration encrypts all existing plaintext connection credentials.
"""

import json
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "012"
down_revision = "011"


def upgrade() -> None:
    fernet_key = os.environ.get("FERNET_KEY", "")
    if not fernet_key:
        print("WARNING: FERNET_KEY not set — skipping credential encryption. Set FERNET_KEY and re-run.")
        return

    from cryptography.fernet import Fernet
    f = Fernet(fernet_key.encode())

    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id, credentials FROM connections"))
    rows = result.fetchall()

    encrypted_count = 0
    for row in rows:
        creds = row[1]
        if creds and "_encrypted" not in (creds if isinstance(creds, dict) else {}):
            # Verify first row decrypts (safety check)
            if encrypted_count == 0:
                plaintext = json.dumps(creds).encode()
                ct = f.encrypt(plaintext)
                # Verify round-trip
                assert json.loads(f.decrypt(ct)) == creds, "Round-trip verification failed!"

            plaintext = json.dumps(creds).encode()
            ciphertext = f.encrypt(plaintext).decode()
            new_creds = json.dumps({"_encrypted": ciphertext})
            conn.execute(sa.text("UPDATE connections SET credentials = :creds WHERE id = :id"), {"creds": new_creds, "id": row[0]})
            encrypted_count += 1

    print(f"Encrypted {encrypted_count} connection credentials.")


def downgrade() -> None:
    # Cannot downgrade without the key — credentials would be lost
    print("WARNING: Cannot downgrade encrypted credentials. Restore from backup if needed.")
