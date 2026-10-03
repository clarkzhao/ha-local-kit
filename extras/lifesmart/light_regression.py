# SPDX-License-Identifier: GPL-3.0-only
"""Dimmer regressions using the installed HA classes, without appliance controls."""
import copy
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, call, patch

root = Path(sys.argv.pop(1))
package = types.ModuleType('light_regression')
package.__path__ = [str(root)]
sys.modules[package.__name__] = package
light = importlib.import_module(f'{package.__name__}.light')
tcp = importlib.import_module(f'{package.__name__}.core.local_tcp_client')
hub_module = importlib.import_module(f'{package.__name__}.hub')
from homeassistant.exceptions import HomeAssistantError

RAW = {'agt': 'test-hub', 'me': 'strip', 'devtype': 'SL_LI_WW', 'name': 'Strip',
       'data': {'P1': {'type': 207, 'val': 194}, 'P2': {'type': 207, 'val': 48}}}


class DimmerRegression(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = tcp.LifeSmartLocalTCPClient('invalid.test', 1, 'unused', 'unused')
        self.client._async_send_single_command = AsyncMock(return_value=0)
        self.client._async_send_multi_command = AsyncMock(return_value=0)
        self.entity = light.LifeSmartDimmerLight(copy.deepcopy(RAW), self.client, 'test')
        self.entity.entity_id = 'light.strip'
        self.entity.async_write_ha_state = lambda: None

    async def test_brightness_preserves_temperature_and_does_not_resend_power(self):
        await self.entity.async_turn_on(brightness=128)
        self.client._async_send_single_command.assert_awaited_once_with('test-hub', 'strip', 'P1', 0xcf, 128)
        self.client._async_send_multi_command.assert_not_awaited()
        self.assertEqual(self.entity.brightness, 194, 'Socket send is not device confirmation')

    async def test_color_temperature_endpoints_match_device_spec(self):
        for kelvin, code in [(2700, 0), (6500, 255), (4600, 128)]:
            await self.entity.async_turn_on(color_temp_kelvin=kelvin)
            self.client._async_send_single_command.assert_awaited_with('test-hub', 'strip', 'P2', 0xcf, code)

    async def test_combined_request_uses_individual_io_packets(self):
        await self.entity.async_turn_on(brightness=128, color_temp_kelvin=4600)
        self.assertEqual(self.client._async_send_single_command.await_args_list, [
            call('test-hub', 'strip', 'P1', 0xcf, 128),
            call('test-hub', 'strip', 'P2', 0xcf, 128)])
        self.client._async_send_multi_command.assert_not_awaited()

    async def test_real_push_routes_to_dimmer_and_preserves_other_channel(self):
        hub = object.__new__(hub_module.LifeSmartHub)
        hub.hass = object()
        hub.config_entry = types.SimpleNamespace(options={})
        signals = []
        def dispatched(hass, signal, data):
            signals.append(signal)
            if signal == f'{light.LIFESMART_SIGNAL_UPDATE_ENTITY}_{self.entity.unique_id}':
                self.entity._handle_update(data)
        with patch.object(hub_module, 'dispatcher_send', side_effect=dispatched):
            for idx, value in [('P1', 128), ('P2', 255)]:
                await hub.data_update_handler({'type': 'io', 'msg': {
                    'devtype': 'SL_LI_WW', 'agt': 'test-hub', 'me': 'strip',
                    'idx': idx, 'type': 207, 'val': value}})
        self.assertEqual(self.entity.brightness, 128)
        self.assertEqual(self.entity.color_temp_kelvin, 6500)
        self.assertEqual(len(signals), 4)

    async def test_transport_failure_raises_and_keeps_confirmed_state(self):
        self.client._async_send_single_command.return_value = -1
        with self.assertRaises(HomeAssistantError):
            await self.entity.async_turn_on(brightness=128, color_temp_kelvin=4600)
        self.assertEqual(self.entity.brightness, 194)
        self.client._async_send_single_command.assert_awaited_once()

    async def test_color_temperature_from_off_also_enables_power(self):
        self.entity._handle_update({'P1': {'type': 206}})
        await self.entity.async_turn_on(color_temp_kelvin=2700)
        self.assertEqual(self.client._async_send_single_command.await_args_list, [
            call('test-hub', 'strip', 'P2', 0xcf, 0),
            call('test-hub', 'strip', 'P1', 0x81, 1)])

    async def test_power_controls_use_confirmed_reports(self):
        await self.entity.async_turn_off()
        self.client._async_send_single_command.assert_awaited_once_with('test-hub', 'strip', 'P1', 0x80, 0)
        self.assertTrue(self.entity.is_on)
        self.entity._handle_update({'P1': {'type': 206}})
        self.assertFalse(self.entity.is_on)
        await self.entity.async_turn_on()
        self.client._async_send_single_command.assert_awaited_with('test-hub', 'strip', 'P1', 0x81, 1)

    async def test_readback_mapping_and_roundtrip_quantization(self):
        self.assertAlmostEqual(self.entity.color_temp_kelvin, 2700 + 48 * 3800 / 255)
        await self.entity.async_turn_on(color_temp_kelvin=self.entity.color_temp_kelvin)
        self.client._async_send_single_command.assert_awaited_once_with('test-hub', 'strip', 'P2', 0xcf, 48)

    async def test_partial_failure_retains_confirmed_brightness(self):
        async def send(agt, me, idx, typ, value):
            if idx == 'P1':
                self.entity._handle_update({'P1': {'type': typ, 'val': value}})
                return 0
            return -1
        self.client._async_send_single_command.side_effect = send
        with self.assertRaises(HomeAssistantError):
            await self.entity.async_turn_on(brightness=128, color_temp_kelvin=6500)
        self.assertEqual(self.entity.brightness, 128)
        self.assertAlmostEqual(self.entity.color_temp_kelvin, 2700 + 48 * 3800 / 255)


unittest.main(verbosity=2)
