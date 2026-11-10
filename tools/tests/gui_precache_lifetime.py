#!/usr/bin/env python3
"""Run SP/MP precaching and the production GUI lookup against counted owners."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
from sound_settings import body

ROOT = Path(__file__).resolve().parents[2]


def source(module, mutation=None):
    multiplayer = (ROOT / 'src' / module / 'MultiplayerGame.cpp').read_text()
    game = (ROOT / 'src' / module / 'Game_local.cpp').read_text()
    ui = (ROOT / 'src/ui/UserInterface.cpp').read_text()
    precache = body(multiplayer, 'void idMultiplayerGame::Precache(')
    dictionary = body(game, 'else if ( MATCH( "gui_" ) )')
    dictionary = dictionary[dictionary.index('{'):]
    lookup = body(ui, 'idUserInterface *idUserInterfaceManagerLocal::FindGui(')
    if mutation == 'mp_duplicate':
        precache = precache.replace('true, false, true', 'true')
    elif mutation == 'dictionary_duplicate':
        dictionary = dictionary.replace('true, false, true', 'true')
    elif mutation == 'shared_gameplay':
        lookup = lookup.replace('!forceNOTUnique &&', 'false &&')
    fixture = (ROOT / 'tools/tests/native/GuiPrecacheLifetimeTest.cpp').read_text()
    return fixture.replace('// @LOOKUP@', lookup).replace('// @PRECACHE@', precache).replace('// @DICTIONARY@', dictionary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mutations', action='store_true')
    args = parser.parse_args()
    scratch = ROOT / '.tmp/gui-precache-lifetime'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        for module in ('game', 'mpgame'):
            for mutation in [None] + (['mp_duplicate', 'dictionary_duplicate', 'shared_gameplay'] if args.mutations else []):
                cpp = Path(directory) / (module + '-' + (mutation or 'production') + '.cpp')
                exe = cpp.with_suffix('.exe' if os.name == 'nt' else '')
                cpp.write_text(source(module, mutation))
                subprocess.run([os.environ.get('CXX', 'clang++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                str(cpp), '-o', str(exe)], cwd=directory, check=True)
                result = subprocess.run([str(exe)], cwd=directory, text=True, capture_output=True)
                if mutation:
                    assert result.returncode != 0 and 'FAIL ' in result.stderr, (module, mutation, result)
                    print(f'{module} {mutation}: rejected ({result.stderr.strip()})')
                else:
                    assert result.returncode == 0, result.stdout + result.stderr
                    print(module + ': ' + result.stdout.strip())


if __name__ == '__main__':
    main()
