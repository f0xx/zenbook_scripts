#!/bin/bash
ATTEMPTS=${ATTEMPTS:-3}
SLEEP=${SLEEP:-0.1}
SUDO=${SUDO:-$(which sudo 2>/dev/null)}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIGHTNESS_SCRIPT=${BRIGHTNESS_SCRIPT:-$(which kb-brightness 2>/dev/null)}

[ -z "${BRIGHTNESS_SCRIPT}" ] && BRIGHTNESS_SCRIPT=${SCRIPT_DIR}/brightness.sh
[ -x "${BRIGHTNESS_SCRIPT}" ] || ( logger -s -t "$0" "can't find brightness control script"; exit 1 )

CURRENT=$(${BRIGHTNESS_SCRIPT} get)

trap "${SUDO} ${BRIGHTNESS_SCRIPT} ${CURRENT}" EXIT

LIMITS=$(${BRIGHTNESS_SCRIPT} limits)
HI_LIMIT=$(echo ${LIMITS} | awk '{print $2}')
LO_LIMIT=$(echo ${LIMITS} | awk '{print $1}')

for attempt in $(seq 1 ${ATTEMPTS}); do
  for index in $(seq ${LO_LIMIT} ${HI_LIMIT}); do
    ${SUDO} ${BRIGHTNESS_SCRIPT} ${index} >/dev/null 2>&1
    sleep ${SLEEP}
  done
done

