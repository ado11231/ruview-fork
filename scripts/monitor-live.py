#!/usr/bin/env python3
"""
Live CSI terminal dashboard — reads ESP32 serial output and renders
a real-time display: frame rate, RSSI bar, channel, health status.

Usage:
    python scripts/monitor-live.py /dev/cu.usbmodem1101
    python scripts/monitor-live.py /dev/cu.usbmodem1101 --baud 115200
"""

import argparse
import re
import sys
import time
from collections import deque

import serial

PATTERN = re.compile(r"CSI cb #(\d+): len=(\d+) rssi=(-?\d+) ch=(\d+)")
RSSI_BAR_WIDTH = 30
HISTORY = 20  # frames to keep for rate calculation

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
CLEAR  = "\033[2J\033[H"


def rssi_color(rssi):
    if rssi >= -50:
        return GREEN
    if rssi >= -65:
        return YELLOW
    return RED


def rssi_bar(rssi):
    # -30 dBm = full bar, -90 dBm = empty
    ratio = max(0.0, min(1.0, (rssi + 90) / 60))
    filled = int(ratio * RSSI_BAR_WIDTH)
    color = rssi_color(rssi)
    bar = color + "█" * filled + RESET + "░" * (RSSI_BAR_WIDTH - filled)
    return bar


def health_label(fps, rssi):
    if fps < 10:
        return RED + "SLOW" + RESET
    if fps < 40:
        return YELLOW + "OK" + RESET
    if rssi < -75:
        return YELLOW + "WEAK SIGNAL" + RESET
    return GREEN + "GOOD" + RESET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port", nargs="?", default="/dev/cu.usbmodem1101")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as e:
        print(f"Cannot open {args.port}: {e}")
        sys.exit(1)

    timestamps = deque(maxlen=HISTORY)
    last_frame = 0
    last_rssi = 0
    last_ch = 0
    last_len = 0
    total = 0
    dropped = 0
    prev_seq = None

    print(f"\n{CYAN}WiFi-DensePose CSI Monitor{RESET} — {args.port} @ {args.baud}")
    print("Press Ctrl+C to quit\n")

    try:
        while True:
            raw = ser.readline()
            if not raw:
                continue
            try:
                line = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                continue

            m = PATTERN.search(line)
            if not m:
                continue

            seq    = int(m.group(1))
            length = int(m.group(2))
            rssi   = int(m.group(3))
            ch     = int(m.group(4))

            now = time.monotonic()
            timestamps.append(now)
            total += 1

            if prev_seq is not None and seq > prev_seq + 1:
                dropped += seq - prev_seq - 1
            prev_seq = seq

            last_frame = seq
            last_rssi  = rssi
            last_ch    = ch
            last_len   = length

            # Frame rate over recent window
            if len(timestamps) >= 2:
                elapsed = timestamps[-1] - timestamps[0]
                fps = (len(timestamps) - 1) / elapsed if elapsed > 0 else 0.0
            else:
                fps = 0.0

            subcarriers = length // 2

            sys.stdout.write(CLEAR)
            sys.stdout.write(
                f"{BOLD}{CYAN}╔══ CSI Live Monitor ══════════════════════════╗{RESET}\n"
                f"{BOLD}{CYAN}║{RESET}  Port       {CYAN}{args.port}{RESET}\n"
                f"{BOLD}{CYAN}║{RESET}  Frame #    {BOLD}{last_frame}{RESET}\n"
                f"{BOLD}{CYAN}║{RESET}  Channel    {BOLD}{last_ch}{RESET}\n"
                f"{BOLD}{CYAN}║{RESET}  Frame len  {last_len} bytes → {subcarriers} subcarriers\n"
                f"{BOLD}{CYAN}║{RESET}\n"
                f"{BOLD}{CYAN}║{RESET}  RSSI  {rssi_color(last_rssi)}{last_rssi} dBm{RESET}\n"
                f"{BOLD}{CYAN}║{RESET}  {rssi_bar(last_rssi)}\n"
                f"{BOLD}{CYAN}║{RESET}\n"
                f"{BOLD}{CYAN}║{RESET}  Rate    {BOLD}{fps:.1f} fps{RESET}\n"
                f"{BOLD}{CYAN}║{RESET}  Total   {total} frames received\n"
                f"{BOLD}{CYAN}║{RESET}  Dropped {dropped} frames (gaps in seq)\n"
                f"{BOLD}{CYAN}║{RESET}\n"
                f"{BOLD}{CYAN}║{RESET}  Health  {health_label(fps, last_rssi)}\n"
                f"{BOLD}{CYAN}╚══════════════════════════════════════════════╝{RESET}\n"
            )
            sys.stdout.flush()

    except KeyboardInterrupt:
        print(f"\n\nStopped. Total frames: {total}, Dropped: {dropped}")
        ser.close()


if __name__ == "__main__":
    main()
