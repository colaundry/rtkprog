# SPDX-FileCopyrightText: 2026 A Labs GmbH
# SPDX-License-Identifier: Apache-2.0

from .base import ChipConfig
from .rtl8752h import RTL8752H
from .rtl8762c import RTL8762C
from .rtl8762g import RTL8762G
from .rtl8762j import RTL8762J

_CHIPS: tuple[ChipConfig, ...] = (RTL8762C, RTL8762G, RTL8752H, RTL8762J)

# Primary lookup by chip ID
CHIP_REGISTRY: dict[int, ChipConfig] = {chip.chip_id: chip for chip in _CHIPS}

# Fallback lookup by magic word
MAGIC_WORD_REGISTRY: dict[int, ChipConfig] = {
    chip.magic_word: chip for chip in _CHIPS if chip.magic_word is not None
}

__all__ = [
    "ChipConfig",
    "CHIP_REGISTRY",
    "MAGIC_WORD_REGISTRY",
    "RTL8762C",
    "RTL8762G",
    "RTL8752H",
    "RTL8762J",
]
