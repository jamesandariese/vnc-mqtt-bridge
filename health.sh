#!/bin/sh

DT=$(date +%s)
CT=$(stat -c %Z capture.time)

if [ $(( DT - CT )) -gt $(( ${HEALTH_MULTIPLIER-60} * INTERVAL )) ];then
    echo bad
    false
else
    echo good
    true
fi
