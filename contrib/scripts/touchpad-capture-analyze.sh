#!/usr/bin/env bash
# Summarize platform-touchpad capture JSONL with jq.
#
#   platform-touchpad capture -o /tmp/tp.jsonl --seconds 30
#   contrib/scripts/touchpad-capture-analyze.sh /tmp/tp.jsonl
#
set -euo pipefail

FILE=${1:-}
if [[ -z "${FILE}" || ! -f "${FILE}" ]]; then
	echo "Usage: $0 <capture.jsonl>" >&2
	exit 2
fi
command -v jq >/dev/null || { echo "jq required" >&2; exit 1; }

echo "=== meta ==="
jq -r 'select(.kind=="meta") | "device=\(.device)\nkey=\(.key)\nname=\(.name)\npipeline=\(.pipeline)"' "${FILE}"

echo
echo "=== totals ==="
jq -s '
  map(select(.kind != "meta"))
  | {
      frames: length,
      passed: map(select(.passed)) | length,
      dropped: map(select(.passed|not)) | length,
      typing_armed_frames: map(select(.typing_armed)) | length
    }
' "${FILE}"

echo
echo "=== drops by filter ==="
jq -s '
  map(select(.kind != "meta" and .dropped_by != null))
  | group_by(.dropped_by)
  | map({filter: .[0].dropped_by, count: length})
  | sort_by(-.count)
' "${FILE}"

echo
echo "=== largest jumps among outlier drops (need xy) ==="
jq -s '
  map(select(.dropped_by == "outlier_reject+typing" or .dropped_by == "outlier_reject"))
  | .[0:20]
  | map({t, xy, typing_armed, stages})
' "${FILE}"

echo
echo "=== sample: first 5 drops ==="
jq -c 'select(.kind != "meta" and (.passed|not))' "${FILE}" | head -5

echo
echo "=== jq one-liners ==="
cat <<'EOF'
# count drops while typing_armed
jq -s 'map(select(.typing_armed and (.passed|not)))|length' FILE

# timeline of drop reasons
jq -r 'select(.dropped_by)|"\(.t)\t\(.dropped_by)\t\(.xy)"' FILE

# pass rate
jq -s 'map(select(.kind!="meta"))|(map(select(.passed))|length)/length' FILE
EOF
