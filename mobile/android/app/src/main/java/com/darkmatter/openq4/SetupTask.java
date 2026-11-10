// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import java.io.InterruptedIOException;
import java.lang.ref.WeakReference;

/** One retained setup operation, with UI-thread delivery and explicit cancellation ownership. */
final class SetupTask<T> {
    enum Status { IDLE, RUNNING, STOPPING, SUCCEEDED, FAILED, CANCELLED }
    enum Phase { CHECKING_DATA, CHECKING_EXISTING, COPYING_DATA, VERIFYING_DATA, CHECKING_PACKAGE, COPYING_PACKAGE, PACKING_EXPORT, EXPORTING }

    static final class Progress {
        final Phase phase;
        final String name;
        final int completed, files;
        final long bytes, totalBytes;
        Progress(Phase phase, String name, int completed, int files, long bytes, long totalBytes) {
            if (phase == null || name == null || completed < 0 || files < completed || bytes < 0 || totalBytes < -1 ||
                    (totalBytes >= 0 && bytes > totalBytes)) throw new IllegalArgumentException("Invalid setup progress");
            this.phase = phase;
            this.name = name;
            this.completed = completed;
            this.files = files;
            this.bytes = bytes;
            this.totalBytes = totalBytes;
        }
    }

    interface Reporter {
        boolean update(Phase phase, String name, int completed, int files, long bytes, long totalBytes);
        boolean cancelled();
    }
    interface Work<T> {
        T run(Reporter reporter) throws Exception;
        /** Best-effort provider cancellation; called off the UI thread. */
        default void cancel() throws Exception {}
    }
    interface Dispatcher { void post(Runnable callback); }
    interface Observer<T> { void changed(State<T> state); }

    static final class State<T> {
        final Status status;
        final Progress progress;
        final T result;
        final Exception failure;
        State(Status status, Progress progress, T result, Exception failure) {
            this.status = status;
            this.progress = progress;
            this.result = result;
            this.failure = failure;
        }
        boolean busy() { return status == Status.RUNNING || status == Status.STOPPING; }
    }

    private final Thread uiThread = Thread.currentThread();
    private final Dispatcher dispatcher;
    private WeakReference<Observer<T>> observer = new WeakReference<>(null);
    private State<T> state = new State<>(Status.IDLE, null, null, null);
    private Job current;

    SetupTask(Dispatcher dispatcher) { this.dispatcher = dispatcher; }

    private void requireUiThread() {
        if (Thread.currentThread() != uiThread) throw new IllegalStateException("Setup state belongs to the UI thread");
    }

    State<T> state() { requireUiThread(); return state; }

    void bind(Observer<T> next) {
        requireUiThread();
        observer = new WeakReference<>(next);
        publish();
    }

    void unbind(Observer<T> previous) {
        requireUiThread();
        if (observer.get() == previous) observer.clear();
    }

    private void publish() {
        requireUiThread();
        Observer<T> target = observer.get();
        if (target != null) target.changed(state);
    }

    boolean start(Work<T> work) {
        requireUiThread();
        if (work == null) throw new IllegalArgumentException("Setup work is required");
        if (state.busy()) return false;
        Job job = new Job(work);
        current = job;
        state = new State<>(Status.RUNNING, null, null, null);
        job.thread = new Thread(job::run, "openQ4-setup");
        job.thread.setDaemon(true);
        // Establish the complete owner before notifying a UI observer, which
        // may immediately request cancellation while updating its controls.
        job.thread.start();
        publish();
        return true;
    }

    void cancel() {
        requireUiThread();
        if (current == null || state.status != Status.RUNNING) return;
        Job job = current;
        job.cancelled = true;
        state = new State<>(Status.STOPPING, state.progress, null, null);
        job.thread.interrupt();
        // A provider may take time to acknowledge a close/cancel request. Do
        // not block Android's main thread, or admit another writer meanwhile.
        Thread closer = new Thread(() -> {
            try { job.work.cancel(); }
            catch (Exception ignored) { /* The worker still owns its final result and cleanup. */ }
        }, "openQ4-setup-cancel");
        closer.setDaemon(true);
        closer.start();
        publish();
    }

    private final class Job implements Reporter {
        final Work<T> work;
        Thread thread;
        volatile boolean cancelled;
        private Progress latest;
        private boolean progressPosted;
        private long lastPost;

        Job(Work<T> work) { this.work = work; }

        @Override
        public boolean cancelled() { return cancelled || Thread.currentThread().isInterrupted(); }

        @Override
        public boolean update(Phase phase, String name, int completed, int files, long bytes, long totalBytes) {
            if (cancelled()) return false;
            long now = System.nanoTime();
            boolean post = false;
            synchronized (this) {
                boolean boundary = latest == null || latest.phase != phase || !latest.name.equals(name) ||
                                   latest.completed != completed || bytes == totalBytes;
                latest = new Progress(phase, name, completed, files, bytes, totalBytes);
                if (!progressPosted && (boundary || now - lastPost >= 100_000_000L)) {
                    progressPosted = true;
                    lastPost = now;
                    post = true;
                }
            }
            if (post) dispatcher.post(this::deliverProgress);
            return !cancelled();
        }

        private void deliverProgress() {
            requireUiThread();
            Progress progress;
            synchronized (this) { progress = latest; progressPosted = false; }
            if (current != this || state.status != Status.RUNNING) return;
            state = new State<>(Status.RUNNING, progress, null, null);
            publish();
        }

        void run() {
            T result = null;
            Exception failure = null;
            try {
                if (cancelled()) throw new InterruptedIOException("Setup cancelled");
                result = work.run(this);
            } catch (InterruptedIOException | InterruptedException stopped) {
                cancelled = true;
                Thread.currentThread().interrupt();
            } catch (Exception error) {
                failure = error;
            }
            if (Thread.currentThread().isInterrupted()) cancelled = true;
            T finished = result;
            Exception error = failure;
            dispatcher.post(() -> {
                requireUiThread();
                if (current != this) return;
                Progress progress;
                synchronized (this) { progress = latest; }
                if (cancelled) state = new State<>(Status.CANCELLED, progress, null, null);
                else if (error != null) state = new State<>(Status.FAILED, progress, null, error);
                else state = new State<>(Status.SUCCEEDED, progress, finished, null);
                publish();
            });
        }
    }
}
