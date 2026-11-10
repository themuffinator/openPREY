"""Extract the production preview worker for persistence-failure injection."""
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text(encoding='utf-8')
blocks = []
for signature in ('struct sessionSavePreviewJob_t {', 'static void Session_PersistCheckpointPreview('):
    start = source.index(signature)
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    if source[end:end+1] == ';':
        end += 1
    blocks.append(source[start:end])
Path(sys.argv[2]).write_text('\n\n'.join(blocks) + '\n', encoding='utf-8')
