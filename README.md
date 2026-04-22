# ruview-fork

Personal fork of [RuView](https://github.com/ruvnet/RuView) by rUv — WiFi-based human pose estimation using ESP32 CSI data.

## What's different in this fork

- **iotdash integration** — mDNS auto-discovery and MQTT transport layer connecting ESP32 CSI data to the iotdash IoT monitoring dashboard
- **Device client** (`client/device_client.py`) — unified client supporting 17+ device types (ESP32, Raspberry Pi, Jetson, etc.) with automatic network discovery
- **MQTT listener** (`backend/discovery/mqtt_listener.py`) — devices publish metrics over MQTT, works across networks with AP isolation
- **CSI pipeline** — ESP32 → sensing server → device client → iotdash dashboard with live spectrogram and subcarrier visualization
- **Repo cleanup** — removed unused planning docs, monitoring configs, reference scripts, and generated assets

## Original repo

[https://github.com/ruvnet/RuView](https://github.com/ruvnet/RuView)
