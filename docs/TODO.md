# Project TODO

> Focus: ESP32 node setup, CSI data capture, iotdash pipeline, KIMODO + Chronos training pipeline.
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

## 4. KIMODO + Chronos Training Pipeline

### Architecture Overview

```
STAGE 1 — SYNTHETIC DATA (KIMODO, spatial prior)
  KIMODO text prompts
    → 3D skeleton sequences (SOMA 24 joints)
    → convert: SOMA → COCO 17 keypoints
    → CSI simulator (Fresnel zone / field model)
    → synthetic pairs: { CSI[subcarriers×time], pose[17,3], gesture_label }

STAGE 2 — REAL DATA (ESP32 node)
  ESP32 UDP stream
    → collect-training-data.py (activity-labeled)
    → collect-ground-truth.py (CSI + webcam keypoints synced)
    → real pairs: { CSI[subcarriers×time], camera_keypoints[17,2], gesture_label }

STAGE 3 — TEMPORAL MODELING (Chronos, temporal prior)
  CSI subcarrier amplitude time series (multivariate)
    → Chronos fine-tuned on CSI data
    → learns normal CSI temporal dynamics per gesture/pose
    → outputs: anomaly score, continuity prediction, motion event flag

STAGE 4 — MODEL TRAINING (combined)
  Mixed dataset (synthetic + real, ~50/50 adjustable)
    → CSI Encoder (CNN/Transformer): CSI[128,20] → latent[256]
    → Pose head: latent → 17 keypoints [x,y,z] + confidence
    → Gesture head: latent → gesture class + confidence
    → Residual head: latent → Δ(real − simulated) correction
    → Chronos temporal gate: flags physically implausible sequences
    → export: model.safetensors

STAGE 5 — LIVE INFERENCE
  ESP32 CSI
    → noise pre-filter (phase sanitizer, Hampel filter)
    → Chronos gate: is this CSI temporally plausible? (noise rejection)
    → Encoder → latent
    → Residual correction applied (closes sim→real gap)
    → Pose head → 17 keypoints + confidence
    → Gesture head → gesture class + confidence
    → Physics plausibility check (KIMODO prior): valid human pose?
    → output → iotdash / sensing server API
```

### Why both KIMODO and Chronos

| Tool | Role | What it provides |
|------|------|-----------------|
| KIMODO | Spatial prior | Diverse realistic 3D human motions → simulated CSI at scale |
| Chronos | Temporal prior | Models CSI time series dynamics, rejects noise, flags anomalies |

KIMODO teaches the model what bodies in space look like in CSI.
Chronos teaches the model what valid CSI signals look like over time.
Together they cover both the spatial and temporal dimensions of noise rejection.

---

### Step 1 — Install KIMODO
- [ ] Clone `https://github.com/nv-tlabs/kimodo` (outside this repo)
- [ ] Install PyTorch + CUDA, ProtoMotions (`https://github.com/NVlabs/ProtoMotions`), Mujoco
- [ ] Download SOMA checkpoint from HuggingFace: `nvidia/kimodo-v1` (human/SOMA variant)
- [ ] Add to `.env`:
  ```
  KIMODO_CHECKPOINT_PATH=../kimodo/checkpoints/kimodo-v1-soma.pt
  KIMODO_DEVICE=cuda
  KIMODO_OUTPUT_DIR=data/synthetic/kimodo
  ```

### Step 2 — Install Chronos
- [ ] `pip install chronos-forecasting`
- [ ] Start with `amazon/chronos-t5-small` (46M params) for iteration; upgrade to `chronos-t5-large` (710M) for production
- [ ] Add to `.env`:
  ```
  CHRONOS_MODEL=amazon/chronos-t5-small
  CHRONOS_DEVICE=cuda
  ```

### Step 3 — Generate synthetic motions (KIMODO)
- [ ] Write `scripts/kimodo_generate.py` — calls KIMODO Python API with text prompts, saves 3D skeleton sequences to `data/synthetic/kimodo/`
- [ ] Motion prompts to cover (20–30 minimum): walking, standing, sitting, falling, waving, reaching, lying down

### Step 4 — Skeleton conversion
- [ ] Write `scripts/kimodo_to_coco.py` — SOMA 24 joints → COCO 17 keypoints (same mapping as `collect-ground-truth.py`)
- [ ] Visual sanity check: overlay converted keypoints on a rendered frame

### Step 5 — CSI simulator
- [ ] Write `scripts/csi_simulator.py` — 3D keypoint positions + antenna positions + room geometry → synthetic CSI amplitude matrix
  - Reference: `rust-port/wifi-densepose-rs/crates/wifi-densepose-signal/src/ruvsense/field_model.rs`
  - Reference format: `v1/data/proof/sample_csi_data.json`
- [ ] Validate synthetic CSI distributions against real recordings in `data/recordings/`

### Step 6 — Fine-tune Chronos on CSI data
- [ ] Write `scripts/chronos_finetune.py` — fine-tune Chronos on real CSI recordings
- [ ] Each subcarrier = one channel of a multivariate time series; gesture labels as covariates
- [ ] Export fine-tuned weights to `data/models/chronos-csi-v1/`

### Step 7 — Build paired dataset
- [ ] Write `scripts/kimodo_build_dataset.py` — KIMODO motion → CSI sim → labeled JSONL
- [ ] Output to `data/synthetic/kimodo-paired/`, target 10,000+ frames
- [ ] Combine with real data from `data/recordings/` + `data/ground-truth/`; keep `source` field

### Step 8 — Train the model
- [ ] Architecture:
  - CSI Encoder (CNN or Transformer): `CSI[128,20]` → `latent[256]`
  - Pose head: `latent` → `17 × [x,y,z,conf]`
  - Gesture head: `latent` → `(gesture_class, confidence)`
  - Residual head: `latent` → `Δ` sim-to-real correction
  - Chronos gate: pre-filter on temporal anomaly score
- [ ] Target: PCK@20 ≥ 35% (current baseline: 2.5%)
- [ ] Export: `data/models/wiflow-kimodo-v1.safetensors`

### Step 9 — Live inference integration
- [ ] Wire trained model into sensing server inference path
- [ ] Chronos gate runs first (fast) — rejects noise frames before encoder
- [ ] Residual correction applied in encoder forward pass
- [ ] Physics plausibility check rejects poses outside KIMODO human motion space
- [ ] Stream results to iotdash + sensing server API

### Dependencies (`requirements-train.txt`)
```
torch>=2.0
torchvision
chronos-forecasting
mediapipe>=0.10
opencv-python
numpy
scipy
# KIMODO: pip install -e ../kimodo
```

---

## 5. Future Ideas

- [ ] Multi-node CSI — two ESP32-S3 nodes simultaneously for stereo/multistatic sensing
- [ ] Semi-supervised loop — auto-label live CSI using trained model, feed back into training set
- [ ] Publish fork-trained model to HuggingFace alongside existing `wiflow-v1/`
- [ ] iotdash custom widgets for CSI spectrogram and subcarrier heatmap
- [ ] Fine-tune KIMODO on domain-specific motions (hospital/care/security scenarios)
- [ ] Replace Chronos with a CSI-native foundation model once enough data is collected
