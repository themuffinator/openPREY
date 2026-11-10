// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.io.RandomAccessFile;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Read-only retail PK4 validation without SDL/native library initialization. */
final class Pk4Checksum {
    private static final int MAX_ENTRIES = 65535;
    private static final int MAX_DIRECTORY_BYTES = 16 * 1024 * 1024;
    private static final long MAX_EXPANDED_BYTES = 8L * 1024 * 1024 * 1024;

    enum Problem { INVALID_ARCHIVE, LIMIT, CORRUPT_ENTRY, CHANGED_FILE }

    static final class Invalid extends IOException {
        final Problem problem;
        final String entry;
        Invalid(Problem problem, String entry) {
            super("PK4 " + problem + ": " + entry);
            this.problem = problem;
            this.entry = entry;
        }
    }

    interface Progress {
        /** False cancels the read. A zero total means central-directory inspection. */
        boolean update(long verifiedBytes, long totalBytes) throws IOException;
    }

    static final class Result {
        final int checksum;
        final long expandedBytes;
        final boolean payloadVerified;
        Result(int checksum, long expandedBytes, boolean payloadVerified) {
            this.checksum = checksum;
            this.expandedBytes = expandedBytes;
            this.payloadVerified = payloadVerified;
        }
    }

    private static void progress(Progress progress, long verified, long total) throws IOException {
        if (Thread.currentThread().isInterrupted() || (progress != null && !progress.update(verified, total))) {
            throw new InterruptedIOException("PK4 verification cancelled");
        }
    }

    private static int little16(byte[] bytes, int offset) {
        return (bytes[offset] & 255) | ((bytes[offset+1] & 255) << 8);
    }

    private static long little32(byte[] bytes, int offset) {
        return little16(bytes, offset) | ((long)little16(bytes, offset+2) << 16);
    }

    /** Bound classic ZIP metadata before ZipFile allocates its directory index. */
    private static int inspectDirectory(File file, long length) throws IOException {
        byte[] tail = new byte[(int)Math.min(length, 65535 + 22 + 20)];
        try (RandomAccessFile input = new RandomAccessFile(file, "r")) {
            input.seek(length - tail.length);
            input.readFully(tail);
        }
        for (int at = tail.length - 22; at >= 0; --at) {
            if (little32(tail, at) != 0x06054b50L || at + 22 + little16(tail, at+20) != tail.length) continue;
            int count = little16(tail, at+10);
            long size = little32(tail, at+12), offset = little32(tail, at+16);
            // The required retail baseline uses classic, single-disk ZIPs.
            // A ZIP64 locator could supersede the bounded classic metadata.
            if (count == 65535 || size > MAX_DIRECTORY_BYTES || offset == 0xffffffffL ||
                    (at >= 20 && little32(tail, at-20) == 0x07064b50L)) {
                throw new Invalid(Problem.LIMIT, file.getName());
            }
            if (little16(tail, at+4) != 0 || little16(tail, at+6) != 0 ||
                    little16(tail, at+8) != count || size < (long)count * 46 ||
                    offset + size > length - tail.length + at) {
                throw new Invalid(Problem.INVALID_ARCHIVE, file.getName());
            }
            return count;
        }
        throw new Invalid(Problem.INVALID_ARCHIVE, file.getName());
    }

    /**
     * Fold the CRCs of nonempty entries in central-directory order, exactly as
     * FileSystem.cpp does. Full verification also checks each entry's actual
     * uncompressed bytes; the compatibility checksum alone only covers metadata.
     */
    static Result read(File file, boolean verifyPayload, Progress progress) throws IOException {
        progress(progress, 0, 0);
        File canonical = file.getCanonicalFile();
        long length = canonical.length();
        long modified = canonical.lastModified();
        if (!canonical.isFile() || length < 22) throw new Invalid(Problem.INVALID_ARCHIVE, file.getName());
        if (length > Integer.MAX_VALUE) throw new Invalid(Problem.LIMIT, file.getName());
        int entryCount = inspectDirectory(canonical, length);
        ByteArrayOutputStream crcs = new ByteArrayOutputStream();
        long total = 0;
        try (ZipFile zip = new ZipFile(canonical)) {
            if (zip.size() != entryCount) throw new Invalid(Problem.INVALID_ARCHIVE, file.getName());
            List<ZipEntry> entries = new ArrayList<>();
            Set<String> names = new HashSet<>();
            Enumeration<? extends ZipEntry> enumeration = zip.entries();
            while (enumeration.hasMoreElements()) {
                progress(progress, 0, 0);
                ZipEntry entry = enumeration.nextElement();
                if (entries.size() >= MAX_ENTRIES) throw new Invalid(Problem.LIMIT, file.getName());
                String name = entry.getName();
                if (name.length() > 4096 || !names.add(name.replace('\\', '/').toLowerCase(Locale.ROOT))) {
                    throw new Invalid(Problem.INVALID_ARCHIVE, name);
                }
                long size = entry.getSize();
                long crc = entry.getCrc();
                if (size < 0 || size > Integer.MAX_VALUE || size > MAX_EXPANDED_BYTES - total ||
                        crc < 0 || crc > 0xffffffffL || entry.getCompressedSize() < 0 ||
                        entry.getCompressedSize() > length) {
                    throw new Invalid(Problem.LIMIT, name);
                }
                if (entry.getMethod() != ZipEntry.STORED && entry.getMethod() != ZipEntry.DEFLATED) {
                    throw new Invalid(Problem.INVALID_ARCHIVE, name);
                }
                total += size;
                entries.add(entry);
                if (size > 0) {
                    for (int shift = 0; shift < 32; shift += 8) crcs.write((int)(crc >>> shift) & 255);
                }
            }
            if (verifyPayload) {
                byte[] buffer = new byte[64 * 1024];
                long verified = 0;
                progress(progress, 0, total);
                for (ZipEntry entry : entries) {
                    CRC32 actual = new CRC32();
                    long count = 0;
                    try (InputStream input = zip.getInputStream(entry)) {
                        int received;
                        while ((received = input.read(buffer)) != -1) {
                            if (received == 0) throw new Invalid(Problem.CORRUPT_ENTRY, entry.getName());
                            if (received > entry.getSize() - count) throw new Invalid(Problem.CORRUPT_ENTRY, entry.getName());
                            actual.update(buffer, 0, received);
                            count += received;
                            verified += received;
                            progress(progress, verified, total);
                        }
                    }
                    if (count != entry.getSize() || actual.getValue() != entry.getCrc()) {
                        throw new Invalid(Problem.CORRUPT_ENTRY, entry.getName());
                    }
                }
                progress(progress, verified, total);
            }
        }
        if (!file.getCanonicalFile().equals(canonical) || !canonical.isFile() ||
                canonical.length() != length || canonical.lastModified() != modified) {
            throw new Invalid(Problem.CHANGED_FILE, file.getName());
        }
        return new Result(blockChecksum(crcs.toByteArray()), total, verifyPayload);
    }

    /*
     * Derived from the RSA Data Security, Inc. MD4 Message-Digest Algorithm,
     * as retained in src/idlib/hashing/MD4.cpp and specified by RFC 1320.
     * This fold is a historical PK4 compatibility value, not authentication.
     *
     * Copyright (C) 1991-2, RSA Data Security, Inc. Created 1991. All
     * rights reserved.
     *
     * License to copy and use this software is granted provided that it
     * is identified as the "RSA Data Security, Inc. MD4 Message-Digest
     * Algorithm" in all material mentioning or referencing this software
     * or this function.
     *
     * License is also granted to make and use derivative works provided
     * that such works are identified as "derived from the RSA Data
     * Security, Inc. MD4 Message-Digest Algorithm" in all material
     * mentioning or referencing the derived work.
     *
     * RSA Data Security, Inc. makes no representations concerning either
     * the merchantability of this software or the suitability of this
     * software for any particular purpose. It is provided "as is"
     * without express or implied warranty of any kind.
     *
     * These notices must be retained in any copies of any part of this
     * documentation and/or software.
     */
    static int blockChecksum(byte[] bytes) {
        if (bytes.length > 4 * MAX_ENTRIES) throw new IllegalArgumentException("CRC list exceeds PK4 limit");
        int paddedLength = (bytes.length + 9 + 63) & ~63;
        byte[] padded = new byte[paddedLength];
        System.arraycopy(bytes, 0, padded, 0, bytes.length);
        padded[bytes.length] = (byte)0x80;
        long bits = (long)bytes.length * 8;
        for (int i = 0; i < 8; ++i) padded[paddedLength - 8 + i] = (byte)(bits >>> (8 * i));
        int[] state = {0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476};
        int[][] rotations = {{3,7,11,19}, {3,5,9,13}, {3,9,11,15}};
        int[] lastOrder = {0,8,4,12,2,10,6,14,1,9,5,13,3,11,7,15};
        int[] words = new int[16];
        for (int offset = 0; offset < paddedLength; offset += 64) {
            for (int i = 0; i < 16; ++i) {
                int at = offset + i * 4;
                words[i] = (padded[at] & 255) | ((padded[at+1] & 255) << 8) |
                           ((padded[at+2] & 255) << 16) | ((padded[at+3] & 255) << 24);
            }
            int[] work = state.clone();
            for (int round = 0; round < 3; ++round) {
                for (int step = 0; step < 16; ++step) {
                    int a = (-step) & 3;
                    int b = work[(a+1)&3], c = work[(a+2)&3], d = work[(a+3)&3];
                    int term = round == 0 ? (b & c) | (~b & d) :
                               round == 1 ? (b & c) | (b & d) | (c & d) : b ^ c ^ d;
                    int index = round == 0 ? step : round == 1 ? (step % 4) * 4 + step / 4 : lastOrder[step];
                    int constant = round == 0 ? 0 : round == 1 ? 0x5a827999 : 0x6ed9eba1;
                    work[a] = Integer.rotateLeft(work[a] + term + words[index] + constant, rotations[round][step&3]);
                }
            }
            for (int i = 0; i < 4; ++i) state[i] += work[i];
        }
        return state[0] ^ state[1] ^ state[2] ^ state[3];
    }
}
