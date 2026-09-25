#!/usr/bin/env bash
# Create or update an A record in an IONOS-hosted zone via the IONOS DNS API.
#   bash ops/deploy/ionos_dns.sh elnino.example.com 203.0.113.10
# The API key ("<prefix>.<secret>") is read from ~/.ionos_api_key (chmod 600) or $IONOS_API_KEY.
# It is never printed. Docs: https://developer.hosting.ionos.com/docs/dns
set -euo pipefail
FQDN="${1:?fqdn}"; IP="${2:?ip}"; TTL="${3:-3600}"
KEY="${IONOS_API_KEY:-$(cat "$HOME/.ionos_api_key" 2>/dev/null || true)}"
[ -n "$KEY" ] || { echo "no IONOS API key (~/.ionos_api_key)" >&2; exit 1; }
API=https://api.hosting.ionos.com/dns/v1
h=(-sS -H "X-API-Key: $KEY" -H "Accept: application/json")

zones="$(curl "${h[@]}" "$API/zones")"
zone_json="$(python3 -c '
import json,sys
fqdn=sys.argv[1]; zs=json.loads(sys.stdin.read())
if isinstance(zs,dict): sys.exit("IONOS API error: "+json.dumps(zs)[:300])
best=max((z for z in zs if fqdn==z["name"] or fqdn.endswith("."+z["name"])), key=lambda z: len(z["name"]), default=None)
if not best: sys.exit("no zone for "+fqdn)
print(best["id"]); print(best["name"])' "$FQDN" <<<"$zones")"
ZID="$(sed -n 1p <<<"$zone_json")"; ZNAME="$(sed -n 2p <<<"$zone_json")"
echo "zone $ZNAME"

existing="$(curl "${h[@]}" "$API/zones/$ZID?suffix=$FQDN&recordType=A")"
RID="$(python3 -c '
import json,sys
z=json.loads(sys.stdin.read()); fq=sys.argv[1]
r=[x for x in z.get("records",[]) if x["name"]==fq and x["type"]=="A"]
print(r[0]["id"] if r else ""); print(r[0]["content"] if r else "")' "$FQDN" <<<"$existing")"
cur_id="$(sed -n 1p <<<"$RID")"; cur_ip="$(sed -n 2p <<<"$RID")"

if [ -n "$cur_id" ]; then
  if [ "$cur_ip" = "$IP" ]; then echo "A $FQDN -> $IP already set"; exit 0; fi
  curl "${h[@]}" -X PUT -H "Content-Type: application/json" \
    -d "{\"content\":\"$IP\",\"ttl\":$TTL,\"disabled\":false}" "$API/zones/$ZID/records/$cur_id" >/dev/null
  echo "updated A $FQDN: $cur_ip -> $IP"
else
  curl "${h[@]}" -X POST -H "Content-Type: application/json" \
    -d "[{\"name\":\"$FQDN\",\"type\":\"A\",\"content\":\"$IP\",\"ttl\":$TTL,\"prio\":0,\"disabled\":false}]" \
    "$API/zones/$ZID/records" >/dev/null
  echo "created A $FQDN -> $IP"
fi
