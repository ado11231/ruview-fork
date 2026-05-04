# ESP32 Node Setup Guide

From a fresh ESP32-S3 to verified live CSI data — no prior ESP32 experience needed.

---

## What you need

| Item | Notes |
|------|-------|
| ESP32-S3 board | 4 MB or 8 MB flash variant — see [Which binary?](#which-binary-4-mb-vs-8-mb) |
| USB cable | Matches your board's USB port |
| CP210x or CH340 driver | May be needed on macOS/Windows — [CP210x](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers) / [CH340](https://www.wch-ic.com/downloads/CH341SER_EXE.html) |
| Python 3.12 | Via pyenv (see Step 1) |
| WiFi network | 2.4 GHz (5 GHz is not supported by the ESP32-S3 CSI driver) |

---

## Step 1 — Install Python 3.12 via pyenv

Using pyenv keeps your system Python clean and avoids version conflicts.

### macOS

```bash
# Install pyenv via Homebrew
brew install pyenv

# Add pyenv to your shell (add these lines to ~/.zshrc or ~/.bash_profile)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc

# Install Python 3.12 and set it as default
pyenv install 3.12.7
pyenv global 3.12.7

# Verify
python --version   # should print Python 3.12.7
```

### Windows (PowerShell)

```powershell
# Install pyenv-win
Invoke-WebRequest -UseBasicParsing `
  "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" `
  -OutFile "./install-pyenv-win.ps1"
& "./install-pyenv-win.ps1"

# Restart PowerShell, then:
pyenv install 3.12.7
pyenv global 3.12.7

# Verify
python --version   # should print Python 3.12.7
```

---

## Step 2 — Install the flashing tools

Run once after Python is set up:

```bash
pip install "esptool>=5.0" esp-idf-nvs-partition-gen pyserial
```

Verify:

```bash
python -m esptool version   # should print esptool v5.x.x
```

---

## Step 3 — Connect the node

Plug the ESP32-S3 into your machine via USB. Find its serial port:

### macOS

```bash
ls /dev/cu.usbmodem*
# Example output: /dev/cu.usbmodem1101
```

### Windows

Open **Device Manager → Ports (COM & LPT)** and look for:
- `Silicon Labs CP210x USB to UART Bridge (COM7)` — or whatever COM number appears

> The Makefile auto-detects the port on macOS. On Windows, pass `PORT=COM7` explicitly to every make command.

---

## Step 4 — Flash the firmware

Pre-built binaries are in `firmware/esp32-csi-node/release_bins/`. No Docker or ESP-IDF needed.

### macOS (auto-detects port)

```bash
make node-flash
```

### Windows

```bash
make node-flash PORT=COM7
```

Or run esptool directly:

**4 MB board:**

```bash
python -m esptool --chip esp32s3 --port COM7 --baud 460800 \
  write_flash --flash_mode dio --flash_size 4MB \
  0x0     firmware/esp32-csi-node/release_bins/bootloader.bin \
  0x8000  firmware/esp32-csi-node/release_bins/partition-table-4mb.bin \
  0xf000  firmware/esp32-csi-node/release_bins/ota_data_initial.bin \
  0x20000 firmware/esp32-csi-node/release_bins/esp32-csi-node-4mb.bin
```

**8 MB board:**

```bash
python -m esptool --chip esp32s3 --port COM7 --baud 460800 \
  write_flash --flash_mode dio --flash_size 8MB \
  0x0     firmware/esp32-csi-node/release_bins/bootloader.bin \
  0x8000  firmware/esp32-csi-node/release_bins/partition-table.bin \
  0xf000  firmware/esp32-csi-node/release_bins/ota_data_initial.bin \
  0x20000 firmware/esp32-csi-node/release_bins/esp32-csi-node.bin
```

### Which binary? 4 MB vs 8 MB

If you see this warning during flash, your board has 4 MB flash — use the 4 MB commands above:

```
Warning: Set flash_size 8MB is larger than the available flash size of 4MB.
```

If the warning does not appear, use the 8 MB commands.

### Expected flash output

```
Hash of data verified.        ← bootloader
Hash of data verified.        ← partition table
Hash of data verified.        ← ota data
Hash of data verified.        ← firmware
Hard resetting via RTS pin...
```

All four hashes must verify. If any fail, retry — sometimes a poor USB cable causes write errors.

---

## Step 5 — Provision WiFi

This writes your WiFi credentials and the IP of your machine to the node's flash. No reflash needed — you can re-run this any time to update settings.

### macOS (interactive — auto-detects port and your IP)

```bash
make node-setup
```

Output:

```
  Device : /dev/cu.usbmodem1101
  Host IP: 192.168.1.45

  WiFi SSID: YourWiFiName
  WiFi Password:
```

Enter your SSID and password. The node reboots and connects automatically.

### Windows (manual)

First find your machine's IP:

```powershell
ipconfig | findstr "IPv4"
# Example: IPv4 Address. . . . . . . : 192.168.1.45
```

Then provision:

```bash
make node-provision PORT=COM7 SSID="YourWiFiName" PASSWORD="yourpass" IP=192.168.1.45
```

> **2.4 GHz only.** The ESP32-S3 CSI driver only works on 2.4 GHz channels. If your router broadcasts separate 2.4 GHz and 5 GHz SSIDs, use the 2.4 GHz one.

---

## Step 6 — Verify the node is running

### Visual live dashboard (recommended)

```bash
# macOS
make node-live

# Windows
make node-live PORT=COM7
```

You will see a live updating screen:

```
╔══ CSI Live Monitor ══════════════════════════╗
║  Port       /dev/cu.usbmodem1101
║  Frame #    1100
║  Channel    11
║  Frame len  128 bytes → 64 subcarriers
║
║  RSSI  -44 dBm
║  ████████████████░░░░░░░░░░░░░░
║
║  Rate    22.2 fps
║  Total   1100 frames received
║  Dropped 0 frames
║
║  Health  GOOD
╚══════════════════════════════════════════════╝
```

Press `Ctrl+C` to exit.

### Plain serial monitor

```bash
# macOS
make node-monitor

# Windows
make node-monitor PORT=COM7
```

Expected serial lines:

```
I (15308) csi_collector: CSI cb #600: len=128 rssi=-44 ch=11
I (16948) csi_collector: CSI cb #700: len=128 rssi=-45 ch=11
```

**Troubleshooting:**

| Symptom | Fix |
|---------|-----|
| `Retrying WiFi connection...` repeats | Wrong SSID/password — re-run Step 5 |
| No CSI lines appear after WiFi connects | Check firewall is not blocking UDP 5005 |
| `boot: No bootable app partitions` | Wrong partition table flashed — re-run Step 4 with correct 4 MB / 8 MB commands |
| Node crashes immediately and reboots | Flash size mismatch — check which binary you used |

---

## Step 7 — Validate data accuracy

Run this in a second terminal while the node is streaming:

```bash
make node-validate
```

It listens on UDP for 5 seconds and prints a full health report:

```
══ CSI Accuracy Report ═══════════════════════════════

  Basic reception
  [PASS]  UDP packets received         111 frames in 5s (22.2 fps)
  [PASS]  Frame rate > 20 fps
  [PASS]  Single channel (no drift)    channels seen: [11]

  IQ data integrity
  [PASS]  Amplitudes non-zero          mean amplitude = 11.50
  [PASS]  Not all identical values     range: 0.0 – 121.0
  [PASS]  Subcarrier variance > 0      mean variance = 0.996
  [PASS]  Values physically plausible  mean = 11.50 (expect 5–60)

  Signal quality
  [PASS]  RSSI in normal range         mean RSSI = -45.3 dBm
  [PASS]  RSSI stable (static room)    RSSI variance = 0.8

  Last frame — subcarrier amplitudes (64 subcarriers)
   ▁▂▄▅▅▆▆▆▆▅▅▄▃▁  ▁▂▃▄▅▅▅▅▄▄
```

All items should show `PASS`. A smooth sparkline (not flat) confirms real IQ data.

**If `node-validate` receives 0 frames:**

1. Check `make node-live` shows frames arriving — confirms the node is streaming
2. Your machine's IP in provisioning must exactly match the IP shown by `ifconfig` / `ipconfig`
3. Allow UDP port 5005 through your firewall:

```bash
# macOS — allow inbound UDP 5005
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add $(which python3)

# Windows PowerShell (run as Administrator)
netsh advfirewall firewall add rule name="ESP32 CSI" dir=in action=allow protocol=UDP localport=5005
```

---

## Quick reference — all node commands

| Command | macOS | Windows |
|---------|-------|---------|
| Flash firmware | `make node-flash` | `make node-flash PORT=COM7` |
| Provision WiFi (interactive) | `make node-setup` | *(use node-provision below)* |
| Provision WiFi (manual) | `make node-provision SSID="x" PASSWORD="y" IP=z` | same + `PORT=COM7` |
| Visual live dashboard | `make node-live` | `make node-live PORT=COM7` |
| Plain serial monitor | `make node-monitor` | `make node-monitor PORT=COM7` |
| Validate data accuracy | `make node-validate` | `make node-validate` |
| Record CSI to disk | `make node-observe` | `make node-observe` |

---

## Multi-node setup

Each node needs a unique `--node-id`. Plug in one node at a time and provision each:

```bash
# Node 2 (macOS — change port for Windows)
python firmware/esp32-csi-node/provision.py \
  --port /dev/cu.usbmodem1101 \
  --ssid "YourWiFiName" --password "yourpass" \
  --target-ip 192.168.1.45 \
  --node-id 2

# Node 3
python firmware/esp32-csi-node/provision.py \
  --port /dev/cu.usbmodem1101 \
  --ssid "YourWiFiName" --password "yourpass" \
  --target-ip 192.168.1.45 \
  --node-id 3
```

All nodes send to the same UDP port 5005. The `node_id` field in each packet tells them apart.

---

## Next steps

Once all checks pass:

- **Record a session** — `make node-observe` saves raw CSI to `data/recordings/`
- **Live visualization** — `make run-sensing-server` then open the UI
- **Pose pipeline** — pipe recordings into the Python inference stack (`v1/`)
- **Add more nodes** — 3–6 nodes give full-room 3D coverage
