# WiFi-DensePose — Project TODO

> Last updated: 2026-05-04

---

## Status legend

- `[x]` Done
- `[ ]` Not started
- `[~]` In progress / partially done

---

## 1. Node setup and data capture

- [x] Flash firmware to ESP32-S3 (`make node-flash`)
- [x] Interactive WiFi provisioning (`make node-setup` — auto-detects port + IP)
- [x] Live terminal dashboard (`make node-live` — frame rate, RSSI bar, health)
- [x] CSI accuracy validator (`make node-validate` — 5s UDP capture + health report)
- [x] ADR-018 binary packet parser (magic number check, freq→channel, proper 20-byte header)
- [ ] Confirm UDP packets arriving at sensing server: `make node-validate`
- [ ] Set antenna positions in `.env` (`CSI_SIM_TX_POS`, `CSI_SIM_RX_POS`)
- [ ] Set room dimensions in `.env` (`CSI_SIM_ROOM_DIM`)

---

## 2. CSI data collection

- [x] `scripts/collect-training-data.py` — labeled activity recording
- [x] `scripts/collect-ground-truth.py` — CSI + MediaPipe keypoints synced
- [ ] Record at least 5 sessions per activity:
  - `--label walking --duration 60`
  - `--label standing --duration 60`
  - `--label sitting --duration 60`
  - `--label falling --duration 30`
  - `--label waving --duration 30`
- [ ] Verify JSONL frames have: subcarrier amplitudes, RSSI, timestamp, node_id
- [ ] Generate dataset manifest: `python scripts/collect-training-data.py --manifest-only`

---

## 3. KIMODO + Chronos training pipeline

### Architecture

```
STAGE 1 — SYNTHETIC (KIMODO, spatial prior)
  Text prompts → 3D skeletons (SOMA 24 joints) → COCO 17 keypoints
  → CSI simulator → synthetic {CSI[subcarriers×time], pose[17,3], label}

STAGE 2 — REAL (ESP32)
  UDP stream → collect-training-data.py + collect-ground-truth.py
  → real {CSI[subcarriers×time], keypoints[17,2], label}

STAGE 3 — TEMPORAL GATE (Chronos)
  CSI subcarrier time series → fine-tuned Chronos
  → anomaly score, motion event flag

STAGE 4 — TRAINING
  Mixed dataset (50/50 synthetic + real)
  CSI Encoder → Pose head (17 keypoints) + Gesture head + Residual head
  Chronos gate: reject noise frames before encoder
  Target: PCK@20 ≥ 35%  |  export: data/models/wiflow-kimodo-v1.safetensors

STAGE 5 — LIVE INFERENCE
  CSI → Chronos gate → Encoder → Residual correction → Pose + Gesture
  Physics plausibility check (KIMODO prior) → API / iotdash
```

### Step-by-step

- [ ] **Install KIMODO** — clone `github.com/nv-tlabs/kimodo`, install PyTorch + CUDA, ProtoMotions, Mujoco, download `nvidia/kimodo-v1` checkpoint
- [ ] **Install Chronos** — `pip install chronos-forecasting`, start with `amazon/chronos-t5-small`
- [ ] **Write `scripts/kimodo_generate.py`** — call KIMODO API with motion prompts, save 3D skeleton sequences to `data/synthetic/kimodo/`
- [ ] **Write `scripts/kimodo_to_coco.py`** — SOMA 24 joints → COCO 17 keypoints
- [ ] **Write `scripts/csi_simulator.py`** — 3D keypoints + antenna positions + room geometry → synthetic CSI amplitude matrix (reference: `rust-port/.../field_model.rs`)
- [ ] **Write `scripts/chronos_finetune.py`** — fine-tune Chronos on real CSI recordings; each subcarrier = one time-series channel; export to `data/models/chronos-csi-v1/`
- [ ] **Write `scripts/kimodo_build_dataset.py`** — KIMODO motions → CSI sim → labeled JSONL; target 10,000+ frames in `data/synthetic/kimodo-paired/`
- [ ] **Train model** — CSI Encoder + Pose + Gesture + Residual + Chronos gate; export `data/models/wiflow-kimodo-v1.safetensors`
- [ ] **Wire live inference** — Chronos gate → Encoder → Residual correction → sensing server API → iotdash

---

## 4. iotdash MQTT integration

- [ ] Install Mosquitto: `brew install mosquitto && brew services start mosquitto`
- [ ] Write `client/device_client.py` — unified ESP32 + mDNS auto-discovery client
- [ ] Write `backend/discovery/mqtt_listener.py` — MQTT → sensing server WebSocket bridge
- [ ] Add MQTT vars to `.env`:
  ```
  MQTT_BROKER_HOST=localhost
  MQTT_BROKER_PORT=1883
  MQTT_TOPIC_PREFIX=wifi-densepose
  ```
- [ ] End-to-end smoke test: ESP32 → MQTT → mqtt_listener → sensing server WS → iotdash live spectrogram

---

## 5. Future

- [ ] Multi-node: two ESP32-S3s simultaneously for stereo / multistatic sensing
- [ ] Semi-supervised loop — auto-label live CSI with trained model, feed back into training set
- [ ] Publish fork-trained model to HuggingFace alongside `wiflow-v1/`
- [ ] iotdash custom widgets for CSI spectrogram and subcarrier heatmap
- [ ] Fine-tune KIMODO on domain-specific motions (healthcare, security)
- [ ] Replace Chronos with a CSI-native foundation model once enough data is collected
