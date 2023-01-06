#!/bin/bash
# setup.sh

# This file is sourced before the server is started.

SUPS="$(ls $HOME/local/etc/setup_*.sh 2>/dev/null)"
if [ -n "$SUPS" ]; then
  for FIL in $SUPS; do
    echo Sourcing $FIL
    . $FIL
  done
fi
