# Industrial Automation Closed-Loop Demo — Build & Run Guide

## Project Structure

```
industrial_automation/
├── README.md                    ← this file
├── rpi5/                        ← Raspberry Pi 5 Python application
│   ├── requirements.txt
│   ├── main.py                  ← entry point
│   ├── sensors.py               ← HC-SR04 ultrasonic + HC-SR501 PIR drivers
│   ├── spi_master.py            ← SPI1 master (talks to Nucleo)
│   └── controller.py            ← closed-loop state machine
└── nucleo/                      ← NUCLEO-F746ZG STM32 firmware
    ├── README.md                ← Nucleo build instructions
    └── Core/
        ├── Inc/
        │   ├── main.h           ← SPI command/response constants
        │   └── iolink.h         ← IO-Link master API
        └── Src/
            ├── main.c           ← SPI slave + command dispatcher
            └── iolink.c         ← IO-Link master driver (COM2, 1-byte PD)
```

---

## System Summary

```
[HC-SR04]──GPIO23/24──┐
                       ├──[RPi5 Python]──SPI0.0──[NUCLEO-F746ZG]──UART4──[TIOL221EVM]──C/Q──[Zimmer LWR50L-02]
[HC-SR501]──GPIO25─────┘
```

| Layer | Technology | File(s) |
|---|---|---|
| Sensing | HC-SR04 + HC-SR501 via GPIO | `sensors.py` |
| Control logic | Python state machine | `controller.py` |
| RPi5 ↔ Nucleo | SPI (1 MHz, 1-byte frames) | `spi_master.py` / `main.c` |
| IO-Link master | UART4 + TIOL221EVM, COM2 38400 baud | `iolink.c` |
| Actuator | Zimmer LWR50L-02 gripper | IO-Link PDout byte |

---

## Part 1 — Raspberry Pi 5

### Prerequisites

- Raspberry Pi OS (64-bit, Bookworm or later)
- SPI enabled: `sudo raspi-config` → Interface Options → SPI → Enable
- Python 3.11+

### Install dependencies

```bash
cd rpi5/
pip3 install -r requirements.txt
```

### Run

```bash
sudo python3 main.py
```

Optional verbose logging:

```bash
sudo python3 main.py --log-level DEBUG
```

`sudo` is required for low-level GPIO access via RPi.GPIO.

Logs are written to both stdout and `automation.log` in the working directory.

### Stop

Press **Ctrl+C**. The controller sends a RELEASE command before exiting.

---

## Part 2 — NUCLEO-F746ZG Firmware

See [nucleo/README.md](nucleo/README.md) for full build and flash instructions.

### Quick summary

1. Open STM32CubeIDE.
2. Create a new project for **NUCLEO-F746ZG**.
3. Configure peripherals in CubeMX (see `nucleo/README.md`).
4. Copy `nucleo/Core/Inc/` and `nucleo/Core/Src/` into the generated project.
5. Build and flash via the ST-Link on the Nucleo board.

---

## SPI Protocol Reference

| Byte | Direction | Meaning |
|---|---|---|
| `0x01` | RPi5 → Nucleo | CMD_GRIP — close gripper |
| `0x02` | RPi5 → Nucleo | CMD_RELEASE — open gripper |
| `0x03` | RPi5 → Nucleo | CMD_STATUS — read current state |
| `0x00` | Nucleo → RPi5 | RSP_IDLE |
| `0x01` | Nucleo → RPi5 | RSP_GRIPPING |
| `0x02` | Nucleo → RPi5 | RSP_RELEASING |
| `0xFF` | Nucleo → RPi5 | RSP_ERROR |

---

## Control Loop Behaviour

```
IDLE  ──object present──►  GRIPPING  ──grip confirmed──►  RELEASING  ──open confirmed──►  IDLE
  ▲                              │                               │
  └──────────── timeout ─────────┘◄──────────── timeout ────────┘
```

- Detection threshold: `OBJECT_THRESHOLD_CM = 30 cm` (ultrasonic) **OR** PIR active.
- State transition timeout: `TRANSITION_TIMEOUT_S = 3 s`.
- Poll interval: `POLL_INTERVAL_S = 0.1 s` (10 Hz).
