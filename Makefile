# WiFi-DensePose Makefile
# ============================================================

.PHONY: verify verify-verbose verify-audit install install-verify install-python \
        install-rust install-browser install-docker install-field install-full \
        check build-rust build-wasm test-rust bench run-api run-viz clean help \
        node-build node-flash node-provision node-monitor node-observe

# ─── ESP32 Node ──────────────────────────────────────────────
# Build firmware inside ESP-IDF Docker container (required on all platforms)
node-build:
	MSYS_NO_PATHCONV=1 docker run --rm \
	  -v "$(shell pwd)/firmware/esp32-csi-node:/project" -w /project \
	  espressif/idf:v5.2 bash -c \
	  "rm -rf build sdkconfig && idf.py set-target esp32s3 && idf.py build"

# Flash firmware  — usage: make node-flash PORT=COM7
node-flash:
	python -m esptool --chip esp32s3 --port $(PORT) --baud 460800 \
	  write_flash --flash_mode dio --flash_size 8MB \
	  0x0    firmware/esp32-csi-node/build/bootloader/bootloader.bin \
	  0x8000 firmware/esp32-csi-node/build/partition_table/partition-table.bin \
	  0x10000 firmware/esp32-csi-node/build/esp32-csi-node.bin

# Provision WiFi — usage: make node-provision PORT=COM7 SSID="MyWifi" PASSWORD="secret" IP=192.168.1.20
node-provision:
	python firmware/esp32-csi-node/provision.py \
	  --port $(PORT) --ssid "$(SSID)" --password "$(PASSWORD)" --target-ip $(IP)

# Open serial monitor — usage: make node-monitor PORT=COM7
node-monitor:
	python -m serial.tools.miniterm $(PORT) 115200

# Listen for live CSI packets on UDP 5005 (Ctrl+C to stop)
node-observe:
	python scripts/record-csi-udp.py --port 5005 --duration 3600 --output data/recordings

# ─── Installation ────────────────────────────────────────────
# Guided interactive installer
install:
	@./install.sh

# Profile-specific installs (non-interactive)
install-verify:
	@./install.sh --profile verify --yes

install-python:
	@./install.sh --profile python --yes

install-rust:
	@./install.sh --profile rust --yes

install-browser:
	@./install.sh --profile browser --yes

install-docker:
	@./install.sh --profile docker --yes

install-field:
	@./install.sh --profile field --yes

install-full:
	@./install.sh --profile full --yes

# Hardware and environment check only (no install)
check:
	@./install.sh --check-only

# ─── Verification ────────────────────────────────────────────
# Trust Kill Switch -- one-command proof replay
verify:
	@./verify

# Verbose mode -- show detailed feature statistics and Doppler spectrum
verify-verbose:
	@./verify --verbose

# Full audit -- verify pipeline + scan codebase for mock/random patterns
verify-audit:
	@./verify --verbose --audit

# ─── Rust Builds ─────────────────────────────────────────────
build-rust:
	cd rust-port/wifi-densepose-rs && cargo build --release

build-wasm:
	cd rust-port/wifi-densepose-rs && wasm-pack build crates/wifi-densepose-wasm --target web --release

build-wasm-mat:
	cd rust-port/wifi-densepose-rs && wasm-pack build crates/wifi-densepose-wasm --target web --release -- --features mat

test-rust:
	cd rust-port/wifi-densepose-rs && cargo test --workspace

bench:
	cd rust-port/wifi-densepose-rs && cargo bench --package wifi-densepose-signal

# ─── Run ─────────────────────────────────────────────────────
run-api:
	uvicorn v1.src.api.main:app --host 0.0.0.0 --port 8000

run-api-dev:
	uvicorn v1.src.api.main:app --host 0.0.0.0 --port 8000 --reload

run-viz:
	python3 -m http.server 3000 --directory ui

run-docker:
	docker compose up

# ─── Clean ───────────────────────────────────────────────────
clean:
	rm -f .install.log
	cd rust-port/wifi-densepose-rs && cargo clean 2>/dev/null || true

# ─── Help ────────────────────────────────────────────────────
help:
	@echo "WiFi-DensePose Build Targets"
	@echo "============================================================"
	@echo ""
	@echo "  ESP32 Node (see docs/node-setup.md):"
	@echo "    make node-build                    Build firmware (Docker)"
	@echo "    make node-flash PORT=COM7          Flash firmware to device"
	@echo "    make node-provision PORT=COM7 \\"
	@echo "      SSID=MyWifi PASSWORD=secret \\"
	@echo "      IP=192.168.1.20                  Write WiFi credentials (no reflash)"
	@echo "    make node-monitor PORT=COM7        Open serial monitor"
	@echo "    make node-observe                  Listen for live CSI packets"
	@echo ""
	@echo "  Installation:"
	@echo "    make install          Interactive guided installer"
	@echo "    make install-verify   Verification only (~5 MB)"
	@echo "    make install-python   Full Python pipeline (~500 MB)"
	@echo "    make install-rust     Rust pipeline with ~810x speedup"
	@echo "    make install-browser  WASM for browser (~10 MB)"
	@echo "    make install-docker   Docker-based deployment"
	@echo "    make install-field    WiFi-Mat disaster kit (~62 MB)"
	@echo "    make install-full     Everything available"
	@echo "    make check            Hardware/environment check only"
	@echo ""
	@echo "  Verification:"
	@echo "    make verify           Run the trust kill switch"
	@echo "    make verify-verbose   Verbose with feature details"
	@echo "    make verify-audit     Full verification + codebase audit"
	@echo ""
	@echo "  Build:"
	@echo "    make build-rust       Build Rust workspace (release)"
	@echo "    make build-wasm       Build WASM package (browser)"
	@echo "    make build-wasm-mat   Build WASM with WiFi-Mat (field)"
	@echo "    make test-rust        Run all Rust tests"
	@echo "    make bench            Run signal processing benchmarks"
	@echo ""
	@echo "  Run:"
	@echo "    make run-api          Start Python API server"
	@echo "    make run-api-dev      Start API with hot-reload"
	@echo "    make run-viz          Serve 3D visualization (port 3000)"
	@echo "    make run-docker       Start Docker dev stack"
	@echo ""
	@echo "  Utility:"
	@echo "    make clean            Remove build artifacts"
	@echo "    make help             Show this help"
	@echo ""
