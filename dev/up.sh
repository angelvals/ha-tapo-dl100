#!/usr/bin/env bash
# Start a throwaway Home Assistant with this integration and add the lock.
# First run onboards HA (user dev / password devdevdev) and adds the lock from
# .env. Later runs just start the container. dev/down.sh stops it and wipes it.
set -euo pipefail
cd "$(dirname "$0")"
HA=http://localhost:8123
CID="$HA/"

env_file=""
for f in ../.env ../../.env; do [[ -f $f ]] && { env_file=$f; break; }; done
[[ -n $env_file ]] || { echo "No .env found in the repo or its parent (TAPO_USERNAME, TAPO_PASSWORD, TAPO_LOCK_IP)"; exit 1; }
set -a; source "$env_file"; set +a

mkdir -p config
docker compose up -d >/dev/null
printf "Waiting for Home Assistant"
until curl -sf -o /dev/null "$HA/api/onboarding" 2>/dev/null || curl -sf -o /dev/null "$HA/manifest.json"; do printf .; sleep 2; done; echo

json() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }

if [[ -f config/.storage/onboarding ]] && grep -q '"user"' config/.storage/onboarding; then
  echo "Already set up. Open $HA (dev / devdevdev)."; exit 0
fi

code=$(curl -sf -X POST "$HA/api/onboarding/users" -H 'Content-Type: application/json' \
  -d "{\"client_id\":\"$CID\",\"name\":\"Dev\",\"username\":\"dev\",\"password\":\"devdevdev\",\"language\":\"en\"}" | json '["auth_code"]')
token=$(curl -sf -X POST "$HA/auth/token" -d "grant_type=authorization_code&code=$code&client_id=$CID" | json '["access_token"]')
auth=(-H "Authorization: Bearer $token" -H 'Content-Type: application/json')
curl -sf -X POST "$HA/api/onboarding/core_config" "${auth[@]}" -d '{}' >/dev/null
curl -sf -X POST "$HA/api/onboarding/analytics" "${auth[@]}" -d '{}' >/dev/null
curl -sf -X POST "$HA/api/onboarding/integration" "${auth[@]}" -d "{\"client_id\":\"$CID\",\"redirect_uri\":\"${HA}/?auth_callback=1\"}" >/dev/null

flow=$(curl -sf -X POST "$HA/api/config/config_entries/flow" "${auth[@]}" -d '{"handler":"tapo_dl100"}' | json '["flow_id"]')
body=$(TAPO_LOCK_NAME="${TAPO_LOCK_NAME:-Front Door}" python3 -c 'import json,os; print(json.dumps({"name":os.environ["TAPO_LOCK_NAME"],"ip":os.environ["TAPO_LOCK_IP"],"cloud_username":os.environ["TAPO_USERNAME"],"cloud_password":os.environ["TAPO_PASSWORD"],"poll_seconds":300}))')
result=$(curl -s -X POST "$HA/api/config/config_entries/flow/$flow" "${auth[@]}" -d "$body")
echo "$result" | python3 -c 'import json,sys; r=json.load(sys.stdin); print("Add lock:", r.get("type"), r.get("errors") or r.get("title",""))'
echo "$token" > config/.dev_token
echo "Open $HA (dev / devdevdev). API token for scripts is in dev/config/.dev_token."
