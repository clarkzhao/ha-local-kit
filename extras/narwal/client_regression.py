"""Exercise the separate upstream client's read methods with a mocked transport.

No HA installation, credentials, sockets or devices are used.
"""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock

import local_tool

component = Path(sys.argv.pop(1))
NarwalClient = local_tool.client_factory(component)
from narwal_client import CommandResponse
from narwal_client.const import TOPIC_CMD_GET_BASE_STATUS, TOPIC_CMD_GET_DEVICE_INFO

DEMO_ID = '0123456789abcdef0123456789abcdef'


class ClientContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_read_methods_use_only_identity_and_base_status_topics(self):
        calls = []
        async def command(topic, *args, **kwargs):
            calls.append(topic)
            if topic == TOPIC_CMD_GET_DEVICE_INFO:
                return CommandResponse(result_code=1, data={
                    '1': b'demo-product', '2': DEMO_ID.encode(), '3': b'v00.00.00'})
            if topic == TOPIC_CMD_GET_BASE_STATUS:
                return CommandResponse(result_code=1, data={'2': {'3': {'1': 14}}})
            self.fail('Unexpected command: this regression permits only read-only topics')
        instances = []
        def factory(**kwargs):
            client = NarwalClient(**kwargs)
            client.connect = AsyncMock()
            client.disconnect = AsyncMock()
            client.send_command = command
            instances.append(client)
            return client
        identity = local_tool.validate_identity(dict(host='robot.example.test',
            device_id=DEMO_ID, product_key='demo-product'))
        verified, report = await local_tool.query(identity, factory)
        self.assertEqual(verified, identity)
        self.assertEqual(calls, [TOPIC_CMD_GET_DEVICE_INFO, TOPIC_CMD_GET_BASE_STATUS])
        self.assertEqual(report['observed']['working_status'], 'CHARGED')
        self.assertNotIn(DEMO_ID, json.dumps(report))
        instances[0].disconnect.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
