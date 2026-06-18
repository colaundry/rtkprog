# SPDX-FileCopyrightText: 2026 A Labs GmbH
# SPDX-License-Identifier: Apache-2.0

from argparse import ArgumentParser
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

from rtkprog.bluetooth_mac import BluetoothMAC
from rtkprog.validation import (
    EraseRegion,
    ReadRecord,
    WriteRecord,
    erase_region,
    mac_address,
    mac_or_auto,
    read_record,
    write_record,
)

_DEFAULT_PORT: str = "/dev/ttyUSB0"
_DEFAULT_BAUD: int = 921600


@dataclass
class GlobalArgs:
    port: str
    baud: int
    v: int
    quiet: bool
    attempts: int


@dataclass
class WriteArgs:
    records: list[WriteRecord]
    mac: BluetoothMAC | str | None


@dataclass
class ReadArgs:
    regions: list[ReadRecord] | None
    output: str | None


@dataclass
class EraseArgs:
    regions: list[EraseRegion] | None


@dataclass
class MacArgs:
    mac: BluetoothMAC | None


@dataclass
class ResetArgs:
    pass


@dataclass
class TerminalArgs:
    pass


@dataclass
class EfuseArgs:
    pass


CmdArgs = (
    WriteArgs | ReadArgs | EraseArgs | MacArgs | ResetArgs | TerminalArgs | EfuseArgs
)


def get_args() -> tuple[GlobalArgs, CmdArgs]:
    parser = _build_parser()
    ns = parser.parse_args()
    global_args = GlobalArgs(
        port=ns.port,
        baud=ns.baud,
        v=ns.v,
        quiet=ns.quiet,
        attempts=ns.attempts,
    )
    cmd_args: CmdArgs = ns.cmd_args_factory(ns)
    return global_args, cmd_args


def _build_parser() -> ArgumentParser:
    try:
        _version = version("rtkprog")
    except PackageNotFoundError:
        _version = "unknown"

    parser = ArgumentParser(
        prog="rtkprog",
        description="Tool for programming Realtek RTL87x2x BT SoCs",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_version}",
    )

    # Global options
    parser.add_argument(
        "-p",
        "--port",
        default=_DEFAULT_PORT,
        help=f"Serial port (default: {_DEFAULT_PORT})",
    )
    parser.add_argument(
        "-b",
        "--baud",
        type=int,
        default=_DEFAULT_BAUD,
        help=f"Baud rate for binary transfer and terminal (default: {_DEFAULT_BAUD}).",
    )

    parser.add_argument(
        "-n",
        "--attempts",
        type=int,
        default=3,
        help="Number of attempts before giving up (default: 3)",
    )

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v = INFO, -vv = DEBUG)",
    )
    verbosity.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress all output below ERROR",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    write_p = subparsers.add_parser(
        "write",
        help="Write binary file(s) to flash (auto-erases required sectors)",
    )
    write_p.add_argument(
        "-w",
        dest="records",
        metavar="ADDRESS,SEEK,FILE",
        action="append",
        type=write_record,
        required=True,
        help="Write record: flash address, byte offset into file, file path. Repeatable.",
    )
    write_p.add_argument(
        "-m",
        "--mac",
        type=mac_or_auto,
        help="Patch MAC address into the image. Pass a MAC address "
        "(XXXXXXXXXXXX or XX:XX:XX:XX:XX:XX) or 'auto' to read the "
        "current MAC from flash before writing and preserve it.",
    )
    write_p.set_defaults(
        cmd_args_factory=lambda ns: WriteArgs(records=ns.records, mac=ns.mac)
    )

    read_p = subparsers.add_parser(
        "read",
        help="Read flash to file(s)",
    )
    read_mode = read_p.add_mutually_exclusive_group(required=True)
    read_mode.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Output file for full-flash read. Cannot be combined with -r.",
    )
    read_mode.add_argument(
        "-r",
        dest="regions",
        metavar="ADDRESS,SIZE,FILE",
        action="append",
        type=read_record,
        help="Read a specific region: flash address, size in bytes, output file. "
        "Repeatable. Cannot be combined with -o.",
    )
    read_p.set_defaults(
        cmd_args_factory=lambda ns: ReadArgs(regions=ns.regions, output=ns.output)
    )

    erase_p = subparsers.add_parser(
        "erase",
        help="Erase flash sections or entire chip (default)",
    )
    erase_p.add_argument(
        "-r",
        dest="regions",
        metavar="ADDRESS,SIZE",
        action="append",
        type=erase_region,
        help="Erase a specific flash region instead of the whole chip. Repeatable.",
    )
    erase_p.set_defaults(cmd_args_factory=lambda ns: EraseArgs(regions=ns.regions))

    mac_p = subparsers.add_parser(
        "mac",
        help="Read or write the MAC address in flash",
    )
    mac_p.add_argument(
        "-m",
        "--mac",
        type=mac_address,
        help="MAC address to write (XXXXXXXXXXXX or XX:XX:XX:XX:XX:XX). Omit to read.",
    )
    mac_p.set_defaults(cmd_args_factory=lambda ns: MacArgs(mac=ns.mac))

    reset_p = subparsers.add_parser(
        "reset",
        help="Reset the chip",
    )
    reset_p.set_defaults(cmd_args_factory=lambda ns: ResetArgs())

    run_p = subparsers.add_parser(
        "terminal",
        help="Reset the chip and open bidirectional connection to serial port",
    )
    run_p.set_defaults(cmd_args_factory=lambda ns: TerminalArgs())

    efuse_p = subparsers.add_parser(
        "efuse",
        help="Read eFuse CRC16 status",
    )
    efuse_p.set_defaults(cmd_args_factory=lambda ns: EfuseArgs())

    return parser
