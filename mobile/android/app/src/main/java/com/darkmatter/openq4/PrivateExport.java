// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import java.io.Closeable;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Bounded, read-only save/log snapshots. A live snapshot owns the setup lease. */
final class PrivateExport {
    private static final int MAX_FILES = 4096;
    private static final long MAX_BYTES = 2L * 1024 * 1024 * 1024;
    private static final int MAX_PATH_BYTES = 1024;
    static final String MANIFEST = "openq4-export.tsv";
    enum Kind {
        SAVES("savegames"), LOGS("logs");
        final String folder;
        Kind(String folder) { this.folder = folder; }
    }
    enum Code { EMPTY, SOURCE_UNAVAILABLE, UNSAFE_PATH, LIMIT, CHANGED_FILE, CACHE_UNAVAILABLE,
                INSUFFICIENT_SPACE, OUTPUT_UNAVAILABLE, WRITE_FAILED }
    static final class Failure extends IOException {
        final Code code;
        final String name;
        final long requiredBytes, availableBytes;
        Failure(Code code, String name, Throwable cause) { this(code, name, -1, -1, cause); }
        Failure(Code code, String name, long requiredBytes, long availableBytes, Throwable cause) {
            super("Export " + code + ": " + name, cause);
            this.code = code; this.name = name;
            this.requiredBytes = requiredBytes; this.availableBytes = availableBytes;
        }
    }
    interface Progress {
        boolean update(String name, int completed, int files, long bytes, long total);
    }
    static class Storage {
        long available(File directory) { return directory.getUsableSpace(); }
    }
    static final class Snapshot implements Closeable {
        final File file;
        final Kind kind;
        final int count;
        final long sourceBytes, bytes;
        private final Object owner;
        private boolean closed;
        Snapshot(File file, Kind kind, int count, long sourceBytes, Object owner) {
            this.file = file; this.kind = kind; this.count = count;
            this.sourceBytes = sourceBytes; bytes = file.length();
            this.owner = owner;
        }
        @Override public synchronized void close() throws IOException {
            if (closed) return;
            try { removeTemporary(file); }
            finally { closed = true; StorageSession.INSTANCE.endSetup(owner); }
        }
    }

    private static final class Entry {
        final File file;
        final String name;
        final long bytes, modified;
        Entry(File file, String name) {
            this.file = file; this.name = name; bytes = file.length(); modified = file.lastModified();
        }
        void unchanged() throws IOException {
            unlinked(file);
            if (!file.isFile() || file.length() != bytes || file.lastModified() != modified)
                throw new Failure(Code.CHANGED_FILE, name, null);
        }
    }

    private static void progress(Progress observer, String name, int complete, int files, long bytes, long total)
            throws InterruptedIOException {
        if (Thread.currentThread().isInterrupted() ||
                (observer != null && !observer.update(name, complete, files, bytes, total)))
            throw new InterruptedIOException("Export cancelled");
    }

    private static void unlinked(File file) throws IOException {
        if (!file.getAbsoluteFile().equals(file.getCanonicalFile())) throw new Failure(Code.UNSAFE_PATH, file.getName(), null);
    }

    private static void safeName(String name) throws Failure {
        if (name.isEmpty() || name.equals(".") || name.equals("..") || name.endsWith(".") || name.endsWith(" ") ||
                name.indexOf('/') >= 0 || name.indexOf('\\') >= 0 || name.indexOf(':') >= 0)
            throw new Failure(Code.UNSAFE_PATH, name, null);
        for (int i = 0; i < name.length(); ++i) {
            char c = name.charAt(i);
            if (Character.isISOControl(c) || c == '<' || c == '>' || c == '"' || c == '|' || c == '?' || c == '*')
                throw new Failure(Code.UNSAFE_PATH, name, null);
        }
        String stem = name.split("\\.", 2)[0].toUpperCase(Locale.ROOT);
        if (stem.matches("CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]")) throw new Failure(Code.UNSAFE_PATH, name, null);
    }

    private static File[] children(File directory) throws Failure {
        File[] files = directory.listFiles();
        if (files == null) throw new Failure(Code.SOURCE_UNAVAILABLE, directory.getName(), null);
        if (files.length > MAX_FILES) throw new Failure(Code.LIMIT, directory.getName(), null);
        Arrays.sort(files);
        return files;
    }

    private static final class Inventory {
        final List<Entry> entries = new ArrayList<>();
        final Set<String> names = new HashSet<>();
        int visited;
        long bytes;
        void visit(File directory, String prefix, int depth) throws IOException {
            if (depth > 16) throw new Failure(Code.LIMIT, prefix, null);
            for (File file : children(directory)) {
                progress(null, "", 0, 0, 0, 0);
                if (++visited > MAX_FILES) throw new Failure(Code.LIMIT, prefix, null);
                unlinked(file); safeName(file.getName());
                String name = prefix + file.getName();
                if (name.getBytes(StandardCharsets.UTF_8).length > MAX_PATH_BYTES) throw new Failure(Code.LIMIT, name, null);
                if (!names.add(name.toLowerCase(Locale.ROOT))) throw new Failure(Code.UNSAFE_PATH, name, null);
                if (file.isDirectory()) visit(file, name + "/", depth + 1);
                else if (file.isFile()) {
                    Entry entry = new Entry(file, name);
                    if (entry.bytes > MAX_BYTES - bytes) throw new Failure(Code.LIMIT, name, null);
                    bytes += entry.bytes; entries.add(entry);
                } else throw new Failure(Code.SOURCE_UNAVAILABLE, name, null);
            }
        }
    }

    private static Inventory inventory(File files, Kind kind) throws IOException {
        Inventory result = new Inventory();
        File saves = new File(files.getCanonicalFile(), "saves");
        unlinked(saves);
        if (!saves.exists()) return result;
        for (File game : children(saves)) {
            progress(null, "", 0, 0, 0, 0);
            unlinked(game);
            if (!game.isDirectory()) continue;
            safeName(game.getName());
            File data = new File(game, kind.folder);
            unlinked(data);
            if (!data.exists()) continue;
            if (!data.isDirectory()) throw new Failure(Code.SOURCE_UNAVAILABLE, game.getName() + "/" + kind.folder, null);
            if (!result.names.add((game.getName() + "/" + kind.folder).toLowerCase(Locale.ROOT)))
                throw new Failure(Code.UNSAFE_PATH, game.getName(), null);
            result.visit(data, game.getName() + "/" + kind.folder + "/", 0);
        }
        return result;
    }

    private static void sameInventory(Inventory before, Inventory after) throws IOException {
        if (before.entries.size() != after.entries.size() || !before.names.equals(after.names))
            throw new Failure(Code.CHANGED_FILE, "", null);
        for (int i = 0; i < before.entries.size(); ++i) {
            Entry a = before.entries.get(i), b = after.entries.get(i);
            if (!a.name.equals(b.name) || a.bytes != b.bytes || a.modified != b.modified)
                throw new Failure(Code.CHANGED_FILE, a.name, null);
        }
    }

    private static File workDirectory(File cache) throws IOException {
        File directory = new File(cache.getCanonicalFile(), "openq4-exports");
        unlinked(directory);
        if (!directory.isDirectory() && !directory.mkdirs()) throw new Failure(Code.CACHE_UNAVAILABLE, "", null);
        unlinked(directory);
        // This reserved cache folder contains generated snapshots only. Keep
        // unrelated files, and never follow links during abandoned-file cleanup.
        for (File previous : children(directory)) {
            if (previous.getName().matches("export-[A-Za-z0-9_-]+\\.zip\\.part")) removeTemporary(previous);
        }
        return directory;
    }

    private static void removeTemporary(File file) throws IOException {
        unlinked(file);
        if (file.exists() && (!file.isFile() || !file.delete())) throw new Failure(Code.CACHE_UNAVAILABLE, file.getName(), null);
    }

    private static MessageDigest sha256() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException unavailable) { throw new AssertionError(unavailable); }
    }

    private static String hex(byte[] bytes) {
        char[] value = new char[bytes.length * 2];
        char[] digits = "0123456789abcdef".toCharArray();
        for (int i = 0; i < bytes.length; ++i) {
            value[i * 2] = digits[(bytes[i] & 255) >>> 4]; value[i * 2 + 1] = digits[bytes[i] & 15];
        }
        return new String(value);
    }

    static Snapshot create(File files, File cache, Kind kind, Progress observer) throws IOException {
        return create(files, cache, kind, new Storage(), observer);
    }

    static Snapshot create(File files, File cache, Kind kind, Storage storage, Progress observer) throws IOException {
        Object owner = StorageSession.INSTANCE.beginSetup();
        boolean transferred = false;
        try {
            Snapshot result = createOwned(files, cache, kind, storage, observer, owner);
            transferred = true;
            return result;
        } finally {
            if (!transferred) StorageSession.INSTANCE.endSetup(owner);
        }
    }

    private static Snapshot createOwned(File files, File cache, Kind kind, Storage storage, Progress observer,
                                        Object owner) throws IOException {
        if (files == null || cache == null || kind == null) throw new Failure(Code.CACHE_UNAVAILABLE, "", null);
        progress(observer, "", 0, 0, 0, 0);
        Inventory before = inventory(files, kind);
        if (before.entries.isEmpty()) throw new Failure(Code.EMPTY, "", null);
        File directory = workDirectory(cache);
        // Conservative allowance for deflate expansion, headers and the manifest.
        long required = before.bytes + before.bytes / 1000 + (long) before.entries.size() * 4096 + 65536;
        long available = storage.available(directory);
        if (available < required) throw new Failure(Code.INSUFFICIENT_SPACE, "", required, available, null);
        File temporary = File.createTempFile("export-", ".zip.part", directory);
        boolean ready = false;
        Throwable failure = null;
        try {
            StringBuilder manifest = new StringBuilder("openQ4-export-v1\t" + kind.name().toLowerCase(Locale.ROOT) + "\n");
            byte[] buffer = new byte[65536];
            long copied = 0;
            int complete = 0;
            try (FileOutputStream output = new FileOutputStream(temporary); ZipOutputStream zip = new ZipOutputStream(output)) {
                zip.setLevel(1);
                for (Entry entry : before.entries) {
                    progress(observer, entry.name, complete, before.entries.size(), copied, before.bytes);
                    entry.unchanged();
                    ZipEntry packed = new ZipEntry(entry.name); packed.setTime(entry.modified); zip.putNextEntry(packed);
                    MessageDigest digest = sha256();
                    long bytes = 0;
                    FileInputStream source;
                    try { source = new FileInputStream(entry.file); }
                    catch (IOException error) { throw new Failure(Code.SOURCE_UNAVAILABLE, entry.name, error); }
                    try (FileInputStream input = source) {
                        for (;;) {
                            int count;
                            try { count = input.read(buffer); }
                            catch (IOException error) { throw new Failure(Code.SOURCE_UNAVAILABLE, entry.name, error); }
                            if (count < 0) break;
                            if (count > entry.bytes - bytes) throw new Failure(Code.CHANGED_FILE, entry.name, null);
                            bytes += count; copied += count; digest.update(buffer, 0, count); zip.write(buffer, 0, count);
                            progress(observer, entry.name, complete, before.entries.size(), copied, before.bytes);
                        }
                    }
                    if (bytes != entry.bytes) throw new Failure(Code.CHANGED_FILE, entry.name, null);
                    entry.unchanged(); zip.closeEntry();
                    manifest.append(hex(digest.digest())).append('\t').append(bytes).append('\t').append(entry.name).append('\n');
                    progress(observer, entry.name, ++complete, before.entries.size(), copied, before.bytes);
                }
                sameInventory(before, inventory(files, kind));
                ZipEntry index = new ZipEntry(MANIFEST); index.setTime(0); zip.putNextEntry(index);
                zip.write(manifest.toString().getBytes(StandardCharsets.UTF_8)); zip.closeEntry();
                progress(observer, "", complete, before.entries.size(), copied, before.bytes);
                zip.finish(); zip.flush(); output.getFD().sync();
            }
            progress(observer, "", complete, before.entries.size(), copied, before.bytes);
            Snapshot result = new Snapshot(temporary, kind, complete, copied, owner);
            ready = true;
            return result;
        } catch (Failure | InterruptedIOException error) {
            failure = error;
            throw error;
        } catch (IOException error) {
            Failure wrapped = new Failure(Code.CACHE_UNAVAILABLE, "", error);
            failure = wrapped;
            throw wrapped;
        } catch (RuntimeException | Error error) {
            failure = error;
            throw error;
        } finally {
            if (!ready) {
                try { removeTemporary(temporary); }
                catch (IOException cleanup) { if (failure != null) failure.addSuppressed(cleanup); else throw cleanup; }
            }
        }
    }
}
