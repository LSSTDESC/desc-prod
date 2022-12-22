# setup.sh

# This file is sourced before the server is started.

for FIL in $HOME/data/etc/setup_*.sh; do
  echo Sourcing $FIL
  . $FIL
done
