#!/usr/bin/env bash
# KavachAI one-click demo: start the API (if needed), run the 15-step demo,
# print the step summary + report paths. Leaves the server running.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PY="$REPO/.venv/bin/python"
UVICORN="$REPO/.venv/bin/uvicorn"
BASE="http://127.0.0.1:8000"

echo "== KavachAI demo =="

# --- start server if not already up ---------------------------------------
if ! curl -sf -m 2 "$BASE/api/v1/health" >/dev/null 2>&1; then
  echo "starting uvicorn on :8000 ..."
  nohup "$UVICORN" backend.app.main:app --host 127.0.0.1 --port 8000 \
    >/tmp/kavach_demo_server.log 2>&1 &
  SRV_PID=$!
  echo "server PID: $SRV_PID (log: /tmp/kavach_demo_server.log)"
else
  SRV_PID="(already running)"
  echo "server already up at $BASE"
fi

# --- wait for health -------------------------------------------------------
for i in $(seq 1 60); do
  if curl -sf -m 2 "$BASE/api/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$i" = "60" ]; then
    echo "ERROR: server did not become healthy" >&2
    exit 1
  fi
done
echo "server healthy."

# --- run the demo -----------------------------------------------------------
echo "running POST /api/v1/demo/run (seed=42) ..."
START=$(date +%s)
curl -sf -m 300 -X POST "$BASE/api/v1/demo/run" \
  -H 'Content-Type: application/json' \
  -d '{"seed": 42}' -o /tmp/kavach_demo_result.json
END=$(date +%s)
echo "demo wall time: $((END - START))s"
echo

# --- print summary -----------------------------------------------------------
"$PY" - <<'EOF'
import json
r = json.load(open("/tmp/kavach_demo_result.json"))
print(f"experiment_id : {r['experiment_id']}")
print(f"report_id     : {r['report_id']}")
print(f"pdf_url       : {r['pdf_url']}")
print()
print(f"{'#':<3}{'step':<58}{'ok':<5}ms")
nok = 0
for i, s in enumerate(r["steps"], 1):
    ok = "OK " if s["ok"] else "FAIL"
    nok += s["ok"]
    print(f"{i:<3}{s['name']:<58}{ok:<5}{s['ms']}")
    if not s["ok"]:
        print(f"    ERROR: {s['detail'].get('error')}")
print()
print(f"steps ok: {nok}/{len(r['steps'])}")
EOF

echo
echo "report JSON: $BASE/api/v1/reports/$( "$PY" -c "import json;print(json.load(open('/tmp/kavach_demo_result.json'))['report_id'])" ).json"
echo "report PDF : $REPO/reports/$( "$PY" -c "import json;print(json.load(open('/tmp/kavach_demo_result.json'))['report_id'])" ).pdf"
echo "server PID note: ${SRV_PID} (left running)"
