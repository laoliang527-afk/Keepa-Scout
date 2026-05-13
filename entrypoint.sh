#!/bin/sh
# Start ETL in background (logs errors but doesn't block uvicorn)
python -m app.etl &

# Keep uvicorn as the main process (PID 1)
uvicorn app.main:app --host 0.0.0.0 --port 8000
