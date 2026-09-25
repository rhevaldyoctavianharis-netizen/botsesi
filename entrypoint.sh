#!/bin/bash
set -e

echo "🚀 Menjalankan main.py dan cpm1.py..."

python main.py &
PID1=$!

python cpm1.py &
PID2=$!

# Berhenti begitu salah satu proses mati/crash, supaya Render
# mendeteksi container exit dan me-restart keduanya bersamaan.
wait -n "$PID1" "$PID2"
EXIT_CODE=$?

kill "$PID1" "$PID2" 2>/dev/null || true
exit $EXIT_CODE
