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


def build_module_interface(ports, generics,
                           mapped_ports: set | None = None,
                           register_width: int = 32) -> str:
    """
    Build the markdown content for the ## Module Interface section.
    Includes a Generics table (if any) and a Ports table.

    Ports that are mapped as AXI registers are excluded from the table.
    An AXI4-Lite Slave interface row is added at the end of the ports table.
    """
    mapped_ports = mapped_ports or set()
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

    visible_ports = [p for p in ports if p.name not in mapped_ports]
    rows = [
        '| Port | Direction | Width |',
        '|------|-----------|-------|',
    ]
    for p in visible_ports:
        width = p.vhdl_type if p.is_generic_dependent else str(p.width)
        rows.append(f'| `{p.name}` | {p.direction.value} | {width} |')
    rows.append(f'| AXI4-Lite Slave | slave | {register_width} bit |')
    sections.append('### Ports\n\n' + '\n'.join(rows))

    return '\n\n'.join(sections)


def build_register_mapping(regmap_path) -> str:
    """
    Read the _regmap.md file and return its content ready to embed inside a
    ## section of the README:
      - Strips the top-level # title line
      - Downgrades ## headings to ### so they don't act as section boundaries
        for the inject_section logic (registers are sub-sections of
        ## Register Mapping Information, so ### is also semantically correct)
    """
    from pathlib import Path
    content = Path(regmap_path).read_text(encoding='utf-8')
    # Strip the first # title line (e.g. "# Register Map — entity_name")
    lines = content.splitlines(keepends=True)
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
    content = ''.join(lines).lstrip('\n')
    # Downgrade ## to ### so register headings don't break section injection
    content = re.sub(r'^## ', '### ', content, flags=re.MULTILINE)
    return content


def build_register_mapping_warning(entity_name: str) -> str:
    """
    Returns a warning block to embed when _regmap.md is not found.
    """
    return (
        f'> **Warning**: register map documentation not found. '
        f'Run `axi-wrapper-gen` first to generate `{entity_name}_axi/{entity_name}_regmap.md`.'
    )
