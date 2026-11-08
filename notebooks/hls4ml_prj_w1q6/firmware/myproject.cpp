#include <iostream>

#include "myproject.h"
#include "parameters.h"


void myproject(
    hls::stream<input_t> &input_image,
    hls::stream<result_t> &layer29_out
) {

    // hls-fpga-machine-learning insert IO
    #pragma HLS INTERFACE axis port=input_image,layer29_out 
    #pragma HLS DATAFLOW

    // hls-fpga-machine-learning insert load weights
#ifndef __SYNTHESIS__
    static bool loaded_weights = false;
    if (!loaded_weights) {
        nnet::load_weights_from_txt<weight3_t, 432>(w3, "w3.txt");
        nnet::load_weights_from_txt<bias3_t, 16>(b3, "b3.txt");
        nnet::load_weights_from_txt<bn_conv1a_scale_t, 16>(s5, "s5.txt");
        nnet::load_weights_from_txt<bn_conv1a_bias_t, 16>(b5, "b5.txt");
        nnet::load_weights_from_txt<weight7_t, 2304>(w7, "w7.txt");
        nnet::load_weights_from_txt<bias7_t, 16>(b7, "b7.txt");
        nnet::load_weights_from_txt<bn_conv1b_scale_t, 16>(s9, "s9.txt");
        nnet::load_weights_from_txt<bn_conv1b_bias_t, 16>(b9, "b9.txt");
        nnet::load_weights_from_txt<weight12_t, 4608>(w12, "w12.txt");
        nnet::load_weights_from_txt<bias12_t, 32>(b12, "b12.txt");
        nnet::load_weights_from_txt<bn_conv2a_scale_t, 32>(s14, "s14.txt");
        nnet::load_weights_from_txt<bn_conv2a_bias_t, 32>(b14, "b14.txt");
        nnet::load_weights_from_txt<weight16_t, 9216>(w16, "w16.txt");
        nnet::load_weights_from_txt<bias16_t, 32>(b16, "b16.txt");
        nnet::load_weights_from_txt<bn_conv2b_scale_t, 32>(s18, "s18.txt");
        nnet::load_weights_from_txt<bn_conv2b_bias_t, 32>(b18, "b18.txt");
        nnet::load_weights_from_txt<weight21_t, 18432>(w21, "w21.txt");
        nnet::load_weights_from_txt<bias21_t, 64>(b21, "b21.txt");
        nnet::load_weights_from_txt<bn_conv3a_scale_t, 64>(s23, "s23.txt");
        nnet::load_weights_from_txt<bn_conv3a_bias_t, 64>(b23, "b23.txt");
        nnet::load_weights_from_txt<weight25_t, 36864>(w25, "w25.txt");
        nnet::load_weights_from_txt<bias25_t, 64>(b25, "b25.txt");
        nnet::load_weights_from_txt<bn_conv3b_scale_t, 64>(s27, "s27.txt");
        nnet::load_weights_from_txt<bn_conv3b_bias_t, 64>(b27, "b27.txt");
        loaded_weights = true;    }
#endif
    // ****************************************
    // NETWORK INSTANTIATION
    // ****************************************

    // hls-fpga-machine-learning insert layers

    hls::stream<layer2_t> layer2_out("layer2_out");
    #pragma HLS STREAM variable=layer2_out depth=32

    hls::stream<layer36_t> layer36_out("layer36_out");
    #pragma HLS STREAM variable=layer36_out depth=32

    hls::stream<layer3_t> layer3_out("layer3_out");
    #pragma HLS STREAM variable=layer3_out depth=32

    hls::stream<layer5_t> layer5_out("layer5_out");
    #pragma HLS STREAM variable=layer5_out depth=32

    hls::stream<layer6_t> layer6_out("layer6_out");
    #pragma HLS STREAM variable=layer6_out depth=32

    hls::stream<layer37_t> layer37_out("layer37_out");
    #pragma HLS STREAM variable=layer37_out depth=32

    hls::stream<layer7_t> layer7_out("layer7_out");
    #pragma HLS STREAM variable=layer7_out depth=32

    hls::stream<layer9_t> layer9_out("layer9_out");
    #pragma HLS STREAM variable=layer9_out depth=32

    hls::stream<layer10_t> layer10_out("layer10_out");
    #pragma HLS STREAM variable=layer10_out depth=32

    hls::stream<layer11_t> layer11_out("layer11_out");
    #pragma HLS STREAM variable=layer11_out depth=16

    hls::stream<layer38_t> layer38_out("layer38_out");
    #pragma HLS STREAM variable=layer38_out depth=16

    hls::stream<layer12_t> layer12_out("layer12_out");
    #pragma HLS STREAM variable=layer12_out depth=16

    hls::stream<layer14_t> layer14_out("layer14_out");
    #pragma HLS STREAM variable=layer14_out depth=16

    hls::stream<layer15_t> layer15_out("layer15_out");
    #pragma HLS STREAM variable=layer15_out depth=16

    hls::stream<layer39_t> layer39_out("layer39_out");
    #pragma HLS STREAM variable=layer39_out depth=16

    hls::stream<layer16_t> layer16_out("layer16_out");
    #pragma HLS STREAM variable=layer16_out depth=16

    hls::stream<layer18_t> layer18_out("layer18_out");
    #pragma HLS STREAM variable=layer18_out depth=16

    hls::stream<layer19_t> layer19_out("layer19_out");
    #pragma HLS STREAM variable=layer19_out depth=16

    hls::stream<layer20_t> layer20_out("layer20_out");
    #pragma HLS STREAM variable=layer20_out depth=8

    hls::stream<layer40_t> layer40_out("layer40_out");
    #pragma HLS STREAM variable=layer40_out depth=8

    hls::stream<layer21_t> layer21_out("layer21_out");
    #pragma HLS STREAM variable=layer21_out depth=8

    hls::stream<layer23_t> layer23_out("layer23_out");
    #pragma HLS STREAM variable=layer23_out depth=8

    hls::stream<layer24_t> layer24_out("layer24_out");
    #pragma HLS STREAM variable=layer24_out depth=8

    hls::stream<layer41_t> layer41_out("layer41_out");
    #pragma HLS STREAM variable=layer41_out depth=8

    hls::stream<layer25_t> layer25_out("layer25_out");
    #pragma HLS STREAM variable=layer25_out depth=8

    hls::stream<layer27_t> layer27_out("layer27_out");
    #pragma HLS STREAM variable=layer27_out depth=8

    hls::stream<layer28_t> layer28_out("layer28_out");
    #pragma HLS STREAM variable=layer28_out depth=8

    nnet::linear<input_t, layer2_t, linear_config2>(input_image, layer2_out); // input_qact

    nnet::zeropad2d_cl<layer2_t, layer36_t, config36>(layer2_out, layer36_out); // zp2d_conv1a

    nnet::conv_2d_cl<layer36_t, layer3_t, config3>(layer36_out, layer3_out, w3, b3); // conv1a

    nnet::normalize<layer3_t, layer5_t, config5>(layer3_out, layer5_out, s5, b5); // bn_conv1a

    nnet::relu<layer5_t, layer6_t, relu_config6>(layer5_out, layer6_out); // relu_conv1a

    nnet::zeropad2d_cl<layer6_t, layer37_t, config37>(layer6_out, layer37_out); // zp2d_conv1b

    nnet::conv_2d_cl<layer37_t, layer7_t, config7>(layer37_out, layer7_out, w7, b7); // conv1b

    nnet::normalize<layer7_t, layer9_t, config9>(layer7_out, layer9_out, s9, b9); // bn_conv1b

    nnet::relu<layer9_t, layer10_t, relu_config10>(layer9_out, layer10_out); // relu_conv1b

    nnet::pooling2d_cl<layer10_t, layer11_t, config11>(layer10_out, layer11_out); // pool1

    nnet::zeropad2d_cl<layer11_t, layer38_t, config38>(layer11_out, layer38_out); // zp2d_conv2a

    nnet::conv_2d_cl<layer38_t, layer12_t, config12>(layer38_out, layer12_out, w12, b12); // conv2a

    nnet::normalize<layer12_t, layer14_t, config14>(layer12_out, layer14_out, s14, b14); // bn_conv2a

    nnet::relu<layer14_t, layer15_t, relu_config15>(layer14_out, layer15_out); // relu_conv2a

    nnet::zeropad2d_cl<layer15_t, layer39_t, config39>(layer15_out, layer39_out); // zp2d_conv2b

    nnet::conv_2d_cl<layer39_t, layer16_t, config16>(layer39_out, layer16_out, w16, b16); // conv2b

    nnet::normalize<layer16_t, layer18_t, config18>(layer16_out, layer18_out, s18, b18); // bn_conv2b

    nnet::relu<layer18_t, layer19_t, relu_config19>(layer18_out, layer19_out); // relu_conv2b

    nnet::pooling2d_cl<layer19_t, layer20_t, config20>(layer19_out, layer20_out); // pool2

    nnet::zeropad2d_cl<layer20_t, layer40_t, config40>(layer20_out, layer40_out); // zp2d_conv3a

    nnet::conv_2d_cl<layer40_t, layer21_t, config21>(layer40_out, layer21_out, w21, b21); // conv3a

    nnet::normalize<layer21_t, layer23_t, config23>(layer21_out, layer23_out, s23, b23); // bn_conv3a

    nnet::relu<layer23_t, layer24_t, relu_config24>(layer23_out, layer24_out); // relu_conv3a

    nnet::zeropad2d_cl<layer24_t, layer41_t, config41>(layer24_out, layer41_out); // zp2d_conv3b

    nnet::conv_2d_cl<layer41_t, layer25_t, config25>(layer41_out, layer25_out, w25, b25); // conv3b

    nnet::normalize<layer25_t, layer27_t, config27>(layer25_out, layer27_out, s27, b27); // bn_conv3b

    nnet::relu<layer27_t, layer28_t, relu_config28>(layer27_out, layer28_out); // relu_conv3b

    nnet::global_pooling2d_cl<layer28_t, result_t, config29>(layer28_out, layer29_out); // gap

}

