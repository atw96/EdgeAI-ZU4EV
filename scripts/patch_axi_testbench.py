#!/usr/bin/env python3
"""Regenerate myproject_axi_test.cpp for slot-packed GAP output (dynamic ap_fixed decode)."""
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HLS_DIR = REPO / 'notebooks' / 'hls4ml_prj'
DEFINES = HLS_DIR / 'firmware' / 'defines.h'
META = HLS_DIR / 'axi_wrapper_meta.json'
OUT_CPP = HLS_DIR / 'myproject_axi_test.cpp'

sys.path.insert(0, str(REPO / 'scripts'))
from slot32_layout import fmt_c_int_array, slot_beat_maps


def parse_ap_fixed_i(text, typedef_name):
    m = re.search(
        r'typedef nnet::array<ap_fixed<(\d+),\s*(\d+)>,\s*\d+\*1>\s+%s' % typedef_name,
        text,
    )
    if m:
        return int(m.group(1)), int(m.group(2))
    return (16, 6) if typedef_name == 'input_t' else (16, 8)


def parse_output_info(text):
    matches = re.findall(r'#define\s+(N_LAYER_\d+|N_FILT_\d+)\s+(\d+)', text)
    if matches:
        return int(matches[-1][1])
    m = re.search(
        r'typedef nnet::array<ap_fixed<\d+,\s*\d+>,\s*(\d+)\*1>\s+result_t',
        text,
    )
    if m:
        return int(m.group(1))
    raise RuntimeError('cannot parse output dim from defines.h')


def parse_input_words(text):
    m = re.search(r'#define\s+N_INPUT_1_1\s+(\d+)', text)
    if m:
        h = int(re.search(r'#define\s+N_INPUT_2_1\s+(\d+)', text).group(1))
        w = int(re.search(r'#define\s+N_INPUT_3_1\s+(\d+)', text).group(1))
        return int(m.group(1)) * h * w
    m = re.search(r'typedef nnet::array<ap_fixed<\d+,\s*\d+>,\s*(\d+)\*1>\s+input_t', text)
    if m:
        # CIFAR-10 default; hls4ml 1.x may omit N_INPUT_* macros
        return int(os.environ.get('HLS_INPUT_WORDS', '3072'))
    return int(os.environ.get('HLS_INPUT_WORDS', '3072'))


def main():
    if META.is_file():
        meta = json.loads(META.read_text(encoding='utf-8'))
        n_out = int(meta.get('n_outputs', 24))
        out_macro = meta.get('output_macro', 'N_FILT_28')
    else:
        text = DEFINES.read_text(encoding='utf-8')
        n_out = parse_output_info(text)
        out_macro = 'N_FILT_28'

    defines_text = DEFINES.read_text(encoding='utf-8') if DEFINES.is_file() else ''
    in_w, in_i = parse_ap_fixed_i(defines_text, 'input_t')
    out_w, out_i = parse_ap_fixed_i(defines_text, 'result_t')
    n_in = parse_input_words(defines_text)
    use_out_macro = out_macro if re.search(r'#define\s+%s\s' % re.escape(out_macro), defines_text) else None

    beat_lo, beat_hi, n_beats = slot_beat_maps(n_out)
    cpp = '''\
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "firmware/myproject_axi.h"

namespace {

constexpr int kInputWords = %(input_words_expr)s;
constexpr int kOutputWords = %(output_words_expr)s;
constexpr int kOutputBeats = %(n_beats)d;
constexpr int kBeatLo[%(n_beats)d] = %(beat_lo)s;
constexpr int kBeatHi[%(n_beats)d] = %(beat_hi)s;

ap_uint<16> input_float_to_bits(float value) {
    ap_fixed<%(in_w)d, %(in_i)d> fixed_value = value;
    return fixed_value.range(15, 0);
}

float gap_bits_to_float(ap_uint<16> bits) {
    ap_fixed<%(out_w)d, %(out_i)d> fixed_value;
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
    result.beats.reserve(kOutputBeats);
    for (int beat = 0; beat < kOutputBeats; ++beat) {
        output_axi_t axis_word = output_stream.read();
        result.beats.push_back(axis_word.data);
        const int lo = kBeatLo[beat];
        const int hi = kBeatHi[beat];
        if (lo >= 0) {
            result.gap[lo] = gap_bits_to_float(axis_word.data.range(15, 0));
        }
        if (hi >= 0) {
            result.gap[hi] = gap_bits_to_float(axis_word.data.range(31, 16));
        }
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
        'out_macro': out_macro,
        'n_beats': n_beats,
        'beat_lo': fmt_c_int_array(beat_lo),
        'beat_hi': fmt_c_int_array(beat_hi),
        'in_w': in_w,
        'in_i': in_i,
        'out_w': out_w,
        'out_i': out_i,
    }
    cpp = cpp.replace('sample_index %% 5000', 'sample_index % 5000')
    OUT_CPP.write_text(cpp, encoding='utf-8')
    print(
        'Patched %s: kOutputWords=%d input=ap_fixed<%d,%d> result=ap_fixed<%d,%d>'
        % (OUT_CPP, n_out, in_w, in_i, out_w, out_i)
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
