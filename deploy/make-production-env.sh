#!/usr/bin/env bash
# Writes /etc/analekh/production.env on the VM: random passwords for Postgres, MinIO and the
# recalc service, plus the values only you can supply (asked for below; secrets are not echoed).
# Holds no secrets itself. Run once on the server:  bash make-production-env.sh
# Re-running asks before replacing the file, because new passwords would not match the Postgres
# and MinIO data volumes created with the old ones.
set -euo pipefail

TARGET=/etc/analekh/production.env
SITE=${SITE_ADDRESS:-137-23-38-71.sslip.io}

if sudo test -e "$TARGET"; then
  read -r -p "$TARGET exists. Replace it with new passwords? [y/N] " answer
  [ "${answer:-N}" = "y" ] || { echo "Left as it is."; exit 0; }
fi

read -r -p "Contact address for NSE requests (From header): " contact
read -r -p "Gmail address that sends reset codes and alerts: " smtp_user
read -r -s -p "Gmail app password (16 letters, no spaces; not shown): " smtp_pass
echo
read -r -s -p "Anthropic API key (Enter to skip; not shown): " anthropic
echo
read -r -p "Address that receives alerts [$smtp_user]: " alert_to
alert_to=${alert_to:-$smtp_user}

# '@' in the user name must be %40 inside the URL.
smtp_user_enc=${smtp_user//@/%40}
pg=$(openssl rand -hex 24)
minio=$(openssl rand -hex 24)
recalc=$(openssl rand -hex 32)

sudo mkdir -p /etc/analekh
sudo tee "$TARGET" > /dev/null <<EOF
ENV=prod
SITE_ADDRESS=$SITE
CORS_ORIGINS=https://$SITE

POSTGRES_USER=app
POSTGRES_PASSWORD=$pg
POSTGRES_DB=analekh
DATABASE_URL=postgresql+psycopg://app:$pg@postgres:5432/analekh
REDIS_URL=redis://valkey:6379/0

MINIO_ROOT_USER=analekh
MINIO_ROOT_PASSWORD=$minio
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=analekh
MINIO_SECRET_KEY=$minio
MINIO_BUCKET=analekh
MINIO_SECURE=false

RECALC_URL=http://recalc:8080
RECALC_TOKEN=$recalc
RECALC_FALLBACK=fail

USER_AGENT=Analekh/0.1
CONTACT_EMAIL=$contact
SMTP_URL=smtp://$smtp_user_enc:$smtp_pass@smtp.gmail.com:587
ALERT_EMAIL_TO=$alert_to
ANTHROPIC_API_KEY=$anthropic
EOF
# The pipeline runs `docker compose` as gitlab-runner, which reads this file: give that group
# read access and nobody else.
sudo chown root:gitlab-runner /etc/analekh "$TARGET"
sudo chmod 750 /etc/analekh
sudo chmod 640 "$TARGET"
echo "Written: $TARGET (readable by root and the gitlab-runner group only)."
