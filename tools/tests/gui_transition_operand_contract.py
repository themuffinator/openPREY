#!/usr/bin/env python3
"""Execute the production GUI transition operand rule against counted window doubles.

Retail Quake 4 (1.4.2 Quake4.exe, idGuiScript::FixupParms and Script_Transition)
keeps a parse-time copy of a "$var" transition operand only when it names a
rect. Every other var is bound as-is and read when the transition starts. Stock
guis/mphud.gui depends on this: the aim-name fade starts from the name's current
colour and ends on the team tint set after the gui loaded, and the one-flag CTF
pulse flashes toward the carrier's team colour.

This compiles the real FixupParms, Script_Transition and operand reader from
src/ui/GuiScript.cpp, plus the idGSWinVar/idGuiScript declarations from
GuiScript.h, against small window and variable doubles, then checks which
operands are live and which are parse-time snapshots. --mutations reverts the
rule in the extracted source and requires the harness to fail each time.
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


def braced(source: str, signature: str, trailer: str = "") -> str:
    """Return source from signature through its matching brace, skipping strings and comments."""
    start = source.index(signature)
    level = 0
    for match in TOKEN.finditer(source, source.index("{", start)):
        if match.group() == "{":
            level += 1
        elif match.group() == "}":
            level -= 1
            if level == 0:
                end = match.end()
                if trailer:
                    assert source.startswith(trailer, end), f"{signature!r} is not followed by {trailer!r}"
                    end += len(trailer)
                return source[start:end]
    raise AssertionError(f"unclosed production block {signature!r}")


SUPPORT = r'''
#define _CRT_SECURE_NO_WARNINGS
#include <cassert>
#include <cctype>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <map>
#include <memory>
#include <string>
#include <vector>

static unsigned checks = 0;
static void Check(bool ok, const char *why) {
    ++checks;
    if (!ok) {
        std::fprintf(stderr, "FAIL %s\n", why);
        std::exit(1);
    }
}

static std::string Lower(const char *text) {
    std::string out(text);
    for (char &c : out) c = char(std::tolower((unsigned char)c));
    return out;
}

class idStr {
public:
    static int Icmp(const char *a, const char *b) { return std::strcmp(Lower(a).c_str(), Lower(b).c_str()); }
    static int Icmpn(const char *a, const char *b, int n) { return std::strncmp(Lower(a).c_str(), Lower(b).c_str(), size_t(n)); }
    static int Cmpn(const char *a, const char *b, int n) { return std::strncmp(a, b, size_t(n)); }
};
#define STRTABLE_ID "#str_"
#define STRTABLE_ID_LENGTH 5

class idVec4 {
public:
    float x = 0.0f, y = 0.0f, z = 0.0f, w = 0.0f;
    idVec4() = default;
    idVec4(float a, float b, float c, float d) : x(a), y(b), z(c), w(d) {}
    float operator[](int i) const { return (&x)[i]; }
    float &operator[](int i) { return (&x)[i]; }
    bool operator==(const idVec4 &o) const { return x == o.x && y == o.y && z == o.z && w == o.w; }
    // idStr::FloatArrayToString( ..., 2 ): the text a var's c_str() produces.
    const char *ToString(int precision = 2) const {
        static char buffers[4][128];
        static int index = 0;
        char *s = buffers[index];
        index = (index + 1) & 3;
        int n = 0;
        for (int i = 0; i < 4; ++i) {
            n += std::snprintf(s + n, sizeof(buffers[0]) - size_t(n), i ? " %.*f" : "%.*f", precision, double((*this)[i]));
            while (n > 0 && s[n - 1] == '0') s[--n] = '\0';
            while (n > 0 && s[n - 1] == '.') s[--n] = '\0';
        }
        return s;
    }
};

static const idVec4 vec4_zero(0.0f, 0.0f, 0.0f, 0.0f);

class idRectangle {
public:
    float x = 0.0f, y = 0.0f, w = 0.0f, h = 0.0f;
    idVec4 ToVec4() const { return idVec4(x, y, w, h); }
};

class idWindow;
class idWinVar {
public:
    virtual ~idWinVar() = default;
    virtual void Init(const char *n, idWindow *) { name = n; }
    virtual void Set(const char *value) = 0;
    virtual const char *c_str() const = 0;
    size_t Size() const { return sizeof(*this); }
    void SetEval(bool b) { eval = b; }
    bool GetEval() const { return eval; }
    const char *GetName() const { return name.c_str(); }
    std::string name;
    bool eval = true;
};

class idWinStr : public idWinVar {
public:
    idWinStr() = default;
    explicit idWinStr(const char *text) : data(text) {}
    operator const char *() const { return data.c_str(); }
    int Length() const { return int(data.size()); }
    void Set(const char *value) override { data = value; }
    const char *c_str() const override { return data.c_str(); }
    std::string data;
};
class idWinBackground : public idWinStr {};

class idWinVec4 : public idWinVar {
public:
    operator const idVec4 &() const { return data; }
    idVec4 &operator=(const idVec4 &other) { data = other; return data; }
    void Set(const char *value) override {
        if (std::strchr(value, ',')) std::sscanf(value, "%f,%f,%f,%f", &data.x, &data.y, &data.z, &data.w);
        else std::sscanf(value, "%f %f %f %f", &data.x, &data.y, &data.z, &data.w);
    }
    const char *c_str() const override { return data.ToString(); }
    idVec4 data;
};

class idWinRectangle : public idWinVar {
public:
    operator const idRectangle &() const { return data; }
    void Set(const char *value) override {
        if (std::strchr(value, ',')) std::sscanf(value, "%f,%f,%f,%f", &data.x, &data.y, &data.w, &data.h);
        else std::sscanf(value, "%f %f %f %f", &data.x, &data.y, &data.w, &data.h);
    }
    const char *c_str() const override { return data.ToVec4().ToString(); }
    idRectangle data;
};

class idWinFloat : public idWinVar {
public:
    void Set(const char *value) override { data = float(std::atof(value)); }
    const char *c_str() const override {
        static char text[64];
        std::snprintf(text, sizeof(text), "%f", double(data));
        return text;
    }
    float data = 0.0f;
};

class idWinFloatPtr : public idWinVar {
public:
    void Bind(idWinVec4 &vec, int component) { owner = &vec; data = &vec.data[component]; }
    idWinVec4 *GetOwnerVec4() const { return owner; }
    void Set(const char *value) override { *data = float(std::atof(value)); }
    const char *c_str() const override {
        static char text[64];
        std::snprintf(text, sizeof(text), "%f", double(*data));
        return text;
    }
    float *data = nullptr;
    idWinVec4 *owner = nullptr;
};

template<class T> class idList {
public:
    int Num() const { return int(values.size()); }
    T &operator[](int i) { return values.at(size_t(i)); }
    const T &operator[](int i) const { return values.at(size_t(i)); }
    int Append(const T &value) { values.push_back(value); return Num() - 1; }
    void SetGranularity(int) {}
    std::vector<T> values;
};

class idSimpleWindow;
struct drawWin_t {
    idWindow *win = nullptr;
    idSimpleWindow *simp = nullptr;
};

class idUserInterfaceLocal;
class idWindow {
public:
    struct Added { idWinVar *dest; idVec4 from, to; int time; float accel, decel; };
    idWindow(const char *n, idWindow *p, idUserInterfaceLocal *g, float ox = 0.0f, float oy = 0.0f);
    const char *GetName() const { return name.c_str(); }
    idWindow *GetParent() const { return parent; }
    idUserInterfaceLocal *GetGui() const { return gui; }
    idWinVar *GetWinVarByName(const char *n, bool fixup = false, drawWin_t **owner = nullptr);
    void AddDefinedVar(idWinVar *) {}
    // Client space here is the window's own offset from the screen origin.
    void ClientToScreen(idRectangle *r) const { r->x += originX; r->y += originY; }
    void ScreenToClient(idRectangle *r) const { r->x -= originX; r->y -= originY; }
    void AddTransition(idWinVar *dest, idVec4 from, idVec4 to, int time, float accel, float decel) {
        added.push_back({dest, from, to, time, accel, decel});
    }
    void StartTransition() { ++started; }
    std::string name;
    idWindow *parent;
    idUserInterfaceLocal *gui;
    float originX, originY;
    std::map<std::string, idWinVar *> vars;
    drawWin_t self;
    std::vector<Added> added;
    int started = 0;
};

class idSimpleWindow {
public:
    idSimpleWindow(const char *n, idWindow *p) : name(n), parent(p) { self.simp = this; }
    idWindow *GetParent() const { return parent; }
    idWinVar *GetWinVarByName(const char *n) {
        auto found = vars.find(Lower(n));
        return found == vars.end() ? nullptr : found->second;
    }
    std::string name;
    idWindow *parent;
    std::map<std::string, idWinVar *> vars;
    drawWin_t self;
};

class idUserInterfaceLocal {
public:
    idWindow *GetDesktop() const { return windows.front(); }
    const char *GetSourceFile() const { return "guis/transition_contract.gui"; }
    std::vector<idWindow *> windows;
    std::vector<idSimpleWindow *> simples;
};

idWindow::idWindow(const char *n, idWindow *p, idUserInterfaceLocal *g, float ox, float oy)
    : name(n), parent(p), gui(g), originX(ox), originY(oy) {
    self.win = this;
    g->windows.push_back(this);
}

// The parts of idWindow::GetWinVarByName the transition fixup depends on: a
// qualified name resolves in the named window without further fixup, and the
// owner is the variable's window unless that window is the desktop.
idWinVar *idWindow::GetWinVarByName(const char *n, bool fixup, drawWin_t **owner) {
    if (owner) *owner = nullptr;
    const std::string key = Lower(n);
    auto found = vars.find(key);
    if (found != vars.end()) {
        if (owner && parent) *owner = &self;
        return found->second;
    }
    const size_t separator = key.find("::");
    if (!fixup || separator == std::string::npos) return nullptr;
    const std::string window = key.substr(0, separator), var = key.substr(separator + 2);
    for (idWindow *w : gui->windows) {
        if (Lower(w->name.c_str()) == window) return w->GetWinVarByName(var.c_str(), false, owner);
    }
    for (idSimpleWindow *s : gui->simples) {
        if (Lower(s->name.c_str()) == window) {
            if (owner) *owner = &s->self;
            return s->GetWinVarByName(var.c_str());
        }
    }
    return nullptr;
}

class idCVar {
public:
    int GetInteger() const { return value; }
    int value = 0;
} gui_debugScript;

class idLangDict {
public:
    const char *GetString(const char *key) const { return key; }
};

class idCommon {
public:
    void Warning(const char *format, ...) {
        char text[1024];
        va_list args;
        va_start(args, format);
        std::vsnprintf(text, sizeof(text), format, args);
        va_end(args);
        ++warnings;
        lastWarning = text;
    }
    void Printf(const char *format, ...) {
        va_list args;
        va_start(args, format);
        std::vprintf(format, args);
        va_end(args);
    }
    const idLangDict *GetLanguageDict() const { static idLangDict dict; return &dict; }
    int warnings = 0;
    std::string lastWarning;
} commonObject;
static idCommon *common = &commonObject;

enum { SS_GUI = 1 };
class idMaterial {
public:
    void SetSort(int) const {}
};
class idDeclManager {
public:
    const idMaterial *FindMaterial(const char *) { static idMaterial material; return &material; }
    void FindSound(const char *) {}
} declObject;
static idDeclManager *declManager = &declObject;

enum { LEXFL_NOSTRINGCONCAT = 1, LEXFL_ALLOWMULTICHARLITERALS = 2, LEXFL_ALLOWBACKSLASHSTRINGCONCAT = 4 };
class idToken {
public:
    int Icmp(const char *other) const { return idStr::Icmp(text.c_str(), other); }
    bool operator!=(const char *other) const { return text != other; }
    const char *c_str() const { return text.c_str(); }
    std::string text;
};
class idParser {
public:
    explicit idParser(int) {}
    void LoadMemory(const char *, int, const char *) {}
    bool ReadToken(idToken *) { return false; }
};
class idFile;
'''

AFTER_DECLARATIONS = r'''
class idGuiScriptList {
public:
    void FixupParms(idWindow *) {}
};
void Script_Set(idWindow *, idList<idGSWinVar> *) {}
void Script_SetLightColor(idWindow *, idList<idGSWinVar> *) {}
'''

MAIN = r'''
class Script : public idGuiScript {
public:
    using idGuiScript::parms;
    using idGuiScript::handler;
    Script(std::initializer_list<const char *> tokens) {
        for (const char *token : tokens) {
            idGSWinVar parm;
            parm.var = new idWinStr(token);
            parm.own = true;
            parms.Append(parm);
        }
        handler = Script_Transition;
    }
};

static bool Near(const idVec4 &a, const idVec4 &b) {
    for (int i = 0; i < 4; ++i) if (std::fabs(a[i] - b[i]) > 1e-6f) return false;
    return true;
}

// The saved script layout must not change: both operands stay owned vec4 copies.
static void CheckSavedLayout(Script &script, const char *why) {
    for (int c = 1; c < 3; ++c) {
        Check(script.parms[c].own && dynamic_cast<idWinVec4 *>(script.parms[c].var) != nullptr, why);
    }
}

static const idWindow::Added &Run(Script &script, idWindow &window, const char *why) {
    const size_t before = window.added.size();
    script.Execute(&window);
    Check(window.added.size() == before + 1, why);
    return window.added.back();
}

// The window variables outlive every script that points at them.
static std::vector<std::unique_ptr<idWinVar>> windowVars;
template<class T> static T *Var(const char *value) {
    windowVars.push_back(std::make_unique<T>());
    windowVars.back()->Set(value);
    return static_cast<T *>(windowVars.back().get());
}
static idWinVec4 *Vec4(const char *value) { return Var<idWinVec4>(value); }
static idWinRectangle *Rect(const char *value) { return Var<idWinRectangle>(value); }

int main() {
    idUserInterfaceLocal gui;
    idWindow desktop("Desktop", nullptr, &gui);
    desktop.vars["rect"] = Rect("0,0,640,480");
    desktop.vars["aim_text_color"] = Vec4("1,1,1,1");
    desktop.vars["aim_fade_color"] = Vec4("1,1,1,0");
    desktop.vars["neutral"] = Vec4("1,1,.552,0.8");
    desktop.vars["ctfoneflag_color"] = Vec4("1,1,1,1");
    desktop.vars["flag_rect"] = Vec4("10,20,30,40");
    idWinFloat fadeAlpha;
    fadeAlpha.Set("0.25");
    desktop.vars["fade_alpha"] = &fadeAlpha;

    idWindow aimText("aimText", &desktop, &gui);
    idWinVec4 *aimColor = Vec4("1,1,1,0");
    idWinFloatPtr aimAlpha;
    aimAlpha.Bind(*aimColor, 3);
    aimText.vars["forecolor"] = aimColor;
    aimText.vars["forecolor_w"] = &aimAlpha;
    aimText.vars["rect"] = Rect("207,260,215,38");

    idWindow onectf("p_onectf", &desktop, &gui, 100.0f, 50.0f);
    idWindow flag("ctfone_flag", &onectf, &gui);
    flag.vars["rect"] = Rect("97,33,28,28");
    flag.vars["matcolor"] = Vec4("1,1,.552,0.8");
    idWindow pulses("p_pulses", &desktop, &gui);
    idWindow driver("d_ctfone_flag", &pulses, &gui);
    idSimpleWindow pulseRect("pulse_rect", &pulses);
    pulseRect.vars["rect"] = Rect("94,30,34,34");
    gui.simples.push_back(&pulseRect);

    // mphud.gui aimText onTime 0: the name fades from its current colour toward
    // the team tint set by the aim_text named event after the gui loaded.
    Script aimFade{"aimText::forecolor", "$aimText::forecolor", "$desktop::aim_fade_color", "500"};
    aimFade.FixupParms(&aimText);
    CheckSavedLayout(aimFade, "aim-name fade keeps owned operand copies");
    Check(aimFade.parms[0].var == aimColor && !aimFade.parms[0].own, "aim-name fade targets the window's forecolor");
    Check(aimFade.parms[1].live == aimColor, "aim-name fade source is bound to the live forecolor");
    Check(aimFade.parms[2].live == desktop.vars["aim_fade_color"], "aim-name fade target is bound to the live desktop colour");
    aimColor->data = idVec4(1.0f, 1.0f, 1.0f, 0.8f);
    desktop.vars["aim_fade_color"]->Set("0.627,0.862,0.317,0");
    {
        const idWindow::Added &added = Run(aimFade, aimText, "aim-name fade starts a transition");
        Check(added.dest == aimColor && added.time == 500, "aim-name fade animates forecolor over 500 ms");
        Check(added.from == idVec4(1.0f, 1.0f, 1.0f, 0.8f), "aim-name fade starts from the current colour");
        Check(added.to == idVec4(0.627f, 0.862f, 0.317f, 0.0f), "aim-name fade ends on the team tint set after parse");
        Check(!aimColor->GetEval() && aimText.started == 1, "aim-name fade stops the register and starts the window");
    }
    // A restored parse-time copy (older saves carry one) must not replace the live read.
    static_cast<idWinVec4 *>(aimFade.parms[1].var)->data = idVec4(9.0f, 9.0f, 9.0f, 9.0f);
    aimColor->data = idVec4(1.0f, 1.0f, 1.0f, 0.5f);
    Check(Run(aimFade, aimText, "aim-name fade restarts").from == idVec4(1.0f, 1.0f, 1.0f, 0.5f),
        "aim-name fade ignores the saved operand copy");

    // mphud.gui d_ctfone_flag: the one-flag pulse flashes toward the carrier's team colour.
    Script flash{"ctfone_flag::matcolor", "$desktop::neutral", "$desktop::ctfoneflag_color", "250"};
    Script settle{"ctfone_flag::matcolor", "$desktop::ctfoneflag_color", "$desktop::neutral", "750"};
    flash.FixupParms(&driver);
    settle.FixupParms(&driver);
    CheckSavedLayout(flash, "one-flag flash keeps owned operand copies");
    CheckSavedLayout(settle, "one-flag settle keeps owned operand copies");
    desktop.vars["ctfoneflag_color"]->Set("0.415,0.643,0.168,0.8");
    Check(Run(flash, driver, "one-flag flash starts").to == idVec4(0.415f, 0.643f, 0.168f, 0.8f),
        "one-flag flash reaches the carrier's team colour");
    Check(Run(settle, driver, "one-flag settle starts").from == idVec4(0.415f, 0.643f, 0.168f, 0.8f),
        "one-flag settle starts from the carrier's team colour");

    // A rect naming a rect stays a parse-time snapshot, converted into the
    // destination's parent space (mphud's flag pulses return to the authored rect).
    Script pulse{"ctfone_flag::rect", "$ctfone_flag::rect", "$pulse_rect::rect", "250"};
    pulse.FixupParms(&driver);
    CheckSavedLayout(pulse, "rect pulse keeps owned operand copies");
    Check(pulse.parms[1].live == nullptr && pulse.parms[2].live == nullptr, "rect sources are not bound live");
    static_cast<idWinRectangle *>(flag.vars["rect"])->Set("0,0,1,1");
    pulseRect.vars["rect"]->Set("5,5,5,5");
    {
        const idWindow::Added &added = Run(pulse, driver, "rect pulse starts");
        Check(added.from == idVec4(97.0f, 33.0f, 28.0f, 28.0f), "flag pulse rect is a parse-time snapshot");
        Check(added.to == idVec4(-6.0f, -20.0f, 34.0f, 34.0f), "rect snapshot is converted between parent spaces");
    }
    // Without both parents there is nothing to convert; the rect is still a parse-time copy.
    Script whole{"aimText::rect", "$desktop::rect", "0,0,1,1", "100"};
    whole.FixupParms(&aimText);
    desktop.vars["rect"]->Set("1,2,3,4");
    Check(whole.parms[1].live == nullptr && Run(whole, aimText, "desktop rect transition starts").from == idVec4(0.0f, 0.0f, 640.0f, 480.0f),
        "a rect source without parents is still a parse-time snapshot");

    // A vec4 source feeding a rect is live (retail accepts vec4 for rect destinations).
    Script placed{"ctfone_flag::rect", "$desktop::flag_rect", "$ctfone_flag::rect", "100", "0.25", "0.5"};
    placed.FixupParms(&driver);
    desktop.vars["flag_rect"]->Set("1,2,3,4");
    {
        const idWindow::Added &added = Run(placed, driver, "vec4-to-rect transition starts");
        Check(added.from == idVec4(1.0f, 2.0f, 3.0f, 4.0f), "a vec4 source for a rect destination is live");
        Check(added.accel == 0.25f && added.decel == 0.5f, "accel and decel stay literal");
    }

    // A float source is live too and converts through its text, as the parse-time copy did.
    Script alpha{"aimText::forecolor_w", "$desktop::fade_alpha", "0.8", "200"};
    alpha.FixupParms(&aimText);
    CheckSavedLayout(alpha, "float transition keeps owned operand copies");
    aimColor->SetEval(true);
    fadeAlpha.Set("0.375");
    {
        const idWindow::Added &added = Run(alpha, aimText, "float transition starts");
        Check(added.dest == &aimAlpha && Near(added.from, idVec4(0.375f, 0.0f, 0.0f, 0.0f)), "a float source is read when the transition starts");
        Check(Near(added.to, idVec4(0.8f, 0.0f, 0.0f, 0.0f)), "a literal operand is parsed at load");
        Check(!aimAlpha.GetEval() && !aimColor->GetEval(), "a component transition stops both registers");
    }

    // Literals are parsed at load; an unknown var warns and runs from zero.
    Script flashRed{"aimText::forecolor", "1,0,0,1", "$desktop::aim_text_color", "400"};
    flashRed.FixupParms(&aimText);
    Check(flashRed.parms[1].live == nullptr && flashRed.parms[2].live == desktop.vars["aim_text_color"], "only the $ operand is live");
    desktop.vars["aim_text_color"]->Set("1,0.517,0,0.8");
    {
        const idWindow::Added &added = Run(flashRed, aimText, "literal transition starts");
        Check(added.from == idVec4(1.0f, 0.0f, 0.0f, 1.0f) && added.to == idVec4(1.0f, 0.517f, 0.0f, 0.8f), "literal and live operands mix");
    }
    const int warnings = commonObject.warnings;
    Script missing{"aimText::forecolor", "$nowhere::forecolor", "1,1,1,1", "100"};
    missing.FixupParms(&aimText);
    Check(commonObject.warnings == warnings + 1 && commonObject.lastWarning.find("not a valid var") != std::string::npos,
        "an unknown $ operand warns at load");
    Check(missing.parms[1].live == nullptr && Run(missing, aimText, "unknown operand transition starts").from == idVec4(),
        "an unknown $ operand runs from zero");

    std::printf("gui_transition_operand_contract: PASS (%u checks: live $vars, rect snapshots, saved layout)\n", checks);
    return 0;
}
'''

MUTATIONS = {
    # Doom 3's rule: every $ operand is a parse-time copy.
    "snapshot-every-source": ("\t\t\t\t\tparms[c].live = dest;\n", "", "aim-name fade source is bound to the live forecolor"),
    # Binding rects live loses the snapshot the flag pulses return to.
    "bind-rects-live": ("if ( dynamic_cast<idWinRectangle*>( dest ) == NULL ) {", "if ( true ) {", "rect sources are not bound live"),
    # Reading the parse-time copy even when an operand is bound live.
    "ignore-live-binding": ("\tif ( parm.live == NULL ) {\n", "\tif ( true ) {\n", "aim-name fade starts from the current colour"),
}


def build_source(root: Path) -> str:
    header = (root / "src/ui/GuiScript.h").read_text(encoding="utf-8").replace("\r\n", "\n")
    source = (root / "src/ui/GuiScript.cpp").read_text(encoding="utf-8").replace("\r\n", "\n")
    declarations = "\n".join((
        braced(header, "struct idGSWinVar {", ";"),
        "class idGuiScriptList;",
        braced(header, "class idGuiScript {", ";"),
    ))
    functions = "\n".join(braced(source, signature) for signature in (
        "static bool GuiScript_ReadTransitionOperand(",
        "void Script_Transition(",
        "idGuiScript::idGuiScript()",
        "idGuiScript::~idGuiScript()",
        "void idGuiScript::FixupParms(",
    ))
    return SUPPORT + declarations + AFTER_DECLARATIONS + functions + MAIN


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
    parser.add_argument("--mutations", action="store_true", help="also require each reverted rule to fail")
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    compiler = args.compiler or next((path for name in ("clang++", "g++", "c++") if (path := shutil.which(name))), None)
    if compiler is None:
        raise RuntimeError("a C++ compiler is required")
    flags = ["-std=c++17", "-Wall", "-Wextra", "-Wno-unused-parameter", "-Wno-unused-variable"]
    if args.sanitize:
        flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    text = build_source(args.root)
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gui-transition-", dir=ROOT / ".tmp") as scratch:
        directory = Path(scratch)
        result = compile_and_run(compiler, flags, text, directory, "positive")
        print(result.stdout, end="")
        if result.returncode != 0:
            raise SystemExit(f"gui_transition_operand_contract: {result.stderr.strip()}")
        if args.mutations:
            for name, (old, new, expected) in MUTATIONS.items():
                assert text.count(old) == 1, f"mutation {name} no longer matches the production source"
                mutated = compile_and_run(compiler, flags, text.replace(old, new), directory, name)
                if mutated.returncode == 0 or f"FAIL {expected}" not in mutated.stderr:
                    raise SystemExit(f"gui_transition_operand_contract: mutation {name} was not caught "
                                     f"(exit {mutated.returncode}: {mutated.stderr.strip()})")
                print(f"gui_transition_operand_contract: mutation {name} caught ({expected})")


if __name__ == "__main__":
    main()
