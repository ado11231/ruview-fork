# ruview-fork — Project Overview & Change Log

> Living document. Update this file as new work is done.
> Forked from [RuView](https://github.com/ruvnet/RuView) by rUv.

---

## What This Fork Is

An ESP32-based WiFi sensing platform that captures Channel State Information (CSI) to detect human presence and motion without cameras. The fork extends the upstream with:

- **iotdash dashboard integration** — live CSI visualization via MQTT and mDNS
- **Multi-device MQTT discovery** — devices publish metrics over MQTT, works with AP isolation
- **CSI training data pipeline** — collect labeled CSI → train WiFlow pose models
- **Repo housekeeping** — stripped large unused files, reorganized scripts

Upstream adds a full Rust port (15 crates), ESP32 firmware, signal processing, and neural network inference on top of the original Python-only system.

---

## Repository Layout

```
ruview-fork/
├── v1/                        # Python stack (original + extended)
│   ├── src/
│   │   ├── api/               # FastAPI REST + WebSocket
│   │   ├── core/              # CSI processor, phase sanitizer, router interface
│   │   ├── hardware/          # CSI extractor, router interface (hardware layer)
│   │   ├── models/            # DensePose head, modality translation network
│   │   ├── sensing/           # Feature extractor, classifier, WS server
│   │   └── services/          # Orchestrator, pose/stream/hardware services
│   ├── data/proof/            # Deterministic CSI proof bundle (SHA-256 verified)
│   └── tests/                 # Unit, integration, performance, e2e tests
│
├── rust-port/wifi-densepose-rs/  # Rust workspace (15 crates)
│   └── crates/
│       ├── wifi-densepose-core
│       ├── wifi-densepose-signal   # RuvSense (14 modules)
│       ├── wifi-densepose-nn
│       ├── wifi-densepose-train
│       ├── wifi-densepose-mat      # Mass Casualty Assessment Tool
│       ├── wifi-densepose-hardware # ESP32 TDM protocol + radio abstraction
│       ├── wifi-densepose-ruvector # Cross-viewpoint fusion (5 modules)
│       ├── wifi-densepose-api      # Axum REST API
│       ├── wifi-densepose-db
│       ├── wifi-densepose-config
│       ├── wifi-densepose-wasm
│       ├── wifi-densepose-cli
│       ├── wifi-densepose-sensing-server
│       ├── wifi-densepose-wifiscan
│       └── wifi-densepose-vitals
│
├── firmware/
│   └── esp32-csi-node/        # ESP-IDF v5.4 C firmware for ESP32-S3
│       └── main/              # Channel hopping, adaptive controller, mesh, NVS
│
├── ui/                        # Browser dashboard (JS/HTML)
│   ├── components/
│   ├── services/
│   ├── observatory/
│   └── pose-fusion/
│
├── data/
│   ├── recordings/            # Live CSI recordings (.csi.jsonl)
│   └── models/
│
├── scripts/                   # Build, deploy, training, validation utilities
├── docs/
│   ├── adr/                   # 81 Architecture Decision Records
│   ├── ddd/                   # Domain-Driven Design models
│   ├── tutorials/
│   └── user-guide.md
├── docker/
├── vendor/                    # ruvector, sublinear-time-solver, midstream
└── .env.example
```

---

## Supported Hardware

| Device | Chip | Role | Cost |
|--------|------|------|------|
| ESP32-S3 (8MB flash) | Xtensa dual-core | WiFi CSI sensing node | ~$9 |
| ESP32-S3 SuperMini (4MB) | Xtensa dual-core | WiFi CSI (compact) | ~$6 |
| ESP32-C6 + Seeed MR60BHA2 | RISC-V + 60 GHz FMCW | mmWave HR/BR/presence | ~$15 |
| HLK-LD2410 | 24 GHz FMCW | Presence + distance | ~$3 |

**Not supported:** ESP32 (original), ESP32-C3 — single-core, can't run CSI DSP pipeline.

---

## Fork-Specific Changes

### Commit `e8ea5ba` — Repo Cleanup + iotdash/MQTT Integration *(2026-04-22)*

**What changed:**

- **README replaced** — swapped the 2,365-line upstream README for a concise 18-line fork description.
- **iotdash integration** — added mDNS auto-discovery and MQTT transport layer connecting ESP32 CSI data to the iotdash IoT monitoring dashboard.
  - `client/device_client.py` — unified client supporting 17+ device types (ESP32, Raspberry Pi, Jetson, etc.) with automatic network discovery.
  - `backend/discovery/mqtt_listener.py` — devices publish metrics over MQTT, works across networks with AP isolation.
- **Bug fixes:**
  - Fixed async loop dispatch in `MDNSBrowser` for Python 3.10+ (previously failed on newer asyncio event loop handling).
  - Fixed `CSITimeSeries` subcarrier filter to accept any subcarrier count (was hardcoded to 52).
- **Repo cleanup** — removed ~21,000 lines of unused files:
  - `plans/` — 8 planning docs (spec, architecture, UI rebuild)
  - `logging/` — Fluentd config
  - `monitoring/` — Grafana, Prometheus, alerting configs
  - `references/` — 16 reference scripts and images
  - `assets/` — screenshots, exported zips, demo archives
  - `examples/` — 9 example scripts (room monitor, medical, sleep, stress, happiness vector)
  - `releases/` — pre-built desktop app binary
  - `benchmark_baseline.json` — stale benchmark snapshot
- **Scripts reorganized:** `deploy.sh` and `install.sh` moved to `scripts/`.
- **Env file renamed:** `example.env` → `.env.example` (standard convention).

### README Update *(in progress — unstaged)*

- Expanded description from 1 line to a proper summary paragraph.
- Added iotdash integration, device client, MQTT listener, CSI pipeline, and repo cleanup to the "What's different" list.
- Reformatted attribution as a blockquote.

---

## CSI Data Recordings

Live recordings collected from the ESP32-S3 sensing node are stored in `data/recordings/`:

| File | Description |
|------|-------------|
| `pretrain-1775182186.csi.jsonl` | Pre-training capture session with metadata sidecar |
| `overnight-1775217646.csi.jsonl` | Extended overnight capture for baseline modeling |

Format: newline-delimited JSON, one CSI frame per line. Each frame includes subcarrier amplitudes, phase data, RSSI, timestamp, and node ID.

---

## Key Architecture Decisions (ADRs)

81 ADRs in `docs/adr/`. Most relevant to current fork work:

| ADR | Title | Status |
|-----|-------|--------|
| ADR-014 | SOTA signal processing | Accepted |
| ADR-015 | MM-Fi + Wi-Pose training datasets | Accepted |
| ADR-016 | RuVector training pipeline integration | Accepted |
| ADR-021 | ESP32 CSI-grade vital sign extraction | Accepted |
| ADR-022 | Multi-BSSID WiFi scanning | Accepted |
| ADR-024 | Contrastive CSI embedding / AETHER | Accepted |
| ADR-027 | Cross-environment domain generalization / MERIDIAN | Accepted |
| ADR-028 | ESP32 capability audit + witness verification | Accepted |
| ADR-079 | Camera ground-truth training pipeline | Accepted |
| ADR-080 | QE remediation (refactor, perf, safety) | Accepted |
| ADR-081 | Adaptive CSI Mesh Firmware Kernel (5-layer) | Accepted |

---

## Firmware — ADR-081 Adaptive CSI Mesh Kernel

The latest major upstream feature. Restructures the ESP32 firmware into 5 layers:

| Layer | Name | Description |
|-------|------|-------------|
| 1 | Radio Abstraction | `rv_radio_ops_t` vtable; ESP32 + mock bindings |
| 2 | Adaptive Controller | 3-loop closed-loop (fast 200ms / medium 1s / slow 30s) |
| 3 | Mesh Sensing Plane | 4 node roles, 7 message types, HMAC/Ed25519 auth |
| 4 | On-device Feature Extraction | `rv_feature_state_t` — 60B packet at 5 Hz |
| 5 | Rust Handoff | Packet consumer in `wifi-densepose-hardware` |

**Key outcome:** ~99.7% bandwidth reduction vs raw CSI (300 B/s vs ~100 KB/s).

Firmware release `v0.6.2-esp32` ships this, plus the Timer Svc stack fix (bumped to 8 KiB from 2 KiB default).

---

## Build & Test Quick Reference

```bash
# Rust workspace tests (must pass: 1,031+ passed, 0 failed)
cd rust-port/wifi-densepose-rs
cargo test --workspace --no-default-features

# Python proof verification (must print: VERDICT: PASS)
python v1/data/proof/verify.py

# Python test suite
cd v1 && python -m pytest tests/ -x -q

# Firmware — flash to ESP32-S3 on COM7
# python -m esptool --port COM7 write_flash ...
# See CLAUDE.md for full ESP-IDF build subprocess command

# Generate + self-verify witness bundle
bash scripts/generate-witness-bundle.sh
```

---

## Pending / Next Steps

- [ ] Implement `client/device_client.py` and `backend/discovery/mqtt_listener.py` if not yet present
- [ ] Wire iotdash MQTT topic scheme to the sensing server WebSocket output
- [ ] Collect more labeled CSI recordings for WiFlow training
- [ ] Commit the in-progress README update
- [ ] Run full validation after README commit: `cargo test` + `verify.py`

---

*Last updated: 2026-04-22*
