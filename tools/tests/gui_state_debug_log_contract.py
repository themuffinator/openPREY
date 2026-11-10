#!/usr/bin/env python3
"""Execute the production GUI state setters against a dictionary that releases replaced values.

idDict keeps its values in idStrPool, and idDict::Set frees the old pooled
string once no other key shares it. idUserInterfaceLocal::SetStateString used to
read the old value's pointer before the store and print it after, so with
gui_debugScript 4 a 2026-09-27 multiplayer run logged main_notice_text as
(was "<garbage bytes>") when the HUD notice changed.

This compiles the real SetStateString, SetStateBool, SetStateInt and
SetStateFloat from src/ui/UserInterface.cpp against a dictionary double whose
Set overwrites the replaced value the way freed pool memory reads back, then
checks the logged lines, the stored values, and that below gui_debugScript 4
SetStateString makes no extra lookup for logging. --mutations reintroduces reads after the
store and requires the harness to fail each time.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]

TOKEN = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', re.S)


def braced(source: str, signature: str) -> str:
    """Return source from signature through its matching brace, skipping strings and comments."""
    start = source.index(signature)
    level = 0
    for match in TOKEN.finditer(source, source.index("{", start)):
        if match.group() == "{":
            level += 1
        elif match.group() == "}":
            level -= 1
            if level == 0:
                return source[start:match.end()]
    raise AssertionError(f"unclosed production block {signature!r}")


SUPPORT = r'''
#define _CRT_SECURE_NO_WARNINGS
#include <cctype>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <vector>
#include "src/ui/GuiStateNumber.h"

static const char *va(const char *format, ...) {
    static char text[1024];
    va_list args;
    va_start(args, format);
    std::vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    return text;
}

static unsigned checks = 0;
static void Check(bool ok, const char *why) {
    ++checks;
    if (!ok) {
        std::fprintf(stderr, "FAIL %s\n", why);
        std::exit(1);
    }
}

class idStr {
public:
    idStr(const char *text = "") : data(text) {}
    const char *c_str() const { return data.c_str(); }
    static int Icmp(const char *a, const char *b) {
        for (;; ++a, ++b) {
            const int ca = std::tolower((unsigned char)*a), cb = std::tolower((unsigned char)*b);
            if (ca != cb) return ca < cb ? -1 : 1;
            if (ca == 0) return 0;
        }
    }
    std::string data;
};

// idDict::Set stores the new value before it releases the old one, and a
// released pool string is freed once no other key shares it. An identical
// value is the same pool string, so storing it again releases nothing. Here a
// released value stays allocated but is overwritten, so a late read is
// deterministic and shows up in the log instead of being undefined.
struct idKeyValue {
    std::string key;
    std::unique_ptr<char[]> value;
    struct ValueView {
        const char *text;
        const char *c_str() const { return text; }
        bool operator==(const char *other) const { return std::strcmp(text, other) == 0; }
    };
    ValueView GetValue() const { return {value.get()}; }
};

class idDict {
public:
    const idKeyValue *FindKey(const char *key) const { return Find(key); }
    const char *GetString(const char *key, const char *defaultString = "") const {
        ++lookups;
        const Entry *entry = Find(key);
        return entry != nullptr ? entry->value.get() : defaultString;
    }
    bool GetBool(const char *key, const char *defaultString = "0") const { return std::atoi(GetString(key, defaultString)) != 0; }
    int GetInt(const char *key, const char *defaultString = "0") const { return std::atoi(GetString(key, defaultString)); }
    float GetFloat(const char *key, const char *defaultString = "0") const { return float(std::atof(GetString(key, defaultString))); }

    void Set(const char *key, const char *value) {
        if (key == nullptr || key[0] == '\0') return;
        std::unique_ptr<char[]> stored(new char[std::strlen(value) + 1]);
        std::strcpy(stored.get(), value);
        Entry *entry = Find(key);
        if (entry == nullptr) {
            entries.push_back({key, std::move(stored)});
            return;
        }
        if (std::strcmp(entry->value.get(), stored.get()) == 0) return;
        std::unique_ptr<char[]> old = std::move(entry->value);
        entry->value = std::move(stored);
        std::memset(old.get(), '#', std::strlen(old.get()));
        released.push_back(std::move(old));
    }
    void SetBool(const char *key, bool value) { SetFormatted(key, "%i", value ? 1 : 0); }
    void SetInt(const char *key, int value) { SetFormatted(key, "%i", value); }
    void SetFloat(const char *key, float value) { SetFormatted(key, "%f", double(value)); }

    mutable int lookups = 0;

private:
    using Entry = idKeyValue;
    Entry *Find(const char *key) const {
        for (const Entry &entry : entries) {
            if (idStr::Icmp(entry.key.c_str(), key) == 0) return const_cast<Entry *>(&entry);
        }
        return nullptr;
    }
    template<class T> void SetFormatted(const char *key, const char *format, T value) {
        char text[64];
        std::snprintf(text, sizeof(text), format, value);
        Set(key, text);
    }
    std::vector<Entry> entries;
    std::vector<std::unique_ptr<char[]>> released;
};

class idCVar {
public:
    int GetInteger() const { return value; }
    int value = 0;
} gui_debugScript;

class idCommon {
public:
    void Printf(const char *format, ...) {
        char text[1024];
        va_list args;
        va_start(args, format);
        std::vsnprintf(text, sizeof(text), format, args);
        va_end(args);
        log += text;
    }
    std::string log;
} commonObject;
static idCommon *common = &commonObject;

class idUserInterfaceLocal {
public:
    void SetStateString(const char *varName, const char *value);
    void SetStateBool(const char *varName, const bool value);
    void SetStateInt(const char *varName, const int value);
    void SetStateFloat(const char *varName, const float value);
    idDict state;
    idStr source;
    // The Remastered HUD peer (src/ui/RetainedHud.cpp) receives each stored value.
    struct Peer {
        std::string key, value;
        void ForwardState(const char *name, const char *stored) { key = name; value = stored; }
    } peer, essentialPeer, *remastered = &peer, *essentialHud = &essentialPeer;
};
'''

MAIN = r'''
static std::string TakeLog() {
    std::string text;
    text.swap(commonObject.log);
    return text;
}

static bool Stored(const idUserInterfaceLocal &gui, const char *key, const char *value) {
    return std::strcmp(gui.state.GetString(key, "<missing>"), value) == 0;
}

int main() {
    idUserInterfaceLocal gui;
    gui.source = idStr("guis/mphud.gui");
    gui_debugScript.value = 4;

    // The 2026-09-27 capture: the one-flag notice changes while gui_debugScript 4 logs it.
    gui.state.Set("main_notice_text", "YOUR TEAM HAS THE FLAG");
    gui.SetStateString("main_notice_text", "YOUR TEAM HAS DROPPED THE FLAG");
    Check(TakeLog() == "GUI: state main_notice_text = \"YOUR TEAM HAS DROPPED THE FLAG\" (was \"YOUR TEAM HAS THE FLAG\") gui=guis/mphud.gui\n",
        "the log names the value the store replaced");
    Check(Stored(gui, "main_notice_text", "YOUR TEAM HAS DROPPED THE FLAG"), "the new notice is stored");

    gui.SetStateString("aim_text", "Player");
    Check(TakeLog() == "GUI: state aim_text = \"Player\" (was \"\") gui=guis/mphud.gui\n", "a new key logs an empty previous value");

    // The comparison is case-insensitive; the store is not.
    gui.SetStateString("aim_text", "PLAYER");
    Check(TakeLog().empty() && Stored(gui, "aim_text", "PLAYER"), "a case-only change is stored without a log line");

    // The caller's value can point into the string the store releases.
    gui.state.Set("chat_line", "[team] incoming");
    gui.SetStateString("chat_line", gui.state.GetString("chat_line") + 7);
    Check(TakeLog() == "GUI: state chat_line = \"incoming\" (was \"[team] incoming\") gui=guis/mphud.gui\n",
        "a value pointing into the replaced string is logged intact");
    Check(Stored(gui, "chat_line", "incoming"), "a value pointing into the replaced string is stored intact");
    gui.SetStateString("chat_line", gui.state.GetString("chat_line"));
    Check(TakeLog().empty() && Stored(gui, "chat_line", "incoming"), "storing the current value again is not logged");
    Check(gui.peer.key == "chat_line" && gui.peer.value == "incoming", "the HUD peer receives the stored value");
    Check(gui.essentialPeer.key == "chat_line" && gui.essentialPeer.value == "incoming", "the essential HUD receives the stored value");

    // The typed setters read their old value as a number before the store.
    gui.state.Set("player_score", "7");
    gui.SetStateInt("player_score", 12);
    Check(TakeLog() == "GUI: state player_score = 12 (was 7) gui=guis/mphud.gui\n", "SetStateInt logs the replaced integer");
    gui.state.Set("flag_taken", "1");
    gui.SetStateBool("flag_taken", false);
    Check(TakeLog() == "GUI: state flag_taken = 0 (was 1) gui=guis/mphud.gui\n", "SetStateBool logs the replaced bool");
    gui.state.Set("notice_alpha", "0.250000");
    gui.SetStateFloat("notice_alpha", 0.5f);
    Check(TakeLog() == "GUI: state notice_alpha = 0.5000 (was 0.2500) gui=guis/mphud.gui\n", "SetStateFloat logs the replaced float");
    Check(Stored(gui, "player_score", "12") && Stored(gui, "flag_taken", "0") && Stored(gui, "notice_alpha", "0.500000"),
        "the typed setters store their values");
    Check(gui.peer.key == "notice_alpha" && gui.peer.value == "0.500000", "the HUD peer receives the typed setters' stored text");
    Check(gui.essentialPeer.key == "notice_alpha" && gui.essentialPeer.value == "0.500000", "the essential HUD receives the typed setters' stored text");

    // The shared store helper finds the existing entry. Below level 4 there
    // must be no additional GetString lookup to prepare a debug log line.
    gui.remastered = nullptr;
    gui.essentialHud = nullptr;
    gui_debugScript.value = 3;
    const int lookups = gui.state.lookups;
    gui.SetStateString("main_notice_text", "YOUR TEAM HAS THE FLAG");
    Check(TakeLog().empty() && gui.state.lookups == lookups, "below level 4 the string setter neither reads nor logs the old value");
    Check(Stored(gui, "main_notice_text", "YOUR TEAM HAS THE FLAG"), "below level 4 the string setter still stores");

    std::printf("gui_state_debug_log_contract: PASS (%u checks: logged old values, stored values, no debug lookup below level 4)\n", checks);
    return 0;
}
'''

MUTATIONS = {
    # The 2026-09-27 bug: the old value's pointer is read after the store released it.
    "store-before-log": (
        '\t\tconst char *newValue = value ? value : "";\n',
        '\t\tstate.Set( varName, value );\n\t\tconst char *newValue = value ? value : "";\n',
        "the log names the value the store replaced",
    ),
    # Copying only the old value still reads the caller's pointer after the store.
    "copy-old-then-store": (
        '\t\tconst char *oldValue = state.GetString( varName, "" );\n',
        '\t\tconst std::string oldCopy = state.GetString( varName, "" );\n'
        '\t\tstate.Set( varName, value );\n'
        '\t\tconst char *oldValue = oldCopy.c_str();\n',
        "a value pointing into the replaced string is logged intact",
    ),
    # Reading the old value on every store puts a lookup on the normal path.
    "read-old-on-every-store": (
        '\tif ( gui_debugScript.GetInteger() > 3 ) {\n\t\tconst char *oldValue = state.GetString( varName, "" );\n',
        '\tconst char *oldValue = state.GetString( varName, "" );\n\tif ( gui_debugScript.GetInteger() > 3 ) {\n',
        "below level 4 the string setter neither reads nor logs the old value",
    ),
}


def build_source(root: Path) -> str:
    source = (root / "src/ui/UserInterface.cpp").read_text(encoding="utf-8").replace("\r\n", "\n")
    functions = "\n".join(braced(source, f"void idUserInterfaceLocal::{name}(") for name in (
        "SetStateString",
        "SetStateBool",
        "SetStateInt",
        "SetStateFloat",
    ))
    return SUPPORT + braced(source, "static const char *SetGuiDictionaryValue(") + functions + MAIN


def compile_and_run(compiler: str, flags: list[str], text: str, directory: Path, name: str) -> subprocess.CompletedProcess:
    source_path = directory / f"{name}.cpp"
    binary = directory / f"{name}.exe"
    source_path.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run([compiler, *flags, str(source_path), "-o", str(binary)], check=True)
    return subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--compiler")
    parser.add_argument("--mutations", action="store_true", help="also require each reintroduced late read to fail")
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    compiler = args.compiler or next((path for name in ("clang++", "g++", "c++") if (path := shutil.which(name))), None)
    if compiler is None:
        raise RuntimeError("a C++ compiler is required")
    flags = ["-std=c++17", "-Wall", "-Wextra", "-Wno-unused-parameter", "-I", str(args.root)]
    if args.sanitize:
        flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    text = build_source(args.root)
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gui-state-log-", dir=ROOT / ".tmp") as scratch:
        directory = Path(scratch)
        result = compile_and_run(compiler, flags, text, directory, "positive")
        print(result.stdout, end="")
        if result.returncode != 0:
            raise SystemExit(f"gui_state_debug_log_contract: {result.stderr.strip()}")
        if args.mutations:
            for name, (old, new, expected) in MUTATIONS.items():
                assert text.count(old) == 1, f"mutation {name} no longer matches the production source"
                mutated = compile_and_run(compiler, flags, text.replace(old, new), directory, name)
                if mutated.returncode == 0 or f"FAIL {expected}" not in mutated.stderr:
                    raise SystemExit(f"gui_state_debug_log_contract: mutation {name} was not caught "
                                     f"(exit {mutated.returncode}: {mutated.stderr.strip()})")
                print(f"gui_state_debug_log_contract: mutation {name} caught ({expected})")


if __name__ == "__main__":
    main()
