# Run from repo root: .\start-backend.ps1
Set-Location "$PSScriptRoot\backend"
& ".venv\Scripts\uvicorn" main:app --reload --host 127.0.0.1 --port 8000
