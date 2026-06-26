#!/usr/bin/env python3
"""Point build_prj.tcl at myproject_axi (single AXIS wrapper for BD + board)."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BUILD = REPO / 'notebooks' / 'hls4ml_prj' / 'build_prj.tcl'
AXI_CPP = REPO / 'notebooks' / 'hls4ml_prj' / 'firmware' / 'myproject_axi.cpp'

OLD = """set_top ${project_name}
add_files firmware/${project_name}.cpp -cflags "-std=c++0x\""""
NEW = """set_top ${project_name}_axi
add_files firmware/${project_name}_axi.cpp -cflags "-std=c++0x"
add_files firmware/${project_name}.cpp -cflags "-std=c++0x\""""


def main() -> int:
    if not BUILD.is_file():
        print('ERROR: missing %s' % BUILD, file=sys.stderr)
        return 1
    text = BUILD.read_text(encoding='utf-8')
    if 'set_top ${project_name}_axi' in text:
        print('build_prj.tcl already set_top myproject_axi (legacy)')
        return 0
    if re.search(r'set_top\s+\$\{synth_top_name\}', text) and AXI_CPP.is_file():
        print('build_prj.tcl already uses synth_top_name=myproject_axi (hls4ml default)')
        return 0
    if OLD not in text:
        print('ERROR: expected set_top block not found', file=sys.stderr)
        return 1
    BUILD.write_text(text.replace(OLD, NEW, 1), encoding='utf-8')
    print('patched %s: set_top -> myproject_axi' % BUILD.name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
