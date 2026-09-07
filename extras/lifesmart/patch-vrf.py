# SPDX-License-Identifier: GPL-3.0-only
# Contains/adapts GPL upstream snippets; see README.md and ../../licenses/GPL-3.0.txt
"""Apply a narrow VRF patch; fail if the expected upstream code has changed."""
from pathlib import Path
import sys

root = Path(sys.argv[1])

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'Expected exactly one matching block: {old[:100]!r}')
    return text.replace(old, new, 1)

path = root / 'climate.py'
newline = '\r\n' if b'\r\n' in path.read_bytes() else '\n'
text = path.read_text(encoding='utf-8')
text = replace_once(text, '    LIFESMART_F_HVAC_MODE_MAP,', '    LIFESMART_F_FAN_MAP,')
text = replace_once(text,
    'self._attr_fan_modes = list(LIFESMART_F_HVAC_MODE_MAP.keys())',
    'self._attr_fan_modes = list(LIFESMART_F_FAN_MAP.keys())')
start = text.index('    def _update_v_air_p(')
end = text.index('    def _update_sl_uaccb(', start)
block = text[start:end]
block = replace_once(block, 'safe_get(data, "T", "v")', '_temperature_from_io(data, "T")')
block = replace_once(block, 'safe_get(data, "tT", "v")', '_temperature_from_io(data, "tT")')
text = text[:start] + block + text[end:]
path.write_bytes(text.replace('\n', newline).encode('utf-8'))

path = root / 'core/client_base.py'
newline = '\r\n' if b'\r\n' in path.read_bytes() else '\n'
text = path.read_text(encoding='utf-8')
text = replace_once(text, '    REVERSE_F_HVAC_MODE_MAP,\n', '')
text = replace_once(text,
    '''        if hvac_mode == HVACMode.OFF:
            return await self._async_send_single_command(agt, me, "P1", CMD_TYPE_OFF, 0)

        await self._async_send_single_command(agt, me, "P1", CMD_TYPE_ON, 1)''',
    '''        # VRF virtual indoor units use O; physical wall panels use P1.
        power_idx = "O" if device_type == "V_AIR_P" else "P1"
        if hvac_mode == HVACMode.OFF:
            return await self._async_send_single_command(agt, me, power_idx, CMD_TYPE_OFF, 0)

        await self._async_send_single_command(agt, me, power_idx, CMD_TYPE_ON, 1)''')
text = replace_once(text,
    '''        if device_type == "V_AIR_P":
            mode_val = REVERSE_F_HVAC_MODE_MAP.get(hvac_mode)''',
    '''        if device_type == "V_AIR_P":
            mode_val = REVERSE_LIFESMART_HVAC_MODE_MAP.get(hvac_mode)''')
path.write_bytes(text.replace('\n', newline).encode('utf-8'))
print('Patched climate.py and core/client_base.py')
