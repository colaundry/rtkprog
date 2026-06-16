# SPDX-FileCopyrightText: 2026 A Labs GmbH
# SPDX-License-Identifier: Apache-2.0

from .base import ChipConfig

RTL8762J = ChipConfig(
    name="RTL8762J",
    chip_id=0x3B,
    magic_word=None,
    loader_firmware_files=("RTL87x2J_FW_A.bin", "flash_avl.bin"),
    flash_start=0x2000000,
    flash_end=0x3000000,
    flash_page_size=0x400,
    flash_address_mac=None,
    efuse_register=None,
    efuse_crc16_offset=None,
    fw_loader_trigger_addr=0x2001997C,
    fw_loader_trigger_value=0x20006031,
)
