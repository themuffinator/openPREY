// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

// Optional, thread-local observation of the actual VFS sources read by one
// parser. Missing include candidates matter too: a new higher-priority file
// must invalidate a consumer's cache. Does not affect parser ownership.
class idParserSourceObserver {
public:
    using Callback = void (*)(void*, const char*, const char*, int);
    idParserSourceObserver(const void* parser, void* context, Callback callback)
        : parser(parser), context(context), callback(callback), previous(current) { current = this; }
    ~idParserSourceObserver() { current = previous; }
    idParserSourceObserver(const idParserSourceObserver&) = delete;
    idParserSourceObserver& operator=(const idParserSourceObserver&) = delete;
    static void Notify(const void* parser, const char* path, const char* data, int size) {
        for (auto* observer = current; observer; observer = observer->previous)
            if (observer->parser == parser) observer->callback(observer->context, path, data, size);
    }
private:
    const void* parser;
    void* context;
    Callback callback;
    idParserSourceObserver* previous;
    static inline thread_local idParserSourceObserver* current = nullptr;
};
