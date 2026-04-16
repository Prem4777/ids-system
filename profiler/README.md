# Packet Profiler (Phase 2)

Capture packets in short windows and send model-compatible feature payloads to the backend `/predict` endpoint.

## Run

```powershell
cd profiler
pip install -r requirements.txt
python packet_profiler.py --api http://127.0.0.1:8000/predict --window-seconds 3
```

Optional interface pinning:

```powershell
python packet_profiler.py --interface "Wi-Fi" --window-seconds 3
```

Notes:

- This profiler maps basic window stats into your model schema to keep requests valid.
- Accuracy depends on how close these derived features are to training-time features.
