#!/usr/bin/env python3
"""Repair patch_axi_wrapper.py sequential csynth guard block."""
import re
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'scripts' / 'patch_axi_wrapper.py'
text = p.read_text(encoding='utf-8')

marker = "    if not use_dataflow and out_axis_bits == 32 and pack_mode == 'slot':"
first = text.find(marker)
second = text.find(marker, first + 1)
if second != -1:
    end = text.find('    myproject_cpp = fw /', second)
    text = text[:second] + text[end:]
    print('removed duplicate block')

inline_old = """        inline_block = textwrap.dedent(
            '''
                hls::stream<input_t> model_input("model_input");
                hls::stream<result_t> model_output("model_output");
                #pragma HLS STREAM variable=model_input depth=%(input_stream_depth)d
                #pragma HLS STREAM variable=model_output depth=%(output_stream_depth)d

                axis_to_model_stream(input_stream, model_input);
                %(myproject_inline_guard)smyproject(model_input, model_output);
                model_to_axis_stream(model_output, output_stream);
            '''
        ) % {
            'input_stream_depth': input_stream_depth,
            'output_stream_depth': output_stream_depth,
            'myproject_inline_guard': (
                '#pragma HLS INLINE off\\n                '
                if not use_dataflow else ''
            ),
        }
        cpp = cpp.replace(
            inline_block,
            '                run_axi_sequential(input_stream, output_stream);\\n',
            1,
        )"""

inline_new = """        cpp = re.sub(
            r'    hls::stream<input_t> model_input\\("model_input"\\);\\n'
            r'    hls::stream<result_t> model_output\\("model_output"\\);\\n'
            r'    #pragma HLS STREAM variable=model_input depth=\\d+\\n'
            r'    #pragma HLS STREAM variable=model_output depth=\\d+\\n\\n'
            r'    axis_to_model_stream\\(input_stream, model_input\\);\\n'
            r'(?:    #pragma HLS INLINE off\\n(?:                )?)?'
            r'    myproject\\(model_input, model_output\\);\\n'
            r'    model_to_axis_stream\\(model_output, output_stream\\);',
            '    run_axi_sequential(input_stream, output_stream);',
            cpp,
            count=1,
        )"""

if inline_old in text:
    text = text.replace(inline_old, inline_new)
    print('replaced inline_block with regex')
else:
    print('inline_block pattern missing (maybe already fixed)')

text = re.sub(
    r"cpp = cpp\.replace\(\s*'\s*\n\} // namespace',\s*sequential_helper \+ '[^']*',\s*1,\s*\)",
    "cpp = cpp.replace('} // namespace', sequential_helper + '} // namespace', 1)",
    text,
    count=1,
)

p.write_text(text, encoding='utf-8')
print('wrote', p)
