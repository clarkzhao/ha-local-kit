"""Forward a loopback-only port to the configured LifeSmart LAN gateway.

Colima guests can reach this listener through their configured host gateway.
No payloads or credentials are logged. The upstream address is fixed at startup.
"""
import argparse
import asyncio
import logging
import socket
import json
from pathlib import Path
from types import SimpleNamespace

LOG = logging.getLogger("lifesmart_relay")


async def run(args):
    async def handle(reader, writer):
        upstream_writer = None
        tasks = []
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(args.gateway, args.gateway_port), timeout=5
            )
            for connection in (writer, upstream_writer):
                connection.get_extra_info("socket").setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            async def copy(source, destination):
                while True:
                    data = await source.read(65536)
                    if not data:
                        return
                    destination.write(data)
                    await destination.drain()

            tasks = [asyncio.create_task(copy(reader, upstream_writer)),
                     asyncio.create_task(copy(upstream_reader, writer))]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except (OSError, asyncio.TimeoutError) as exc:
            LOG.warning("Connection ended: %s", type(exc).__name__)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for connection in (upstream_writer, writer):
                if connection is not None:
                    connection.close()
                    try:
                        await connection.wait_closed()
                    except OSError:
                        pass

    server = await asyncio.start_server(handle, "127.0.0.1", args.listen_port)
    LOG.info("Listening on loopback port %s; fixed LAN gateway %s:%s", args.listen_port, args.gateway, args.gateway_port)
    async with server:
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Fixed loopback TCP relays; no payload logging")
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    endpoints = json.loads(args.config.read_text())
    ports = set()
    for ep in endpoints:
        if not isinstance(ep['gateway'], str) or not ep['gateway']:
            raise ValueError('gateway required')
        for field in ('gateway_port','listen_port'):
            if type(ep[field]) is not int or not 1 <= ep[field] <= 65535:
                raise ValueError('invalid port')
        if ep['listen_port'] in ports:
            raise ValueError('duplicate listen port')
        ports.add(ep['listen_port'])
    if not endpoints:
        raise ValueError('no relays configured')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    async def serve():
        async with asyncio.TaskGroup() as group:
            for ep in endpoints:
                group.create_task(run(SimpleNamespace(**ep)))
    asyncio.run(serve())


if __name__ == '__main__':
    main()
