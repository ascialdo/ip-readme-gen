"""
Tests for ip-readme-gen.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from ir.model import Direction, AccessType, Port, Generic
from injector.readme import (
    MARKER,
    SEPARATOR,
    inject_generated_block,
    build_module_interface,
    build_compact_regmap,
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


def _sample_cfg():
    return {
        'top_entity': 'rtl/pwm_ctrl.vhd',
        'register_width': 32,
        'registers': {
            'REG_CTRL': {
                'offset': '0x00',
                'fields': [
                    {'port': 'enable', 'bits': [0, 0], 'access': 'RW'},
                    {'port': 'duty',   'bits': [8, 1], 'access': 'RW'},
                ],
            },
            'REG_STATUS': {
                'offset': '0x04',
                'fields': [
                    {'port': 'status', 'bits': [3, 0], 'access': 'RO'},
                ],
            },
        },
    }


# ---------------------------------------------------------------------------
# inject_generated_block
# ---------------------------------------------------------------------------

class TestInjectGeneratedBlock(unittest.TestCase):

    def test_appends_marker_when_absent(self):
        readme = "# My IP\n\nSome intro.\n"
        result = inject_generated_block(readme, 'Content.')
        self.assertIn(MARKER, result)
        self.assertIn('Content.', result)

    def test_marker_is_after_existing_content(self):
        readme = "# My IP\n\nIntro.\n"
        result = inject_generated_block(readme, 'Content.')
        self.assertGreater(result.index(MARKER), result.index('Intro.'))

    def test_replaces_everything_after_existing_marker(self):
        readme = f"# My IP\n\nIntro.\n\n{SEPARATOR}\n{MARKER}\n\nOld generated content.\n"
        result = inject_generated_block(readme, 'New generated content.')
        self.assertIn('New generated content.', result)
        self.assertNotIn('Old generated content.', result)

    def test_preserves_content_above_marker(self):
        readme = f"# My IP\n\nCustom section.\n\n{SEPARATOR}\n{MARKER}\n\nOld.\n"
        result = inject_generated_block(readme, 'New.')
        self.assertIn('Custom section.', result)

    def test_marker_appears_exactly_once(self):
        readme = "# My IP\n\nIntro.\n"
        result = inject_generated_block(readme, 'Content.')
        self.assertEqual(result.count(MARKER), 1)

    def test_repeated_injection_marker_still_once(self):
        readme = "# My IP\n\nIntro.\n"
        result = inject_generated_block(readme, 'Content.')
        result = inject_generated_block(result, 'Content.')
        self.assertEqual(result.count(MARKER), 1)

    def test_repeated_injection_content_not_duplicated(self):
        readme = "# My IP\n\nIntro.\n"
        result = inject_generated_block(readme, 'My content.')
        result = inject_generated_block(result, 'My content.')
        self.assertEqual(result.count('My content.'), 1)

    # ── separator tests ──────────────────────────────────────────────────────

    def test_separator_added_on_first_append(self):
        readme = "# My IP\n\nIntro.\n"
        result = inject_generated_block(readme, 'Content.')
        self.assertIn(SEPARATOR, result)
        # Separator must appear before the marker
        self.assertLess(result.index(SEPARATOR), result.index(MARKER))

    def test_separator_appears_exactly_once_after_first_run(self):
        readme = "# My IP\n\nIntro.\n"
        result = inject_generated_block(readme, 'Content.')
        self.assertEqual(result.count(SEPARATOR + "\n" + MARKER), 1)

    def test_separator_not_duplicated_on_repeat(self):
        readme = "# My IP\n\nIntro.\n"
        result = inject_generated_block(readme, 'Content.')
        result = inject_generated_block(result, 'Content.')
        self.assertEqual(result.count(SEPARATOR + "\n" + MARKER), 1)

    def test_user_content_before_separator_is_preserved(self):
        readme = "# My IP\n\nUser section.\n\nMore user text.\n"
        result = inject_generated_block(readme, 'Generated.')
        self.assertIn('User section.', result)
        self.assertIn('More user text.', result)
        # User content must appear before the separator
        self.assertLess(result.index('More user text.'), result.index(SEPARATOR))

    def test_migration_marker_without_separator(self):
        """README written by an older version of the tool (no separator)."""
        readme = f"# My IP\n\nIntro.\n\n{MARKER}\n\nOld content.\n"
        result = inject_generated_block(readme, 'New content.')
        self.assertIn('New content.', result)
        self.assertNotIn('Old content.', result)
        # After migration the separator must be present
        self.assertIn(SEPARATOR + "\n" + MARKER, result)
        # The marker must appear exactly once
        self.assertEqual(result.count(MARKER), 1)


# ---------------------------------------------------------------------------
# build_module_interface
# ---------------------------------------------------------------------------

class TestBuildModuleInterface(unittest.TestCase):

    def test_contains_module_interface_heading(self):
        content = build_module_interface(_sample_ports(), [])
        self.assertIn('## Module Interface', content)

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

    def test_no_axi4lite_slave_row(self):
        content = build_module_interface(_sample_ports(), [])
        self.assertNotIn('AXI4-Lite Slave', content)

    def test_no_ports_still_renders_ports_table(self):
        content = build_module_interface([], [])
        self.assertIn('### Ports', content)

    def test_generic_dependent_port_shows_type_string(self):
        p = Port(
            name='data',
            direction=Direction.IN,
            width=None,
            vhdl_type='std_logic_vector(DATA_WIDTH-1 downto 0)',
        )
        content = build_module_interface([p], [])
        self.assertIn('std_logic_vector(DATA_WIDTH-1 downto 0)', content)


# ---------------------------------------------------------------------------
# build_compact_regmap
# ---------------------------------------------------------------------------

class TestBuildCompactRegmap(unittest.TestCase):

    def test_contains_register_mapping_heading(self):
        result = build_compact_regmap(_sample_cfg())
        self.assertIn('## Register Mapping Information', result)

    def test_register_names_present(self):
        result = build_compact_regmap(_sample_cfg())
        self.assertIn('REG_CTRL', result)
        self.assertIn('REG_STATUS', result)

    def test_offsets_present(self):
        result = build_compact_regmap(_sample_cfg())
        self.assertIn('0x00', result)
        self.assertIn('0x04', result)

    def test_field_ports_present(self):
        result = build_compact_regmap(_sample_cfg())
        self.assertIn('enable', result)
        self.assertIn('duty', result)
        self.assertIn('status', result)

    def test_access_types_present(self):
        result = build_compact_regmap(_sample_cfg())
        self.assertIn('RW', result)
        self.assertIn('RO', result)

    def test_bits_notation(self):
        result = build_compact_regmap(_sample_cfg())
        self.assertIn('[0:0]', result)   # enable
        self.assertIn('[1:8]', result)   # duty  (bits[0]=1 low, bits[1]=8 high)
        self.assertIn('[0:3]', result)   # status

    def test_register_name_shown_only_on_first_field(self):
        result = build_compact_regmap(_sample_cfg())
        self.assertEqual(result.count('REG_CTRL'), 1)

    def test_no_registers_placeholder(self):
        result = build_compact_regmap({'registers': {}})
        self.assertIn('No registers defined', result)

    def test_no_registers_key(self):
        result = build_compact_regmap({})
        self.assertIn('No registers defined', result)

    def test_repeated_injection_not_duplicated(self):
        regmap_section = build_compact_regmap(_sample_cfg())
        readme = "# My IP\n\nIntro.\n"
        result = inject_generated_block(readme, regmap_section)
        result = inject_generated_block(result, regmap_section)
        self.assertEqual(result.count('## Register Mapping Information'), 1)
        self.assertEqual(result.count(SEPARATOR + "\n" + MARKER), 1)


# ---------------------------------------------------------------------------
# build_register_mapping_warning
# ---------------------------------------------------------------------------

class TestBuildRegisterMappingWarning(unittest.TestCase):

    def test_contains_entity_name(self):
        result = build_register_mapping_warning('my_entity')
        self.assertIn('my_entity', result)

    def test_contains_warning_keyword(self):
        result = build_register_mapping_warning('my_entity')
        self.assertIn('Warning', result)

    def test_mentions_axi_wrapper_gen(self):
        result = build_register_mapping_warning('my_entity')
        self.assertIn('axi-wrapper-gen', result)

    def test_contains_heading(self):
        result = build_register_mapping_warning('my_entity')
        self.assertIn('## Register Mapping Information', result)


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
