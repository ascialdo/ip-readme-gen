"""
README section injector.

Appends (or replaces) a generated block at the bottom of the README.
Everything above the USER_END_MARKER is treated as user content and is
never modified. The marker is preceded by a visible horizontal rule so
the boundary is clear in rendered markdown.
"""
from __future__ import annotations

import re

# HTML comment used to detect the generated section boundary.
MARKER = "<!-- AUTO GENERATED - DO NOT EDIT BELOW THIS LINE -->"
# Visible separator written immediately before the marker.
SEPARATOR = "---"


def inject_generated_block(readme_text: str, content: str) -> str:
    """
    Append a generated block at the bottom of the README, or replace the
    existing one if the MARKER is already present.

    User content above the marker is never modified.  A horizontal-rule
    separator (``---``) is written immediately before the marker so the
    boundary is visible in rendered markdown.

    Idempotent: running multiple times produces the same output.
    Migration-safe: handles READMEs that already have the MARKER but were
    written before the separator was introduced.
    """
    idx = readme_text.find(MARKER)
    if idx != -1:
        # Strip trailing whitespace/newlines, then remove a preceding
        # separator if one was already written by a previous run.
        before = readme_text[:idx].rstrip('\n')
        if before.endswith(SEPARATOR):
            before = before[:-len(SEPARATOR)].rstrip('\n')
        return before + "\n\n" + SEPARATOR + "\n" + MARKER + "\n\n" + content.strip() + "\n"
    return readme_text.rstrip('\n') + "\n\n" + SEPARATOR + "\n" + MARKER + "\n\n" + content.strip() + "\n"


def build_module_interface(ports, generics, mapped_ports: set | None = None) -> str:
    """
    Build the markdown content for the ## Module Interface section.
    Includes a Generics table (if any) and a Ports table.

    Ports that are mapped as AXI registers are excluded from the table.
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
    sections.append('### Ports\n\n' + '\n'.join(rows))

    return '## Module Interface\n\n' + '\n\n'.join(sections)


def build_compact_regmap(cfg: dict) -> str:
    """
    Build a compact, flat register map table from axi_config.json.

    Each field gets one row. When a register has multiple fields the register
    name and offset are shown only on the first field row.
    """
    registers = cfg.get('registers', {})
    if not registers:
        return '## Register Mapping Information\n\n_No registers defined._'

    rows = [
        '| Register | Offset | Field | Bits | Access |',
        '|----------|--------|-------|------|--------|',
    ]
    for reg_name, reg in registers.items():
        offset = reg.get('offset', '—')
        fields = reg.get('fields', [])
        if not fields:
            rows.append(f'| `{reg_name}` | `{offset}` | — | — | — |')
            continue
        for i, fld in enumerate(fields):
            col_reg    = f'`{reg_name}`' if i == 0 else ''
            col_offset = f'`{offset}`'   if i == 0 else ''
            port       = fld.get('port', '—')
            bits       = fld.get('bits', [])
            bits_str   = f'[{bits[1]}:{bits[0]}]' if len(bits) == 2 else '—'
            access     = fld.get('access', '—')
            rows.append(f'| {col_reg} | {col_offset} | `{port}` | {bits_str} | {access} |')

    return '## Register Mapping Information\n\n' + '\n'.join(rows)


def build_register_mapping_warning(entity_name: str) -> str:
    """
    Returns a warning block to embed when _regmap.md is not found.
    Only used as a fallback when the register map file is absent and
    no registers are defined in axi_config.json.
    """
    return (
        f'## Register Mapping Information\n\n'
        f'> **Warning**: register map documentation not found. '
        f'Run `axi-wrapper-gen` first to generate '
        f'`{entity_name}_axi/{entity_name}_regmap.md`.'
    )
