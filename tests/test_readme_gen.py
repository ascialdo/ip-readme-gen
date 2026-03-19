"""
Tests for ip-readme-gen.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from ir.model import Direction, AccessType, Port, Generic
from injector.readme import (
    inject_section,
    build_module_interface,
    build_register_mapping,
    build_register_mapping_warning,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _port(name, direction, width, vhdl_type=None):
    if vhdl_type is None:
        vhdl_type = 'std_logic' if width == 1 else f'std_logic_vector({width - 1} downto 0)'
    return Port(name=name, direction=direction, width=width, vhdl_type=vhdl_type)


def _generic(name, vhdl_type='integer', default='8'):
    return Generic(name=name, vhdl_type=vhdl_type, default=default)


def _sample_ports():
    return [
        _port('clk',       Direction.IN,  1),
        _port('rst_n',     Direction.IN,  1),
        _port('enable',    Direction.IN,  1),
        _port('duty',      Direction.IN,  8),
        _port('pwm_out',   Direction.OUT, 1),
        _port('status',    Direction.OUT, 4),
    ]


def _sample_generics():
    return [
        _generic('CLK_FREQ_HZ', 'integer', '100_000_000'),
        _generic('PWM_BITS',    'integer', '8'),
    ]


# ---------------------------------------------------------------------------
# inject_section
# ---------------------------------------------------------------------------

class TestInjectSection(unittest.TestCase):

    def test_replaces_existing_section(self):
        readme = "# My IP\n\nSome intro.\n\n## Module Interface\n\nOld content here.\n\n## Usage\n\nUsage text.\n"
        result = inject_section(readme, 'Module Interface', 'New content.')
        self.assertIn('New content.', result)
        self.assertNotIn('Old content here.', result)

    def test_preserves_other_sections(self):
        readme = "# My IP\n\n## Module Interface\n\nOld.\n\n## Usage\n\nUsage text.\n"
        result = inject_section(readme, 'Module Interface', 'New.')
        self.assertIn('## Usage', result)
        self.assertIn('Usage text.', result)

    def test_appends_if_section_missing(self):
        readme = "# My IP\n\nSome intro.\n"
        result = inject_section(readme, 'Module Interface', 'New content.')
        self.assertIn('## Module Interface', result)
        self.assertIn('New content.', result)

    def test_appended_section_is_after_existing_content(self):
        readme = "# My IP\n\nIntro.\n"
        result = inject_section(readme, 'Module Interface', 'Content.')
        self.assertGreater(result.index('## Module Interface'), result.index('Intro.'))

    def test_two_injections_both_present(self):
        readme = "# My IP\n\nIntro.\n"
        result = inject_section(readme, 'Module Interface', 'Interface content.')
        result = inject_section(result, 'Register Mapping Information', 'Regmap content.')
        self.assertIn('## Module Interface', result)
        self.assertIn('## Register Mapping Information', result)

    def test_replace_preserves_heading(self):
        readme = "## Module Interface\n\nOld.\n"
        result = inject_section(readme, 'Module Interface', 'New.')
        self.assertIn('## Module Interface', result)

    def test_section_at_end_of_file_no_trailing_heading(self):
        readme = "# Title\n\n## Module Interface\n\nLast section, no next heading.\n"
        result = inject_section(readme, 'Module Interface', 'Replaced.')
        self.assertIn('Replaced.', result)
        self.assertNotIn('Last section', result)


# ---------------------------------------------------------------------------
# build_module_interface
# ---------------------------------------------------------------------------

class TestBuildModuleInterface(unittest.TestCase):

    def test_ports_table_present(self):
        content = build_module_interface(_sample_ports(), [])
        self.assertIn('### Ports', content)
        self.assertIn('| Port |', content)

    def test_all_ports_in_table(self):
        content = build_module_interface(_sample_ports(), [])
        for name in ('clk', 'rst_n', 'enable', 'duty', 'pwm_out', 'status'):
            self.assertIn(name, content)

    def test_port_direction_in_table(self):
        content = build_module_interface(_sample_ports(), [])
        self.assertIn('in', content)
        self.assertIn('out', content)

    def test_port_width_in_table(self):
        content = build_module_interface(_sample_ports(), [])
        self.assertIn('8', content)   # duty width

    def test_generics_table_present(self):
        content = build_module_interface([], _sample_generics())
        self.assertIn('### Generics', content)
        self.assertIn('| Generic |', content)

    def test_all_generics_in_table(self):
        content = build_module_interface([], _sample_generics())
        self.assertIn('CLK_FREQ_HZ', content)
        self.assertIn('PWM_BITS', content)

    def test_generic_default_in_table(self):
        content = build_module_interface([], _sample_generics())
        self.assertIn('100_000_000', content)

    def test_no_generics_section_when_empty(self):
        content = build_module_interface(_sample_ports(), [])
        self.assertNotIn('### Generics', content)

    def test_mapped_ports_excluded(self):
        mapped = {'duty', 'status'}
        content = build_module_interface(_sample_ports(), [], mapped_ports=mapped)
        self.assertNotIn('`duty`', content)
        self.assertNotIn('`status`', content)
        self.assertIn('`clk`', content)
        self.assertIn('`enable`', content)

    def test_unmapped_ports_still_present(self):
        mapped = {'duty'}
        content = build_module_interface(_sample_ports(), [], mapped_ports=mapped)
        self.assertIn('`pwm_out`', content)

    def test_axi4lite_slave_row_present(self):
        content = build_module_interface(_sample_ports(), [])
        self.assertIn('AXI4-Lite Slave', content)
        self.assertIn('slave', content)

    def test_axi4lite_slave_shows_register_width(self):
        content = build_module_interface(_sample_ports(), [], register_width=64)
        self.assertIn('64 bit', content)

    def test_generic_dependent_port_shows_type_string(self):
        p = Port(
            name='data',
            direction=Direction.IN,
            width=None,
            vhdl_type='std_logic_vector(DATA_WIDTH-1 downto 0)',
        )
        content = build_module_interface([p], [])
        self.assertIn('std_logic_vector(DATA_WIDTH-1 downto 0)', content)

    def test_no_ports_still_has_axi_row(self):
        content = build_module_interface([], [])
        self.assertIn('AXI4-Lite Slave', content)


# ---------------------------------------------------------------------------
# build_register_mapping
# ---------------------------------------------------------------------------

class TestBuildRegisterMapping(unittest.TestCase):

    def _write_regmap(self, content: str) -> str:
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
        f.write(content)
        f.close()
        return f.name

    def tearDown(self):
        # cleanup handled per-test
        pass

    def test_title_stripped(self):
        path = self._write_regmap('# Register Map — my_entity\n\n## REG_CTRL\n\nContent.\n')
        try:
            result = build_register_mapping(path)
            self.assertNotIn('# Register Map', result)
            self.assertIn('## REG_CTRL', result)
        finally:
            os.unlink(path)

    def test_content_preserved(self):
        path = self._write_regmap('# Title\n\nSome register content.\n')
        try:
            result = build_register_mapping(path)
            self.assertIn('Some register content.', result)
        finally:
            os.unlink(path)

    def test_no_title_line_unchanged(self):
        path = self._write_regmap('## REG_CTRL\n\nContent.\n')
        try:
            result = build_register_mapping(path)
            self.assertIn('REG_CTRL', result)
        finally:
            os.unlink(path)

    def test_register_headings_downgraded_to_h3(self):
        path = self._write_regmap('# Title\n\n## REG_CTRL — Offset `0x0000`\n\nContent.\n\n## REG_STATUS — Offset `0x0004`\n\nContent.\n')
        try:
            result = build_register_mapping(path)
            self.assertNotIn('\n## REG_CTRL', result)
            self.assertNotIn('\n## REG_STATUS', result)
            self.assertIn('### REG_CTRL', result)
            self.assertIn('### REG_STATUS', result)
        finally:
            os.unlink(path)

    def test_repeated_injection_does_not_duplicate(self):
        """Injecting the same section twice must not grow the README."""
        regmap_content = '# Title\n\n## REG_CTRL\n\nSome field.\n\n## REG_STATUS\n\nAnother field.\n'
        path = self._write_regmap(regmap_content)
        try:
            content = build_register_mapping(path)
            readme = '# My IP\n\nIntro.\n'
            result = inject_section(readme, 'Register Mapping Information', content)
            result = inject_section(result, 'Register Mapping Information', content)
            self.assertEqual(result.count('## Register Mapping Information'), 1)
            self.assertEqual(result.count('### REG_CTRL'), 1)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# build_register_mapping_warning
# ---------------------------------------------------------------------------

class TestBuildRegisterMappingWarning(unittest.TestCase):

    def test_contains_entity_name(self):
        result = build_register_mapping_warning('my_entity')
        self.assertIn('my_entity', result)

    def test_contains_warning_keyword(self):
        result = build_register_mapping_warning('my_entity')
        self.assertLower(result)

    def assertLower(self, text):
        self.assertIn('warning', text.lower())

    def test_mentions_axi_wrapper_gen(self):
        result = build_register_mapping_warning('my_entity')
        self.assertIn('axi-wrapper-gen', result)


# ---------------------------------------------------------------------------
# VHDL parser integration
# ---------------------------------------------------------------------------

class TestVHDLParserIntegration(unittest.TestCase):

    _VHDL = """\
library ieee;
use ieee.std_logic_1164.all;

entity pwm_ctrl is
    generic (
        CLK_HZ  : integer := 100_000_000;
        BITS    : integer := 8
    );
    port (
        clk     : in  std_logic;
        rst_n   : in  std_logic;
        enable  : in  std_logic;
        duty    : in  std_logic_vector(7 downto 0);
        pwm_out : out std_logic
    );
end entity pwm_ctrl;
architecture rtl of pwm_ctrl is begin end architecture rtl;
"""

    def setUp(self):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.vhd', delete=False, encoding='utf-8')
        f.write(self._VHDL)
        f.close()
        self.vhd_path = f.name

    def tearDown(self):
        os.unlink(self.vhd_path)

    def test_entity_name_extracted(self):
        from parser.vhdl_parser import parse_entity
        name, _, _ = parse_entity(self.vhd_path)
        self.assertEqual(name, 'pwm_ctrl')

    def test_ports_extracted(self):
        from parser.vhdl_parser import parse_entity
        _, ports, _ = parse_entity(self.vhd_path)
        names = [p.name for p in ports]
        self.assertIn('clk', names)
        self.assertIn('pwm_out', names)

    def test_generics_extracted(self):
        from parser.vhdl_parser import parse_entity
        _, _, generics = parse_entity(self.vhd_path)
        names = [g.name for g in generics]
        self.assertIn('CLK_HZ', names)
        self.assertIn('BITS', names)

    def test_module_interface_built_from_parsed(self):
        from parser.vhdl_parser import parse_entity
        _, ports, generics = parse_entity(self.vhd_path)
        content = build_module_interface(ports, generics)
        self.assertIn('CLK_HZ', content)
        self.assertIn('pwm_out', content)
        self.assertIn('out', content)


if __name__ == '__main__':
    unittest.main()
