// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/** Small release diagnostics, written only while the caller owns setup storage. */
final class SetupDiagnostics {
    private static final long LIMIT = 256 * 1024;

    private static void unlinked(File path) throws IOException {
        if (!path.getAbsoluteFile().equals(path.getCanonicalFile())) throw new IOException("Linked diagnostic path");
    }

    static boolean record(File files, String message, Throwable error) {
        try {
            File directory = new File(files.getCanonicalFile(), "saves/baseoq4/logs");
            unlinked(directory);
            if (!directory.isDirectory() && !directory.mkdirs()) return false;
            unlinked(directory);
            File log = new File(directory, "setup.log"), previous = new File(directory, "setup-previous.log");
            unlinked(log); unlinked(previous);
            if ((log.exists() && !log.isFile()) || (previous.exists() && !previous.isFile())) return false;
            SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.ROOT);
            format.setTimeZone(TimeZone.getTimeZone("UTC"));
            StringBuilder text = new StringBuilder(format.format(new Date())).append(' ').append(bounded(message)).append('\n');
            // Limit provider messages, cause depth and frames without first
            // constructing an unbounded stack trace from a remote exception.
            for (int causes = 0; error != null && causes < 4; ++causes, error = error.getCause()) {
                text.append(error.getClass().getName()).append(": ").append(bounded(error.getMessage())).append('\n');
                StackTraceElement[] frames = error.getStackTrace();
                for (int i = 0; i < Math.min(8, frames.length); ++i) text.append("  ").append(bounded(frames[i].toString())).append('\n');
            }
            byte[] bytes = text.toString().getBytes(StandardCharsets.UTF_8);
            if (log.length() > LIMIT - bytes.length) {
                if (previous.exists() && !previous.delete()) return false;
                if (!log.renameTo(previous)) return false;
            }
            try (FileOutputStream output = new FileOutputStream(log, true)) { output.write(bytes); }
            return true;
        } catch (IOException | RuntimeException unavailable) { return false; }
    }

    private static String bounded(String value) {
        if (value == null) return "";
        return value.substring(0, Math.min(1024, value.length())).replaceAll("[\\p{Cntrl}\\p{Cf}]", " ");
    }
}
