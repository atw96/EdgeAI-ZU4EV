#ifndef DEFINES_H_
#define DEFINES_H_

#include "ap_fixed.h"
#include "ap_int.h"
#include "nnet_utils/nnet_types.h"
#include <array>
#include <cstddef>
#include <cstdio>
#include <tuple>
#include <tuple>


// hls-fpga-machine-learning insert numbers

// hls-fpga-machine-learning insert layer-precision
typedef nnet::array<ap_fixed<16,6>, 3*1> input_t;
typedef nnet::array<ap_fixed<6,1,AP_RND,AP_SAT,0>, 3*1> layer2_t;
typedef ap_fixed<18,8> input_qact_table_t;
typedef nnet::array<ap_fixed<6,1,AP_RND,AP_SAT,0>, 3*1> layer36_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> conv1a_accum_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 16*1> layer3_t;
typedef ap_fixed<6,1> weight3_t;
typedef ap_uint<1> bias3_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 16*1> layer5_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv1a_scale_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv1a_bias_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 16*1> layer6_t;
typedef ap_fixed<18,8> relu_conv1a_table_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 16*1> layer37_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> conv1b_accum_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 16*1> layer7_t;
typedef ap_fixed<6,1> weight7_t;
typedef ap_uint<1> bias7_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 16*1> layer9_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv1b_scale_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv1b_bias_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 16*1> layer10_t;
typedef ap_fixed<18,8> relu_conv1b_table_t;
typedef ap_fixed<16,6> model_default_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 16*1> layer11_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 16*1> layer38_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> conv2a_accum_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 32*1> layer12_t;
typedef ap_fixed<6,1> weight12_t;
typedef ap_uint<1> bias12_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 32*1> layer14_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv2a_scale_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv2a_bias_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 32*1> layer15_t;
typedef ap_fixed<18,8> relu_conv2a_table_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 32*1> layer39_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> conv2b_accum_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 32*1> layer16_t;
typedef ap_fixed<6,1> weight16_t;
typedef ap_uint<1> bias16_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 32*1> layer18_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv2b_scale_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv2b_bias_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 32*1> layer19_t;
typedef ap_fixed<18,8> relu_conv2b_table_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 32*1> layer20_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 32*1> layer40_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> conv3a_accum_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 64*1> layer21_t;
typedef ap_fixed<6,1> weight21_t;
typedef ap_uint<1> bias21_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 64*1> layer23_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv3a_scale_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv3a_bias_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 64*1> layer24_t;
typedef ap_fixed<18,8> relu_conv3a_table_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 64*1> layer41_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> conv3b_accum_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 64*1> layer25_t;
typedef ap_fixed<6,1> weight25_t;
typedef ap_uint<1> bias25_t;
typedef nnet::array<ap_fixed<16,8,AP_RND_CONV,AP_SAT,0>, 64*1> layer27_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv3b_scale_t;
typedef ap_fixed<16,8,AP_RND_CONV,AP_SAT,0> bn_conv3b_bias_t;
typedef nnet::array<ap_ufixed<6,2,AP_RND_CONV,AP_SAT,0>, 64*1> layer28_t;
typedef ap_fixed<18,8> relu_conv3b_table_t;
typedef ap_ufixed<18,8,AP_RND_CONV,AP_SAT,0> gap_accum_t;
typedef nnet::array<ap_ufixed<12,2,AP_RND_CONV,AP_SAT,0>, 64*1> result_t;

// hls-fpga-machine-learning insert emulator-defines


#endif
