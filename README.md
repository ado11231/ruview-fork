# WiFi-DensePose

Camera-free human presence and motion detection using WiFi Channel State Information (CSI). An ESP32-S3 node captures raw RF channel data over UDP; a Rust signal processing pipeline turns it into pose estimates, vital signs, and activity labels — no cameras, no wearables.

> Built on [RuView](https://github.com/ruvnet/RuView) by rUv.

---

## Hardware

| Device | Role | Cost |
|--------|------|------|
| ESP32-S3 (8 MB flash) | Primary CSI sensing node | ~$9 |
| ESP32-S3 SuperMini (4 MB) | Compact sensing node | ~$6 |
| ESP32-C6 + Seeed MR60BHA2 | mmWave HR/BR/presence fusion | ~$15 |

**Not supported:** ESP32 (original), ESP32-C3 — single-core, cannot run the CSI DSP pipeline.

---

## Quick start

**New node?** Follow the [Node Setup Guide](docs/node-setup.md) — flash, provision, and verify CSI data in about 10 minutes.

```bash
# macOS — auto-detects USB port and local IP
make node-flash
make node-setup        # interactive WiFi provisioning
make node-live         # real-time terminal dashboard
make node-validate     # 5-second accuracy report
```

```bash
# Windows — specify port explicitly
make node-flash PORT=COM7
make node-provision PORT=COM7 SSID="YourWiFi" PASSWORD="pass"
make node-live PORT=COM7
make node-validate
```

---

## What this fork adds

| Feature | Status |
|---------|--------|
| Auto-detect USB port + host IP | Done |
| Interactive `make node-setup` (WiFi provisioning) | Done |
| Live terminal dashboard (`make node-live`) | Done |
| CSI accuracy validator (`make node-validate`) | Done |
| ADR-018 binary packet parser (magic number, freq→channel) | Done |
| Labeled CSI recording sessions (`collect-training-data.py`) | Done |
| Camera-synchronized ground truth (`collect-ground-truth.py`) | Done |
| KIMODO synthetic motion → CSI pipeline | Planned |
| Chronos temporal gate for noise rejection | Planned |
| iotdash MQTT integration | Planned |

---

## Repository layout

```
firmware/esp32-csi-node/   ESP32-S3 C firmware (CSI collector, TDM, NVS config)
rust-port/wifi-densepose-rs/  Rust workspace — 15 signal processing + inference crates
v1/                        Python source (core, hardware, services, API)
scripts/                   Data capture and training pipeline scripts
docs/node-setup.md         Step-by-step node setup (start here)
docs/adr/                  81 Architecture Decision Records
docs/TODO.md               Current priorities and roadmap
data/recordings/           Raw CSI recordings (JSONL)
```

---

## Makefile reference

| Command | Description |
|---------|-------------|
| `make node-build` | Build firmware in ESP-IDF Docker container |
| `make node-flash` | Flash firmware (auto-detects port on macOS) |
| `make node-setup` | Interactive WiFi provisioning (macOS) |
| `make node-provision SSID=… PASSWORD=…` | Manual WiFi provisioning |
| `make node-live` | Live RSSI / fps / health dashboard |
| `make node-validate` | 5-second UDP capture + accuracy report |
| `make node-monitor` | Plain serial monitor (115200 baud) |
| `make node-observe` | Record CSI packets to `data/recordings/` |

---

## Training pipeline

The goal is a model that infers 17-keypoint human pose from live CSI without any camera input.

```
KIMODO text prompts → 3D skeleton sequences
  → CSI simulator → synthetic labeled pairs

ESP32 UDP stream → collect-training-data.py (activity labels)
  + collect-ground-truth.py (MediaPipe keypoints synced)
  → real labeled pairs

Mixed dataset → CSI Encoder → Pose head + Gesture head
  Chronos temporal gate → noise rejection
  → export: data/models/wiflow-kimodo-v1.safetensors
```

See [docs/TODO.md](docs/TODO.md) for the full step-by-step build plan.

---

## Staying in sync with upstream

```bash
git fetch upstream
git merge upstream/main
```

The `upstream` remote points to `ruvnet/RuView`.
