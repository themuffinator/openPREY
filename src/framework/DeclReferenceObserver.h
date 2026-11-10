// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once
class idDecl;

// Engine-thread scopes can remember all parse-time dependencies, including
// script sounds, tables and widget-owned materials. No game-module ABI change.
class idDeclReferenceObserver {
public:
    using Callback = void (*)(void*, const idDecl*);
    idDeclReferenceObserver(void* context, Callback callback)
        : context(context), callback(callback), previous(current) { current = this; }
    ~idDeclReferenceObserver() { current = previous; }
    idDeclReferenceObserver(const idDeclReferenceObserver&) = delete;
    idDeclReferenceObserver& operator=(const idDeclReferenceObserver&) = delete;
    static void Notify(const idDecl* decl) {
        for (auto* observer = current; observer; observer = observer->previous)
            observer->callback(observer->context, decl);
    }
private:
    void* context;
    Callback callback;
    idDeclReferenceObserver* previous;
    static inline thread_local idDeclReferenceObserver* current = nullptr;
};
