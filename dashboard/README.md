# IDS Dashboard

Streamlit dashboard for read-only live IDS monitoring.

## Features

- Health and metrics cards
- Live latest detection status (Normal/Attack + attack type + confidence)
- Live event table and class distribution chart
- Auto-refresh controls in sidebar
- No manual model testing inputs

## Local Run

```powershell
cd dashboard
pip install -r requirements.txt
$env:IDS_API_BASE_URL="http://127.0.0.1:8000"
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 5000
```

Recommended (explicit venv interpreter):

```powershell
cd "c:/Users/premg/OneDrive/Desktop/IDS project/dashboard"
& "c:/Users/premg/OneDrive/Desktop/IDS project/.venv/Scripts/python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 5000
```
