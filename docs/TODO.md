# Project TODO

> Focus: ESP32 node setup, CSI data capture, iotdash pipeline, KIMODO training pipeline.
> Last updated: 2026-04-22

---

## 1. Node Configuration (ESP32)

- [ ] Flash latest firmware (`v0.6.2-esp32`) to ESP32-S3 on COM7
- [ ] Provision WiFi credentials via `firmware/esp32-csi-node/provision.py --port COM7 --ssid <ssid> --password <pw> --target-ip <sensing-server-ip>`
- [ ] Verify node is streaming CSI packets — monitor serial output: `python -m serial.tools.miniterm COM7 115200`
- [ ] Confirm UDP packets arriving at sensing server port (default 5006): `python scripts/record-csi-udp.py --port 5006`
- [ ] Set antenna positions in `.env` (`CSI_SIM_TX_POS`, `CSI_SIM_RX_POS`) to match physical placement in the room
- [ ] Set room dimensions in `.env` (`CSI_SIM_ROOM_DIM`) for CSI simulation accuracy

---

## 2. CSI Data Capture

- [ ] Run `scripts/collect-training-data.py` to record labeled CSI sessions for each activity:
  - `--label walking --duration 60`
  - `--label standing --duration 60`
  - `--label sitting --duration 60`
  - `--label falling --duration 30`
  - `--label waving --duration 30`
- [ ] Run `scripts/collect-ground-truth.py` with webcam open to capture camera-synchronized keypoints (MediaPipe) alongside CSI — saves paired data to `data/ground-truth/`
- [ ] Verify recordings saved correctly to `data/recordings/*.csi.jsonl` — each frame should have subcarrier amplitudes, RSSI, timestamp, and node ID
- [ ] Generate dataset manifest: `python scripts/collect-training-data.py --manifest-only --output-dir data/recordings`
- [ ] Target: at minimum 5 recordings per activity before training

---

## 3. iotdash Pipeline

The README describes this pipeline but the key files **do not exist yet**.

### Files to create
- [ ] `client/device_client.py` — unified client supporting ESP32 + other device types with mDNS auto-discovery
- [ ] `backend/discovery/mqtt_listener.py` — subscribes to MQTT topics and bridges incoming device metrics to the sensing server WebSocket

### Configuration
- [ ] Install and run an MQTT broker (Mosquitto recommended): `brew install mosquitto && brew services start mosquitto`
- [ ] Add to `.env`:
  ```
  MQTT_BROKER_HOST=localhost
  MQTT_BROKER_PORT=1883
  MQTT_USERNAME=
  MQTT_PASSWORD=
  MQTT_TLS_ENABLED=false
  MQTT_TOPIC_PREFIX=wifi-densepose
  ```
- [ ] Define MQTT topic scheme: `wifi-densepose/<node-id>/metrics` and `wifi-densepose/<node-id>/csi`
- [ ] Wire `mqtt_listener.py` output → sensing server WebSocket so the iotdash dashboard receives live CSI frames
- [ ] Confirm mDNS discovery works (or falls back to direct IP when AP isolation is on)
- [ ] Update `.env.example` with all MQTT vars

### Smoke test
- [ ] End-to-end: ESP32 powers on → publishes to MQTT → `mqtt_listener.py` receives → sensing server WS → iotdash dashboard shows live spectrogram

---

## 4. KIMODO Training Pipeline

**Goal:** Use NVIDIA KIMODO to generate synthetic 3D human motion sequences, simulate matching CSI signals, and train WiFlow to 35%+ PCK@20 (currently 2.5% without ground-truth labels).

```
KIMODO (text prompt) → 3D skeleton (SOMA joints)
    → convert: SOMA 24 joints → COCO 17 keypoints
    → CSI simulator: 3D body position → synthetic CSI amplitudes
    → paired dataset: { csi_window[128,20], keypoints[17,2] }
    → WiFlow supervised training
```

### Step 1 — Install KIMODO
- [ ] Clone `https://github.com/nv-tlabs/kimodo` (outside this repo)
- [ ] Install dependencies — requires PyTorch + CUDA, ProtoMotions (`https://github.com/NVlabs/ProtoMotions`), Mujoco
- [ ] Download SOMA checkpoint from HuggingFace: `nvidia/kimodo-v1` (use the human/SOMA variant, not G1 robot)
- [ ] Add to `.env`:
  ```
  KIMODO_CHECKPOINT_PATH=../kimodo/checkpoints/kimodo-v1-soma.pt
  KIMODO_DEVICE=cuda
  KIMODO_OUTPUT_DIR=data/synthetic/kimodo
  ```

### Step 2 — Generate synthetic motions
- [ ] Write `scripts/kimodo_generate.py` — calls KIMODO Python API with text prompts and saves 3D skeleton frame sequences to `data/synthetic/kimodo/` as JSONL
- [ ] Define motion prompts (at least 20–30):
  - walking forward/backward, turning
  - standing still, shifting weight
  - sitting down, standing up
  - raising arms, waving, reaching
  - falling, stumbling
  - lying down

### Step 3 — Skeleton format conversion
- [ ] Write `scripts/kimodo_to_coco.py` — converts SOMA 24-joint output → 17 COCO keypoints (same mapping as `collect-ground-truth.py`)
- [ ] Visual sanity check: overlay converted keypoints on a rendered frame to confirm joints land in the right places

### Step 4 — CSI simulator
- [ ] Write `scripts/csi_simulator.py` — takes 3D keypoint positions + antenna positions + room geometry, outputs synthetic CSI amplitude matrix `[subcarriers × time]` using the Fresnel zone model
  - Reference: `rust-port/wifi-densepose-rs/crates/wifi-densepose-signal/src/ruvsense/field_model.rs`
  - Reference format: `v1/data/proof/sample_csi_data.json`
- [ ] Validate: compare synthetic CSI distributions against real recordings in `data/recordings/` (check amplitude range, subcarrier variance)

### Step 5 — Build paired dataset
- [ ] Write `scripts/kimodo_build_dataset.py` — orchestrates steps 2–4, outputs `{ csi_window, keypoints, confidence, source: "synthetic" }` to `data/synthetic/kimodo-paired/`
- [ ] Target: 10,000+ synthetic paired frames
- [ ] Mix real + synthetic: combine with `data/recordings/` and `data/ground-truth/`; keep `source` field so you can ablate

### Step 6 — Train WiFlow
- [ ] Feed combined dataset into supervised training pipeline (ADR-079)
- [ ] Add `--synthetic-weight` flag (start at 0.3–0.5 since real data is higher fidelity)
- [ ] Evaluate PCK@20 — target ≥ 35%
- [ ] Export to `data/models/wiflow-kimodo-v1.safetensors`

### Dependencies (add to `requirements-train.txt`)
```
torch>=2.0
torchvision
mediapipe>=0.10
opencv-python
numpy
scipy
# KIMODO: pip install -e ../kimodo
```

---

## 5. Future Ideas

- [ ] Multi-node CSI capture — run two ESP32-S3 nodes simultaneously for stereo/multistatic sensing
- [ ] Fine-tune KIMODO itself on domain-specific motions (e.g. hospital/care scenarios) using BONES-SEED as base
- [ ] Auto-label live CSI recordings using the trained WiFlow model (semi-supervised loop)
- [ ] Publish fork-trained model to HuggingFace `ruv/ruview` alongside existing `wiflow-v1/`
- [ ] iotdash dashboard custom widgets for CSI spectrogram and subcarrier heatmap
