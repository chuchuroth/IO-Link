# Nucleo Firmware — User Code Integration

`main.c` is **not tracked in git** — CubeMX regenerates it and owns it entirely.
`app.c` / `app.h` contain all application logic and **are** tracked in git.

## One-Time Setup: 3 Lines to Add to Your CubeMX main.c

After generating code in CubeIDE, add these **3 snippets** to the CubeMX-generated `main.c`:

### 1. In `/* USER CODE BEGIN Includes */`
```c
#include "app.h"
```

### 2. In `/* USER CODE BEGIN 2 */`  (after all `MX_xxx_Init()` calls)
```c
app_init(&hspi1);
```

### 3. In `/* USER CODE BEGIN WHILE */`  (inside `while (1)`)
```c
app_run();
```

---

## What app.c Does

- `app_init()` — calls `iolink_init()` and arms the first SPI slave transfer
- `app_run()` — processes one pending SPI command per call:
  - `CMD_GRIP (0x01)` → runs `iolink_cycle(GRIP)` → sets `spi_tx_byte = RSP_GRIPPING`
  - `CMD_RELEASE (0x02)` → runs `iolink_cycle(RELEASE)` → sets `spi_tx_byte = RSP_RELEASING`
  - `CMD_STATUS (0x03)` → reads PDin from device → returns GRIPPING / RELEASING / IDLE
- `HAL_SPI_TxRxCpltCallback()` — defined in `app.c`; only sets `new_cmd_flag`, does NOT re-arm early (that was the root cause of the IDLE responses)

## Files tracked in git

| File | Purpose |
|---|---|
| `Core/Src/app.c` | All application logic |
| `Core/Inc/app.h` | Public API + integration instructions |
| `Core/Src/iolink.c` | IO-Link driver (echo-flush fix included) |
| `Core/Inc/iolink.h` | IO-Link API + constants |

## Files NOT tracked in git (owned by CubeMX)

- `Core/Src/main.c` — contains real `SystemClock_Config`, `MX_GPIO_Init`, `MX_SPI1_Init`, etc.
