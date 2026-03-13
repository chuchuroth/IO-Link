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

/* --------------------------------------------------------------------------
 * SPI command bytes (RPi5 → Nucleo)
 * -------------------------------------------------------------------------- */
#define CMD_GRIP     (0x01u)
#define CMD_RELEASE  (0x02u)
#define CMD_STATUS   (0x03u)

/* --------------------------------------------------------------------------
 * SPI response bytes (Nucleo → RPi5)
 * -------------------------------------------------------------------------- */
#define RSP_IDLE      (0x00u)
#define RSP_GRIPPING  (0x01u)
#define RSP_RELEASING (0x02u)
#define RSP_ERROR     (0xFFu)

#endif /* MAIN_H */
