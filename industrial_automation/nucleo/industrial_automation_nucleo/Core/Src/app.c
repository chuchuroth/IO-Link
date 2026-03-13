/**
 * @file  app.c
 * @brief Application logic: SPI slave command dispatcher + IO-Link control.
 *
 * This file is CubeMX-safe — it contains only application code and is never
 * touched by CubeMX code regeneration.
 *
 * Integration into CubeMX main.c (see app.h for the full recipe):
 *   1. #include "app.h"   in USER CODE BEGIN Includes
 *   2. app_init(&hspi1);  in USER CODE BEGIN 2  (after MX inits)
 *   3. app_run();         in USER CODE BEGIN WHILE
 */

#include "app.h"
#include "iolink.h"
#include "stm32f7xx_hal.h"

/* --------------------------------------------------------------------------
 * SPI protocol constants (RPi5 ↔ Nucleo)
 * -------------------------------------------------------------------------- */
#define CMD_GRIP      (0x01u)
#define CMD_RELEASE   (0x02u)
#define CMD_STATUS    (0x03u)

#define RSP_IDLE      (0x00u)
#define RSP_GRIPPING  (0x01u)
#define RSP_RELEASING (0x02u)
#define RSP_ERROR     (0xFFu)

/* --------------------------------------------------------------------------
 * Module state
 * -------------------------------------------------------------------------- */
static SPI_HandleTypeDef *g_spi = NULL;

static volatile uint8_t spi_rx_byte  = 0x00;
static volatile uint8_t spi_tx_byte  = RSP_IDLE;
static volatile uint8_t new_cmd_flag = 0;

/* --------------------------------------------------------------------------
 * Internal helpers
 * -------------------------------------------------------------------------- */
static void spi_arm_next_transfer(void)
{
    HAL_SPI_TransmitReceive_IT(g_spi,
                               (uint8_t *)&spi_tx_byte,
                               (uint8_t *)&spi_rx_byte,
                               1);
}

/* --------------------------------------------------------------------------
 * HAL callback — fires from HAL_SPI_IRQHandler in stm32f7xx_it.c
 * -------------------------------------------------------------------------- */
void HAL_SPI_TxRxCpltCallback(SPI_HandleTypeDef *hspi)
{
    if (hspi->Instance != SPI1) return;

    /* Flag command for processing in app_run().
     * Do NOT call spi_arm_next_transfer() here — spi_tx_byte has not yet
     * been updated.  app_run() arms the next transfer after updating it. */
    new_cmd_flag = 1;
}

/* --------------------------------------------------------------------------
 * Public API
 * -------------------------------------------------------------------------- */

void app_init(SPI_HandleTypeDef *spi)
{
    g_spi = spi;

    /* IO-Link: send wake-up pulse, wait for device startup */
    iolink_init();

    /* Pre-load MISO with IDLE and arm the first SPI slave transfer */
    spi_tx_byte = RSP_IDLE;
    spi_arm_next_transfer();
}

void app_run(void)
{
    if (!new_cmd_flag) return;
    new_cmd_flag = 0;

    uint8_t cmd   = spi_rx_byte;
    uint8_t pd_in = 0x00;
    int     rc    = IOLINK_OK;

    /* Ignore 0x00 dummy bytes the RPi5 sends while reading */
    if (cmd == 0x00) {
        spi_arm_next_transfer();
        return;
    }

    switch (cmd)
    {
    case CMD_GRIP:
        rc = iolink_cycle(IOLINK_PD_GRIP, &pd_in);
        spi_tx_byte = (rc == IOLINK_OK) ? RSP_GRIPPING : RSP_ERROR;
        break;

    case CMD_RELEASE:
        rc = iolink_cycle(IOLINK_PD_RELEASE, &pd_in);
        spi_tx_byte = (rc == IOLINK_OK) ? RSP_RELEASING : RSP_ERROR;
        break;

    case CMD_STATUS:
        rc = iolink_cycle(IOLINK_PD_RELEASE, &pd_in);
        if (rc != IOLINK_OK) {
            spi_tx_byte = RSP_ERROR;
        } else if (pd_in & IOLINK_STATUS_GRIPPED) {
            spi_tx_byte = RSP_GRIPPING;
        } else if (pd_in & IOLINK_STATUS_OPEN) {
            spi_tx_byte = RSP_RELEASING;
        } else {
            spi_tx_byte = RSP_IDLE;
        }
        break;

    default:
        /* Unknown command — keep current spi_tx_byte unchanged */
        break;
    }

    /* Arm AFTER spi_tx_byte is set so the correct response is pre-loaded */
    spi_arm_next_transfer();
}
