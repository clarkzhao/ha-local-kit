# SPDX-License-Identifier: GPL-3.0-only
"""Check the staged upstream Hub with mocked TCP and no live HA configuration."""
import asyncio
import importlib
import inspect
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

root = Path(sys.argv.pop(1)).resolve()
package = types.ModuleType('startup_regression_upstream')
package.__path__ = [str(root)]
sys.modules[package.__name__] = package
hub_module = importlib.import_module(f'{package.__name__}.hub')
from homeassistant.config_entries import ConfigEntry


class UpstreamStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistent_tcp_task_is_background_and_cleanup_cancels(self):
        self.assertTrue({'hass', 'target', 'name'} <= set(inspect.signature(
            ConfigEntry.async_create_background_task).parameters))
        ready, stopped = asyncio.Event(), asyncio.Event()
        tasks = []
        async def connect(callback):
            ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        async def devices():
            await ready.wait()
            return [{'name': 'synthetic-device'}]
        def background(hass, target, name):
            task = asyncio.create_task(target, name=name)
            tasks.append(task)
            return task
        def forbidden_foreground(target):
            target.close()
            self.fail('Persistent TCP task must not be tracked as foreground startup work')
        hass = types.SimpleNamespace(async_create_task=forbidden_foreground)
        entry = types.SimpleNamespace(entry_id='synthetic-entry', data=dict(
            host='gateway.example.test', port=8888, username='synthetic', password='unused'),
            async_create_background_task=background)
        hub = hub_module.LifeSmartHub(hass, entry)
        client = types.SimpleNamespace(async_connect=connect, async_get_all_devices=devices)
        try:
            with patch.object(hub_module, 'LifeSmartLocalTCPClient', return_value=client):
                await asyncio.wait_for(hub._setup_local_client(), 1)
            self.assertEqual(len(tasks), 1)
            self.assertFalse(tasks[0].done())
            self.assertEqual(hub.devices, [{'name': 'synthetic-device'}])
            await hub._cleanup_local_task()
            self.assertTrue(stopped.is_set())
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
