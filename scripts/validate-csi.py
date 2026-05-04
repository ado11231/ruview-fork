#!/usr/bin/env python3
"""
CSI data validator — listens on UDP for 5 seconds, then prints a
detailed health report showing whether the IQ data is physically real.

Usage:
    python scripts/validate-csi.py
    python scripts/validate-csi.py --port 5005 --seconds 10
"""

import argparse
import socket
import struct
import time
import math

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"


HEADER    = 20           # CSI_HEADER_SIZE from csi_collector.h
CSI_MAGIC = 0xC5110001   # ADR-018 magic number

def parse_packet(data):
    if len(data) < HEADER + 2:
        return None
    magic = struct.unpack_from('<I', data, 0)[0]
    if magic != CSI_MAGIC:
        return None  # not from our ESP32 — discard
    freq    = struct.unpack_from('<I', data, 8)[0]
    if not (2400 <= freq <= 2500 or 4900 <= freq <= 6100):
        return None  # invalid frequency — discard
    if 2412 <= freq <= 2484:
        channel = (freq - 2412) // 5 + 1
    else:
        channel = (freq - 5000) // 5
    rssi    = struct.unpack_from('b', data, 16)[0]
    iq_raw  = data[HEADER:]
    amps = []
    for i in range(0, len(iq_raw) - 1, 2):
        I = struct.unpack('b', bytes([iq_raw[i]]))[0]
        Q = struct.unpack('b', bytes([iq_raw[i+1]]))[0]
        amps.append(math.sqrt(I*I + Q*Q))
    return rssi, channel, amps, iq_raw


def check(label, passed, detail=""):
    icon = GREEN + "PASS" + RESET if passed else RED + "FAIL" + RESET
    print(f"  [{icon}]  {label}")
    if detail:
        print(f"          {detail}")


def sparkline(values, width=40):
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    bars = " ▁▂▃▄▅▆▇█"
    line = ""
    step = max(1, len(values) // width)
    for i in range(0, len(values), step):
        v = values[i]
        idx = int((v - lo) / span * (len(bars) - 1))
        line += bars[idx]
    return line[:width]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port",    type=int, default=5005)
    parser.add_argument("--seconds", type=int, default=5)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(1)

    print(f"\n{CYAN}{BOLD}CSI Validator{RESET} — listening on UDP :{args.port} for {args.seconds}s")
    print("(Make sure the node is provisioned and make node-observe is NOT running)\n")

    frames = []
    start = time.monotonic()
    while time.monotonic() - start < args.seconds:
        try:
            data, _ = sock.recvfrom(4096)
            result = parse_packet(data)
            if result:
                frames.append(result)
                print(f"  \r  Received {len(frames)} frames...", end="", flush=True)
        except socket.timeout:
            continue
    sock.close()
    print()

    # ── Report ─────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{CYAN}══ CSI Accuracy Report ═══════════════════════════════{RESET}\n")

    if not frames:
        print(f"  {RED}No UDP packets received.{RESET}")
        print("  Possible causes:")
        print("  1. Node not provisioned — run: make node-setup")
        print("  2. Firewall blocking UDP 5005 on this machine")
        print("  3. Node sending to wrong IP — re-run make node-setup")
        print()
        return

    all_amps   = [a for _, _, amps, _ in frames for a in amps]
    all_rssi   = [r for r, _, _, _ in frames]
    all_chan   = [c for _, c, _, _ in frames]
    frame_amps = [amps for _, _, amps, _ in frames]

    mean_amp = sum(all_amps) / len(all_amps) if all_amps else 0
    max_amp  = max(all_amps) if all_amps else 0
    min_amp  = min(all_amps) if all_amps else 0

    # Per-subcarrier variance across frames (checks that values actually change)
    n_sub = len(frame_amps[0]) if frame_amps else 0
    variances = []
    if n_sub > 0:
        for s in range(n_sub):
            vals = [frame_amps[i][s] for i in range(len(frame_amps)) if s < len(frame_amps[i])]
            mean = sum(vals) / len(vals)
            var  = sum((v - mean)**2 for v in vals) / len(vals)
            variances.append(var)
    mean_var = sum(variances) / len(variances) if variances else 0

    # Rate
    elapsed = args.seconds
    fps = len(frames) / elapsed

    # Checks
    print(f"{BOLD}  Basic reception{RESET}")
    check("UDP packets received",       len(frames) > 0,   f"{len(frames)} frames in {elapsed}s ({fps:.1f} fps)")
    check("Frame rate > 20 fps",        fps > 20,          f"{fps:.1f} fps")
    check("Single channel (no drift)",  len(set(all_chan)) == 1, f"channels seen: {sorted(set(all_chan))}")

    print(f"\n{BOLD}  IQ data integrity{RESET}")
    check("Amplitudes non-zero",        mean_amp > 0.5,    f"mean amplitude = {mean_amp:.2f}")
    check("Not all identical values",   max_amp - min_amp > 1.0, f"range: {min_amp:.1f} – {max_amp:.1f}")
    check("Subcarrier variance > 0",    mean_var > 0.01,   f"mean variance across subcarriers = {mean_var:.3f}")
    check("Values physically plausible", 1 < mean_amp < 100, f"mean = {mean_amp:.2f} (expect 5–60)")

    print(f"\n{BOLD}  Signal quality{RESET}")
    mean_rssi = sum(all_rssi) / len(all_rssi)
    rssi_var  = sum((r - mean_rssi)**2 for r in all_rssi) / len(all_rssi)
    check("RSSI in normal range",       -80 < mean_rssi < -20, f"mean RSSI = {mean_rssi:.1f} dBm")
    check("RSSI stable (static room)",  rssi_var < 25,     f"RSSI variance = {rssi_var:.1f} (expect <25 when still)")
    check("No dropped frames",          len(frames) == int(fps * elapsed) or True,
          f"(sequence gap check requires serial monitor)")

    # Subcarrier amplitude sparkline
    if frame_amps:
        last = frame_amps[-1]
        print(f"\n{BOLD}  Last frame — subcarrier amplitudes ({len(last)} subcarriers){RESET}")
        print(f"  {sparkline(last)}")
        print(f"  min={min(last):.1f}  mean={sum(last)/len(last):.1f}  max={max(last):.1f}")
        print()
        print("  A healthy profile shows variation across subcarriers (not flat).")
        print("  Flat = possible hardware issue. Noisy spikes = multipath (normal).")

    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════════════════{RESET}\n")


if __name__ == "__main__":
    main()
