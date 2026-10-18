#!/bin/bash
# Clean guest-side app+LLM chain test (no setsid; proper PID kill).
set -u
cd /home/linux1/blackbox
export BLACKBOX_LLM_URL=http://127.0.0.1:38899/narrate
pkill -f 'uvicorn backend.main:app --host 127.0.0.1 --port 8010' 2>/dev/null
sleep 1
nohup .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 > /tmp/app_llm.log 2>&1 &
APP=$!
echo "app_pid=$APP"
i=0
while [ $i -lt 90 ]; do
  if curl -sf http://127.0.0.1:8010/health > /dev/null 2>&1; then break; fi
  i=$((i+1))
  sleep 2
done
echo "health_wait_iters=$i"
T0=$(date +%s)
curl -s -X POST http://127.0.0.1:8010/explain -H 'Content-Type: application/json' -d '{"demo_mode": true}' > /tmp/explain_llm.json
T1=$(date +%s)
echo "explain_wall_s=$((T1-T0))"
python3 - <<'PY'
import json
d = json.load(open('/tmp/explain_llm.json'))
llm = d.get('llm_narrative', {})
print('APP_EXPLAIN available=', llm.get('available'), 'model=', llm.get('model'))
print('latency_ms=', llm.get('latency_ms'))
print('TEXT:', (llm.get('text') or llm.get('reason') or '')[:400])
print('score_unchanged=', d['certificate']['impact_score']['score'])
PY
kill $APP 2>/dev/null
wait $APP 2>/dev/null
echo DONE
