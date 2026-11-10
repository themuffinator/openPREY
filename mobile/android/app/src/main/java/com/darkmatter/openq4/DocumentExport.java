// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import android.content.ContentResolver;
import android.content.Context;
import android.net.Uri;
import android.os.CancellationSignal;
import android.os.OperationCanceledException;
import android.os.ParcelFileDescriptor;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.io.OutputStream;

/** Writes one completed private snapshot to the document created by the picker. */
final class DocumentExport implements SetupTask.Work<DocumentExport.Result> {
    static final class Result {
        final PrivateExport.Kind kind;
        final int files;
        final long bytes;
        Result(PrivateExport.Snapshot snapshot) { kind = snapshot.kind; files = snapshot.count; bytes = snapshot.bytes; }
    }

    private final Context context;
    private final Uri destination;
    private final PrivateExport.Kind kind;
    private final CancellationSignal cancellation = new CancellationSignal();
    private final Object gate = new Object();
    private volatile boolean stopped;
    private ManagedOutput active;

    DocumentExport(Context context, Uri destination, PrivateExport.Kind kind) {
        this.context = context.getApplicationContext();
        this.destination = destination;
        this.kind = kind;
    }

    private void checkCancelled(SetupTask.Reporter reporter) throws InterruptedIOException {
        if (stopped || cancellation.isCanceled() || reporter.cancelled() || Thread.currentThread().isInterrupted())
            throw new InterruptedIOException("Document export cancelled");
    }

    private ManagedOutput open(ContentResolver resolver, SetupTask.Reporter reporter) throws IOException {
        checkCancelled(reporter);
        ParcelFileDescriptor descriptor;
        try {
            // ACTION_CREATE_DOCUMENT supplied a new document; never open a
            // selected existing file or request a read/persisted grant here.
            descriptor = resolver.openFileDescriptor(destination, "wt", cancellation);
        } catch (OperationCanceledException stopped) {
            throw new InterruptedIOException("Document open cancelled");
        } catch (IOException | RuntimeException error) {
            checkCancelled(reporter);
            throw new PrivateExport.Failure(PrivateExport.Code.OUTPUT_UNAVAILABLE, "", error);
        }
        if (descriptor == null) throw new PrivateExport.Failure(PrivateExport.Code.OUTPUT_UNAVAILABLE, "", null);
        ManagedOutput output;
        try { output = new ManagedOutput(new ParcelFileDescriptor.AutoCloseOutputStream(descriptor)); }
        catch (RuntimeException error) {
            try { descriptor.close(); } catch (IOException close) { error.addSuppressed(close); }
            throw new PrivateExport.Failure(PrivateExport.Code.OUTPUT_UNAVAILABLE, "", error);
        }
        synchronized (gate) {
            if (!stopped && !cancellation.isCanceled() && !reporter.cancelled() && !Thread.currentThread().isInterrupted() && active == null) {
                active = output;
                return output;
            }
        }
        try { output.close(); } finally { checkCancelled(reporter); }
        throw new PrivateExport.Failure(PrivateExport.Code.OUTPUT_UNAVAILABLE, "", null);
    }

    private final class ManagedOutput extends OutputStream {
        private final OutputStream output;
        private boolean closed;
        ManagedOutput(OutputStream output) { this.output = output; }
        @Override public void write(int value) throws IOException { output.write(value); }
        @Override public void write(byte[] bytes, int offset, int count) throws IOException { output.write(bytes, offset, count); }
        @Override public void flush() throws IOException { output.flush(); }
        @Override public synchronized void close() throws IOException {
            if (closed) return;
            try { output.close(); }
            finally {
                closed = true;
                synchronized (gate) { if (active == this) active = null; }
            }
        }
    }

    @Override public Result run(SetupTask.Reporter reporter) throws Exception {
        checkCancelled(reporter);
        if (destination == null || !"content".equals(destination.getScheme()))
            throw new PrivateExport.Failure(PrivateExport.Code.OUTPUT_UNAVAILABLE, "", null);
        try (PrivateExport.Snapshot snapshot = PrivateExport.create(context.getFilesDir(), context.getCacheDir(), kind,
                (name, completed, files, bytes, total) -> !stopped && !cancellation.isCanceled() && !reporter.cancelled() &&
                    reporter.update(SetupTask.Phase.PACKING_EXPORT, name, completed, files, bytes, total))) {
            checkCancelled(reporter);
            try (ManagedOutput output = open(context.getContentResolver(), reporter);
                 FileInputStream input = new FileInputStream(snapshot.file)) {
                byte[] buffer = new byte[65536];
                long bytes = 0;
                for (;;) {
                    if (!reporter.update(SetupTask.Phase.EXPORTING, "", 0, 0, bytes, snapshot.bytes))
                        throw new InterruptedIOException("Document export cancelled");
                    checkCancelled(reporter);
                    int count = input.read(buffer);
                    if (count < 0) break;
                    if (count > snapshot.bytes - bytes) throw new PrivateExport.Failure(PrivateExport.Code.CHANGED_FILE, "", null);
                    output.write(buffer, 0, count);
                    bytes += count;
                }
                if (bytes != snapshot.bytes) throw new PrivateExport.Failure(PrivateExport.Code.CHANGED_FILE, "", null);
                output.flush();
                checkCancelled(reporter);
            } catch (PrivateExport.Failure | InterruptedIOException error) { throw error; }
            catch (IOException | RuntimeException error) {
                checkCancelled(reporter);
                throw new PrivateExport.Failure(PrivateExport.Code.WRITE_FAILED, "", error);
            }
            // Some providers return a pipe. A successful close means the
            // provider accepted the stream, not that a cloud upload finished.
            checkCancelled(reporter);
            return new Result(snapshot);
        }
    }

    @Override public void cancel() {
        ManagedOutput output;
        synchronized (gate) { stopped = true; output = active; }
        try { cancellation.cancel(); }
        finally {
            if (output != null) {
                try { output.close(); }
                catch (IOException ignored) { /* The cancelled destination may contain a partial archive. */ }
            }
        }
    }
}
