# ESP32 Node Setup Guide

From a fresh ESP32-S3 to streaming CSI data in 5 steps.

---

## What you need

| Item | Notes |
|------|-------|
| ESP32-S3 board (8 MB flash) | DevKitC-1, XIAO ESP32-S3, or similar |
| USB cable | Matches your board's USB connector |
| CP210x driver | Windows/macOS only — [download](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers) |
| Docker Desktop | For building firmware |
| Python 3.10+ | For flashing and provisioning |

Install the Python tools once:

```bash
pip install "esptool>=5.0" esp-idf-nvs-partition-gen
```

---

## Step 1 — Connect the node

Plug the ESP32-S3 into your machine via USB.

Find the serial port:

| OS | Command | Typical result |
|----|---------|----------------|
| macOS | `ls /dev/cu.*` | `/dev/cu.SLAB_USBtoUART` |
| Linux | `ls /dev/ttyUSB*` | `/dev/ttyUSB0` |
| Windows | Device Manager → Ports | `COM7` |

Use that port value in every command below (`COM7` in the examples).

---

## Step 2 — Build and flash the firmware

**Build** (Docker is required — ESP-IDF does not work from Git Bash on Windows):

```bash
# Run from the repo root
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$(pwd)/firmware/esp32-csi-node:/project" -w /project \
  espressif/idf:v5.2 bash -c \
  "rm -rf build sdkconfig && idf.py set-target esp32s3 && idf.py build"
```

Or use the Makefile shortcut:

```bash
make node-build
```

**Flash** (replace `COM7` with your port):

```bash
python -m esptool --chip esp32s3 --port COM7 --baud 460800 \
  write_flash --flash_mode dio --flash_size 8MB \
  0x0   firmware/esp32-csi-node/build/bootloader/bootloader.bin \
  0x8000 firmware/esp32-csi-node/build/partition_table/partition-table.bin \
  0x10000 firmware/esp32-csi-node/build/esp32-csi-node.bin
```

Or:

```bash
make node-flash PORT=COM7
```

---

## Step 3 — Provision WiFi credentials

No reflash needed. The provision script writes your WiFi credentials and the sensing server IP directly to the node's flash storage.

```bash
python firmware/esp32-csi-node/provision.py \
  --port COM7 \
  --ssid "YourWiFiName" \
  --password "YourWiFiPassword" \
  --target-ip 192.168.1.20
```

`--target-ip` is **your machine's local IP** (the machine that will run the sensing server). Find it with `ipconfig` (Windows) or `ifconfig` / `ip a` (macOS/Linux).

Or:

```bash
make node-provision PORT=COM7 SSID="YourWiFiName" PASSWORD="yourpass" IP=192.168.1.20
```

> **Re-provisioning:** you can run this command again any time to update WiFi or target IP without reflashing firmware. Every run replaces all settings — always include `--ssid`, `--password`, and `--target-ip` together.

---

## Step 4 — Verify the node is streaming

Open the serial monitor to confirm WiFi connected and CSI is streaming:

```bash
python -m serial.tools.miniterm COM7 115200
```

Or:

```bash
make node-monitor PORT=COM7
```

Expected output:

```
I (321) main: ESP32-S3 CSI Node — Node ID: 1
I (345) main: WiFi STA initialized, connecting to: YourWiFiName
I (1023) main: Connected to WiFi — IP: 192.168.1.45
I (1025) main: CSI streaming active -> 192.168.1.20:5005
```

Press `Ctrl+]` to exit the monitor.

**Common issues:**

| Symptom | Fix |
|---------|-----|
| No output at all | Wrong baud rate — use `115200` |
| `Connecting to WiFi...` repeats | Wrong SSID or password — re-run provision |
| Connected but no CSI frames received later | Firewall blocking UDP 5005 (see Step 5) |

---

## Step 5 — Observe CSI packets

On the machine running the sensing server, open a terminal and run:

```bash
python scripts/record-csi-udp.py --port 5005 --duration 60
```

Or:

```bash
make node-observe
```

You should see live output like:

```
Listening on UDP :5005 for 60s...
  500 frames | 20 fps | nodes: [1] | 25s / 60s
  1000 frames | 20 fps | nodes: [1] | 50s / 60s

=== CSI Recording Complete ===
  Frames: 1200
  Duration: 60s
  Rate: 20 fps
  Nodes: [1]
  Output: data/recordings/session-1234567890.csi.jsonl
```

If you see `0 frames`, check:
1. Node serial output confirms `CSI streaming active`
2. The `--target-ip` you provisioned matches this machine's IP
3. UDP port 5005 is not blocked by a firewall

**Windows firewall rule:**

```powershell
netsh advfirewall firewall add rule name="ESP32 CSI" dir=in action=allow protocol=UDP localport=5005
```

---

## Multi-node setup

Each additional node needs its own `--node-id` so packets can be distinguished:

```bash
# Node 1 (already provisioned above, node_id defaults to 1)

# Node 2
python firmware/esp32-csi-node/provision.py \
  --port COM8 \
  --ssid "YourWiFiName" --password "YourWiFiPassword" \
  --target-ip 192.168.1.20 \
  --node-id 2

# Node 3
python firmware/esp32-csi-node/provision.py \
  --port COM9 \
  --ssid "YourWiFiName" --password "YourWiFiPassword" \
  --target-ip 192.168.1.20 \
  --node-id 3
```

All nodes send to the same UDP port. The `node_id` field in each packet identifies which node it came from.

---

## Next steps

Once you have frames flowing, the foundation is set for:

- **Noise reduction** — signal conditioning and subcarrier filtering (`docs/signal-conditioning.md`)
- **Data collection** — labeled recording sessions for training (`scripts/collect-training-data.py`)
- **Live visualization** — start the sensing server and open the UI (`make run-sensing-server`)
- **Vynth pipeline** — streaming CSI to the Vynth dashboard (`docs/vynth-pipeline.md`)

For advanced firmware configuration (edge processing tiers, channel hopping, TDM mesh), see the full [firmware reference](../firmware/esp32-csi-node/README.md).
