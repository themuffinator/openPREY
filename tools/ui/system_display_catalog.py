#!/usr/bin/env python3
"""The SYSTEM page's display list keys, which the settings service publishes.

The display pass declares every settings.display.* key here, so the page and
the service schema agree. The device, span, resolution and refresh rows read
them; the draft aliases for r_screen and r_multiScreen belong to those rows.
The slot counts match SystemDisplayDeviceSlots, SystemDisplayModeSlots and
SystemDisplayRefreshSlots in src/ui/application/SystemDisplay.h.
"""
from __future__ import annotations

DEVICE_SLOTS, MODE_SLOTS, REFRESH_SLOTS = 8, 40, 16
PREFIX = 'settings.display.'


def keys():
    """Every display list key and its declaration, in publication order."""
    declarations = {
        PREFIX + 'available': {'type': 'boolean', 'initial': False},
        PREFIX + 'spanAvailable': {'type': 'boolean', 'initial': False},
        PREFIX + 'catalog': {'type': 'string', 'initial': ''},
        PREFIX + 'count': {'type': 'number', 'initial': 0},
        PREFIX + 'optionCount': {'type': 'number', 'initial': 1},
    }
    for index in range(DEVICE_SLOTS):
        declarations[f'{PREFIX}{index}.label'] = {'type': 'string', 'initial': ''}
    for name, slots in (('mode', MODE_SLOTS), ('refresh', REFRESH_SLOTS)):
        declarations[f'{PREFIX}{name}.optionCount'] = {'type': 'number', 'initial': 0}
        declarations[f'{PREFIX}{name}.selected'] = {'type': 'number', 'initial': 0}
        for index in range(slots):
            declarations[f'{PREFIX}{name}.{index}.label'] = {'type': 'string', 'initial': ''}
    return declarations


def declare(document):
    """Declare exactly the display list keys in a composed SYSTEM document."""
    wanted = keys()
    for key in [key for key in document['state'] if key.startswith(PREFIX) and key not in wanted]:
        del document['state'][key]
    document['state'].update(wanted)
