// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import android.content.ContentResolver;
import android.content.res.AssetFileDescriptor;
import android.database.Cursor;
import android.net.Uri;
import android.os.CancellationSignal;
import android.os.OperationCanceledException;
import android.provider.DocumentsContract;
import java.io.Closeable;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InterruptedIOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Read access confined to the document tree the player selected in the system picker. */
final class DocumentSource implements RetailImport.Source, Closeable {
    private static final int MAX_CHILDREN = 4096;
    private static final String[] COLUMNS = {
        DocumentsContract.Document.COLUMN_DOCUMENT_ID,
        DocumentsContract.Document.COLUMN_DISPLAY_NAME,
        DocumentsContract.Document.COLUMN_MIME_TYPE,
        DocumentsContract.Document.COLUMN_SIZE,
        DocumentsContract.Document.COLUMN_FLAGS
    };
    private final ContentResolver resolver;
    private final Uri tree;
    private final CancellationSignal cancellation = new CancellationSignal();
    private final Map<String, Uri> documents = new HashMap<>();
    private final Object gate = new Object();
    private ManagedInput active;

    DocumentSource(ContentResolver resolver, Uri tree) throws IOException {
        if (tree == null || !"content".equals(tree.getScheme()) || !DocumentsContract.isTreeUri(tree)) {
            throw unavailable("", null);
        }
        this.resolver = resolver;
        this.tree = tree;
    }

    private static RetailImport.Failure unavailable(String name, Throwable cause) {
        return new RetailImport.Failure(RetailImport.Code.SOURCE_UNAVAILABLE, name, cause);
    }

    private void checkCancelled() throws InterruptedIOException {
        if (cancellation.isCanceled() || Thread.currentThread().isInterrupted()) {
            throw new InterruptedIOException("Document source cancelled");
        }
    }

    private static final class Listing {
        final List<RetailImport.Entry> files = new ArrayList<>();
        String childBase;
    }

    private Listing list(String directory) throws IOException {
        checkCancelled();
        Listing result = new Listing();
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, directory);
        try (Cursor cursor = resolver.query(children, COLUMNS, null, null, null, cancellation)) {
            if (cursor == null) throw unavailable("", null);
            int idColumn = cursor.getColumnIndexOrThrow(COLUMNS[0]);
            int nameColumn = cursor.getColumnIndexOrThrow(COLUMNS[1]);
            int typeColumn = cursor.getColumnIndexOrThrow(COLUMNS[2]);
            int sizeColumn = cursor.getColumnIndex(COLUMNS[3]);
            int flagsColumn = cursor.getColumnIndex(COLUMNS[4]);
            int count = 0;
            while (cursor.moveToNext()) {
                checkCancelled();
                if (++count > MAX_CHILDREN) throw new RetailImport.Failure(RetailImport.Code.LIMIT, "", null);
                String id = cursor.getString(idColumn), name = cursor.getString(nameColumn), type = cursor.getString(typeColumn);
                if (id == null || id.length() > 4096 || name == null || name.length() > 1024) {
                    throw unavailable("", null);
                }
                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(type)) {
                    // Accept the installation root as a convenience only when
                    // it contains no direct PK4s and exactly one q4base folder.
                    if (name.equalsIgnoreCase("q4base")) {
                        if (result.childBase != null) throw new RetailImport.Failure(RetailImport.Code.DUPLICATE_NAME, name, null);
                        result.childBase = id;
                    }
                    continue;
                }
                if (!name.toLowerCase(Locale.ROOT).endsWith(".pk4") || RetailData.ignoredGameCode(name)) continue;
                int flags = flagsColumn < 0 || cursor.isNull(flagsColumn) ? 0 : cursor.getInt(flagsColumn);
                // Virtual documents require conversion, which cannot preserve
                // the player's exact retail archive. Ask for the real file.
                if ((flags & DocumentsContract.Document.FLAG_VIRTUAL_DOCUMENT) != 0) throw unavailable(name, null);
                long bytes = sizeColumn < 0 || cursor.isNull(sizeColumn) ? -1 : cursor.getLong(sizeColumn);
                if (documents.containsKey(id)) throw new RetailImport.Failure(RetailImport.Code.DUPLICATE_NAME, name, null);
                documents.put(id, DocumentsContract.buildDocumentUriUsingTree(tree, id));
                result.files.add(new RetailImport.Entry(id, name, bytes));
            }
        } catch (OperationCanceledException cancelled) {
            throw new InterruptedIOException("Document query cancelled");
        } catch (RuntimeException error) {
            throw unavailable("", error);
        }
        checkCancelled();
        return result;
    }

    @Override
    public List<RetailImport.Entry> entries() throws IOException {
        checkCancelled();
        documents.clear();
        try {
            Listing result = list(DocumentsContract.getTreeDocumentId(tree));
            if (result.files.isEmpty() && result.childBase != null) result = list(result.childBase);
            return result.files;
        } catch (RuntimeException error) {
            throw unavailable("", error);
        }
    }

    @Override
    public InputStream open(RetailImport.Entry entry) throws IOException {
        checkCancelled();
        Uri document = documents.get(entry.id);
        if (document == null) throw unavailable(entry.name, null);
        AssetFileDescriptor descriptor;
        try {
            descriptor = resolver.openAssetFileDescriptor(document, "r", cancellation);
        } catch (OperationCanceledException cancelled) {
            throw new InterruptedIOException("Document open cancelled");
        } catch (RuntimeException error) {
            throw unavailable(entry.name, error);
        }
        if (descriptor == null) throw unavailable(entry.name, null);
        ManagedInput input;
        try {
            // This stream honors any provider-supplied start offset/length.
            input = new ManagedInput(descriptor.createInputStream(), descriptor);
        } catch (IOException | RuntimeException error) {
            descriptor.close();
            throw unavailable(entry.name, error);
        }
        synchronized (gate) {
            if (!cancellation.isCanceled() && !Thread.currentThread().isInterrupted() && active == null) {
                active = input;
                return input;
            }
        }
        input.close();
        checkCancelled();
        throw unavailable(entry.name, null);
    }

    private final class ManagedInput extends FilterInputStream {
        private final AssetFileDescriptor descriptor;
        private boolean closed;
        ManagedInput(InputStream input, AssetFileDescriptor descriptor) {
            super(input);
            this.descriptor = descriptor;
        }
        @Override
        public int read(byte[] buffer, int offset, int count) throws IOException {
            checkCancelled();
            try {
                int result = super.read(buffer, offset, count);
                checkCancelled();
                return result;
            } catch (IOException error) {
                checkCancelled();
                throw error;
            }
        }
        @Override
        public int read() throws IOException {
            checkCancelled();
            try {
                int result = super.read();
                checkCancelled();
                return result;
            } catch (IOException error) {
                checkCancelled();
                throw error;
            }
        }
        @Override
        public void close() throws IOException {
            synchronized (gate) {
                if (closed) return;
                closed = true;
                if (active == this) active = null;
            }
            try { super.close(); }
            finally { descriptor.close(); }
        }
    }

    /** Requests provider cancellation and closes the active read descriptor. */
    @Override
    public void close() {
        cancellation.cancel();
        ManagedInput input;
        synchronized (gate) { input = active; }
        if (input != null) {
            try { input.close(); }
            catch (IOException ignored) { /* A cancelled source has no data to flush. */ }
        }
    }
}
