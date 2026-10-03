# SPDX-License-Identifier: GPL-3.0-only
"""Check staged patch preparation without Home Assistant or device connections."""
import importlib.util
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'extras/lifesmart'


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


utils = load('patch_utils')
staging = load('stage')


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_invalid_second_result_writes_neither_file(self):
        first, second = self.root / 'first.py', self.root / 'second.py'
        for path in (first, second):
            path.write_bytes(b'value = 1\n')
        with self.assertRaises(SyntaxError):
            utils.write_patches({first: 'value = 2\n', second: 'invalid syntax !'})
        for path in (first, second):
            self.assertEqual(path.read_bytes(), b'value = 1\n')

    def test_matching_failure_in_second_light_target_preserves_first(self):
        light = self.root / 'light.py'
        source = '''class LifeSmartDimmerLight(Base):
    def temperature(self):
        ratio = (255 - val) / 255.0
    async def async_turn_on(self):
        pass

class LifeSmartSPOTRGBLight(Base):
    pass
'''
        light.write_text(source, encoding='utf-8')
        hub = self.root / 'hub.py'
        hub.write_text('unsupported = True\n', encoding='utf-8')
        before = {path: path.read_bytes() for path in (light, hub)}
        result = subprocess.run([sys.executable, str(TOOLS / 'patch-light.py'), str(self.root)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_writes_preserve_each_targets_newlines(self):
        unix, windows = self.root / 'unix.py', self.root / 'windows.py'
        unix.write_bytes(b'value = 1\n')
        windows.write_bytes(b'value = 1\r\n')
        utils.write_patches({unix: 'value = 2\n', windows: 'value = 2\n'})
        self.assertEqual(unix.read_bytes(), b'value = 2\n')
        self.assertEqual(windows.read_bytes(), b'value = 2\r\n')

    def test_stage_rejects_output_inside_source(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            staging.stage(self.root, self.root / 'nested')
        self.assertFalse((self.root / 'nested').exists())

    @patch.object(staging.subprocess, 'run')
    def test_stage_refuses_existing_output(self, run):
        source, output = self.root / 'source', self.root / 'output'
        source.mkdir()
        output.mkdir()
        with self.assertRaises(FileExistsError):
            staging.stage(source, output)
        run.assert_not_called()

    @patch.object(staging.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'patch'))
    def test_failed_stage_leaves_source_unchanged(self, run):
        source, output = self.root / 'source', self.root / 'output'
        source.mkdir()
        (source / 'hub.py').write_bytes(b'value = 1\n')
        with self.assertRaises(subprocess.CalledProcessError):
            staging.stage(source, output)
        self.assertEqual((source / 'hub.py').read_bytes(), b'value = 1\n')


if __name__ == '__main__':
    unittest.main()
