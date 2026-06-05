#!/usr/bin/env python3
"""
register_acu4ev_board.py
EdgeAI-ZU4EV — Register custom ACU4EV board config with local hls4ml installation

Usage:
    python3 hls4ml_board/register_acu4ev_board.py

This copies acu4ev.json into the hls4ml package directory so it appears
as a supported board in VivadoAccelerator backend.
"""

import os
import sys
import json
import shutil

def find_hls4ml_boards_dir():
    """Locate the boards directory inside the installed hls4ml package."""
    try:
        import hls4ml
        hls4ml_root = os.path.dirname(hls4ml.__file__)
    except ImportError:
        print('[ERROR] hls4ml not found. Install with: pip install hls4ml')
        sys.exit(1)

    # hls4ml 0.6.x path for VivadoAccelerator boards
    candidates = [
        os.path.join(hls4ml_root, 'backends', 'vivado',
                     'vivado_accelerator', 'boards'),
        # Alternative path in some versions
        os.path.join(hls4ml_root, 'writer', 'templates',
                     'vivado_accelerator', 'boards'),
    ]

    for path in candidates:
        if os.path.isdir(path):
            return path

    # Fallback: search for any boards dir containing pynq-zu.json
    for root, dirs, files in os.walk(hls4ml_root):
        if 'pynq-zu.json' in files:
            return root

    print('[ERROR] Could not find hls4ml boards directory.')
    print(f'        hls4ml root: {hls4ml_root}')
    print('        Expected to find a directory containing pynq-zu.json')
    sys.exit(1)


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    source_json = os.path.join(script_dir, 'acu4ev.json')

    if not os.path.exists(source_json):
        print(f'[ERROR] Source JSON not found: {source_json}')
        sys.exit(1)

    boards_dir = find_hls4ml_boards_dir()
    print(f'[INFO] hls4ml boards directory: {boards_dir}')

    # List existing boards for reference
    existing = [f for f in os.listdir(boards_dir) if f.endswith('.json')]
    print(f'[INFO] Existing boards: {existing}')

    dest = os.path.join(boards_dir, 'acu4ev.json')

    # Load and validate our JSON first
    with open(source_json) as f:
        config = json.load(f)

    print(f'[INFO] Board config:')
    print(f'         name : {config.get("board_name")}')
    print(f'         part : {config.get("part")}')
    print(f'         clock: {config.get("clock_period")} ns')
    print(f'         LUTs : {config.get("resources", {}).get("LUT")}')

    # Copy to hls4ml boards directory
    shutil.copy2(source_json, dest)
    print(f'[OK] Copied to: {dest}')

    # Verify registration
    try:
        import importlib
        import hls4ml
        importlib.reload(hls4ml)

        # Try to get supported boards list
        try:
            from hls4ml.backends.vivado.vivado_accelerator_config import \
                VivadoAcceleratorConfig
            boards = VivadoAcceleratorConfig.get_supported_boards()
            if 'acu4ev' in boards:
                print('[OK] acu4ev board successfully registered!')
                print(f'     All boards: {boards}')
            else:
                print('[WARN] Board registered but not detected in list.')
                print(f'       Current list: {boards}')
        except Exception as e:
            print(f'[WARN] Could not verify via API: {e}')
            print('       File copied successfully — should work after Python restart.')

    except Exception as e:
        print(f'[WARN] Verification failed: {e}')
        print('[OK] File copied — registration should be active after restart.')

    print()
    print('Usage in your notebook:')
    print("""
    hls_model = hls4ml.converters.convert_from_keras_model(
        model,
        hls_config   = hls_config,
        output_dir   = 'hls4ml_prj',
        backend      = 'Vivado',          # Note: 2020.1 uses 'Vivado', not 'VivadoAccelerator'
        part         = 'xczu4ev-sfvc784-1-i',
        clock_period = 5,
        io_type      = 'io_stream',
    )
    """)


if __name__ == '__main__':
    main()
