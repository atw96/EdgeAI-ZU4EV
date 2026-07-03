#!/usr/bin/env python3
"""One-shot patch: switch board path to serial 32-bit GAP output."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SERIAL_ENV = """export OUTPUT_AXIS_BITS=32 OUTPUT_PACK_MODE=serial AXI_DATAFLOW=0
export OUT_DIM=24 OUT_BYTES=96 OUT_LAYOUT=gap_ps OUT_FIXED_SCALE=1024
export IN_FIXED_SCALE=1024"""


def patch_file(rel, old, new):
    p = REPO / rel
    text = p.read_text(encoding='utf-8')
    if old not in text:
        if new in text:
            print('skip (already patched):', rel)
            return
        raise SystemExit('pattern not found in %s' % rel)
    p.write_text(text.replace(old, new, 1), encoding='utf-8')
    print('patched:', rel)


def patch_replace_all(rel, replacements):
    p = REPO / rel
    text = p.read_text(encoding='utf-8')
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
    p.write_text(text, encoding='utf-8')
    print('patched:', rel)


def main():
  # slot32_layout
    p = REPO / 'scripts/slot32_layout.py'
    text = p.read_text(encoding='utf-8')
    if 'decode_serial32_raw' not in text:
        text = text.replace(
            'def decode_slot32_raw(raw, out_scale, n_outputs=None):',
            '''def serial32_out_bytes(n_outputs):
    """Bytes for serial 32-bit AXIS (one logit per beat, low 16 bits)."""
    return int(n_outputs) * 4


def decode_serial32_raw(raw, out_scale, n_outputs=None):
    if n_outputs is None:
        n_outputs = int(os.environ.get('OUT_DIM', '10'))
    scale = float(out_scale)
    scores = []
    for idx in range(n_outputs):
        lo_v = struct.unpack_from('<h', raw, idx * 4)[0]
        scores.append(lo_v / scale)
    return scores


def decode_slot32_raw(raw, out_scale, n_outputs=None):''')
        p.write_text(text, encoding='utf-8')
        print('patched: slot32_layout.py')

    patch_file(
        'scripts/patch_axi_wrapper.py',
        "        'out_bytes': slot32_out_bytes(n_outputs) if (\n"
        "            out_axis_bits == 32 and pack_mode in ('serial', 'slot')\n"
        "        ) else 20,",
        "        'out_bytes': (\n"
        "            n_outputs * 4 if (out_axis_bits == 32 and pack_mode == 'serial')\n"
        "            else slot32_out_bytes(n_outputs) if (\n"
        "                out_axis_bits == 32 and pack_mode == 'slot'\n"
        "            ) else 20\n"
        "        ),",
    )
    patch_file(
        'scripts/patch_axi_wrapper.py',
        "if not use_dataflow and out_axis_bits == 32 and pack_mode == 'slot':",
        "if not use_dataflow and out_axis_bits == 32 and pack_mode in ('slot', 'serial'):",
    )

    patch_replace_all('scripts/dma_infer_common.py', [
        (
            'from slot32_layout import decode_slot32_raw, slot32_out_bytes',
            'from slot32_layout import decode_serial32_raw, decode_slot32_raw, serial32_out_bytes, slot32_out_bytes',
        ),
        (
            """OUT_LAYOUT = os.environ.get('OUT_LAYOUT', 'int16')
_default_out_bytes = slot32_out_bytes(OUT_DIM) if OUT_LAYOUT in (
    'slot32', 'gap_ps',
) else (40 if OUT_LAYOUT == 'serial32' else 20)
OUT_BYTES = int(os.environ.get('OUT_BYTES', str(_default_out_bytes)))""",
            """OUT_LAYOUT = os.environ.get('OUT_LAYOUT', 'int16')
OUTPUT_PACK_MODE = os.environ.get('OUTPUT_PACK_MODE', 'slot').lower()
if OUT_LAYOUT in ('slot32', 'gap_ps'):
    if OUTPUT_PACK_MODE == 'serial':
        _default_out_bytes = serial32_out_bytes(OUT_DIM)
    else:
        _default_out_bytes = slot32_out_bytes(OUT_DIM)
else:
    _default_out_bytes = 40 if OUT_LAYOUT == 'serial32' else 20
OUT_BYTES = int(os.environ.get('OUT_BYTES', str(_default_out_bytes)))


def decode_gap_raw(raw, out_scale=None, n_outputs=None):
    if n_outputs is None:
        n_outputs = OUT_DIM
    if out_scale is None:
        out_scale = int(os.environ.get('OUT_FIXED_SCALE', '1024'))
    if OUTPUT_PACK_MODE == 'serial':
        return decode_serial32_raw(raw, out_scale, n_outputs)
    return decode_slot32_raw(raw, out_scale, n_outputs)""",
        ),
        (
            "out_scale = int(os.environ.get('OUT_FIXED_SCALE', '256'))\n        return decode_slot32_raw(raw, out_scale, OUT_DIM)",
            "out_scale = int(os.environ.get('OUT_FIXED_SCALE', '1024'))\n        return decode_gap_raw(raw, out_scale, OUT_DIM)",
        ),
        (
            "if OUT_LAYOUT == 'slot32':\n            return decode_slot32_raw(raw, out_scale, OUT_DIM)",
            "if OUT_LAYOUT == 'slot32':\n            return decode_gap_raw(raw, out_scale, OUT_DIM)",
        ),
    ])

    # patch_axi_testbench - add serial branch in main()
    p = REPO / 'scripts/patch_axi_testbench.py'
    text = p.read_text(encoding='utf-8')
    if 'pack_mode == \'serial\'' not in text:
        insert_point = "    beat_lo, beat_hi, n_beats = slot_beat_maps(n_out)\n    cpp = '''\\"
        serial_block = """    pack_mode = meta.get('output_pack_mode', os.environ.get('OUTPUT_PACK_MODE', 'slot')).lower()
    if pack_mode == 'serial':
        n_beats = n_out
        cpp = '''\\
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <cmath>

#include "firmware/myproject_axi.h"

namespace {

constexpr int kInputWords = %(input_words_expr)s;
constexpr int kOutputWords = %(output_words_expr)s;
constexpr int kBenchInputScale = %(input_scale)d;

ap_uint<16> input_float_to_bits(float value) {
    ap_int<16> raw = (ap_int<16>)std::round(value * float(kBenchInputScale));
    return (ap_uint<16>)raw;
}

float gap_bits_to_float(ap_uint<16> bits) {
    %(out_ap)s<%(out_w)d, %(out_i)d> fixed_value;
    fixed_value.range(15, 0) = bits;
    return static_cast<float>(fixed_value);
}

std::vector<float> parse_line(const std::string &line) {
    std::vector<float> values;
    std::stringstream line_stream(line);
    float value = 0.0f;
    while (line_stream >> value) {
        values.push_back(value);
    }
    return values;
}

void write_input_stream(const std::vector<float> &values, hls::stream<input_axi_t> &input_stream) {
    for (int index = 0; index < kInputWords; ++index) {
        input_axi_t axis_word;
        axis_word.data = input_float_to_bits(values[index]);
        axis_word.keep = -1;
        axis_word.strb = -1;
        axis_word.last = (index == (kInputWords - 1)) ? 1 : 0;
        input_stream.write(axis_word);
    }
}

struct GapCsimResult {
    std::vector<float> gap;
    std::vector<ap_uint<32>> beats;
};

GapCsimResult collect_output_stream(hls::stream<output_axi_t> &output_stream) {
    GapCsimResult result;
    result.gap.assign(kOutputWords, 0.0f);
    result.beats.reserve(kOutputWords);
    for (int idx = 0; idx < kOutputWords; ++idx) {
        output_axi_t axis_word = output_stream.read();
        result.beats.push_back(axis_word.data);
        result.gap[idx] = gap_bits_to_float(axis_word.data.range(15, 0));
    }
    return result;
}

void write_gap_values(const std::vector<float> &values, std::ostream &out_stream) {
    for (int index = 0; index < static_cast<int>(values.size()); ++index) {
        out_stream << values[index];
        if (index + 1 != static_cast<int>(values.size())) {
            out_stream << ' ';
        }
    }
    out_stream << std::endl;
}

void write_beat_hex(const std::vector<ap_uint<32>> &beats, std::ostream &out_stream) {
    for (int index = 0; index < static_cast<int>(beats.size()); ++index) {
        out_stream << std::hex << beats[index].to_uint() << std::dec;
        if (index + 1 != static_cast<int>(beats.size())) {
            out_stream << ' ';
        }
    }
    out_stream << std::endl;
}

} // namespace

int main() {
    std::ifstream input_file("tb_data/tb_input_features.dat");
    std::ifstream prediction_file("tb_data/tb_output_predictions.dat");

    #ifdef RTL_SIM
        std::string result_path = "tb_data/rtl_cosim_results.log";
        std::string beats_path = "tb_data/rtl_cosim_beats.log";
    #else
        std::string result_path = "tb_data/csim_results.log";
        std::string beats_path = "tb_data/csim_axis_beats.log";
    #endif

    std::ofstream result_file(result_path);
    std::ofstream beats_file(beats_path);
    std::string input_line;
    std::string prediction_line;
    int sample_index = 0;

    if (input_file.is_open() && prediction_file.is_open()) {
        while (std::getline(input_file, input_line) && std::getline(prediction_file, prediction_line)) {
            if (sample_index %% 5000 == 0) {
                std::cout << "Processing input " << sample_index << std::endl;
            }

            std::vector<float> input_values = parse_line(input_line);
            if (static_cast<int>(input_values.size()) != kInputWords) {
                std::cerr << "Unexpected input width in testbench." << std::endl;
                return 1;
            }

            hls::stream<input_axi_t> input_stream("input_stream");
            hls::stream<output_axi_t> output_stream("output_stream");
            write_input_stream(input_values, input_stream);
            myproject_axi(input_stream, output_stream);
            GapCsimResult out = collect_output_stream(output_stream);
            write_gap_values(out.gap, result_file);
            write_beat_hex(out.beats, beats_file);
            sample_index++;
        }
    } else {
        std::cout << "INFO: Unable to open input/predictions file, using zero input." << std::endl;
        std::vector<float> input_values(kInputWords, 0.0f);
        hls::stream<input_axi_t> input_stream("input_stream");
        hls::stream<output_axi_t> output_stream("output_stream");
        write_input_stream(input_values, input_stream);
        myproject_axi(input_stream, output_stream);
        GapCsimResult out = collect_output_stream(output_stream);
        write_gap_values(out.gap, std::cout);
        write_gap_values(out.gap, result_file);
        write_beat_hex(out.beats, beats_file);
    }

    return 0;
}
''' % {
            'input_words_expr': str(n_in),
            'output_words_expr': use_out_macro if use_out_macro else str(n_out),
            'in_w': in_w,
            'in_i': in_i,
            'in_ap': in_ap,
            'input_scale': in_scale,
            'out_w': out_w,
            'out_i': out_i,
            'out_ap': out_ap,
        }
        cpp = cpp.replace('sample_index %% 5000', 'sample_index % 5000')
        OUT_CPP.write_text(cpp, encoding='utf-8')
        print(
            'Patched %s: serial kOutputWords=%d input=%s<%d,%d> scale=%d result=%s<%d,%d>'
            % (OUT_CPP, n_out, in_ap, in_w, in_i, in_scale, out_ap, out_w, out_i)
        )
        return 0

    """
        # This is too invasive - let me do a simpler approach in the patch script
        pass

    print('done')


if __name__ == '__main__':
    main()
