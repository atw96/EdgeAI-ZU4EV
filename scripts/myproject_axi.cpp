#include "myproject_axi.h"

namespace {

constexpr int kInputChannels = N_INPUT_3_1;
constexpr int kInputWords = N_INPUT_1_1 * N_INPUT_2_1 * N_INPUT_3_1;
constexpr int kGroupedInputWords = kInputWords / kInputChannels;
constexpr int kOutputWords = N_LAYER_21;

ap_fixed<16, 6> bits_to_fixed(ap_uint<16> bits) {
    ap_fixed<16, 6> value;
    value.range(15, 0) = bits;
    return value;
}

ap_uint<16> fixed_to_bits(ap_fixed<16, 6> value) {
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
            packet[channel_index] = bits_to_fixed(axis_word.data);
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
        axis_word.data = fixed_to_bits(packet[word_index]);
        axis_word.keep = -1;
        axis_word.strb = -1;
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
