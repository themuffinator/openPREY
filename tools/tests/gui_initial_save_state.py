#!/usr/bin/env python3
"""Exercise window initialization and save admission before the first draw."""
import os
from pathlib import Path
import subprocess
import tempfile
from sound_settings import body

ROOT = Path(__file__).resolve().parents[2]


def source(mutation=None):
    text = (ROOT / 'src/ui/Window.cpp').read_text()
    init = body(text, 'void idWindow::CommonInit()')
    if mutation == 'missing_x':
        init = init.replace('actualX = actualY = 0.0f;', 'actualY = 0.0f;')
    elif mutation == 'missing_y':
        init = init.replace('actualX = actualY = 0.0f;', 'actualX = 0.0f;')
    writer = body(text, 'void idWindow::WriteToSaveGame(')
    admission = writer[:writer.index('\n\tif ( !WriteSaveGameString')]
    return ((ROOT / 'tools/tests/native/GuiInitialSaveStateTest.cpp').read_text()
            .replace('// @INIT@', init)
            .replace('// @ADMISSION@', admission + '\n}\n'))


def main():
    scratch = ROOT / '.tmp/gui-initial-save-state'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        env = dict(os.environ, TEMP=directory, TMP=directory, TMPDIR=directory)
        for mutation in (None, 'missing_x', 'missing_y'):
            cpp = Path(directory) / ((mutation or 'production') + '.cpp')
            exe = cpp.with_suffix('.exe' if os.name == 'nt' else '')
            cpp.write_text(source(mutation))
            subprocess.run([os.environ.get('CXX', 'clang++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-variable', str(cpp), '-o', str(exe)], cwd=directory, env=env, check=True)
            result = subprocess.run([str(exe)], cwd=directory, env=env, text=True, capture_output=True)
            if mutation:
                assert result.returncode != 0 and 'FAIL' in result.stderr, result
                print(mutation + ': rejected (' + result.stderr.strip() + ')')
            else:
                assert result.returncode == 0, result.stdout + result.stderr
                print(result.stdout.strip())


if __name__ == '__main__':
    main()
