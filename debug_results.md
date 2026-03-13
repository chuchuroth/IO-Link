# Debug Results — Industrial Automation Closed-Loop Demo

**System:** Raspberry Pi 5 → NUCLEO-F746ZG → TIOL221EVM → Zimmer LWR50L-02 gripper  
**Date:** 2026-03-13  
**Repo:** `git@github.com:chuchuroth/IO-Link.git`

---

## System Architecture

```
RPi5 (Python controller)
  │  SPI0.0 @ 1 MHz, Mode 0, full-duplex
  ▼
NUCLEO-F746ZG (STM32F746ZG, SPI1 slave)
  │  UART4 @ 38400 baud (IO-Link COM2), half-duplex C/Q line
  ▼
TIOL221EVM (IO-Link transceiver)
  │  24 V IO-Link C/Q line
  ▼
Zimmer LWR50L-02 (Class B IO-Link gripper)
```

**SPI Protocol (1-byte frames):**

| Byte (RPi5 → Nucleo) | Meaning |
|---|---|
| `0x01` CMD_GRIP | Close gripper |
| `0x02` CMD_RELEASE | Open gripper |
| `0x03` CMD_STATUS | Read device status |

| Byte (Nucleo → RPi5) | Meaning |
|---|---|
| `0x00` RSP_IDLE | Idle / waiting |
| `0x01` RSP_GRIPPING | Grip command accepted / confirmed |
| `0x02` RSP_RELEASING | Release command accepted / confirmed |
| `0xFF` RSP_ERROR | IO-Link timeout or CRC failure |

---

## Bugs Found and Fixed

### Bug 1 — Wrong source file edited (all early fixes went to the wrong path)

**Symptom:** Every firmware fix had no effect after reflash.

**Root cause:** All edits were going to `nucleo/Core/Src/iolink.c` and `nucleo/Core/Src/main.c`, but the CubeIDE project compiles from `nucleo/industrial_automation_nucleo/Core/Src/`. The two directory trees are separate — git was tracking the wrong one.

**Fix:** Identified the correct path via `find`. All subsequent edits target `nucleo/industrial_automation_nucleo/Core/Src/`.

---

### Bug 2 — TIOL221EVM UART echo consumed device response

**Symptom:** `iolink_cycle()` always returned `IOLINK_ERR_TIMEOUT` or garbled data. Gripper never moved.

**Root cause:** While `EN=HIGH` (transmitting), the TIOL221EVM echoes all 3 TX bytes back on the DOUT/RX line. `HAL_UART_Receive` consumed these echo bytes instead of the real 2-byte device D-sequence response.

**Fix:** Added echo flush in `iolink_cycle()` after `HAL_UART_Transmit`, before reading the device response:

```c
// After HAL_UART_Transmit (EN set LOW):
uint8_t echo[3];
HAL_UART_Receive(&huart4, echo, 3, 3);          // drain echo bytes
huart4.Instance->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NCF;
huart4.RxState = HAL_UART_STATE_READY;
// Now receive real response:
HAL_UART_Receive(&huart4, rx, 2, UART_RX_TIMEOUT_MS);
```

**Note on macro name:** STM32F7 uses `USART_ICR_NCF` (Noise Clear Flag), not `USART_ICR_NECF` — the latter does not exist on this family.

**Commit:** `6bcc2ec`

---

### Bug 3 — CubeMX regenerated `main.h`, wiping CMD/RSP constants

**Symptom:** CubeIDE build error: `'RSP_IDLE' undeclared here (not in a function)` for all CMD/RSP constants.

**Root cause:** CubeMX regenerates `main.h` on every "Generate Code" run, overwriting custom `#define` constants.

**Fix:** Moved all CMD/RSP constants from `main.h` to `iolink.h` (never touched by CubeMX). Added `void Error_Handler(void);` declaration to `main.h` and `Error_Handler()` definition to `main.c` (required by CubeMX-generated `stm32f7xx_hal_msp.c`).

**Commits:** `ee81cf0`, `4951f34`

---

### Bug 4 — `spi_arm_next_transfer()` called in ISR before `spi_tx_byte` was updated

**Symptom:** After the echo flush fix, SPI responses were still always `RSP_IDLE` regardless of command.

**Root cause:** `HAL_SPI_TxRxCpltCallback` called `spi_arm_next_transfer()` immediately when the SPI transfer completed. This loaded the **current** `spi_tx_byte` (still `RSP_IDLE`) into the SPI TX hardware register. The main loop then ran `iolink_cycle()` and updated `spi_tx_byte = RSP_GRIPPING`, but it was too late — the TX register was already loaded for the next transfer.

**Fix:** Removed `spi_arm_next_transfer()` from the ISR. The ISR now only sets `new_cmd_flag = 1`. The main loop calls `spi_arm_next_transfer()` **after** updating `spi_tx_byte`:

```c
// ISR — only flag:
void HAL_SPI_TxRxCpltCallback(SPI_HandleTypeDef *hspi) {
    if (hspi->Instance != SPI1) return;
    new_cmd_flag = 1;   // NO spi_arm_next_transfer() here
}

// Main loop — update response THEN arm:
case CMD_GRIP:
    rc = iolink_cycle(IOLINK_PD_GRIP, &pd_in);
    spi_tx_byte = (rc == IOLINK_OK) ? RSP_GRIPPING : RSP_ERROR;
    break;
// ...
spi_arm_next_transfer();   // called AFTER switch block
```

**Commit:** `a86af3d`

---

### Bug 5 — `main.c` init stubs had no bodies (root cause of 0x00 SPI response)

**Symptom:** Diagnostic PING test (`0xAA → expect 0x55`) returned `0x00`. SPI peripheral was not responding at all.

**Root cause:** Our repo's `main.c` contained **stub** implementations of `SystemClock_Config()`, `MX_GPIO_Init()`, `MX_SPI1_Init()`, `MX_USART4_UART_Init()` with no code bodies. When pulled from git to the CubeIDE machine, these stubs silently replaced the CubeMX-generated functions that contain the real peripheral init code. The MCU booted but SPI was never initialized.

**Fix:** Removed `main.c` from git tracking entirely (`.gitignore`). Moved all application logic into `app.c` / `app.h` which are CubeMX-safe (never touched by code regeneration).

Integration into the CubeMX-owned `main.c` is reduced to 3 lines in USER CODE sections — see [INTEGRATION.md](nucleo/industrial_automation_nucleo/INTEGRATION.md).

**Commit:** `007d643`

---

## Current Status

| Layer | Status |
|---|---|
| RPi5 Python controller (`main.py`) | ✅ Running |
| SPI communication (RPi5 ↔ Nucleo) | ⏳ Pending re-test after Bug 5 fix |
| IO-Link UART driver (echo-flush) | ✅ Fixed |
| Gripper physical motion | ⏳ Pending reflash with new app.c structure |

---

## Next Steps

1. In CubeIDE: pull latest → add `app.c` to build → add 3 USER CODE lines to `main.c` → Clean → Build → Flash
2. Run PING test to confirm SPI layer:
   ```bash
   sudo python3 - <<'EOF'
   import spidev, time
   spi = spidev.SpiDev(); spi.open(0,0); spi.max_speed_hz=1_000_000; spi.mode=0
   def xfr(c): time.sleep(0.00002); return spi.xfer2([c])[0]
   xfr(0x01); time.sleep(0.3); r = xfr(0x01)
   print("GRIP:", {0x01:"GRIPPING",0x00:"IDLE",0xFF:"ERROR"}.get(r, hex(r)))
   spi.close()
   EOF
   ```
3. Once `GRIPPING` / `RELEASING` confirmed, run full closed-loop demo: `sudo python3 main.py`

---

## File Map (tracked in git)

```
nucleo/industrial_automation_nucleo/
├── Core/
│   ├── Inc/
│   │   ├── app.h          ← application API + CubeMX integration instructions
│   │   ├── iolink.h       ← IO-Link driver API + CMD/RSP SPI constants
│   │   └── main.h         ← Error_Handler declaration only
│   └── Src/
│       ├── app.c          ← SPI dispatch loop + HAL_SPI callback (CubeMX-safe)
│       └── iolink.c       ← IO-Link master driver (echo-flush fix included)
└── INTEGRATION.md         ← 3-line recipe for CubeMX main.c
```

`main.c` is **not tracked** (gitignored) — owned entirely by CubeMX.
