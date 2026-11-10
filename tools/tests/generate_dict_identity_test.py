"""Exercise the production dictionary mutators with independent storage stubs."""
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text(encoding='utf-8')
parts = []
for method, result in [('operator=', 'idDict &'), ('Copy', 'void '),
                       ('TransferKeyValues', 'void '), ('SetDefaults', 'void '),
                       ('Clear', 'void '), ('Set', 'void '), ('Delete', 'void '),
                       ('FindKeyIndex', 'int '), ('FindKey', 'const idKeyValue *')]:
    start = source.index(f'{result}idDict::{method}(')
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    parts.append(source[start:end])
Path(sys.argv[2]).write_text('\n'.join(parts) + '\n', encoding='utf-8')
