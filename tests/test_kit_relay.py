import asyncio
import socket
from types import SimpleNamespace
import unittest
from ha_local_kit.relays import run


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_binary_payload_round_trip_and_listener_survives_disconnect(self):
        async def echo(reader,writer):
            try:
                while data := await reader.read(65536):
                    writer.write(data)
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        server=await asyncio.start_server(echo,'127.0.0.1',0)
        upstream=server.sockets[0].getsockname()[1]
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        task=asyncio.create_task(run(SimpleNamespace(gateway='127.0.0.1',gateway_port=upstream,listen_port=port)))
        try:
            for attempt in range(30):
                try:
                    reader,writer=await asyncio.open_connection('127.0.0.1',port)
                    break
                except ConnectionRefusedError:
                    await asyncio.sleep(.01)
            else:self.fail('relay did not bind')
            payload=bytes(range(256))*512
            writer.write(payload);await writer.drain()
            self.assertEqual(await asyncio.wait_for(reader.readexactly(len(payload)),2),payload)
            writer.close();await writer.wait_closed()
            reader,writer=await asyncio.open_connection('127.0.0.1',port)
            writer.write(b'again');await writer.drain()
            self.assertEqual(await asyncio.wait_for(reader.readexactly(5),2),b'again')
            writer.close();await writer.wait_closed()
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True)
            server.close();await server.wait_closed()


if __name__=='__main__':unittest.main()
