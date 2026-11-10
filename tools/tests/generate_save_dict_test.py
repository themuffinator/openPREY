"""Compile both production dictionary writers against an independent wire oracle."""
from pathlib import Path
import sys

parts = []
for mode, path in zip(('sp', 'mp'), sys.argv[1:3]):
    source = Path(path).read_text(encoding='utf-8')
    for method in ('WriteChecked', 'FlushWriteBuffer', 'Write', 'WriteInt', 'WriteJoint',
                   'WriteShort', 'WriteByte', 'WriteSignedChar', 'WriteFloat', 'WriteBool',
                   'WriteString', 'WriteDict', 'InvalidateUserInterface', 'WriteUserInterface'):
        start = source.index(f'void idSaveGame::{method}(')
        opening = source.index('{', start)
        depth, end = 1, opening + 1
        while depth:
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        parts.append(source[start:end].replace('idSaveGame::', f'idSaveGame_{mode}::'))
Path(sys.argv[3]).write_text('\n'.join(parts) + '\n', encoding='utf-8')
