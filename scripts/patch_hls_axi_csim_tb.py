#!/usr/bin/env python3
"""Use myproject_axi_test.cpp as HLS csim testbench when top is myproject_axi."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BUILD = REPO / 'notebooks' / 'hls4ml_prj' / 'build_prj.tcl'
AXI_TB = REPO / 'notebooks' / 'hls4ml_prj' / 'myproject_axi_test.cpp'
OLD = 'add_files -tb ${project_name}_test.cpp -cflags "-std=c++0x"'
NEW = 'add_files -tb ${project_name}_axi_test.cpp -cflags "-std=c++0x"'


def main() -> int:
    if not BUILD.is_file():
        print('ERROR: missing %s' % BUILD, file=sys.stderr)
        return 1
    text = BUILD.read_text(encoding='utf-8')
    if NEW in text:
        print('build_prj.tcl already uses myproject_axi_test.cpp for csim (legacy)')
        return 0
    if re.search(r'add_files -tb \$\{synth_top_name\}_test\.cpp', text) and AXI_TB.is_file():
        print('build_prj.tcl already uses synth_top_name_test (myproject_axi_test.cpp)')
        return 0
    if OLD not in text:
        print('WARN: expected tb add_files line not found', file=sys.stderr)
        return 1
    text = text.replace(OLD, NEW, 1)
    text = text.replace(
        'add_files -tb ${project_name}_test.cpp -cflags "-std=c++0x -DRTL_SIM"',
        'add_files -tb ${project_name}_axi_test.cpp -cflags "-std=c++0x -DRTL_SIM"',
        1,
    )
    BUILD.write_text(text, encoding='utf-8')
    print('patched build_prj.tcl: csim tb -> myproject_axi_test.cpp')
    return 0


if __name__ == '__main__':
    sys.exit(main())
