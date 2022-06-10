#!/usr/bin/env bash
set -euo pipefail

python3 seller.py &
SELLER=$!

python3 shipper.py &
SHIPPER=$!

sleep 2
python3 buyer.py &
BUYER=$!

read -n1 -rsp $'Press any key to stop...\n'

kill $SELLER $SHIPPER $BUYER
