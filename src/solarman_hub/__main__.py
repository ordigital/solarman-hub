import argparse
import asyncio
from contextlib import suppress
import os
from pathlib import Path
import signal
import getpass
import json
import sys

from aiohttp import web

from .runtime import Runtime
from .web import admin_token, create_app
from .auth import password_record, save_password


async def run(args):
    runtime = Runtime(args.data_dir, args.tcp_host, args.tcp_port)
    runner = web.AppRunner(create_app(runtime), access_log=None)
    await runner.setup()
    host = args.web_host if args.web_host is not None else runtime.active.server.web_host
    port = args.web_port if args.web_port is not None else runtime.active.server.web_port
    try:
        await runtime.start()
        await web.TCPSite(runner, host, port).start()
        print(f"Solarman Hub: WWW {host}:{port}; TCP {runtime.tcp_host}:{runtime.tcp_port}", flush=True)
        print(f"Token administratora: {args.data_dir / 'admin-token.txt'} (plik lokalny)", flush=True)
        stopped = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGTERM, signal.SIGINT):
            with suppress(NotImplementedError):
                loop.add_signal_handler(signum, stopped.set)
        await stopped.wait()
    finally:
        await runner.cleanup()
        await runtime.close()


def main():
    parser = argparse.ArgumentParser(description="Solarman Hub — lokalny serwer V5, WWW i MQTT")
    parser.add_argument("command", nargs="?", choices=["serve", "token", "password", "check-config"], default="serve")
    parser.add_argument("--hash-stdin", action="store_true", help="Read a precomputed password record from standard input (password command only)")
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("HUB_DATA_DIR", "data")))
    parser.add_argument("--tcp-host")
    parser.add_argument("--tcp-port", type=int)
    parser.add_argument("--web-host")
    parser.add_argument("--web-port", type=int)
    args = parser.parse_args()
    if args.hash_stdin and args.command != "password":
        parser.error("--hash-stdin requires the password command")
    args.data_dir.mkdir(parents=True, exist_ok=True)
    if args.command == "token":
        print(admin_token(args.data_dir))
    elif args.command == "password":
        try:
            if args.hash_stdin:
                record = json.loads(sys.stdin.read(1025))
            else:
                candidate = getpass.getpass("New administrator password (at least 8 characters): ")
                if candidate != getpass.getpass("Repeat password: "):
                    parser.error("Passwords do not match")
                record = password_record(candidate)
            save_password(args.data_dir, record)
        except ValueError as error:
            parser.error(str(error))
        print("Administrator password saved. Restart the Hub to use it. The recovery token is unchanged.")
    elif args.command == "check-config":
        runtime = Runtime(args.data_dir)
        print("Konfiguracja i profile są poprawne:", runtime.active_revision)
    else:
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
