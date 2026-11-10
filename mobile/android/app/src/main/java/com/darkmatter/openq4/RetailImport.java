// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import android.system.ErrnoException;
import android.system.Os;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

/** Cancellable, per-archive import into app-owned storage. Never owns private saves. */
final class RetailImport {
    private static final int MAX_FILES = 4096;
    private static final int MAX_ARCHIVES = 128;
    private static final long MAX_TOTAL_BYTES = 32L * 1024 * 1024 * 1024;

    static final class Entry {
        final String id, name;
        final long bytes; // -1 means the document provider does not report a size.
        Entry(String id, String name, long bytes) {
            this.id = id;
            this.name = name;
            this.bytes = bytes;
        }
    }

    interface Source {
        List<Entry> entries() throws IOException;
        InputStream open(Entry entry) throws IOException;
    }

    enum Code { SOURCE_UNAVAILABLE, INVALID_NAME, DUPLICATE_NAME, LIMIT, DESTINATION_UNAVAILABLE,
                INSUFFICIENT_SPACE, SOURCE_CHANGED, INVALID_ARCHIVE, WRONG_VERSION, COPY_FAILED, COMMIT_FAILED }
    static final class Failure extends IOException {
        final Code code;
        final String name;
        final long requiredBytes, availableBytes;
        Failure(Code code, String name, Throwable cause) {
            this(code, name, -1, -1, cause);
        }
        Failure(Code code, String name, long requiredBytes, long availableBytes, Throwable cause) {
            super("Retail import " + code + ": " + name, cause);
            this.code = code;
            this.name = name;
            this.requiredBytes = requiredBytes;
            this.availableBytes = availableBytes;
        }
    }

    enum Phase { INSPECTING, CHECKING_EXISTING, COPYING, VERIFYING, CHECKING_INSTALLATION }
    interface Progress {
        /** Per-file bytes, or complete-installation bytes in the final phase; -1 means unknown. */
        boolean update(Phase phase, String name, int completedFiles, int files, long bytes, long totalBytes);
    }

    static final class Result {
        final int copied, reused;
        final RetailData.Report report;
        Result(int copied, int reused, RetailData.Report report) {
            this.copied = copied;
            this.reused = reused;
            this.report = report;
        }
    }

    // The default is Android's atomic same-volume replacement. The small
    // adapter also permits deterministic space and commit failure fixtures.
    static class Storage {
        long available(File directory) { return directory.getUsableSpace(); }
        void replace(File temporary, File target) throws IOException {
            try { Os.rename(temporary.getAbsolutePath(), target.getAbsolutePath()); }
            catch (ErrnoException error) { throw new IOException(error); }
        }
    }

    private static void progress(Progress observer, Phase phase, String name,
                                 int completed, int count, long bytes, long total) throws InterruptedIOException {
        if (Thread.currentThread().isInterrupted() ||
                (observer != null && !observer.update(phase, name, completed, count, bytes, total))) {
            throw new InterruptedIOException("Retail import cancelled");
        }
    }

    private static void requireUnlinked(File file) throws IOException {
        if (!file.getAbsoluteFile().equals(file.getCanonicalFile())) {
            throw new Failure(Code.DESTINATION_UNAVAILABLE, file.getName(), null);
        }
    }

    private static void requireDirectory(File directory) throws IOException {
        requireUnlinked(directory);
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new Failure(Code.DESTINATION_UNAVAILABLE, directory.getName(), null);
        }
        requireUnlinked(directory);
    }

    private static void discardPartial(File file) throws IOException {
        requireUnlinked(file);
        if (file.exists() && (!file.isFile() || !file.delete())) {
            throw new Failure(Code.DESTINATION_UNAVAILABLE, file.getName(), null);
        }
    }

    private static Map<String, File> destinations(File directory) throws IOException {
        File[] children = directory.listFiles();
        if (children == null) throw new Failure(Code.DESTINATION_UNAVAILABLE, directory.getName(), null);
        if (children.length > MAX_FILES) throw new Failure(Code.LIMIT, directory.getName(), null);
        Map<String, File> files = new TreeMap<>();
        for (File child : children) {
            String name = child.getName().toLowerCase(Locale.ROOT);
            if (!name.endsWith(".pk4") || RetailData.ignoredGameCode(name)) continue;
            if (files.put(name, child) != null) throw new Failure(Code.DUPLICATE_NAME, name, null);
            if (files.size() > MAX_ARCHIVES) throw new Failure(Code.LIMIT, directory.getName(), null);
            requireUnlinked(child);
            if (!child.isFile()) throw new Failure(Code.DESTINATION_UNAVAILABLE, child.getName(), null);
        }
        return files;
    }

    private static Map<String, Entry> plan(Source source) throws IOException {
        List<Entry> entries = source.entries();
        if (entries == null) throw new Failure(Code.SOURCE_UNAVAILABLE, "", null);
        if (entries.size() > MAX_FILES) throw new Failure(Code.LIMIT, "", null);
        Map<String, Entry> plan = new TreeMap<>();
        long bytes = 0;
        for (Entry entry : entries) {
            if (entry == null || entry.id == null || entry.name == null) throw new Failure(Code.INVALID_NAME, "", null);
            String name = entry.name.toLowerCase(Locale.ROOT);
            if (!name.endsWith(".pk4") || RetailData.ignoredGameCode(name)) continue;
            // Only flat archive names become local paths. Provider IDs remain opaque.
            if (name.length() > 128 || !name.matches("[a-z0-9][a-z0-9_.-]*\\.pk4")) {
                throw new Failure(Code.INVALID_NAME, entry.name, null);
            }
            if (entry.bytes < -1 || entry.bytes > Integer.MAX_VALUE || entry.bytes > MAX_TOTAL_BYTES - bytes) {
                throw new Failure(Code.LIMIT, entry.name, null);
            }
            if (entry.bytes > 0) bytes += entry.bytes;
            if (plan.put(name, entry) != null) throw new Failure(Code.DUPLICATE_NAME, entry.name, null);
            if (plan.size() > MAX_ARCHIVES) throw new Failure(Code.LIMIT, "", null);
        }
        if (plan.isEmpty()) throw new Failure(Code.SOURCE_UNAVAILABLE, "", null);
        return plan;
    }

    private static void requireSpace(Storage storage, File work, File temporary, String name, long bytes)
            throws IOException {
        // A retry truncates only its own regular temporary file, reclaiming it.
        long required = Math.max(0, bytes - temporary.length());
        long available = storage.available(work);
        if (required > available) throw new Failure(Code.INSUFFICIENT_SPACE, name, required, available, null);
    }

    static Result run(Source source, File external, Progress observer) throws IOException {
        return run(source, external, RetailData.OFFICIAL, new Storage(), observer);
    }

    /** Serialize writers in the host process, including configuration-change retries. */
    static synchronized Result run(Source source, File external, List<RetailData.Expected> expected,
                                   Storage storage, Progress observer) throws IOException {
        progress(observer, Phase.INSPECTING, "", 0, 0, 0, -1);
        Map<String, Entry> planned = plan(source);
        if (external == null) throw new Failure(Code.DESTINATION_UNAVAILABLE, "", null);
        File root = external.getCanonicalFile();
        requireDirectory(root);
        File data = new File(root, "q4base"), work = new File(root, ".openq4-import");
        requireDirectory(data);
        requireDirectory(work);
        Map<String, File> existing = destinations(data);
        Map<String, RetailData.Expected> catalogue = new TreeMap<>();
        for (RetailData.Expected item : expected) catalogue.put(item.name, item);
        int copied = 0, reused = 0, finished = 0;
        long receivedTotal = 0;
        for (Map.Entry<String, Entry> item : planned.entrySet()) {
            String name = item.getKey();
            Entry entry = item.getValue();
            File target = existing.containsKey(name) ? existing.get(name) : new File(data, name);
            File temporary = new File(work, name + ".part");
            final int completed = finished;
            RetailData.Expected known = catalogue.get(name);
            requireUnlinked(target);
            if (target.exists() && known != null) {
                boolean healthy = false;
                try {
                    Pk4Checksum.Result installed = Pk4Checksum.read(target, true, (bytes, total) -> {
                        progress(observer, Phase.CHECKING_EXISTING, name, completed, planned.size(), bytes, total);
                        return true;
                    });
                    healthy = installed.checksum == known.checksum;
                } catch (InterruptedIOException cancelled) {
                    throw cancelled;
                } catch (IOException damaged) {
                    // Only an independently validated temporary copy may replace it.
                }
                if (healthy) {
                    // A healthy official copy is already usable. Do not replace
                    // it from a stale, incomplete or unavailable source provider.
                    discardPartial(temporary);
                    ++reused;
                    ++finished;
                    continue;
                }
            }
            requireUnlinked(temporary);
            if (temporary.exists() && !temporary.isFile()) throw new Failure(Code.DESTINATION_UNAVAILABLE, name, null);
            requireSpace(storage, work, temporary, name, entry.bytes < 0 ? 65536 : entry.bytes);
            long received = 0;
            progress(observer, Phase.COPYING, name, completed, planned.size(), 0, entry.bytes);
            try (InputStream input = source.open(entry)) {
                if (input == null) throw new Failure(Code.SOURCE_UNAVAILABLE, name, null);
                try (FileOutputStream output = new FileOutputStream(temporary)) {
                    byte[] buffer = new byte[65536];
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        if (count == 0) throw new Failure(Code.COPY_FAILED, name, null);
                        if (count > Integer.MAX_VALUE - received || count > MAX_TOTAL_BYTES - receivedTotal) {
                            throw new Failure(Code.LIMIT, name, null);
                        }
                        if (entry.bytes >= 0 && count > entry.bytes - received) {
                            throw new Failure(Code.SOURCE_CHANGED, name, null);
                        }
                        progress(observer, Phase.COPYING, name, completed, planned.size(), received, entry.bytes);
                        output.write(buffer, 0, count);
                        received += count;
                        receivedTotal += count;
                    }
                    if (entry.bytes >= 0 && received != entry.bytes) throw new Failure(Code.SOURCE_CHANGED, name, null);
                    output.getFD().sync();
                }
            } catch (InterruptedIOException cancelled) {
                throw cancelled;
            } catch (Failure failure) {
                throw failure;
            } catch (IOException error) {
                long remaining = entry.bytes < 0 ? 65536 : Math.max(0, entry.bytes - received);
                long available = storage.available(work);
                if (remaining > available) throw new Failure(Code.INSUFFICIENT_SPACE, name, remaining, available, error);
                throw new Failure(Code.COPY_FAILED, name, error);
            }
            progress(observer, Phase.COPYING, name, completed, planned.size(), received, entry.bytes);
            Pk4Checksum.Result result;
            try {
                result = Pk4Checksum.read(temporary, true, (bytes, total) -> {
                    progress(observer, Phase.VERIFYING, name, completed, planned.size(), bytes, total);
                    return true;
                });
            } catch (InterruptedIOException cancelled) {
                throw cancelled;
            } catch (IOException error) {
                throw new Failure(Code.INVALID_ARCHIVE, name, error);
            }
            if (known != null && known.required && result.checksum != known.checksum) {
                throw new Failure(Code.WRONG_VERSION, name, null);
            }
            // Cancellation before promotion leaves the previous file intact.
            progress(observer, Phase.VERIFYING, name, completed, planned.size(), result.expandedBytes, result.expandedBytes);
            requireUnlinked(data);
            requireUnlinked(work);
            requireUnlinked(temporary);
            requireUnlinked(target);
            if (target.exists() && !target.isFile()) throw new Failure(Code.DESTINATION_UNAVAILABLE, name, null);
            try { storage.replace(temporary, target); }
            catch (IOException error) { throw new Failure(Code.COMMIT_FAILED, name, error); }
            existing.put(name, target);
            ++copied;
            ++finished;
        }
        // Successfully committed files survive cancellation/process death and
        // are re-verified on retry. Abandoned .part files are never mounted.
        RetailData.Report report = RetailData.scan(data, expected, (phase, name, done, count, bytes, total) ->
            observer == null || observer.update(Phase.CHECKING_INSTALLATION, name, done, count, bytes,
                                                phase == RetailData.Phase.INSPECTING ? -1 : total));
        return new Result(copied, reused, report);
    }
}
