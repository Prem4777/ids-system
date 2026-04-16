# Two-Stage IoT Intrusion Detection System (IDS)

## Project Summary

This repository contains a complete IDS pipeline for IoT traffic using a two-stage ML architecture:

1. Stage 1 model for high-frequency attack classes
2. Stage 2 model for rare/long-tail classes routed through an "Other" branch
3. API + dashboard + packet profiler + traffic simulation for end-to-end validation

The project also includes notebooks, pretrained artifacts, and an ESP32 client for Phase 3 style hardware integration.

## Repository Structure

```
.
|- backend/            # FastAPI inference service
|- dashboard/          # Streamlit monitoring UI
|- data/               # Train/test/validation datasets
|- esp32/              # ESP32 client sketch
|- figures/            # Architecture and paper figures
|- models/             # Trained model artifacts and metadata
|- notebooks/          # Training/inference notebooks
|- profiler/           # Live packet feature extraction + API calls
|- scripts/            # Stack start/stop scripts
|- simulation/         # Attack/normal traffic generators
|- IDS_Research_Paper.tex
|- references.bib
'- README.md
```

## Prerequisites

- Windows 10/11 (PowerShell examples below), Linux/macOS also supported with equivalent commands
- Python 3.10+ recommended
- Git
- Optional for simulation/hardware phases:
  - Wireshark/Npcap (packet capture)
  - ESP32 board + Arduino IDE

## Quick Setup

### 1) Clone and enter project

```powershell
git clone <YOUR_GITHUB_REPO_URL>
cd "IDS project"
```

### 2) Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Install dependencies

```powershell
pip install -r requirements.txt
```

If you want per-service installs instead:

```powershell
pip install -r backend/requirements.txt
pip install -r dashboard/requirements.txt
pip install -r profiler/requirements.txt
```

### 4) Download datasets (required)

CSV files are intentionally not committed to this repository.

1. Download the required CSV files from your source (Kaggle, TON_IoT source, or your internal dataset storage).
2. Place each file in the exact location documented in `data/DATASET_LAYOUT.md`.
3. Keep file names unchanged so notebooks and services work without path edits.

### 5) Download model artifacts (required for inference)

Model files are intentionally not committed to this repository.

1. Download pretrained model artifacts from your storage/release location, or train models locally using notebooks.
2. Place model files in the exact paths documented in `models/MODEL_LAYOUT.md`.
3. Keep filenames unchanged so backend and notebooks resolve paths correctly.

### 6) Start local stack

```powershell
cd scripts
.\start_stack.ps1
```

Default endpoints:

- Backend API: `http://127.0.0.1:8000`
- Dashboard: `http://127.0.0.1:5000`

Stop services:

```powershell
cd scripts
.\stop_stack.ps1
```

## Project Phases

## Phase 1: Data and Model Development

Goal: train and evaluate the two-stage IDS model.

1. Use datasets in `data/`.
2. Run notebooks in `notebooks/` (recommended order):
   - `ton_iot_main_model_training.ipynb`
   - `ids_two_stage_training.ipynb`
   - `ton_iot_inference.ipynb`
3. Export model artifacts to `models/ton_iot/`.
4. Validate metrics on `data/test.csv` and `data/validation.csv`.

Expected output:

- Stage 1 + Stage 2 model artifacts (`.joblib`)
- Metadata and label encoder files

## Phase 2: System Integration and Traffic Validation

Goal: run inference as a service and validate using generated traffic.

1. Start API + dashboard using `scripts/start_stack.ps1`.
2. Generate traffic from `simulation/`:
   - `normal_traffic.py`
   - `slow_traffic.py`
   - `burst_traffic.py`
   - `scan_traffic.py`
   - `run_scenario.ps1` / `run_multi_attack.ps1`
3. Run packet profiler:

```powershell
cd profiler
python packet_profiler.py --api http://127.0.0.1:8000/predict --window-seconds 3
```

4. Confirm API responses and dashboard attack labeling in real time.

Expected output:

- End-to-end detection visibility (traffic -> profiler -> API -> dashboard)
- Baseline integration metrics and behavior logs

## Phase 3: Edge/IoT Device Integration (ESP32)

Goal: connect device-side telemetry or client traffic to IDS workflow.

1. Open `esp32/phase3_sensor_client.ino` in Arduino IDE.
2. Configure Wi-Fi credentials and backend endpoint.
3. Flash firmware to ESP32.
4. Run backend stack and verify device data/events are processed.

Expected output:

- Device-connected IDS demonstration
- Foundation for real deployment and alerting extensions

## Running Components Individually

### Backend

```powershell
cd backend
pip install -r requirements.txt
python app.py
```

### Dashboard

```powershell
cd dashboard
pip install -r requirements.txt
streamlit run app.py --server.port 5000
```

### Profiler

```powershell
cd profiler
pip install -r requirements.txt
python packet_profiler.py --api http://127.0.0.1:8000/predict --window-seconds 3
```

## Notes

- Keep model files under `models/ton_iot/` in sync with backend loading logic.
- If a notebook fails with JSON escaping issues, convert single backslashes in paths (for example `..\folder`).
- For reproducibility, run notebooks with fixed seeds and save updated metadata files.

## License

Add your preferred license information here (MIT/Apache-2.0/etc.).
