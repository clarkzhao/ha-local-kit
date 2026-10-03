# SPDX-License-Identifier: GPL-3.0-only
"""Patch dimmer controls, Kelvin mapping and IO routing in a staged integration."""
from pathlib import Path
import sys
from patch_utils import replace_once, write_patches


root = Path(sys.argv[1])
updates = {}
path = root / 'light.py'
text = path.read_text(encoding='utf-8')
start = text.index('class LifeSmartDimmerLight(')
end = text.index('\n\nclass LifeSmartSPOTRGBLight(', start)
block = text[start:end]
block = replace_once(block, 'ratio = (255 - val) / 255.0', 'ratio = val / 255.0')
start_method = block.index('    async def async_turn_on(')
block = block[:start_method] + '''    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set requested IOs; update state from device reports."""
        from homeassistant.exceptions import HomeAssistantError

        commands = []
        if ATTR_BRIGHTNESS in kwargs:
            brightness = max(0, min(255, round(kwargs[ATTR_BRIGHTNESS])))
            commands.append(("P1", CMD_TYPE_SET_VAL, brightness))
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            min_k, max_k = self._attr_min_color_temp_kelvin, self._attr_max_color_temp_kelvin
            kelvin = max(min_k, min(kwargs[ATTR_COLOR_TEMP_KELVIN], max_k))
            # LifeSmart defines P2=0 as warm and P2=255 as cold.
            temp_val = round((kelvin - min_k) * 255 / (max_k - min_k))
            commands.append(("P2", CMD_TYPE_SET_VAL, temp_val))
        if not commands or (not self._attr_is_on and ATTR_BRIGHTNESS not in kwargs):
            commands.append(("P1", CMD_TYPE_ON, 1))

        # The gateway rejects multi-EpSet; P1/P2 support independent writes.
        for idx, command_type, value in commands:
            result = await self._client.async_send_single_command(
                self.agt, self.me, idx, command_type, value
            )
            if result != 0:
                raise HomeAssistantError(f"LifeSmart dimmer command failed: {idx} ({result})")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send power off; update state from device reports."""
        from homeassistant.exceptions import HomeAssistantError

        result = await self._client.turn_off_light_switch_async("P1", self.agt, self.me)
        if result != 0:
            raise HomeAssistantError(f"LifeSmart dimmer power command failed ({result})")
'''
text = text[:start] + block + text[end:]
updates[path] = text

path = root / 'hub.py'
text = path.read_text(encoding='utf-8')
text = replace_once(text, '    CLIMATE_TYPES,', '    CLIMATE_TYPES,\n    LIGHT_DIMMER_TYPES,')
text = replace_once(text,
    'if device_type in CLIMATE_TYPES and sub_device_key:',
    'if device_type in (CLIMATE_TYPES | LIGHT_DIMMER_TYPES) and sub_device_key:')
text = replace_once(text,
    '# Climate entities represent the whole device and subscribe without',
    '# Climate and dimmer entities represent the whole device and subscribe without')
updates[path] = text
write_patches(updates)
print('Patched light.py and hub.py')
