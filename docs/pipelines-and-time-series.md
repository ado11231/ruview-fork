# Pipelines & Time Series Reference

WiFi-DensePose data pipelines and time series capabilities across the Rust and Python codebases.

---

## Data Pipelines

### 1. End-to-End Signal Pipeline (Rust)

```
ESP32/Router → CSI Frames
      ↓
wifi-densepose-signal (preprocessing)
  ├─ CsiProcessor      — noise removal, windowing, normalization
  ├─ PhaseSanitizer    — unwrapping (Itoh/QualityGuided), z-score outlier removal, smoothing
  ├─ FeatureExtractor  — amplitude, phase diff, correlation, Doppler, PSD (FFT-based)
  ├─ MotionDetector    — 4-component score: variance(0.4) + correlation(0.3) + phase(0.3) + Doppler(0.3)
  └─ Spectrogram       — STFT with Hann/Hamming/Blackman window → (n_freq × n_time) CNN input
      ↓
wifi-densepose-vitals (physiology extraction)
  ├─ CsiVitalPreprocessor  — EMA static suppression (α=0.05) → per-subcarrier residuals
  ├─ BreathingExtractor    — 2nd-order IIR bandpass (0.1–0.5 Hz), zero-crossing → RR
  ├─ HeartRateExtractor    — IIR bandpass (0.8–2.0 Hz), autocorrelation peak → HR
  └─ VitalAnomalyDetector  — Welford z-score (2.5σ), clinical thresholds (apnea, tachy, brady)
      ↓
wifi-densepose-signal/ruvsense (advanced multi-layered sensing)
  ├─ FieldModel                 — 10+ min empty-room calibration → SVD eigenmodes → residual extraction
  ├─ PoseTracker                — 17-keypoint Kalman trajectory + AETHER re-ID embeddings
  ├─ LongitudinalBaseline       — 7-day Welford baselines per person, 5 biomechanical drift metrics
  ├─ TemporalGestureClassifier  — DTW/LCS/edit distance template matching
  ├─ MultistatiicGeometry       — attention-weighted multi-TX/RX path fusion
  └─ IntentionDetector          — 200–500ms pre-movement lead signal detection
      ↓
ruvector-temporal-tensor (compression & storage)
  ├─ Tiered quantization: 8-bit hot (4x) → 7-bit warm (4.57x) → 5-bit (6.4x) → 3-bit cold (10.67x)
  ├─ Access-pattern-driven tier promotion/demotion
  └─ Random-access frame decode without full decompression
      ↓
wifi-densepose-mat (tracking & localization)
  ├─ KalmanFilter     — 6D state [px,py,pz,vx,vy,vz], constant-velocity model
  ├─ Triangulation    — multi-AP position estimation
  ├─ EnsembleDetector — breathing + heartbeat + movement voting
  └─ AlertGenerator   — threshold-based clinical triage
      ↓
REST API / WebSocket stream
  └─ PoseEstimate: 17 COCO keypoints + confidence + timestamp
```

### 2. Multi-AP WiFi Scanning Pipeline (`wifi-densepose-wifiscan`)

```
Platform adapters (netsh / CoreWLAN / iw)
      ↓
BssidRegistry — Welford RSSI variance per BSSID (lifetime tracking)
      ↓
AttentionWeighter → Correlator → QualityGate → PredictiveGate
      ↓
MultiApFrame aggregation → BreathingExtractor → MotionEstimator
      ↓
FingerprintMatcher (location)
```

### 3. Python Sensing Pipeline (`v1/src/`)

```
WifiCollector (ring buffer, configurable sample_rate_hz)
      ↓
RssiFeatureExtractor
  ├─ Time-domain: mean, variance, std, skewness, kurtosis, range, IQR
  └─ Frequency: dominant_freq_hz, breathing_band_power, motion_band_power, total_power
      ↓
PresenceClassifier → SensingResult (presence, MotionLevel, confidence)
      ↓
ModalityTranslationNetwork (CSI 64-ch → 512-dim visual features)
      ↓
DensePoseHead
  ├─ Segmentation head: body-part classification (N parts + background)
  └─ UV regression head: surface coordinate prediction
      ↓
ServiceOrchestrator → PoseService / StreamService → WebSocket
```

### 4. Training Pipeline (`wifi-densepose-train`)

```
MmFiDataset (S{subject}/A{action}/*.npy) or SyntheticCsiDataset (physics-based, seed=42)
      ↓
DataLoader (batched, deterministic shuffle, windowed overlap)
      ↓
CsiSample: amplitude[window, tx, rx, subcarriers] + phase[...] + keypoints[17,2]
      ↓
Training loop: MSE / L1 / focal loss → APK / OKS / PCK / PCP metrics
      ↓
Checkpointing + early stopping
```

---

## Time Series Capabilities

### Temporal Compression — `ruvector-temporal-tensor`

| Tier | Bits | Ratio | Trigger |
|------|------|-------|---------|
| Hot | 8 | 4.0x | 100+ accesses |
| Warm | 7 | 4.57x | Default |
| Warm aggressive | 5 | 6.4x | Low access |
| Cold | 3 | 10.67x | <5 accesses |

- Frame-to-frame delta encoding + second-order deltas
- Groupwise symmetric quantization (min-max per group)
- Random-access decode of a single frame without decompressing the full segment
- WASM-compatible (zero native deps)

### Kalman Filter — `wifi-densepose-mat/tracking/kalman.rs`

- **State**: `[px, py, pz, vx, vy, vz]` — 6D constant-velocity model
- **Observation**: position only, `H = [I₃ | 0₃]`
- **Covariance**: full 6×6 `P` updated each step
- **Innovation**: `y = z − H·x`, gain `K = P·H^T · S⁻¹`
- Configurable process noise `σ²_accel` and observation noise `σ²_obs`
- Used for multi-person survivor tracking in disaster scenarios (`wifi-densepose-mat`)

### Welford Online Statistics

Used in four separate subsystems:

| Location | What it tracks |
|----------|----------------|
| `vitals/anomaly.rs` | Running mean/variance for z-score anomaly detection (2.5σ threshold) |
| `wifiscan/domain/registry.rs` | Per-BSSID RSSI mean/variance over full lifetime |
| `signal/ruvsense/field_model.rs` | Per-link CSI baseline (mean/variance) for empty-room calibration |
| `signal/ruvsense/longitudinal.rs` | 7-day per-person biomechanical baselines (5 metrics) |

### Physiological Time Series

**Breathing** (`vitals/breathing.rs`):
- 2nd-order IIR bandpass, 0.1–0.5 Hz
- Zero-crossing rate → respiratory frequency
- Weighted fusion across subcarriers (needs 10s minimum)
- Clinical alerts: apnea (<4 BPM), bradypnea (<8), tachypnea (>30)

**Heart Rate** (`vitals/heartrate.rs`):
- IIR bandpass 0.8–2.0 Hz
- Autocorrelation peak detection
- Phase-coherence subcarrier weighting (needs 4+ subcarriers, 5s minimum)
- Physiological validation gate: 40–180 BPM

### Longitudinal Biomechanics — `ruvsense/longitudinal.rs`

Tracks five metrics per person over days using Welford baselines:

| Metric | Description |
|--------|-------------|
| `GaitSymmetry` | 0.0 = perfect symmetry |
| `StabilityIndex` | Lower = less stable |
| `BreathingRegularity` | Coefficient of variation of breath intervals |
| `MicroTremor` | High-frequency pose jitter in mm |
| `ActivityLevel` | Normalized 0–1 |

- Baseline activates after **7+ observation days**
- Drift alert: >2σ sustained for **3+ consecutive days**
- Three monitoring levels: Physiological → Drift → RiskCorrelation

### DTW Gesture Classification — `ruvsense/temporal_gesture.rs`

- Three distance algorithms: **DTW**, **LCS**, **Edit Distance**
- Template library with L2-normalized feature vectors
- Result cache (default 256 capacity) for repeated comparisons
- Max sequence length: 1024 frames
- Distance threshold: 50.0 (configurable)

### Spectrogram / STFT — `signal/spectrogram.rs`

- Window functions: Rectangular, Hann, Hamming, Blackman
- Frequency resolution: `sample_rate / window_size`
- Output shape: `(n_freq × n_time)` — direct CNN input
- Used as the primary input representation for the neural backbone

### RSSI Time Series (Python) — `v1/src/sensing/feature_extractor.py`

- Ring buffer with configurable `sample_rate_hz`
- 30-second sliding window (configurable)
- CUSUM change-point detection with configurable threshold
- 7 time-domain + 4 frequency-domain features per window

---

## Key Numerical Constants

| Parameter | Value |
|-----------|-------|
| Breathing band | 0.1–0.5 Hz |
| Cardiac band | 0.8–2.0 Hz |
| Anomaly z-score threshold | 2.5 σ |
| ESP32 subcarriers | 56 (interpolated from 114) |
| Kalman state dimensions | 6 (pos + vel in 3D) |
| Welford baseline activation | 7 days |
| Drift detection window | 3 consecutive days |
| Drift threshold | >2 σ |
| Temporal compression range | 4.0x – 10.67x |
| COCO keypoints | 17 |
| Pose confidence threshold | 0.5 default |

---

## Layer Summary

The repo stacks four layers of time series processing:

1. **Raw CSI buffering** — temporal tensor compression with tiered quantization
2. **Physiological extraction** — IIR filters + autocorrelation for breathing and heart rate
3. **Behavioral tracking** — Kalman filter + DTW gesture classification
4. **Longitudinal health monitoring** — Welford baselines tracked over days per person

Each layer feeds the next.
