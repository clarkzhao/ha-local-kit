# SPDX-License-Identifier: GPL-3.0-only
"""Publish TCP snapshots after reconnects and refreshes in a staged integration."""
from pathlib import Path
import sys
from patch_utils import replace_once, write_patches


root = Path(sys.argv[1])
updates = {}
path = root/'core/local_tcp_client.py'
text = path.read_text(encoding='utf-8')
text = replace_once(text,
    '            self.reader, self.writer = None, None\n',
    '            self.reader, self.writer = None, None\n            self.device_ready.clear()\n')
text = replace_once(text,
    '                            elif stage == "loading":\n                                eps = safe_get(decoded, 1, "ret", 1, "eps", default={})',
    '''                            elif isinstance(safe_get(decoded, 1, "ret", 1, "eps"), dict):
                                # Login, reconnect and heartbeat replies are snapshots.
                                eps = safe_get(decoded, 1, "ret", 1, "eps", default={})''')
text = replace_once(text,
    '                                stage = "loaded"\n',
    '''                                stage = "loaded"
                                if callback and callable(callback):
                                    await callback({"type": "refresh"})
''')
text = replace_once(text,
    '    async def _async_get_all_devices(self, timeout=10) -> list[dict[str, Any]]:',
    '''    async def async_refresh_devices(self, timeout=10) -> list[dict[str, Any]]:
        """Request and await a fresh gateway snapshot."""
        if not self.is_connected:
            raise ConnectionError("LifeSmart TCP client is disconnected")
        self.device_ready.clear()
        result = await self._send_packet(self._factory.build_get_config_packet(self.node))
        if result != 0:
            raise ConnectionError("LifeSmart TCP snapshot request failed")
        await asyncio.wait_for(self.device_ready.wait(), timeout=timeout)
        return list(self.devices.values())

    async def _async_get_all_devices(self, timeout=10) -> list[dict[str, Any]]:''')
updates[path] = text

path = root/'hub.py'
text = path.read_text(encoding='utf-8')
text = replace_once(text,
    '        await self.data_update_handler(data)\n',
    '''        if data.get("type") == "refresh":
            self._publish_device_snapshot(list(self.client.devices.values()))
            return
        await self.data_update_handler(data)

    def _publish_device_snapshot(self, devices: list[dict]) -> None:
        """Replace both caches before notifying entities."""
        self.devices = devices
        entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        # Initial login may precede the entry's publication in hass.data.
        if entry_data is not None:
            entry_data["devices"] = devices
            dispatcher_send(self.hass, LIFESMART_SIGNAL_UPDATE_ENTITY)
''')
text = replace_once(text,
    '''            new_devices = await self.client.async_get_all_devices()
            self.devices = new_devices
            dispatcher_send(self.hass, LIFESMART_SIGNAL_UPDATE_ENTITY)''',
    '''            if isinstance(self.client, LifeSmartLocalTCPClient):
                # The TCP refresh callback publishes the response to HA.
                await self.client.async_refresh_devices()
            else:
                new_devices = await self.client.async_get_all_devices()
                self._publish_device_snapshot(new_devices)''')
updates[path] = text
write_patches(updates)
print('Patched core/local_tcp_client.py and hub.py snapshot refresh')
