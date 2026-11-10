// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

/** One atomic preference value; drafts never become engine settings implicitly. */
final class TouchSettings {
    static final String SAVED = "touch_settings", DRAFT = "touch_settings_draft";
    static final TouchSettings DEFAULT = new TouchSettings(0, 10, 5);
    final int preset, sensitivityStep, sizeStep;

    TouchSettings(int preset, int sensitivityStep, int sizeStep) {
        if (preset < 0 || preset > 2 || sensitivityStep < 1 || sensitivityStep > 40 || sizeStep < 0 || sizeStep > 15)
            throw new IllegalArgumentException("Invalid touch settings");
        this.preset = preset; this.sensitivityStep = sensitivityStep; this.sizeStep = sizeStep;
    }

    float sensitivity() { return sensitivityStep / 10.0f; }
    float scale() { return .75f + sizeStep * .05f; }
    float[] engineValues() { return new float[] {preset, sensitivity(), scale()}; }
    String encode() { return "1:" + preset + ":" + sensitivityStep + ":" + sizeStep; }

    static TouchSettings decode(String encoded) {
        if (encoded == null || !encoded.matches("1:[0-2]:[0-9]{1,2}:[0-9]{1,2}")) return DEFAULT;
        try {
            String[] fields = encoded.split(":");
            return new TouchSettings(Integer.parseInt(fields[1]), Integer.parseInt(fields[2]), Integer.parseInt(fields[3]));
        } catch (IllegalArgumentException invalid) { return DEFAULT; }
    }

    /** The gameplay bridge uses the same 0.25 degrees per physical dp. */
    static float lookDegrees(float pixels, float density, float sensitivity) {
        if (!Float.isFinite(pixels) || !Float.isFinite(density) || density < .25f || density > 16 ||
                !Float.isFinite(sensitivity) || sensitivity < .1f || sensitivity > 4) return 0;
        return pixels * .25f * sensitivity / density;
    }
}
