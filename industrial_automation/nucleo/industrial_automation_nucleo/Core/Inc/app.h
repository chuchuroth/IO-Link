/**
 * @file  app.h
 * @brief Application layer for IO-Link master + SPI slave.
 *
 * Usage in CubeMX-generated main.c:
 *
 *   USER CODE BEGIN Includes
 *     #include "app.h"
 *   USER CODE END Includes
 *
 *   USER CODE BEGIN 2         (after all MX_xxx_Init calls)
 *     app_init(&hspi1);
 *   USER CODE END 2
 *
 *   USER CODE BEGIN WHILE
 *     app_run();
 *   USER CODE END WHILE
 *
 * The SPI callback HAL_SPI_TxRxCpltCallback is defined in app.c and
 * is automatically called by the HAL IRQ handler — no extra wiring needed.
 */

#ifndef APP_H
#define APP_H

#include "stm32f7xx_hal.h"

/**
 * @brief Initialise IO-Link and arm the first SPI slave transfer.
 * @param spi  Pointer to the CubeMX-generated hspi1 handle.
 */
void app_init(SPI_HandleTypeDef *spi);

/**
 * @brief Process any pending SPI command.  Call inside the main while(1) loop.
 */
void app_run(void);

#endif /* APP_H */
