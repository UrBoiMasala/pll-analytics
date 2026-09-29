"""Check that local Markdown file and image links resolve inside the checkout.

External websites and heading fragments are deliberately not fetched or validated.
This check is offline and uses only Python's standard library.
"""
from pathlib import Path
import os
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SKIP = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'test-results'}
LINK = re.compile(r'\]\(([^)]+)\)')


def check(root=ROOT):
    failures = []
    count = 0
    for directory, folders, files in os.walk(root):
        folders[:] = [name for name in folders if name not in SKIP]
        for name in sorted(files):
            if not name.endswith('.md'):
                continue
            source = Path(directory) / name
            for match in LINK.finditer(source.read_text(encoding='utf-8')):
                target = match.group(1).strip()
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                count += 1
                destination = (source.parent / unquote(parsed.path)).resolve()
                if not destination.exists():
                    failures.append(f'{source.relative_to(root)}: {target}')
    return count, failures


if __name__ == '__main__':
    count, failures = check()
    for failure in failures:
        print('Missing local link:', failure)
    print(f'Checked {count} local links; {len(failures)} missing targets.')
    raise SystemExit(bool(failures))
