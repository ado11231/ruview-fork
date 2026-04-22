# Agent Prompt — CSI Training Pipeline Repo

Use this prompt when spinning up an agent in the new training repo.

---

## Context

You are building a training pipeline for a WiFi-based human pose and gesture detection system. The system uses an ESP32-S3 WiFi node to capture **Channel State Information (CSI)** — raw subcarrier amplitude and phase data from WiFi signals that gets disturbed by human bodies moving through the room. No cameras are used at deployment time.

The parent project is a fork of RuView (`github.com/ruvnet/RuView`), a Rust + Python platform for WiFi sensing. The fork (`ruview-fork`) is already running and streaming live CSI data from an ESP32-S3 node to an iotdash IoT dashboard over MQTT.

**Current accuracy problem:** The existing WiFlow model (974KB, 186K params) achieves only **2.5% PCK@20** because it was trained without ground-truth pose labels. The target is **35%+ PCK@20**. This training repo solves that.

---

## What This Repo Builds

A standalone training pipeline that:
1. Generates synthetic training data using **KIMODO** (NVIDIA's 3D motion diffusion model)
2. Models CSI temporal dynamics using **Chronos** (Amazon's time series foundation model)
3. Trains a combined encoder model to detect gestures and estimate 17-keypoint COCO poses from CSI
4. Exports a model that runs live in the sensing server alongside the ESP32 node

---

## The Full Pipeline

```
STAGE 1 — SYNTHETIC DATA (KIMODO)
  Text prompts → KIMODO → 3D skeleton sequences (SOMA 24 joints)
  → scripts/kimodo_to_coco.py → COCO 17 keypoints
  → scripts/csi_simulator.py → synthetic CSI[subcarriers × time]
  → data/synthetic/kimodo-paired/ — { CSI, pose[17,3], gesture_label }

STAGE 2 — REAL DATA (from ruview-fork)
  ESP32 node → UDP → collect-training-data.py → data/recordings/*.csi.jsonl
  ESP32 node + webcam → collect-ground-truth.py → data/ground-truth/*.jsonl
  Paired: { CSI[subcarriers × time], camera_keypoints[17,2], gesture_label }

STAGE 3 — TEMPORAL MODELING (Chronos)
  CSI subcarrier amplitudes = multivariate time series (each subcarrier = 1 channel)
  Fine-tune Chronos on real CSI recordings
  At inference: Chronos gate rejects temporally implausible frames (noise rejection)

STAGE 4 — MODEL TRAINING
  Mixed dataset: synthetic (KIMODO) + real (ESP32) — ~50/50, adjustable
  Architecture:
    CSI Encoder (CNN or Transformer): CSI[128,20] → latent[256]
    Pose head:    latent → 17 × [x,y,z,confidence]
    Gesture head: latent → (gesture_class, confidence)
    Residual head: latent → Δ correction (closes sim-to-real domain gap)
    Chronos gate: temporal anomaly pre-filter before encoder
  Target: PCK@20 ≥ 35%
  Export: data/models/wiflow-kimodo-v1.safetensors

STAGE 5 — LIVE INFERENCE (runs in ruview-fork sensing server)
  ESP32 CSI
    → noise pre-filter (Hampel, phase sanitize)
    → Chronos gate (reject noise frames)
    → Encoder + residual correction
    → Pose head + Gesture head
    → Physics plausibility check (KIMODO learned motion space)
    → output to iotdash dashboard + sensing server API
```

---

## CSI Data Format

Each frame in `*.csi.jsonl` (one JSON object per line):
```json
{
  "timestamp": 1775182186.123,
  "node_id": "3c:0f:02:e9:b5:f8",
  "rssi": -48,
  "subcarriers": [0.42, 0.38, 0.51, ...],  // 52 or 64 amplitude values
  "phase": [1.2, -0.8, 0.3, ...],           // optional phase per subcarrier
  "label": "walking"                         // present in labeled recordings
}
```

Ground-truth files (`data/ground-truth/*.jsonl`) add:
```json
{
  "timestamp": 1775182186.123,
  "keypoints": [[x,y,conf], ...],  // 17 COCO keypoints
  "csi_ref": "pretrain-1775182186.csi.jsonl"
}
```

---

## Key Design Decisions

**Why KIMODO for synthetic data?**
The model needs diverse, physically realistic 3D human motions. KIMODO (trained on 700+ hours of studio mocap) generates far more variety than manual collection. Synthetic CSI from these motions gives the model spatial priors for what valid human-body CSI disturbance patterns look like.

**Why Chronos for temporal modeling?**
CSI subcarrier amplitudes over time are a multivariate time series. Chronos (Amazon, zero-shot multivariate) learns the temporal continuity of valid CSI sequences. At inference it acts as a fast pre-filter: if incoming CSI doesn't match learned temporal dynamics (e.g. random hardware noise, packet corruption), it gets rejected before reaching the encoder.

**Why the residual head?**
The model trains on both simulated CSI (from KIMODO's perfect 3D bodies) and real CSI (from actual ESP32 hardware in a specific room). The residual head learns the systematic difference — multipath reflections, antenna placement, hardware quirks — and corrects for it at inference time, so the encoder always sees CSI in the simulation's coordinate space where the weights are accurate.

---

## Repo Structure to Build

```
csi-training-pipeline/
├── scripts/
│   ├── kimodo_generate.py       # KIMODO API → 3D skeleton JSONL
│   ├── kimodo_to_coco.py        # SOMA 24 joints → COCO 17 keypoints
│   ├── csi_simulator.py         # 3D pose + room geometry → synthetic CSI
│   ├── kimodo_build_dataset.py  # orchestrates stages 1-3, outputs paired JSONL
│   ├── chronos_finetune.py      # fine-tune Chronos on real CSI recordings
│   └── train.py                 # main training entry point
├── model/
│   ├── encoder.py               # CSI Encoder (CNN/Transformer)
│   ├── heads.py                 # Pose head, Gesture head, Residual head
│   ├── chronos_gate.py          # Chronos temporal pre-filter wrapper
│   └── pipeline.py              # full inference pipeline
├── data/
│   ├── synthetic/kimodo/        # raw KIMODO skeleton outputs
│   ├── synthetic/kimodo-paired/ # paired (CSI, pose, label) JSONL
│   ├── recordings/              # real CSI from ESP32 (copied from ruview-fork)
│   ├── ground-truth/            # camera-synced keypoints (from ruview-fork)
│   └── models/                  # trained model exports (.safetensors)
├── requirements-train.txt
├── .env.example
└── README.md
```

---

## Environment Variables (`.env`)

```
# KIMODO
KIMODO_CHECKPOINT_PATH=../kimodo/checkpoints/kimodo-v1-soma.pt
KIMODO_DEVICE=cuda
KIMODO_OUTPUT_DIR=data/synthetic/kimodo

# Chronos
CHRONOS_MODEL=amazon/chronos-t5-small
CHRONOS_DEVICE=cuda

# CSI Simulator — match your physical room setup
CSI_SIM_TX_POS=0,0,1.2        # ESP32 TX antenna (x,y,z metres)
CSI_SIM_RX_POS=4,0,1.2        # ESP32 RX antenna
CSI_SIM_ROOM_DIM=5,4,2.4      # room width, depth, height

# Training
SYNTHETIC_WEIGHT=0.5           # fraction of batch from synthetic data
BATCH_SIZE=64
LEARNING_RATE=1e-4
EPOCHS=50
```

---

## Dependencies (`requirements-train.txt`)

```
torch>=2.0
torchvision
chronos-forecasting
mediapipe>=0.10
opencv-python
numpy
scipy
safetensors
# KIMODO: pip install -e ../kimodo  (clone nv-tlabs/kimodo separately)
```

---

## External Tools to Clone Separately

- KIMODO: `https://github.com/nv-tlabs/kimodo`
- KIMODO checkpoints: `https://huggingface.co/collections/nvidia/kimodo-v1` (SOMA variant)
- KIMODO demo: `https://huggingface.co/spaces/nvidia/Kimodo`
- ProtoMotions (KIMODO dependency): `https://github.com/NVlabs/ProtoMotions`
- Chronos: installed via pip (`chronos-forecasting`)

---

## Reference Files in ruview-fork

These exist in the parent repo and should be referenced or copied:

| File | Purpose |
|------|---------|
| `scripts/collect-ground-truth.py` | SOMA→COCO keypoint mapping, MediaPipe integration |
| `scripts/collect-training-data.py` | CSI packet format (ADR-018/069), JSONL structure |
| `v1/data/proof/sample_csi_data.json` | Reference CSI amplitude format (1000 frames, seed=42) |
| `rust-port/.../ruvsense/field_model.rs` | Fresnel zone / SVD room model — port this to Python for CSI simulator |
| `data/recordings/*.csi.jsonl` | Real ESP32 CSI recordings to copy into this repo's `data/recordings/` |

---

## Success Criteria

- [ ] Synthetic dataset: 10,000+ paired (CSI, pose, gesture) frames generated
- [ ] Chronos fine-tuned on real CSI, anomaly gate working (reduces noise frames by >50%)
- [ ] Model trains without NaN loss, converges within 50 epochs
- [ ] PCK@20 ≥ 35% on held-out real recordings (vs 2.5% baseline)
- [ ] Gesture classification accuracy ≥ 80% on 5 classes (walking/standing/sitting/waving/falling)
- [ ] Exported model loads cleanly in ruview-fork sensing server
- [ ] Live inference: pose + gesture results appear on iotdash dashboard in real time
