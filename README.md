# ruview-fork

ESP32-based WiFi sensing platform that captures Channel State Information to detect human presence and motion without cameras. Extends the original with a CSI training data pipeline and Vynth dashboard integration.

> Forked from [RuView](https://github.com/ruvnet/RuView) by rUv

## Get started

**New node?** → [Node Setup Guide](docs/node-setup.md) — connect, flash, provision, observe CSI in 5 steps.

```bash
make node-build
make node-flash PORT=COM7
make node-provision PORT=COM7 SSID="wifi" PASSWORD="pass" IP=192.168.1.20
make node-observe
```

## What's different in this fork

- **Vynth pipeline** — ESP32 CSI data streamed to the Vynth dashboard via MQTT
- **CSI training pipeline** — labeled recording sessions for pose estimation model training
- **Simplified node setup** — single-command build, flash, and provision flow

## Original repo

[https://github.com/ruvnet/RuView](https://github.com/ruvnet/RuView)

## Staying in sync with upstream

```bash
git fetch upstream
git merge upstream/main
```

The `upstream` remote points to `ruvnet/RuView`. Pull upstream changes whenever you want to pick up firmware fixes or new features from the original repo.
