// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

using byte = unsigned char;
struct idLib {
    static int SizeToInt(size_t value, const char*) { return static_cast<int>(value); }
};
struct idStr {
    static void Copynz(char* destination, const char* source, int size) {
        if (size > 0) {
            size_t length = std::strlen(source);
            if (length >= static_cast<size_t>(size)) length = static_cast<size_t>(size - 1);
            std::memcpy(destination, source, length);
            destination[length] = '\0';
        }
    }
};
#include "CmdArgsUnderTest.inc"
#define ID_INLINE inline
#include "src/idlib/containers/List.h"

#define CHECK(condition) do { if (!(condition)) { std::fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition); std::exit(1); } } while (0)

static void CheckOwned(const idCmdArgs& args) {
    const auto begin = reinterpret_cast<std::uintptr_t>(&args);
    for (int i = 0; i < args.Argc(); ++i) {
        const auto pointer = reinterpret_cast<std::uintptr_t>(args.Argv(i));
        // Test ownership before dereferencing: the broken copy can be dangling.
        CHECK(pointer >= begin && pointer < begin + sizeof(args));
        CHECK(std::memchr(args.Argv(i), '\0', begin + sizeof(args) - pointer) != nullptr);
    }
}

static void CopyAndReload() {
    idCmdArgs pending;
    pending.AppendArg("connect");
    pending.AppendArg("[::1]:28140");
    const idCmdArgs replay(pending);
    CheckOwned(replay);
    pending.ClearSensitive();
    CHECK(replay.Argc() == 2);
    CHECK(std::strcmp(replay.Argv(0), "connect") == 0);
    CHECK(std::strcmp(replay.Argv(1), "[::1]:28140") == 0);
    pending = replay;
    CheckOwned(pending);
    pending = pending;
    CheckOwned(pending);
    CHECK(std::strcmp(pending.Argv(1), "[::1]:28140") == 0);
    pending.AppendArg("independent");
    CHECK(pending.Argc() == 3 && replay.Argc() == 2);
    const idCmdArgs empty;
    const idCmdArgs emptyCopy(empty);
    CHECK(emptyCopy.Argc() == 0);
}

static void StartupQueue() {
    idList<idCmdArgs> queue;
    // The real startup list grows at 16, 32 and 48; the failing connect was #48.
    for (int i = 0; i < 100; ++i) {
        idCmdArgs command;
        command.AppendArg(i % 16 == 0 ? "connect" : "echo");
        command.AppendArg(std::to_string(i).c_str());
        queue.Append(command);
        command.ClearSensitive();
        CheckOwned(queue[i]);
    }
    for (int i = 0; i < 100; ++i) {
        idCmdArgs dispatch;
        dispatch = queue[0];
        queue.RemoveIndex(0);
        CheckOwned(dispatch);
        CHECK(dispatch.Argc() == 2);
        CHECK(std::strcmp(dispatch.Argv(0), i % 16 == 0 ? "connect" : "echo") == 0);
        CHECK(std::string(dispatch.Argv(1)) == std::to_string(i));
    }
    CHECK(queue.Num() == 0);

    idCmdArgs command;
    command.AppendArg("connect");
    command.AppendArg("127.0.0.1:28140");
    idList<idCmdArgs> aliases(1);
    aliases.Append(command);
    aliases.Append(aliases[0]);
    aliases.Insert(aliases[1], 0);
    for (int i = 0; i < aliases.Num(); ++i) {
        CheckOwned(aliases[i]);
        CHECK(std::strcmp(aliases[i].Argv(1), "127.0.0.1:28140") == 0);
    }
}

int main() {
    StartupQueue();
    CopyAndReload();
    std::puts("command arguments: queue growth, aliased insertion, copy and reload ownership passed");
}
