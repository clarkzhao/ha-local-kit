# SPDX-License-Identifier: GPL-3.0-only
# Contains/adapts GPL upstream snippets; see README.md and ../../licenses/GPL-3.0.txt
"""Regressions against the installed HA climate service validation and protocol map.

All command methods are mocked; running this file never controls appliances.
Usage: python test-lifesmart-vrf.py /path/to/lifesmart
"""
import copy
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, call, patch

root = Path(sys.argv.pop(1))
package = types.ModuleType('vrf_regression')
package.__path__ = [str(root)]
sys.modules[package.__name__] = package
climate = importlib.import_module(f'{package.__name__}.climate')
tcp = importlib.import_module(f'{package.__name__}.core.local_tcp_client')
hub_module = importlib.import_module(f'{package.__name__}.hub')
from homeassistant.components.climate import HVACMode
from homeassistant.exceptions import ServiceValidationError

RAW = {
    'agt': 'test-hub', 'me': 'test-vrf', 'devtype': 'V_AIR_P', 'name': 'VRF test',
    'data': {'O': {'type': 129, 'val': 1}, 'MODE': {'type': 206, 'val': 3},
             'F': {'type': 206, 'val': 15}, 'T': {'type': 8, 'val': 260},
             'tT': {'type': 136, 'val': 255}},
}

class VrfRegression(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = tcp.LifeSmartLocalTCPClient('invalid.test', 1, 'unused', 'unused')
        self.client._async_send_single_command = AsyncMock(return_value=0)
        self.entity = climate.LifeSmartClimate(copy.deepcopy(RAW), self.client, 'test')
        self.entity.entity_id = 'climate.vrf_test'

    async def test_ha_fan_service_accepts_all_advertised_strings(self):
        self.assertEqual(self.entity.fan_modes, ['low', 'medium', 'high'])
        for fan, code in [('low', 15), ('medium', 45), ('high', 75)]:
            await self.entity.async_handle_set_fan_mode_service(fan)
            self.client._async_send_single_command.assert_awaited_with(
                'test-hub', 'test-vrf', 'F', 0xCE, code)

    async def test_invalid_fan_is_validation_error_not_type_error(self):
        with self.assertRaises(ServiceValidationError):
            await self.entity.async_handle_set_fan_mode_service('unsupported')
        self.client._async_send_single_command.assert_not_awaited()

    async def test_power_off_targets_o_and_sends_no_mode(self):
        await self.entity.async_set_hvac_mode(HVACMode.OFF)
        self.client._async_send_single_command.assert_awaited_once_with(
            'test-hub', 'test-vrf', 'O', 0x80, 0)

    async def test_all_advertised_active_modes_have_protocol_commands(self):
        for mode, code in [(HVACMode.AUTO, 1), (HVACMode.FAN_ONLY, 2),
                           (HVACMode.COOL, 3), (HVACMode.HEAT, 4), (HVACMode.DRY, 5)]:
            self.client._async_send_single_command.reset_mock()
            await self.entity.async_set_hvac_mode(mode)
            self.assertEqual(self.client._async_send_single_command.await_args_list, [
                call('test-hub', 'test-vrf', 'O', 0x81, 1),
                call('test-hub', 'test-vrf', 'MODE', 0xCE, code)])

    async def test_dry_mode_is_actually_sent(self):
        await self.entity.async_set_hvac_mode(HVACMode.DRY)
        self.client._async_send_single_command.assert_awaited_with(
            'test-hub', 'test-vrf', 'MODE', 0xCE, 5)

    async def test_temperature_write_scales_to_tenths(self):
        await self.entity.async_set_temperature(temperature=25.5)
        self.client._async_send_single_command.assert_awaited_once_with(
            'test-hub', 'test-vrf', 'tT', 0x88, 255)

    async def test_tcp_temperature_without_v(self):
        self.assertEqual(self.entity.current_temperature, 26)
        self.assertEqual(self.entity.target_temperature, 25.5)

    async def test_cloud_temperature_v_takes_precedence(self):
        data = copy.deepcopy(RAW['data'])
        data['T']['v'] = 24.5
        data['tT']['v'] = 25
        self.entity._update_state(data)
        self.assertEqual(self.entity.current_temperature, 24.5)
        self.assertEqual(self.entity.target_temperature, 25)

    async def test_existing_partial_update_merge_is_preserved(self):
        self.entity.async_write_ha_state = lambda: None
        self.entity._handle_update({'F': {'type': 206, 'val': 45}})
        self.assertEqual(self.entity.hvac_mode, HVACMode.COOL)
        self.assertEqual(self.entity.target_temperature, 25.5)
        self.assertEqual(self.entity.fan_mode, 'medium')
        self.entity._handle_update({'tT': {'type': 136, 'val': 265}})
        self.assertEqual(self.entity.target_temperature, 26.5)

    async def test_physical_panel_still_uses_p1(self):
        await self.client.async_set_climate_hvac_mode('test-hub', 'panel', 'SL_NATURE', HVACMode.OFF)
        self.client._async_send_single_command.assert_awaited_once_with('test-hub', 'panel', 'P1', 0x80, 0)

    async def test_real_hub_push_updates_aggregate_climate_and_io_sensor(self):
        hub = object.__new__(hub_module.LifeSmartHub)
        hub.hass = object()
        hub.config_entry = types.SimpleNamespace(options={})
        self.entity.async_write_ha_state = lambda: None
        signals = []
        def dispatched(hass, signal, data):
            signals.append((signal, data))
            if signal == f'{climate.LIFESMART_SIGNAL_UPDATE_ENTITY}_{self.entity.unique_id}':
                self.entity._handle_update(data)
        with patch.object(hub_module, 'dispatcher_send', side_effect=dispatched):
            await hub.data_update_handler({'type':'io','msg':{
                'devtype':'V_AIR_P','agt':'test-hub','me':'test-vrf',
                'idx':'F','type':206,'val':45}})
        self.assertEqual(self.entity.fan_mode, 'medium')
        self.assertEqual(self.entity.target_temperature, 25.5)
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0][1]['idx'], 'F')
        self.assertEqual(signals[1][1], {'F':{'type':206,'val':45}})

    async def test_non_climate_push_is_unchanged(self):
        hub = object.__new__(hub_module.LifeSmartHub)
        hub.hass = object()
        hub.config_entry = types.SimpleNamespace(options={})
        msg={'devtype':'SL_SW_IF3','agt':'test-hub','me':'switch','idx':'L1','type':129,'val':1}
        with patch.object(hub_module, 'dispatcher_send') as dispatch:
            await hub.data_update_handler({'type':'io','msg':msg})
        dispatch.assert_called_once()
        self.assertEqual(dispatch.call_args.args[2], msg)

unittest.main(verbosity=2)
