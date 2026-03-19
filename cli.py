#!/usr/bin/env python3
"""
ip-readme-gen — Injects module interface and register map sections into README.md.

Usage:
    ip-readme-gen

Requires axi_config.json in the current directory (same file used by axi-wrapper-gen).
Requires README.md in the current directory.

Updates two sections in README.md:
    ## Module Interface          — ports and generics extracted from the VHD file
    ## Register Mapping Information — embedded from <entity>_axi/<entity>_regmap.md
                                     (warning injected if file not found)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


# ── colour helpers ────────────────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

def bold(t):   return _c("1",  t)
def green(t):  return _c("32", t)
def yellow(t): return _c("33", t)
def red(t):    return _c("31", t)
def cyan(t):   return _c("36", t)
def dim(t):    return _c("2",  t)


def print_banner():
    print()
    print(bold(cyan("  ╔══════════════════════════════════════════╗")))
    print(bold(cyan("  ║           IP README Generator            ║")))
    print(bold(cyan("  ╚══════════════════════════════════════════╝")))
    print()

def print_ok(msg):   print(f"  {green('✓')} {msg}")
def print_warn(msg): print(f"  {yellow('⚠')} {msg}")
def print_err(msg):  print(f"  {red('✗')} {msg}")
def print_info(msg): print(f"  {dim('·')} {msg}")


# ── config ────────────────────────────────────────────────────────────────────

_CONFIG_FILE = 'axi_config.json'
_README_FILE = 'README.md'

_SECTION_INTERFACE = 'Module Interface'
_SECTION_REGMAP    = 'Register Mapping Information'


def _load_config() -> tuple[str, str]:
    """Read axi_config.json, return (top_entity_path, raw_json_path)."""
    cfg_path = Path(_CONFIG_FILE)
    if not cfg_path.exists():
        print_err(f"'{_CONFIG_FILE}' not found in current directory.")
        sys.exit(1)

    try:
        cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print_err(f"Failed to parse '{_CONFIG_FILE}': {e}")
        sys.exit(1)

    if 'top_entity' not in cfg:
        print_err(f"'{_CONFIG_FILE}' is missing required key: top_entity")
        sys.exit(1)

    rtl_path = cfg['top_entity']
    if not Path(rtl_path).exists():
        print_err(f"top_entity file not found: '{rtl_path}'")
        sys.exit(1)

    return rtl_path


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print_banner()
    print_info(f"Config:  {bold(_CONFIG_FILE)}")
    print_info(f"Target:  {bold(_README_FILE)}")

    # Check README exists
    readme_path = Path(_README_FILE)
    if not readme_path.exists():
        print_err(f"'{_README_FILE}' not found in current directory.")
        return 1

    # Load config
    rtl_path = _load_config()
    print_info(f"Entity file: {bold(rtl_path)}")

    # Parse VHDL entity
    print()
    try:
        from parser.vhdl_parser import parse_entity
        entity_name, ports, generics = parse_entity(rtl_path)
        print_ok(f"Entity '{bold(entity_name)}' parsed — "
                 f"{len(ports)} port(s), {len(generics)} generic(s)")
    except Exception as e:
        print_err(f"VHDL parse failed: {e}")
        return 1

    # Locate _regmap.md
    regmap_path = Path(rtl_path).parent / f"{entity_name}_axi" / f"{entity_name}_regmap.md"
    regmap_found = regmap_path.exists()
    if regmap_found:
        print_ok(f"Register map found: {regmap_path}")
    else:
        print_warn(f"Register map not found: {regmap_path}")
        print_warn("Run axi-wrapper-gen first. A warning will be added to the README.")

    # Build section content
    from injector.readme import (
        build_module_interface,
        build_register_mapping,
        build_register_mapping_warning,
        inject_section,
    )

    interface_content = build_module_interface(ports, generics)

    if regmap_found:
        regmap_content = build_register_mapping(regmap_path)
    else:
        regmap_content = build_register_mapping_warning(entity_name)

    # Inject into README
    readme_text = readme_path.read_text(encoding='utf-8')
    readme_text = inject_section(readme_text, _SECTION_INTERFACE, interface_content)
    readme_text = inject_section(readme_text, _SECTION_REGMAP, regmap_content)
    readme_path.write_text(readme_text, encoding='utf-8')

    print_ok(f"'{_README_FILE}' updated")
    print()
    print(green(bold(f"  Done — '{_README_FILE}' sections updated.")))
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
