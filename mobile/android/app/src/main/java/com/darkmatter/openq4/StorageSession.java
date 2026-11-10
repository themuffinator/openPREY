// SPDX-License-Identifier: GPL-3.0-or-later
package com.darkmatter.openq4;

import java.io.IOException;

/** Process-local ownership of files shared by setup and the native game. */
final class StorageSession {
    static final StorageSession INSTANCE = new StorageSession();
    static final class Busy extends IOException {}
    private Object setup;
    private Object activity;
    private Object engine;

    synchronized boolean gameActive() { return activity != null || engine != null; }
    synchronized boolean activityActive() { return activity != null; }

    synchronized Object beginSetup() throws Busy {
        if (setup != null || gameActive()) throw new Busy();
        setup = new Object();
        return setup;
    }

    synchronized void endSetup(Object owner) {
        if (owner == null || setup != owner) throw new IllegalStateException("Unknown setup owner");
        setup = null;
        notifyAll();
    }

    synchronized void activityCreated(Object owner) {
        if (owner == null || (activity != null && activity != owner))
            throw new IllegalStateException("Duplicate game Activity");
        activity = owner;
    }

    synchronized void activityDestroyed(Object owner) {
        if (activity == owner) activity = null;
        // SDL has a bounded join in onDestroy. A still-running engine keeps
        // its separate lease until main() actually returns.
        notifyAll();
    }

    synchronized boolean beginEngine(Object owner) throws InterruptedException {
        // Android can recreate the game directly from Recents while a setup
        // operation is finishing. Only SDLThread waits; never Android's UI.
        while (activity == owner && setup != null) wait();
        if (activity != owner) return false;
        if (engine != null) throw new IllegalStateException("Duplicate native engine");
        engine = owner;
        return true;
    }

    synchronized void endEngine(Object owner) {
        if (engine != owner) throw new IllegalStateException("Unknown engine owner");
        engine = null;
        notifyAll();
    }
}
