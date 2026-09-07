# SPDX-License-Identifier: GPL-3.0-only
"""Exercise startup and cancellation with a never-ending synthetic TCP task."""
import asyncio
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('startup_patch', Path(__file__).resolve().parents[1] / 'extras/lifesmart/startup_patch.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SOURCE = '''class Hub:
    async def setup(self):
        if self.client:
            self._local_task = self.hass.async_create_task(
                self.client.async_connect(self._local_update_callback)
            )
        await self.client.ready.wait()

    async def unload(self):
        self._local_task.cancel()
        try:
            await self._local_task
        except asyncio.CancelledError:
            pass
'''


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_does_not_wait_for_persistent_connection_and_unload_cancels(self):
        namespace = {'asyncio': asyncio}
        exec(module.patched(SOURCE)[0], namespace)
        hub = namespace['Hub']()
        ready, disconnected = asyncio.Event(), asyncio.Event()

        async def connect(callback):
            ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                disconnected.set()

        foreground, background = [], []
        def create_foreground(coro):
            task = asyncio.create_task(coro)
            foreground.append(task)
            return task
        def create_background(hass, coro, name):
            task = asyncio.create_task(coro, name=name)
            background.append(task)
            return task
        hub.client = types.SimpleNamespace(ready=ready, async_connect=connect)
        hub.hass = types.SimpleNamespace(async_create_task=create_foreground)
        hub.config_entry = types.SimpleNamespace(async_create_background_task=create_background)
        hub._local_update_callback = lambda data: None
        try:
            await asyncio.wait_for(hub.setup(), .5)
            await asyncio.wait_for(asyncio.gather(*foreground), .5)
            self.assertEqual(len(background), 1)
            self.assertFalse(hub._local_task.done())
            await hub.unload()
            self.assertTrue(disconnected.is_set())
        finally:
            for task in foreground + background:
                task.cancel()
            await asyncio.gather(*foreground, *background, return_exceptions=True)

    def test_staged_patch_check_idempotence_and_line_endings(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'hub.py'
            original = SOURCE.replace('\n', '\r\n').encode()
            path.write_bytes(original)
            self.assertTrue(module.apply(temp, check=True))
            self.assertEqual(path.read_bytes(), original)
            output = Path(temp) / 'hub.patched.py'
            self.assertTrue(module.apply(temp, output=output))
            self.assertEqual(path.read_bytes(), original)
            changed = output.read_bytes()
            self.assertIn(b'\r\n', changed)
            with self.assertRaises(FileExistsError):
                module.apply(temp, output=output)
            self.assertEqual(output.read_bytes(), changed)
            # Simulate the user accepting the generated file in a test copy.
            path.write_bytes(changed)
            self.assertFalse(module.apply(temp, output=Path(temp) / 'unused.py'))
            self.assertFalse((Path(temp) / 'unused.py').exists())

    def test_concurrent_source_edit_is_never_overwritten(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'hub.py'
            path.write_text(SOURCE)
            original_patcher = module.patched
            def editor_race(source):
                path.write_text('# an independent editor changed this file\n')
                return original_patcher(source)
            with patch.object(module, 'patched', side_effect=editor_race):
                module.apply(temp, output=Path(temp) / 'review.py')
            self.assertEqual(path.read_text(), '# an independent editor changed this file\n')

    def test_output_cannot_replace_the_source(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'hub.py'
            path.write_text(SOURCE)
            with self.assertRaisesRegex(ValueError, 'Output must not be the source'):
                module.apply(temp, output=path)
            self.assertEqual(path.read_text(), SOURCE)

    def test_unknown_source_is_not_modified(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'hub.py'
            path.write_text('class Different: pass\n')
            with self.assertRaisesRegex(ValueError, 'Unsupported source'):
                module.apply(temp)
            self.assertEqual(path.read_text(), 'class Different: pass\n')


if __name__ == '__main__':
    unittest.main()
