"""Extract checkpoint handoff and storage production code for fault injection."""
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text(encoding='utf-8')
blocks = []
for signature in ('struct sessionSaveStorageJob_t {',
                  'static void Session_WriteCheckpointPayload(',
                  'static bool Session_QueueCheckpointStorage('):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    if source[end:end+1] == ';':
        end += 1
    blocks.append(source[start:end])
Path(sys.argv[2]).write_text('\n\n'.join(blocks) + '\n', encoding='utf-8')
