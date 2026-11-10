#!/usr/bin/env python3
"""Reject false passes in the actual-emitter distance measurement harness."""
from copy import deepcopy
import unittest

from sound_distance_runtime import assess, collect


CASE = {"tag": "0_0", "shader": "weapon_lightninggun_fireloop", "distance": 520,
        "origin": [520, 0, 0], "quadratic": False, "falloff": .5, "authored_db": -6}
CHANNEL = ('SOUND_DISTANCE emitter=2 channel=0 shader="weapon_lightninggun_fireloop" '
           'flags=32 origin=520,0,0 direct=520 spatial=520 min=40 max=1000 '
           'authoredGain=0.5 volumeDB=-15.7289 portals=0\n')
BACKEND = ('SOUND_DISTANCE_BACKEND available=1 source=10 playing=1 gain=0.1625 '
           'listenerGain=1 position=0,0,-520 rolloff=0 reference=1 innerRadius=40 sourceRadius=20\n')
WORLD = 'SOUND_DISTANCE_WORLD available=1 listener=1 area=28 origin=0,0,0\n'


def log(rows=CHANNEL + BACKEND, world=WORLD):
    return ('DISTANCE_GAMEPLAY_READY\nDISTANCE_SAMPLE_0_0 \n' + world + rows
            + 'SOUND_DISTANCE_END channels=1\nDISTANCE_SAMPLE_END \nDISTANCE_COMPLETE\n')


class DistanceTest(unittest.TestCase):
    def sample(self):
        return collect(log(), [CASE])

    def test_linear_and_physical(self):
        samples = self.sample()
        assess(samples, False)
        self.assertAlmostEqual(samples[0]["expected_gain"], .1625)
        samples[0]["backend"]["listenerGain"] = ".25"
        assess(samples, True)

    def test_quadratic(self):
        samples = self.sample()
        samples[0]["quadratic"] = True
        samples[0]["backend"]["gain"] = ".08125"
        assess(samples, False)

    def test_selects_known_emitter_among_stock_channels(self):
        background = CHANNEL.replace("origin=520,0,0", "origin=5000,0,0") + BACKEND
        samples = collect(log(background + CHANNEL + BACKEND), [CASE])
        self.assertEqual(samples[0]["matching_shader_channels"], 2)
        self.assertEqual(samples[0]["channel"]["origin"], "520,0,0")
        assess(samples, False)

    def test_rejects_duplicate_or_missing_fixture(self):
        for rows in (CHANNEL + BACKEND + CHANNEL + BACKEND, "", CHANNEL):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                collect(log(rows), [CASE])

    def test_rejects_incomplete_actions(self):
        for text in (log().replace("DISTANCE_COMPLETE", ""), log(world=""),
                     log() + "Unknown command 'spawn'\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                collect(text, [CASE])

    def test_rejects_changed_units_gain_and_routing(self):
        original = self.sample()
        mutations = (
            ("channel", "direct", "13.208"), ("channel", "min", "1.016"),
            ("channel", "max", "25.4"), ("channel", "authoredGain", "1"),
            ("channel", "spatial", "600"), ("channel", "portals", "1"),
            ("world", "origin", "1,0,0"), ("world", "area", "-1"),
            ("backend", "position", "0,0,-13.208"), ("backend", "gain", ".3"),
            ("backend", "rolloff", "1"), ("backend", "playing", "0"),
            ("backend", "innerRadius", "1.016"), ("backend", "sourceRadius", "0"),
            ("backend", "available", "0"),
        )
        for owner, key, value in mutations:
            samples = deepcopy(original)
            samples[0][owner][key] = value
            with self.subTest(owner=owner, key=key), self.assertRaises(ValueError):
                assess(samples, False)

    def test_fast_distance_approximation(self):
        samples = self.sample()
        samples[0]["channel"].update(direct="519.2", spatial="519.2")
        samples[0]["backend"]["gain"] = str(.5 * .65 * (1000 - 519.2) / 960)
        assess(samples, False)

    def test_silent_distance_can_release_voice_but_not_hide_backend_error(self):
        samples = self.sample()
        samples[0].update(distance=1000, origin=[1000, 0, 0])
        samples[0]["channel"].update(origin="1000,0,0", direct="1000", spatial="1000")
        samples[0]["backend"] = {"available": "0"}
        assess(samples, False)
        samples[0]["backend"]["error"] = "1"
        with self.assertRaises(ValueError):
            assess(samples, False)


if __name__ == "__main__":
    unittest.main()
