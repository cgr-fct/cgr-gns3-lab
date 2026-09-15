#!/bin/bash
# Raw NVUE REST API calls with curl - run from the netauto station.
#   ./curl_examples.sh sw1            (device name from inventory.yml, or an IP)
set -e
DEV=${1:-sw1}
HOST=$(python3 -c "import yaml,sys; d=yaml.safe_load(open('inventory.yml'))['devices']; print(d.get('$DEV',{}).get('host','$DEV'))")
PASS=${CGR_PASSWORD:-CumulusLab1!}
API="https://$HOST:8765/nvue_v1"
C="curl -sk -u cumulus:$PASS -H Content-Type:application/json"

echo "### 1. GET the applied configuration of the system object"
$C "$API/system?rev=applied&filled=false" | jq .

echo "### 2. GET operational state of all interfaces (names + oper status)"
$C "$API/interface" | jq 'to_entries[] | {name: .key, state: .value.link.state?}' 2>/dev/null | head -40

echo "### 3. Create a new revision (changeset)"
REV=$($C -X POST "$API/revision" | jq -r 'keys[0]')
REV_URL=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$REV")
echo "revision: $REV"

echo "### 4. Stage a change in that revision (PATCH = merge)"
$C -X PATCH "$API/system/message?rev=$REV_URL" \
   -d '{"pre-login": "CGR lab - configured over the NVUE REST API"}' | jq .

echo "### 5. Apply the revision (like: nv config apply -y)"
$C -X PATCH "$API/revision/$REV_URL" \
   -d '{"state": "apply", "auto-prompt": {"ays": "ays_yes"}}' | jq .

echo "### 6. Check the revision state (repeat until 'applied')"
for _ in $(seq 1 20); do
  STATE=$($C "$API/revision/$REV_URL" | jq -r .state)
  echo "  state: $STATE"; [ "$STATE" = "applied" ] && break; sleep 2
done

echo "### 7. Read it back"
$C "$API/system/message?rev=applied" | jq .
