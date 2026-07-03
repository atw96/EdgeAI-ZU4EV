#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "firmware/myproject_axi.h"

namespace {

constexpr int kInputWords = N_INPUT_1_1 * N_INPUT_2_1 * N_INPUT_3_1;
constexpr int kOutputWords = N_LAYER_21;

ap_uint<16> float_to_fixed_bits(float value) {
    ap_fixed<16, 6> fixed_value = value;
    return fixed_value.range(15, 0);
}

float fixed_bits_to_float(ap_uint<16> bits) {
    ap_fixed<16, 6> fixed_value;
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
        axis_word.data = float_to_fixed_bits(values[index]);
        axis_word.keep = -1;
        axis_word.strb = -1;
        axis_word.last = (index == (kInputWords - 1)) ? 1 : 0;
        input_stream.write(axis_word);
    }
}

std::vector<float> collect_output_stream(hls::stream<output_axi_t> &output_stream) {
    std::vector<float> values;
    values.reserve(kOutputWords);
    for (int index = 0; index < kOutputWords; ++index) {
        output_axi_t axis_word = output_stream.read();
        values.push_back(fixed_bits_to_float(axis_word.data));
    }
    return values;
}

void write_output_values(const std::vector<float> &values, std::ostream &out_stream) {
    for (int index = 0; index < static_cast<int>(values.size()); ++index) {
        out_stream << values[index];
        if (index + 1 != static_cast<int>(values.size())) {
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
    #else
        std::string result_path = "tb_data/csim_results.log";
    #endif

    std::ofstream result_file(result_path);
    std::string input_line;
    std::string prediction_line;
    int sample_index = 0;

    if (input_file.is_open() && prediction_file.is_open()) {
        while (std::getline(input_file, input_line) && std::getline(prediction_file, prediction_line)) {
            if (sample_index % 5000 == 0) {
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
            std::vector<float> outputs = collect_output_stream(output_stream);
            write_output_values(outputs, result_file);
            sample_index++;
        }
    } else {
        std::cout << "INFO: Unable to open input/predictions file, using zero input." << std::endl;
        std::vector<float> input_values(kInputWords, 0.0f);
        hls::stream<input_axi_t> input_stream("input_stream");
        hls::stream<output_axi_t> output_stream("output_stream");
        write_input_stream(input_values, input_stream);
        myproject_axi(input_stream, output_stream);
        std::vector<float> outputs = collect_output_stream(output_stream);
        write_output_values(outputs, std::cout);
        write_output_values(outputs, result_file);
    }

    return 0;
}
