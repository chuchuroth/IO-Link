##############################################################################
# Makefile for industrial_automation_nucleo (STM32F746ZG, Cortex-M7)
# Toolchain: arm-none-eabi-gcc (apt: gcc-arm-none-eabi)
# Flash:     OpenOCD via ST-Link on NUCLEO-F746ZG
##############################################################################

TARGET   = industrial_automation_nucleo
BUILD    = build

# MCU flags
MCU      = -mcpu=cortex-m7 -mthumb -mfpu=fpv5-d16 -mfloat-abi=hard

# Preprocessor defines (match CubeIDE project)
DEFS     = -DSTM32F746xx -DUSE_HAL_DRIVER -DDEBUG

# Optimization / debug
OPT      = -Og -g3

# Linker script
LDSCRIPT = STM32F746ZGTX_FLASH.ld

##############################################################################
# Source files
##############################################################################

# Application + HAL glue
CORE_SRC = \
  Core/Src/main.c                        \
  Core/Src/app.c                         \
  Core/Src/iolink.c                      \
  Core/Src/stm32f7xx_hal_msp.c           \
  Core/Src/stm32f7xx_hal_timebase_tim.c  \
  Core/Src/stm32f7xx_it.c                \
  Core/Src/syscalls.c                    \
  Core/Src/sysmem.c                      \
  Core/Src/system_stm32f7xx.c

# HAL driver sources (only enabled modules)
HAL_DIR  = Drivers/STM32F7xx_HAL_Driver/Src
HAL_SRC  = \
  $(HAL_DIR)/stm32f7xx_hal.c             \
  $(HAL_DIR)/stm32f7xx_hal_cortex.c      \
  $(HAL_DIR)/stm32f7xx_hal_dma.c         \
  $(HAL_DIR)/stm32f7xx_hal_dma_ex.c      \
  $(HAL_DIR)/stm32f7xx_hal_exti.c        \
  $(HAL_DIR)/stm32f7xx_hal_flash.c       \
  $(HAL_DIR)/stm32f7xx_hal_flash_ex.c    \
  $(HAL_DIR)/stm32f7xx_hal_gpio.c        \
  $(HAL_DIR)/stm32f7xx_hal_pwr.c         \
  $(HAL_DIR)/stm32f7xx_hal_pwr_ex.c      \
  $(HAL_DIR)/stm32f7xx_hal_rcc.c         \
  $(HAL_DIR)/stm32f7xx_hal_rcc_ex.c      \
  $(HAL_DIR)/stm32f7xx_hal_spi.c         \
  $(HAL_DIR)/stm32f7xx_hal_tim.c         \
  $(HAL_DIR)/stm32f7xx_hal_tim_ex.c      \
  $(HAL_DIR)/stm32f7xx_hal_uart.c        \
  $(HAL_DIR)/stm32f7xx_hal_uart_ex.c

# Startup (assembly)
ASM_SRC  = Core/Startup/startup_stm32f746zgtx.s

C_SRCS   = $(CORE_SRC) $(HAL_SRC)

##############################################################################
# Include paths
##############################################################################

INCS = \
  -ICore/Inc \
  -IDrivers/CMSIS/Device/ST/STM32F7xx/Include \
  -IDrivers/CMSIS/Include \
  -IDrivers/STM32F7xx_HAL_Driver/Inc \
  -IDrivers/STM32F7xx_HAL_Driver/Inc/Legacy

##############################################################################
# Compiler / linker
##############################################################################

CC       = arm-none-eabi-gcc
AS       = arm-none-eabi-gcc -x assembler-with-cpp
OBJCOPY  = arm-none-eabi-objcopy
SIZE     = arm-none-eabi-size

CFLAGS   = $(MCU) $(DEFS) $(OPT) $(INCS) \
           -Wall -fdata-sections -ffunction-sections \
           -std=c11 --specs=nano.specs

ASFLAGS  = $(MCU) $(DEFS) $(OPT) $(INCS) \
           -Wall -fdata-sections -ffunction-sections

LDFLAGS  = $(MCU) -T$(LDSCRIPT) \
           --specs=nano.specs --specs=nosys.specs \
           -Wl,--gc-sections \
           -Wl,-Map=$(BUILD)/$(TARGET).map,--cref \
           -lc -lm -lnosys

##############################################################################
# Build rules
##############################################################################

C_OBJS   = $(addprefix $(BUILD)/, $(C_SRCS:.c=.o))
ASM_OBJS = $(addprefix $(BUILD)/, $(ASM_SRC:.s=.o))
ALL_OBJS = $(C_OBJS) $(ASM_OBJS)

.PHONY: all clean flash size

all: $(BUILD)/$(TARGET).elf $(BUILD)/$(TARGET).bin
	@$(SIZE) $<

$(BUILD)/$(TARGET).elf: $(ALL_OBJS)
	@echo "  LD   $@"
	@$(CC) $(ALL_OBJS) $(LDFLAGS) -o $@

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).elf
	@echo "  BIN  $@"
	@$(OBJCOPY) -O binary $< $@

$(BUILD)/%.o: %.c
	@mkdir -p $(dir $@)
	@echo "  CC   $<"
	@$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/%.o: %.s
	@mkdir -p $(dir $@)
	@echo "  AS   $<"
	@$(AS) $(ASFLAGS) -c $< -o $@

size: $(BUILD)/$(TARGET).elf
	$(SIZE) $<

clean:
	rm -rf $(BUILD)

flash: $(BUILD)/$(TARGET).bin
	@echo "  Flashing via OpenOCD (ST-Link)..."
	openocd \
	  -f interface/stlink.cfg \
	  -f target/stm32f7x.cfg \
	  -c "program $(BUILD)/$(TARGET).bin verify reset exit 0x08000000"
