#!/usr/bin/env python3
"""Regenerate myproject_axi.cpp/.h using input_t/result_t types from defines.h."""
import json
import os
import re
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HLS_DIR = REPO / 'notebooks' / 'hls4ml_prj'
DEFINES = HLS_DIR / 'firmware' / 'defines.h'

sys.path.insert(0, str(REPO / 'scripts'))
from slot32_layout import fmt_c_int_array, slot32_out_bytes, slot_beat_maps


def parse_ap_fixed(typedef_line):
    m = re.search(r'ap_(?:fixed|ufixed)<(\d+)\s*,\s*(-?\d+)', typedef_line)
    if not m:
        raise RuntimeError('cannot parse ap_fixed from: %s' % typedef_line)
    return int(m.group(1)), int(m.group(2))


def find_input_typedef_line(text):
    for line in text.splitlines():
        if 'typedef' not in line:
            continue
        if re.search(r'\binput_image_t\b', line):
            return line
        if re.search(r'\binput_t\b', line) and 'input_axi' not in line:
            return line
    raise RuntimeError('no input_t / input_image_t typedef in defines.h')


def input_array_typedef_name(input_line):
    m = re.search(r'\b(input_image_t|input_t)\b\s*;', input_line)
    if m:
        return m.group(1)
    raise RuntimeError('cannot parse input array typedef name from: %s' % input_line)


def parse_input_dims(text):
    m1 = re.search(r'#define\s+N_INPUT_1_1\s+(\d+)', text)
    if m1:
        h = int(re.search(r'#define\s+N_INPUT_2_1\s+(\d+)', text).group(1))
        w = int(re.search(r'#define\s+N_INPUT_3_1\s+(\d+)', text).group(1))
        c = int(m1.group(1))
        return c * h * w, c
    channels = 3
    for name in ('input_image_t', 'input_t'):
        m = re.search(
            r'typedef nnet::array<ap_(?:fixed|ufixed)<[^>]+>,\s*(\d+)\*1>\s+' + name,
            text,
        )
        if m:
            channels = int(m.group(1))
            break
    words = int(os.environ.get('HLS_INPUT_WORDS', '3072'))
    return words, channels


def output_words_expr(output_macro, n_outputs, text):
    if re.search(r'#define\s+%s\s' % re.escape(output_macro), text):
        return output_macro
    return str(n_outputs)


def parse_output_macro(text):
    matches = re.findall(r'#define\s+(N_LAYER_\d+)\s+(\d+)', text)
    if matches:
        name, val = matches[-1]
        return name, int(val)
    m = re.search(
        r'typedef nnet::array<ap_(?:fixed|ufixed)<[^>]+>,\s*(\d+)\*1>\s+result_t',
        text,
    )
    if m:
        n = int(m.group(1))
        for fname, fval in reversed(
            re.findall(r'#define\s+(N_FILT_\d+)\s+(\d+)', text)
        ):
            if int(fval) == n:
                return fname, n
        return ('N_OUT_%d' % n, n)
    raise RuntimeError('no N_LAYER_* or result_t in defines.h')


def main():
    if not DEFINES.exists():
        print('ERROR: missing %s' % DEFINES, file=sys.stderr)
        return 1

    out_axis_bits = int(os.environ.get('OUTPUT_AXIS_BITS', '16'))
    pack_mode = os.environ.get('OUTPUT_PACK_MODE', 'pair').lower()
    use_dataflow = os.environ.get('AXI_DATAFLOW', '0') != '0'
    # DATAFLOW=0 runs axis->myproject->axis sequentially; deep FIFOs only
    # bloat synthesis (appears hung at conv unroll). depth=1024 needed only
    # when DATAFLOW=1 pipelines input feed with myproject.
    if use_dataflow:
        input_stream_depth = int(os.environ.get('AXI_INPUT_STREAM_DEPTH', '1024'))
        output_stream_depth = int(os.environ.get('AXI_OUTPUT_STREAM_DEPTH', '64'))
    else:
        # Sequential axis->myproject->axis still fills model_input (1024 packets)
        # before myproject reads; depth=2 deadlocks and S2MM never completes.
        input_stream_depth = int(os.environ.get('AXI_INPUT_STREAM_DEPTH', '1024'))
        output_stream_depth = int(os.environ.get('AXI_OUTPUT_STREAM_DEPTH', '64'))
    if out_axis_bits not in (16, 32):
        print('ERROR: OUTPUT_AXIS_BITS must be 16 or 32', file=sys.stderr)
        return 1
    if pack_mode not in ('pair', 'serial', 'slot'):
        print('ERROR: OUTPUT_PACK_MODE must be pair, serial, or slot', file=sys.stderr)
        return 1

    text = DEFINES.read_text(encoding='utf-8')
    input_line = find_input_typedef_line(text)
    input_array_typedef = input_array_typedef_name(input_line)
    result_line = next(
        l for l in text.splitlines()
        if re.search(r'\bresult_t\s*;', l) and 'typedef' in l
    )
    in_w, in_i = parse_ap_fixed(input_line)
    out_w, out_i = parse_ap_fixed(result_line)
    output_macro, n_outputs = parse_output_macro(text)
    input_words, input_channels = parse_input_dims(text)
    out_words = output_words_expr(output_macro, n_outputs, text)
    beat_lo, beat_hi, n_beats = slot_beat_maps(n_outputs)

    in_type = 'ap_fixed<%d, %d>' % (in_w, in_i)
    if 'ap_ufixed' in result_line:
        out_type = 'ap_ufixed<%d, %d>' % (out_w, out_i)
    else:
        out_type = 'ap_fixed<%d, %d>' % (out_w, out_i)
    in_scale = 1 << (in_w - in_i)
    out_scale = 1 << (out_w - out_i)
    bench_in_scale = int(os.environ.get('IN_FIXED_SCALE', '1024'))

    fw = HLS_DIR / 'firmware'
    if out_axis_bits == 32 and pack_mode == 'slot':
        # Pack two int16 logits per 32-bit beat on DMA-writable slots only
        # (beat indices 0,1,4,5,8); dummy beats on hole indices 2,3,6,7,9.
        header = textwrap.dedent('''\
            #ifndef MYPROJECT_AXI_H_
            #define MYPROJECT_AXI_H_

            #include "ap_axi_sdata.h"
            #include "ap_fixed.h"
            #include "hls_stream.h"

            #include "defines.h"
            #include "myproject.h"

            typedef ap_axiu<16, 0, 0, 0> input_axi_t;
            typedef ap_axiu<32, 0, 0, 0> output_axi_t;

            void myproject_axi(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<output_axi_t> &output_stream
            );

            #endif
        ''')
        cpp = textwrap.dedent('''\
            #include "myproject_axi.h"

            namespace {

            constexpr int kInputChannels = %(input_channels)d;
            constexpr int kInputWords = %(input_words)d;
            constexpr int kGroupedInputWords = kInputWords / kInputChannels;
            constexpr int kOutputWords = %(out_words)s;
            constexpr int kOutputBeats = %(n_beats)d;

            // DMA S2MM skips beat indices where (index %% 4) >= 2; pack pairs on writable beats.
            constexpr int kBeatLo[%(n_beats)d] = %(beat_lo)s;
            constexpr int kBeatHi[%(n_beats)d] = %(beat_hi)s;

            typedef %(in_type)s input_pix_t;
            typedef %(out_type)s output_pix_t;

            constexpr int kBenchInputScale = %(input_scale)d;

            input_pix_t bits_to_input(ap_uint<16> bits) {
                return input_pix_t(float((ap_int<16>)(bits)) / float(kBenchInputScale));
            }

            ap_uint<16> output_to_bits(output_pix_t value) {
                return value.range(15, 0);
            }

            void axis_to_model_stream(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<input_t> &model_input
            ) {
                for (int word_index = 0; word_index < kGroupedInputWords; ++word_index) {
                    #pragma HLS PIPELINE II=1
                    input_t packet;
                    for (int channel_index = 0; channel_index < kInputChannels; ++channel_index) {
                        input_axi_t axis_word = input_stream.read();
                        packet[channel_index] = bits_to_input(axis_word.data);
                    }
                    model_input.write(packet);
                }
            }

            void model_to_axis_stream(
                hls::stream<result_t> &model_output,
                hls::stream<output_axi_t> &output_stream
            ) {
                result_t packet = model_output.read();

                for (int beat = 0; beat < kOutputBeats; ++beat) {
                    #pragma HLS PIPELINE II=1
                    ap_uint<32> packed = 0;
                    const int lo = kBeatLo[beat];
                    const int hi = kBeatHi[beat];
                    if (lo >= 0) {
                        packed.range(15, 0) = output_to_bits(packet[lo]);
                    }
                    if (hi >= 0) {
                        packed.range(31, 16) = output_to_bits(packet[hi]);
                    }
                    output_axi_t axis_word;
                    axis_word.data = packed;
                    axis_word.keep = 0xF;
                    axis_word.strb = 0xF;
                    axis_word.last = (beat == (kOutputBeats - 1)) ? 1 : 0;
                    output_stream.write(axis_word);
                }
            }

            } // namespace

            void myproject_axi(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<output_axi_t> &output_stream
            ) {
                #pragma HLS INTERFACE axis port=input_stream
                #pragma HLS INTERFACE axis port=output_stream
                #pragma HLS INTERFACE ap_ctrl_none port=return
                %(dataflow_pragma)s

                hls::stream<input_t> model_input("model_input");
                hls::stream<result_t> model_output("model_output");
                #pragma HLS STREAM variable=model_input depth=%(input_stream_depth)d
                #pragma HLS STREAM variable=model_output depth=%(output_stream_depth)d

                axis_to_model_stream(input_stream, model_input);
                %(myproject_inline_guard)smyproject(model_input, model_output);
                model_to_axis_stream(model_output, output_stream);
            }
        ''') % {
            'input_channels': input_channels,
            'input_words': input_words,
            'out_words': out_words,
            'in_type': in_type,
            'out_type': out_type,
            'input_scale': bench_in_scale,
            'n_beats': n_beats,
            'beat_lo': fmt_c_int_array(beat_lo),
            'beat_hi': fmt_c_int_array(beat_hi),
            'dataflow_pragma': '#pragma HLS DATAFLOW' if use_dataflow else '',
            'myproject_inline_guard': (
                '#pragma HLS INLINE off\n                '
                if not use_dataflow else ''
            ),
            'input_stream_depth': input_stream_depth,
            'output_stream_depth': output_stream_depth,
        }
    elif out_axis_bits == 32 and pack_mode == 'serial':
        # One logit per 32-bit beat (10 beats / 40 B). Avoids DMA word-2/3 hole
        # that drops paired logits 4-7 when two int16 are packed per beat.
        header = textwrap.dedent('''\
            #ifndef MYPROJECT_AXI_H_
            #define MYPROJECT_AXI_H_

            #include "ap_axi_sdata.h"
            #include "ap_fixed.h"
            #include "hls_stream.h"

            #include "defines.h"
            #include "myproject.h"

            typedef ap_axiu<16, 0, 0, 0> input_axi_t;
            typedef ap_axiu<32, 0, 0, 0> output_axi_t;

            void myproject_axi(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<output_axi_t> &output_stream
            );

            #endif
        ''')
        cpp = textwrap.dedent('''\
            #include "myproject_axi.h"

            namespace {

            constexpr int kInputChannels = %(input_channels)d;
            constexpr int kInputWords = %(input_words)d;
            constexpr int kGroupedInputWords = kInputWords / kInputChannels;
            constexpr int kOutputWords = %(out_words)s;

            typedef %(in_type)s input_pix_t;
            typedef %(out_type)s output_pix_t;

            constexpr int kBenchInputScale = %(input_scale)d;

            input_pix_t bits_to_input(ap_uint<16> bits) {
                return input_pix_t(float((ap_int<16>)(bits)) / float(kBenchInputScale));
            }

            ap_uint<16> output_to_bits(output_pix_t value) {
                return value.range(15, 0);
            }

            void axis_to_model_stream(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<input_t> &model_input
            ) {
                for (int word_index = 0; word_index < kGroupedInputWords; ++word_index) {
                    #pragma HLS PIPELINE II=1
                    input_t packet;
                    for (int channel_index = 0; channel_index < kInputChannels; ++channel_index) {
                        input_axi_t axis_word = input_stream.read();
                        packet[channel_index] = bits_to_input(axis_word.data);
                    }
                    model_input.write(packet);
                }
            }

            void model_to_axis_stream(
                hls::stream<result_t> &model_output,
                hls::stream<output_axi_t> &output_stream
            ) {
                result_t packet = model_output.read();

                for (int idx = 0; idx < kOutputWords; ++idx) {
                    #pragma HLS PIPELINE II=1
                    output_axi_t axis_word;
                    axis_word.data = output_to_bits(packet[idx]);
                    axis_word.keep = 0xF;
                    axis_word.strb = 0xF;
                    axis_word.last = (idx == (kOutputWords - 1)) ? 1 : 0;
                    output_stream.write(axis_word);
                }
            }

            } // namespace

            void myproject_axi(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<output_axi_t> &output_stream
            ) {
                #pragma HLS INTERFACE axis port=input_stream
                #pragma HLS INTERFACE axis port=output_stream
                #pragma HLS INTERFACE ap_ctrl_none port=return
                #pragma HLS DATAFLOW

                hls::stream<input_t> model_input("model_input");
                hls::stream<result_t> model_output("model_output");
                #pragma HLS STREAM variable=model_input depth=4
                #pragma HLS STREAM variable=model_output depth=2

                axis_to_model_stream(input_stream, model_input);
                myproject(model_input, model_output);
                model_to_axis_stream(model_output, output_stream);
            }
        ''') % {
            'input_channels': input_channels,
            'input_words': input_words,
            'out_words': out_words,
            'in_type': in_type,
            'out_type': out_type,
            'input_scale': bench_in_scale,
        }
    elif out_axis_bits == 32:
        header = textwrap.dedent('''\
            #ifndef MYPROJECT_AXI_H_
            #define MYPROJECT_AXI_H_

            #include "ap_axi_sdata.h"
            #include "ap_fixed.h"
            #include "hls_stream.h"

            #include "defines.h"
            #include "myproject.h"

            typedef ap_axiu<16, 0, 0, 0> input_axi_t;
            typedef ap_axiu<32, 0, 0, 0> output_axi_t;

            void myproject_axi(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<output_axi_t> &output_stream
            );

            #endif
        ''')
        cpp = textwrap.dedent('''\
            #include "myproject_axi.h"

            namespace {

            constexpr int kInputChannels = %(input_channels)d;
            constexpr int kInputWords = %(input_words)d;
            constexpr int kGroupedInputWords = kInputWords / kInputChannels;
            constexpr int kOutputWords = %(out_words)s;
            constexpr int kOutputBeats = (kOutputWords + 1) / 2;

            typedef %(in_type)s input_pix_t;
            typedef %(out_type)s output_pix_t;

            constexpr int kBenchInputScale = %(input_scale)d;

            input_pix_t bits_to_input(ap_uint<16> bits) {
                return input_pix_t(float((ap_int<16>)(bits)) / float(kBenchInputScale));
            }

            ap_uint<16> output_to_bits(output_pix_t value) {
                return value.range(15, 0);
            }

            void axis_to_model_stream(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<input_t> &model_input
            ) {
                for (int word_index = 0; word_index < kGroupedInputWords; ++word_index) {
                    #pragma HLS PIPELINE II=1
                    input_t packet;
                    for (int channel_index = 0; channel_index < kInputChannels; ++channel_index) {
                        input_axi_t axis_word = input_stream.read();
                        packet[channel_index] = bits_to_input(axis_word.data);
                    }
                    model_input.write(packet);
                }
            }

            void model_to_axis_stream(
                hls::stream<result_t> &model_output,
                hls::stream<output_axi_t> &output_stream
            ) {
                result_t packet = model_output.read();

                for (int beat_index = 0; beat_index < kOutputBeats; ++beat_index) {
                    #pragma HLS PIPELINE II=1
                    const int lo = beat_index * 2;
                    const int hi = lo + 1;
                    ap_uint<32> packed = 0;
                    packed.range(15, 0) = output_to_bits(packet[lo]);
                    if (hi < kOutputWords) {
                        packed.range(31, 16) = output_to_bits(packet[hi]);
                    }
                    output_axi_t axis_word;
                    axis_word.data = packed;
                    axis_word.keep = 0xF;
                    axis_word.strb = 0xF;
                    axis_word.last = (beat_index == (kOutputBeats - 1)) ? 1 : 0;
                    output_stream.write(axis_word);
                }
            }

            } // namespace

            void myproject_axi(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<output_axi_t> &output_stream
            ) {
                #pragma HLS INTERFACE axis port=input_stream
                #pragma HLS INTERFACE axis port=output_stream
                #pragma HLS INTERFACE ap_ctrl_none port=return
                #pragma HLS DATAFLOW

                hls::stream<input_t> model_input("model_input");
                hls::stream<result_t> model_output("model_output");
                #pragma HLS STREAM variable=model_input depth=4
                #pragma HLS STREAM variable=model_output depth=2

                axis_to_model_stream(input_stream, model_input);
                myproject(model_input, model_output);
                model_to_axis_stream(model_output, output_stream);
            }
        ''') % {
            'input_channels': input_channels,
            'input_words': input_words,
            'out_words': out_words,
            'in_type': in_type,
            'out_type': out_type,
            'input_scale': bench_in_scale,
        }
    else:
        header = textwrap.dedent('''\
            #ifndef MYPROJECT_AXI_H_
            #define MYPROJECT_AXI_H_

            #include "ap_axi_sdata.h"
            #include "ap_fixed.h"
            #include "hls_stream.h"

            #include "defines.h"
            #include "myproject.h"

            typedef ap_axiu<16, 0, 0, 0> input_axi_t;
            typedef ap_axiu<16, 0, 0, 0> output_axi_t;

            void myproject_axi(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<output_axi_t> &output_stream
            );

            #endif
        ''')
        cpp = textwrap.dedent('''\
            #include "myproject_axi.h"

            namespace {

            constexpr int kInputChannels = %(input_channels)d;
            constexpr int kInputWords = %(input_words)d;
            constexpr int kGroupedInputWords = kInputWords / kInputChannels;
            constexpr int kOutputWords = %(out_words)s;

            typedef %(in_type)s input_pix_t;
            typedef %(out_type)s output_pix_t;

            constexpr int kBenchInputScale = %(input_scale)d;

            input_pix_t bits_to_input(ap_uint<16> bits) {
                return input_pix_t(float((ap_int<16>)(bits)) / float(kBenchInputScale));
            }

            ap_uint<16> output_to_bits(output_pix_t value) {
                return value.range(15, 0);
            }

            void axis_to_model_stream(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<input_t> &model_input
            ) {
                for (int word_index = 0; word_index < kGroupedInputWords; ++word_index) {
                    #pragma HLS PIPELINE II=1
                    input_t packet;
                    for (int channel_index = 0; channel_index < kInputChannels; ++channel_index) {
                        input_axi_t axis_word = input_stream.read();
                        packet[channel_index] = bits_to_input(axis_word.data);
                    }
                    model_input.write(packet);
                }
            }

            void model_to_axis_stream(
                hls::stream<result_t> &model_output,
                hls::stream<output_axi_t> &output_stream
            ) {
                result_t packet = model_output.read();

                for (int word_index = 0; word_index < kOutputWords; ++word_index) {
                    #pragma HLS PIPELINE II=1
                    output_axi_t axis_word;
                    axis_word.data = output_to_bits(packet[word_index]);
                    axis_word.keep = 0x3;
                    axis_word.strb = 0x3;
                    axis_word.last = (word_index == (kOutputWords - 1)) ? 1 : 0;
                    output_stream.write(axis_word);
                }
            }

            } // namespace

            void myproject_axi(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<output_axi_t> &output_stream
            ) {
                #pragma HLS INTERFACE axis port=input_stream
                #pragma HLS INTERFACE axis port=output_stream
                #pragma HLS INTERFACE ap_ctrl_none port=return
                #pragma HLS DATAFLOW

                hls::stream<input_t> model_input("model_input");
                hls::stream<result_t> model_output("model_output");
                #pragma HLS STREAM variable=model_input depth=4
                #pragma HLS STREAM variable=model_output depth=2

                axis_to_model_stream(input_stream, model_input);
                myproject(model_input, model_output);
                model_to_axis_stream(model_output, output_stream);
            }
        ''') % {
            'input_channels': input_channels,
            'input_words': input_words,
            'out_words': out_words,
            'in_type': in_type,
            'out_type': out_type,
            'input_scale': bench_in_scale,
        }

    if not use_dataflow and out_axis_bits == 32 and pack_mode in ('slot', 'serial'):
        # Sequential top without DATAFLOW: isolate axis<->myproject in a
        # non-inlined helper so csynth does not monolith LLVM-opt the full net.
        sequential_helper = textwrap.dedent(
            '''
            void run_axi_sequential(
                hls::stream<input_axi_t> &input_stream,
                hls::stream<output_axi_t> &output_stream
            ) {
                #pragma HLS INLINE off
                hls::stream<input_t> model_input("model_input");
                hls::stream<result_t> model_output("model_output");
                #pragma HLS STREAM variable=model_input depth=%(input_stream_depth)d
                #pragma HLS STREAM variable=model_output depth=%(output_stream_depth)d

                axis_to_model_stream(input_stream, model_input);
                myproject(model_input, model_output);
                model_to_axis_stream(model_output, output_stream);
            }
            '''
        ) % {
            'input_stream_depth': input_stream_depth,
            'output_stream_depth': output_stream_depth,
        }
        cpp = cpp.replace(
            '            } // namespace',
            sequential_helper + '\n            } // namespace',
            1,
        )
        inline_block = textwrap.dedent(
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
                '#pragma HLS INLINE off\n                '
                if not use_dataflow else ''
            ),
        }
        cpp = cpp.replace(
            inline_block,
            '                run_axi_sequential(input_stream, output_stream);\n',
            1,
        )

    if input_array_typedef != 'input_t':
        cpp = cpp.replace('hls::stream<input_t>', 'hls::stream<%s>' % input_array_typedef)
        cpp = cpp.replace('input_t packet', '%s packet' % input_array_typedef)

    (fw / 'myproject_axi.h').write_text(header, encoding='utf-8')
    (fw / 'myproject_axi.cpp').write_text(cpp, encoding='utf-8')

    meta = HLS_DIR / 'axi_wrapper_meta.json'
    meta.write_text(json.dumps({
        'input_type': in_type,
        'result_type': out_type,
        'input_scale': in_scale,
        'bench_input_scale': bench_in_scale,
        'output_scale': out_scale,
        'output_macro': output_macro,
        'output_axis_bits': out_axis_bits,
        'output_pack_mode': pack_mode,
        'out_bytes': (
            n_outputs * 4 if (out_axis_bits == 32 and pack_mode == 'serial')
            else slot32_out_bytes(n_outputs) if (
                out_axis_bits == 32 and pack_mode == 'slot'
            ) else 20
        ),
        'n_outputs': n_outputs,
    }, indent=2), encoding='utf-8')

    myproject_cpp = fw / 'myproject.cpp'
    mtext = myproject_cpp.read_text(encoding='utf-8')
    guard = '#pragma HLS INLINE off'
    if not use_dataflow and guard not in mtext:
        m_proj = re.search(
            r'(void myproject\(\s*hls::stream<\w+> &input_image,\s*'
            r'hls::stream<result_t> &layer\d+_out\s*\) \{)\s*\n\s*// hls-fpga-machine-learning insert IO',
            mtext,
        )
        if m_proj:
            needle = m_proj.group(0)
            mtext = mtext.replace(
                needle,
                needle.replace('\n    //', '\n\n    %s\n    //' % guard, 1),
                1,
            )
            myproject_cpp.write_text(mtext, encoding='utf-8')
            print('Patched myproject.cpp: INLINE off (csynth guard)')

    print(
        'Patched AXI wrapper: input=%s (/%d) output=%s (/%d) axis_out=%d-bit pack=%s '
        'dataflow=%s in_depth=%d out_depth=%d'
        % (in_type, in_scale, out_type, out_scale, out_axis_bits, pack_mode,
           use_dataflow, input_stream_depth, output_stream_depth)
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
