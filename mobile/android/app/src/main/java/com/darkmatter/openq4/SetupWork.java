// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import android.content.Context;
import android.net.Uri;
import java.io.File;
import java.io.IOException;
import java.io.InterruptedIOException;
import java.util.List;
import java.util.ArrayList;

/** An operation owns application resources, never an Activity or its views. */
final class SetupWork implements SetupTask.Work<RetailData.Report> {
    private final Context context;
    private final Uri source;
    private final List<RetailData.Expected> expected;
    private volatile DocumentSource documents;

    SetupWork(Context context, Uri source) {
        this(context, source, RetailData.OFFICIAL);
    }

    // The fixture catalogue exercises the complete pipeline with independent
    // test archives; production always selects the engine's official set.
    SetupWork(Context context, Uri source, List<RetailData.Expected> expected) {
        this.context = context.getApplicationContext();
        this.source = source;
        this.expected = new ArrayList<>(expected);
    }

    @Override
    public RetailData.Report run(SetupTask.Reporter progress) throws Exception {
        Object owner = StorageSession.INSTANCE.beginSetup();
        try {
            SetupDiagnostics.record(context.getFilesDir(), source == null ? "Check installed game data" : "Import selected game data", null);
            File external = context.getExternalFilesDir(null);
            if (external == null) throw new RetailImport.Failure(RetailImport.Code.DESTINATION_UNAVAILABLE, "", null);
            RetailData.Report report;
            if (source != null) {
                try (DocumentSource input = new DocumentSource(context.getContentResolver(), source)) {
                    documents = input;
                    if (progress.cancelled()) throw new InterruptedIOException("Setup cancelled");
                    report = RetailImport.run(input, external, expected, new RetailImport.Storage(), (phase, name, completed, files, bytes, total) ->
                        progress.update(importPhase(phase), name, completed, files, bytes, total)).report;
                } finally { documents = null; }
            } else {
                report = RetailData.scan(new File(external, "q4base"), expected, (phase, name, completed, files, bytes, total) ->
                    progress.update(phase == RetailData.Phase.INSPECTING ? SetupTask.Phase.CHECKING_DATA :
                                    SetupTask.Phase.VERIFYING_DATA, name, completed, files, bytes, total));
            }
            if (report.ready()) {
                PackageStorage.extract(context.getAssets(), context.getFilesDir(), (phase, name, bytes, total) ->
                    progress.update(phase == PackageStorage.Phase.COPYING ? SetupTask.Phase.COPYING_PACKAGE :
                                    SetupTask.Phase.CHECKING_PACKAGE, name, 0, 0, bytes, total));
            }
            if (progress.cancelled()) throw new InterruptedIOException("Setup cancelled");
            SetupDiagnostics.record(context.getFilesDir(), "Data check complete: ready=" + report.ready() + ", findings=" + report.issues.size(), null);
            for (RetailData.Issue issue : report.issues)
                SetupDiagnostics.record(context.getFilesDir(), "Data finding: " + issue.code + " " + issue.name, null);
            return report;
        } catch (InterruptedIOException cancelled) {
            SetupDiagnostics.record(context.getFilesDir(), "Setup cancelled", null);
            throw cancelled;
        } catch (Exception error) {
            SetupDiagnostics.record(context.getFilesDir(), "Setup operation failed", error);
            android.util.Log.e("openQ4", "Setup operation failed", error);
            throw error;
        } finally { StorageSession.INSTANCE.endSetup(owner); }
    }

    private static SetupTask.Phase importPhase(RetailImport.Phase phase) {
        switch (phase) {
            case CHECKING_EXISTING: return SetupTask.Phase.CHECKING_EXISTING;
            case COPYING: return SetupTask.Phase.COPYING_DATA;
            case VERIFYING: return SetupTask.Phase.VERIFYING_DATA;
            default: return SetupTask.Phase.CHECKING_DATA;
        }
    }

    @Override
    public void cancel() throws IOException {
        DocumentSource current = documents;
        if (current != null) current.close();
    }
}
