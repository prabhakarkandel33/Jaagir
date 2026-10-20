#!/usr/bin/env bash
# Human-readable Kafka outage + recovery demo (scenario A).
#
#   bash scripts/demo_kafka_outage.sh          # fresh e2e stack, then clean up
#   bash scripts/demo_kafka_outage.sh --keep   # leave the stack running
#
# The Python e2e runner does the work; this script narrates the story and
# prints a clear PASS/FAIL line at the end. Run it from the repo root.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
KEEP=""
[[ "${1:-}" == "--keep" ]] && KEEP="--keep"

echo "=============================================================="
echo " Kafka outage demo (scenario A)"
echo "=============================================================="
echo " 1. Start a disposable stack (project jobportal-e2e, own ports)."
echo " 2. Stop Kafka."
echo " 3. Publish, update and close a job through the public API."
echo "    The API must still answer 200; events wait in the outbox."
echo " 4. Check the candidate replica: it must be stale but valid."
echo " 5. Start Kafka again. The relay drains the backlog in order."
echo " 6. Assert both databases agree on (id, version, status)."
echo "=============================================================="
echo

uv run --project backend python e2e/run_e2e.py --scenario A $KEEP
STATUS=$?

echo
if [[ $STATUS -eq 0 ]]; then
  echo "RESULT: PASS - the API stayed available and the replica converged."
else
  echo "RESULT: FAIL - see the scenario output above."
fi
exit $STATUS
