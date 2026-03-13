/**
 * @file  main.h
 * @brief Application-level defines for NUCLEO-F746ZG firmware.
 *
 * SPI protocol (NUCLEO-F746ZG ↔ Raspberry Pi 5):
 *   SPI1 configured as Full-Duplex SLAVE, CPOL=0 CPHA=0, 8-bit, HW NSS.
 *
 *   Command bytes (RPi5 → Nucleo):
 *     0x01  CMD_GRIP      — close gripper
 *     0x02  CMD_RELEASE   — open gripper
 *     0x03  CMD_STATUS    — return current status (no IO-Link cycle triggered)
 *
 *   Response bytes (Nucleo → RPi5, transmitted during the SAME SPI byte):
 *     0x00  RSP_IDLE      — waiting for a command
 *     0x01  RSP_GRIPPING  — gripper is closing / grip confirmed
 *     0x02  RSP_RELEASING — gripper is opening / open confirmed
 *     0xFF  RSP_ERROR     — IO-Link error (timeout or CRC failure)
 */

#ifndef MAIN_H
#define MAIN_H

/* CMD_* and RSP_* constants are defined in iolink.h to survive CubeMX
 * regeneration of this file. Include iolink.h wherever they are needed. */

/* Required by stm32f7xx_hal_msp.c and other HAL files */
void Error_Handler(void);

#endif /* MAIN_H */
