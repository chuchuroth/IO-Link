"""
main.py — Entry point for the RPi5 industrial automation controller.

Usage:
    sudo python3 main.py [--log-level DEBUG|INFO|WARNING]

sudo is required for RPi.GPIO on Raspberry Pi OS.
"""

import argparse
import logging
import sys

import sensors
from spi_master import SPIMaster
from controller import Controller


def parse_args():
    parser = argparse.ArgumentParser(
        description="Industrial Automation Closed-Loop Controller (RPi5)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging verbosity (default: INFO)",
    )
    return parser.parse_args()


def setup_logging(level_name: str):
    logging.basicConfig(
        level=getattr(logging, level_name),
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("automation.log"),
        ],
    )


def main():
    args = parse_args()
    setup_logging(args.log_level)

    log = logging.getLogger("main")
    log.info("=== Industrial Automation Controller starting ===")

    # Initialise GPIO for sensors
    log.info("Initialising GPIO sensors (HC-SR04, HC-SR501)...")
    sensors.setup()

    # Open SPI link to Nucleo
    log.info("Opening SPI0.0 link to NUCLEO-F746ZG...")
    spi = SPIMaster()

    try:
        controller = Controller(spi)
        controller.run()
    finally:
        log.info("Cleaning up...")
        spi.close()
        sensors.cleanup()
        log.info("=== Controller stopped ===")


if __name__ == "__main__":
    main()
