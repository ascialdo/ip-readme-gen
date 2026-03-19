"""
README section injector.

Finds a ## heading in a README and replaces the content beneath it until
the next ## heading (or end of file). If the heading is not found, appends
the section at the end.
"""
from __future__ import annotations

import re


def inject_section(text: str, heading: str, content: str) -> str:
    """
    Replace or append a ## section in README text.

    - If `## heading` exists: replaces everything between it and the next ##
    - If not found: appends the section at the end
    """
    pattern = re.compile(
        rf'^## {re.escape(heading)}\s*\n[\s\S]*?(?=^## |\Z)',
        re.MULTILINE,
    )
    replacement = f'## {heading}\n\n{content.strip()}\n\n'

    if pattern.search(text):
        return pattern.sub(replacement, text)

    return text.rstrip('\n') + f'\n\n## {heading}\n\n{content.strip()}\n'


def build_module_interface(ports, generics) -> str:
    """
    Build the markdown content for the ## Module Interface section.
    Includes a Generics table (if any) and a Ports table.
    """
    sections = []

    if generics:
        rows = [
            '| Generic | Type | Default |',
            '|---------|------|---------|',
        ]
        for g in generics:
            default = g.default if g.default else '—'
            rows.append(f'| `{g.name}` | {g.vhdl_type} | {default} |')
        sections.append('### Generics\n\n' + '\n'.join(rows))

    if ports:
        rows = [
            '| Port | Direction | Width |',
            '|------|-----------|-------|',
        ]
        for p in ports:
            width = p.vhdl_type if p.is_generic_dependent else str(p.width)
            rows.append(f'| `{p.name}` | {p.direction.value} | {width} |')
        sections.append('### Ports\n\n' + '\n'.join(rows))

    return '\n\n'.join(sections)


def build_register_mapping(regmap_path) -> str:
    """
    Read the _regmap.md file and return its content with the top-level
    # title stripped (to avoid heading hierarchy conflicts in the README).
    """
    from pathlib import Path
    content = Path(regmap_path).read_text(encoding='utf-8')
    # Strip the first # title line (e.g. "# Register Map — entity_name")
    lines = content.splitlines(keepends=True)
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
    return ''.join(lines).lstrip('\n')


def build_register_mapping_warning(entity_name: str) -> str:
    """
    Returns a warning block to embed when _regmap.md is not found.
    """
    return (
        f'> **Warning**: register map documentation not found. '
        f'Run `axi-wrapper-gen` first to generate `{entity_name}_axi/{entity_name}_regmap.md`.'
    )
