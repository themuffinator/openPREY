// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import java.util.Locale;

final class SetupLanguage {
    static final String[] TAGS = {"en", "de", "es", "fr"};
    private static final String[] ENGINE = {"english", "german", "spanish", "french"};
    static int index(String tag) {
        for (int i = 0; i < TAGS.length; ++i) if (TAGS[i].equals(tag)) return i;
        return 0;
    }
    static String systemDefault() { return TAGS[index(Locale.getDefault().getLanguage())]; }
    static String engine(String tag) {
        if (tag == null) return null;
        int i = index(tag);
        return TAGS[i].equals(tag) ? ENGINE[i] : null;
    }
}
