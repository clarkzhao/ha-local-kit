# SPDX-License-Identifier: GPL-3.0-only
"""Exercise real protocol decoding, reconnect and snapshot publication; no devices."""
import asyncio
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

root = Path(sys.argv.pop(1))
package = types.ModuleType('refresh_regression')
package.__path__ = [str(root)]
sys.modules[package.__name__] = package
tcp = importlib.import_module(f'{package.__name__}.core.local_tcp_client')
light = importlib.import_module(f'{package.__name__}.light')
hub_module = importlib.import_module(f'{package.__name__}.hub')
protocol = importlib.import_module(f'{package.__name__}.core.protocol')


def config(on, brightness=92):
    return [{}, {'ret': {1: {'eps': {'strip': {
        'cls': 'SL_LI_WW_V4', 'name': 'Strip',
        '_chd': {'m': {'_chd': {'P1': {'type': 207 if on else 206, 'val': brightness},
                              'P2': {'type': 207, 'val': 85}}}}}}}}}]


LOGIN = [{}, {'ret': {4: {'base': {1: 'node'}, 'agt': {1: 'test-hub'}}}}]


class RefreshRegression(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = tcp.LifeSmartLocalTCPClient('unused', 1, 'unused', 'unused')
        self.hub = object.__new__(hub_module.LifeSmartHub)
        self.hub.client = self.client
        self.hub.config_entry = types.SimpleNamespace(entry_id='test', options={})
        self.hub.devices = []
        self.hub.hass = types.SimpleNamespace(data={hub_module.DOMAIN: {'test': {'devices': []}}})
        self.task = None
        self.encoder = protocol.LifeSmartProtocol()
        self.readers = [asyncio.StreamReader(), asyncio.StreamReader()]
        self.writers = []
        for _ in self.readers:
            writer = MagicMock()
            writer.is_closing.return_value = False
            writer.drain = AsyncMock()
            writer.wait_closed = AsyncMock()
            self.writers.append(writer)
        self.connections = 0
        self.dispatch_patch = patch.object(hub_module, 'dispatcher_send')
        self.dispatch_patch.start()
        self.addCleanup(self.dispatch_patch.stop)

    async def asyncTearDown(self):
        self.client.disconnect()
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

    async def wait(self, predicate):
        async with asyncio.timeout(2):
            while not predicate():
                await asyncio.sleep(.005)

    def feed(self, reader, packet):
        reader.feed_data(self.encoder.encode(packet))

    async def connect(self):
        async def opened(*args, **kwargs):
            index = self.connections
            self.connections += 1
            return self.readers[index], self.writers[index]
        self.open_patch = patch.object(tcp.asyncio, 'open_connection', side_effect=opened)
        self.open_patch.start()
        self.addCleanup(self.open_patch.stop)
        real_sleep = asyncio.sleep
        async def fast_sleep(delay):
            await real_sleep(0 if delay == 5.0 else delay)
        self.sleep_patch = patch.object(tcp.asyncio, 'sleep', new=fast_sleep)
        self.sleep_patch.start()
        self.addCleanup(self.sleep_patch.stop)
        self.task = asyncio.create_task(self.client.async_connect(self.hub._local_update_callback))
        await self.wait(lambda: self.connections == 1)
        self.feed(self.readers[0], LOGIN)
        self.feed(self.readers[0], config(False))
        await self.wait(lambda: self.client.device_ready.is_set())

    async def test_reconnect_replaces_stale_off_entity_without_new_io_push(self):
        await self.connect()
        entity = light.LifeSmartDimmerLight(self.client.devices['strip'], self.client, 'test')
        entity.hass = self.hub.hass
        entity.async_write_ha_state = MagicMock()
        self.assertFalse(entity.is_on)
        def dispatch(hass, signal, *args):
            if signal == hub_module.LIFESMART_SIGNAL_UPDATE_ENTITY:
                entity._handle_global_refresh()
        with patch.object(hub_module, 'dispatcher_send', side_effect=dispatch):
            self.readers[0].feed_eof()
            await self.wait(lambda: self.connections == 2)
            self.assertFalse(self.client.device_ready.is_set())
            self.feed(self.readers[1], LOGIN)
            self.feed(self.readers[1], config(True))
            await self.wait(lambda: entity.is_on)
        self.assertEqual(entity.brightness, 92)
        self.assertAlmostEqual(entity.color_temp_kelvin, 3966.6666666666665)
        self.assertIs(self.hub.devices, self.hub.hass.data[hub_module.DOMAIN]['test']['devices'])
        self.assertIs(entity._raw_device, self.client.devices['strip'])

    async def test_getconfig_reply_after_loaded_updates_both_caches(self):
        await self.connect()
        old = self.hub.devices
        self.feed(self.readers[0], config(True, 128))
        await self.wait(lambda: self.hub.devices is not old)
        self.assertEqual(self.hub.devices[0]['data']['P1'], {'type': 207, 'val': 128})
        self.assertIs(self.hub.devices, self.hub.hass.data[hub_module.DOMAIN]['test']['devices'])

    async def test_periodic_refresh_actually_requests_new_gateway_snapshot(self):
        await self.connect()
        sent = len(self.writers[0].write.call_args_list)
        refresh_task = asyncio.create_task(self.hub._async_periodic_refresh())
        try:
            await self.wait(lambda: len(self.writers[0].write.call_args_list) > sent)
            self.assertFalse(self.client.device_ready.is_set())
            _, decoded = self.encoder.decode(self.writers[0].write.call_args.args[0])
            self.assertEqual(decoded[1]['node'], 'node/me/ep')
            self.feed(self.readers[0], config(True))
            await refresh_task
            self.assertEqual(self.hub.devices[0]['data']['P1']['type'], 207)
        finally:
            refresh_task.cancel()
            await asyncio.gather(refresh_task, return_exceptions=True)

    async def test_timeout_does_not_publish_empty_or_stale_snapshot(self):
        await self.connect()
        previous = self.hub.devices
        with self.assertRaises(TimeoutError):
            await self.client.async_refresh_devices(timeout=.01)
        self.assertIs(self.hub.devices, previous)

    async def test_initial_refresh_before_entry_publication_is_safe(self):
        self.hub.hass.data = {}
        await self.connect()
        self.assertEqual(len(self.hub.devices), 1)

    async def test_cloud_refresh_also_replaces_shared_cache(self):
        devices = [{'me': 'cloud-strip'}]
        self.hub.client = types.SimpleNamespace(async_get_all_devices=AsyncMock(return_value=devices))
        with patch.object(hub_module, 'dispatcher_send') as dispatch:
            await self.hub._async_periodic_refresh()
        self.assertIs(self.hub.hass.data[hub_module.DOMAIN]['test']['devices'], devices)
        dispatch.assert_called_once()


unittest.main(verbosity=2)
