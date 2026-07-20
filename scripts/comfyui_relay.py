from __future__ import annotations

import argparse
import asyncio

from launcher.relay import run_relay


def _port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be from 1 to 65535")
    return port


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local Docker-to-ComfyUI relay")
    parser.add_argument("--bind-host", required=True)
    parser.add_argument("--bind-port", type=_port, required=True)
    parser.add_argument("--target-host", default="127.0.0.1")
    parser.add_argument("--target-port", type=_port, required=True)
    args = parser.parse_args(argv)
    asyncio.run(
        run_relay(
            args.bind_host,
            args.bind_port,
            args.target_host,
            args.target_port,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
