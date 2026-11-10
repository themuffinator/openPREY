"""Extract the production capture resampler for a native pixel-orientation test."""
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text(encoding='utf-8')
start = source.index('static byte *R_ResampleCaptureToAspectRGBA(')
opening = source.index('{', start)
depth = 1
end = opening + 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
Path(sys.argv[2]).write_text(source[start:end] + '\n', encoding='utf-8')
