import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import AsyncMock

spec = importlib.util.spec_from_file_location('local_tool', Path(__file__).resolve().parents[1] / 'extras/narwal/local_tool.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
DEMO_ID = '0123456789abcdef0123456789abcdef'
IDENTITY = dict(host='robot.example.test', port=9002, device_id=DEMO_ID,
                product_key='demo-product', supports_broadcasts=False)


class LocalTests(unittest.IsolatedAsyncioTestCase):
    def client(self, **kwargs):
        self.calls = kwargs
        self.fake = types.SimpleNamespace(
            connect=AsyncMock(), disconnect=AsyncMock(),
            discover_device_id=AsyncMock(), drain_ws_buffer=AsyncMock(),
            get_device_info=AsyncMock(return_value=types.SimpleNamespace(device_id=DEMO_ID, product_key='demo-product')),
            get_status=AsyncMock(return_value=types.SimpleNamespace(result_code=1, accepted=True)),
            state=types.SimpleNamespace(working_status=types.SimpleNamespace(name='CHARGED')))
        return self.fake

    async def test_local_confirmation_and_report_do_not_export_identity(self):
        verified, report = await tool.query({**IDENTITY, 'product_key': ''}, self.client, discover=True)
        self.assertEqual(verified['product_key'], 'demo-product')
        self.fake.discover_device_id.assert_awaited_once()
        self.fake.get_status.assert_awaited_once_with(full_update=True)
        self.fake.disconnect.assert_awaited_once()
        self.assertNotIn(DEMO_ID, json.dumps(report))
        self.assertNotIn(IDENTITY['host'], json.dumps(report))
        self.assertFalse(report['physical_actions_sent'])

    async def test_identity_mismatch_stops_before_status_and_disconnects(self):
        def factory(**kwargs):
            client = self.client(**kwargs)
            client.get_device_info.return_value.device_id = 'f' * 32
            return client
        with self.assertRaisesRegex(tool.ToolError, 'device_identity_mismatch'):
            await tool.query(IDENTITY, factory)
        self.fake.get_status.assert_not_awaited()
        self.fake.disconnect.assert_awaited_once()

    async def test_timeout_releases_connection(self):
        async def blocked():
            await asyncio.Event().wait()
        def factory(**kwargs):
            client = self.client(**kwargs)
            client.connect.side_effect = blocked
            return client
        with self.assertRaises(TimeoutError):
            await tool.query(IDENTITY, factory, timeout=.02)
        self.fake.disconnect.assert_awaited_once()

    async def test_product_key_mismatch_is_not_silently_reconfigured(self):
        with self.assertRaisesRegex(tool.ToolError, 'product_key_mismatch'):
            await tool.query({**IDENTITY, 'product_key': 'other-product'}, self.client)
        self.fake.get_status.assert_not_awaited()
        self.fake.disconnect.assert_awaited_once()

    def test_cli_does_not_print_sensitive_dependency_exception(self):
        with TemporaryDirectory() as temp:
            component = Path(temp) / 'component'
            package = component / 'narwal_client'
            package.mkdir(parents=True)
            private = 'private-host-and-device-marker'
            (package / '__init__.py').write_text(
                "class NarwalClient:\n    def __init__(self, **kwargs):\n        raise RuntimeError('" + private + "')\n")
            identity_path = Path(temp) / 'identity.json'
            identity_path.write_text(json.dumps(IDENTITY))
            result = subprocess.run([sys.executable, '-X', 'utf8', str(Path(tool.__file__)),
                'diagnose', '--identity-file', str(identity_path), '--component', str(component)],
                capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['error'], 'local_query_failed')
            self.assertNotIn(private, result.stdout + result.stderr)
            self.assertNotIn(DEMO_ID, result.stdout + result.stderr)

    def test_account_selection_requires_full_id_not_sn_or_product_id(self):
        rows = {'devices': [{'deviceId': DEMO_ID, 'productId': 'not-a-key', 'SN': 'not-an-id'}]}
        result = tool.select_account(rows, 1, 'robot.example.test')
        self.assertEqual(result['device_id'], DEMO_ID)
        self.assertEqual(result['product_key'], '')
        for index in (0, 2):
            with self.assertRaises(tool.ToolError):
                tool.select_account(rows, index, 'robot.example.test')
        with self.assertRaises(tool.ToolError):
            tool.select_account({'devices': [{'SN': DEMO_ID}]}, 1, 'robot.example.test')

    def test_diagnostic_excludes_arbitrary_strings_and_preserves_unknowns(self):
        private = 'private-value-must-not-survive'
        report = tool.explain({'has_error': private, 'working_status': private,
                              'host': private, 'raw': {'token': private}})
        self.assertNotIn(private, json.dumps(report))
        self.assertIsNone(report['observed']['has_error'])
        self.assertEqual(report['observed']['working_status'], 'UNKNOWN')
        self.assertFalse(report['ha_permissions_evaluated'])

    def test_missing_drying_timer_is_evidence_not_permission_override(self):
        report = tool.explain({'has_recent_dock_drying_status': True,
            'has_dock_drying_timer_snapshot': False, 'blocks_robot_start_for_dock_task': True,
            'working_status': 'CHARGED', 'query_accepted': True})
        codes = {row['code'] for row in report['findings']}
        self.assertIn('drying_timer_missing', codes)
        self.assertIn('dock_blocks_start', codes)
        self.assertNotIn('can_start', report)

    def test_identity_output_exclusive_private_and_outside_checkout(self):
        with self.assertRaises(tool.ToolError):
            tool.private_output(tool.ROOT / '.local' / 'identity.json')
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'identity.json'
            tool.write_private(path, IDENTITY)
            self.assertEqual(json.loads(path.read_text())['device_id'], DEMO_ID)
            if os.name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(tool.ToolError):
                tool.write_private(path, IDENTITY)


if __name__ == '__main__':
    unittest.main()
