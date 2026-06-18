# SPDX-FileCopyrightText: 2026 A Labs GmbH
# SPDX-License-Identifier: Apache-2.0

import logging
import struct
from pathlib import Path

from crccheck.crc import CrcArc

from .chips import CHIP_REGISTRY, MAGIC_WORD_REGISTRY, ChipConfig
from .exceptions import (
    CRCError,
    ProtocolError,
    UnknownChipError,
    UnsupportedOperationError,
)
from .hci import (
    EVENT_PREFIX_LENGTH,
    CommandCompleteEvent,
    HciCommand,
    HciEventStatus,
    OpCode,
    RegType,
)
from .serial import SerialInterface

_FW_DIR: Path = Path(__file__).parent.parent / "fw"

# Magic word ROM address (fallback chip detection method)
_MAGIC_WORD_ADDRESS: int = 0x00032000

# Firmware-loader download
LOADER_CHUNK_SIZE: int = 0xFC  # 252 bytes per frame

_START_FW_LOADER_RESPONSE_LENGTH: int = 93
_MP_PAYLOAD_OFFSET: int = 6
_EUID_OFFSET: int = 69
_EUID_LENGTH: int = 14

# eFuse
EFUSE_CRC16_UNBURNED: bytes = b"\xff\xff"
EFUSE_CRC16_SIZE: int = 2


class BootloaderComInterface:
    """Communication with Realtek chip in bootloader mode."""

    def __init__(
        self,
        transport: SerialInterface,
    ) -> None:
        self._transport = transport
        self._log = logging.getLogger("rtkprog.bootloader")

    def _send_command(
        self, opcode: OpCode | int, params: bytes = b""
    ) -> CommandCompleteEvent:
        # Send HCI command and read back its command complete event
        self._transport.transmit(bytes(HciCommand(opcode, params)))
        return self._read_command_complete()

    def _read_command_complete(self) -> CommandCompleteEvent:
        prefix = self._transport.receive(EVENT_PREFIX_LENGTH)
        if len(prefix) == 0:
            raise ProtocolError(f"No response received")
        if len(prefix) < EVENT_PREFIX_LENGTH:
            raise ProtocolError(f"Too few bytes received: {len(prefix)}/{EVENT_PREFIX_LENGTH}")
        params = self._transport.receive(prefix[-1]) # params length
        return CommandCompleteEvent.parse(prefix + params)

    def probe_chip(self) -> ChipConfig:
        self._log.info("Probing chip")

        chip_id = self._read_chip_id()
        if chip_id is not None:
            chip = CHIP_REGISTRY.get(chip_id)
            if chip is None:
                raise UnknownChipError(f"Unsupported chip ID: 0x{chip_id:02X}")
            self._log.info("Detected %s (chip ID: 0x%02X)", chip.name, chip_id)
            return chip

        # Reading chip id returned IC_TYPE_ERR, using magic-word fallback
        magic_word = self._read_magic_word()
        chip = MAGIC_WORD_REGISTRY.get(magic_word)
        if chip is None:
            raise UnknownChipError(f"Unrecognised magic word: 0x{magic_word:08X}")
        self._log.info("Detected %s (magic word 0x%08X)", chip.name, magic_word)
        return chip

    def _read_chip_id(self) -> int | None:
        event = self._send_command(OpCode.READ_RTK_CHIP_ID)
        if event.opcode != OpCode.READ_RTK_CHIP_ID:
            raise ProtocolError(
                f"Unexpected reply to read chip ID: {event.raw.hex()}"
            )
        if event.status == HciEventStatus.IC_TYPE_ERR:
            self._log.debug("Read chip ID returned IC_TYPE_ERR")
            return None
        if event.status != HciEventStatus.SUCCESS:
            raise ProtocolError(
                f"Read chip ID failed with status 0x{event.status:02X}"
            )
        if not event.return_params:
            raise ProtocolError(f"Read chip ID returned no id: {event.raw.hex()}")
        return event.return_params[0]

    def _read_magic_word(self) -> int:
        # Fallback chip detection by reading magic word at 0x00032000
        params = struct.pack("<BI", RegType.NORMAL, _MAGIC_WORD_ADDRESS)
        self._transport.serial.reset_input_buffer()
        event = self._send_command(OpCode.VENDOR_READ, params).check(OpCode.VENDOR_READ)
        if len(event.return_params) < 4:
            raise ProtocolError(f"Magic word read too short: {event.raw.hex()}")
        return int.from_bytes(event.return_params[:4], "little")

    def upload_firmware_loader(self, chip: ChipConfig) -> None:
        self._log.info("Uploading firmware loader")
        firmware = b"".join(
            (_FW_DIR / name).read_bytes() for name in chip.loader_firmware_files
        )
        for frame_index, offset in enumerate(range(0, len(firmware), LOADER_CHUNK_SIZE)):
            chunk = firmware[offset : offset + LOADER_CHUNK_SIZE]
            frame_byte = bytes((frame_index & 0xFF,))

            event = self._send_command(
                OpCode.LOAD_FIRMWARE, frame_byte + chunk
            ).check(OpCode.LOAD_FIRMWARE)
            if event.return_params[:1] != frame_byte:
                raise ProtocolError(
                    f"Loader frame {frame_index}: ack echoed wrong fragment number "
                    f"{event.return_params[:1].hex()}"
                )

    def start_firmware_loader(self, chip: ChipConfig) -> None:
        self._log.info("Starting firmware loader")
        params = struct.pack(
            "<BII",
            RegType.NORMAL,
            chip.fw_loader_trigger_addr,
            chip.fw_loader_trigger_value,
        )
        self._transport.transmit(bytes(HciCommand(OpCode.VENDOR_WRITE, params)))

        response = self._transport.receive(_START_FW_LOADER_RESPONSE_LENGTH)
        if CommandCompleteEvent.parse(response).opcode != OpCode.VENDOR_WRITE:
            raise ProtocolError(f"Unexpected firmware loader response: {response.hex()}")

        payload = response[_MP_PAYLOAD_OFFSET:]
        if CrcArc.calc(payload) != 0:
            raise CRCError("Firmware loader start response CRC mismatch")

        euid = payload[_EUID_OFFSET : _EUID_OFFSET + _EUID_LENGTH]
        self._log.info("EUID: %s", " ".join(f"{b:02X}" for b in euid))

    def read_efuse_crc16(self, chip: ChipConfig) -> bytes:
        if chip.efuse_register is None:
            raise UnsupportedOperationError(
                f"{chip.name} does not support eFuse operations"
            )

        params = struct.pack("<BI", RegType.NORMAL, chip.efuse_register)
        event = self._send_command(OpCode.VENDOR_READ, params).check(OpCode.VENDOR_READ)

        if chip.efuse_crc16_offset is None:
            raise UnsupportedOperationError(
                f"{chip.name}: efuse_register is set but efuse_crc16_offset is missing"
            )

        return event.raw[
            chip.efuse_crc16_offset : chip.efuse_crc16_offset + EFUSE_CRC16_SIZE
        ]
