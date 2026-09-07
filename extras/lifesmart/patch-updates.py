# SPDX-License-Identifier: GPL-3.0-only
# Contains/adapts GPL upstream snippets; see README.md and ../../licenses/GPL-3.0.txt
"""Route IO pushes to the aggregate climate entity as well as IO entities."""
from pathlib import Path
import sys

path = Path(sys.argv[1]) / 'hub.py'
newline = '\r\n' if b'\r\n' in path.read_bytes() else '\n'
text = path.read_text()
old = 'from .const import (\n'
assert text.count(old) == 1
text = text.replace(old, old + '    CLIMATE_TYPES,\n', 1)
old = '''            dispatcher_send(
                self.hass, f"{LIFESMART_SIGNAL_UPDATE_ENTITY}_{unique_id}", data
            )
'''
assert text.count(old) == 1
text = text.replace(old, old + '''
            # Climate entities represent the whole device and subscribe without
            # an IO suffix. Keep the original IO signal for sensors/switches.
            if device_type in CLIMATE_TYPES and sub_device_key:
                climate_id = generate_unique_id(device_type, hub_id, device_id)
                io_data = {k: data[k] for k in ("type", "val", "v") if k in data}
                if io_data:
                    dispatcher_send(
                        self.hass,
                        f"{LIFESMART_SIGNAL_UPDATE_ENTITY}_{climate_id}",
                        {sub_device_key: io_data},
                    )
''', 1)
path.write_bytes(text.replace('\n', newline).encode())
print('Patched hub.py climate update routing')
