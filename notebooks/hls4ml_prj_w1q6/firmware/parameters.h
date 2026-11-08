#ifndef PARAMETERS_H_
#define PARAMETERS_H_

#include "ap_fixed.h"
#include "ap_int.h"

#include "nnet_utils/nnet_code_gen.h"
#include "nnet_utils/nnet_helpers.h"
// hls-fpga-machine-learning insert includes
#include "nnet_utils/nnet_activation.h"
#include "nnet_utils/nnet_activation_stream.h"
#include "nnet_utils/nnet_batchnorm.h"
#include "nnet_utils/nnet_batchnorm_stream.h"
#include "nnet_utils/nnet_conv2d.h"
#include "nnet_utils/nnet_conv2d_stream.h"
#include "nnet_utils/nnet_padding.h"
#include "nnet_utils/nnet_padding_stream.h"
#include "nnet_utils/nnet_pooling.h"
#include "nnet_utils/nnet_pooling_stream.h"

// hls-fpga-machine-learning insert weights
#include "weights/w3.h"
#include "weights/b3.h"
#include "weights/s5.h"
#include "weights/b5.h"
#include "weights/w7.h"
#include "weights/b7.h"
#include "weights/s9.h"
#include "weights/b9.h"
#include "weights/w12.h"
#include "weights/b12.h"
#include "weights/s14.h"
#include "weights/b14.h"
#include "weights/w16.h"
#include "weights/b16.h"
#include "weights/s18.h"
#include "weights/b18.h"
#include "weights/w21.h"
#include "weights/b21.h"
#include "weights/s23.h"
#include "weights/b23.h"
#include "weights/w25.h"
#include "weights/b25.h"
#include "weights/s27.h"
#include "weights/b27.h"


// hls-fpga-machine-learning insert layer-config
// input_qact
struct linear_config2 : nnet::activ_config {
    static const unsigned n_in = 3072;
    static const unsigned table_size = 1024;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    typedef input_qact_table_t table_t;
};

// zp2d_conv1a
struct config36 : nnet::padding2d_config {
    static const unsigned in_height = 32;
    static const unsigned in_width = 32;
    static const unsigned n_chan = 3;
    static const unsigned out_height = 34;
    static const unsigned out_width = 34;
    static const unsigned pad_top = 1;
    static const unsigned pad_bottom = 1;
    static const unsigned pad_left = 1;
    static const unsigned pad_right = 1;
};

// conv1a
struct config3_mult : nnet::dense_config {
    static const unsigned n_in = 27;
    static const unsigned n_out = 16;
    static const unsigned reuse_factor = 27;
    static const unsigned strategy = nnet::resource;
    static const unsigned n_zeros = 17;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in * n_out, reuse_factor) - n_zeros / reuse_factor;
    typedef conv1a_accum_t accum_t;
    typedef bias3_t bias_t;
    typedef weight3_t weight_t;
    template<class data_T, class res_T, class CONFIG_T>
    using kernel = nnet::DenseResource_rf_leq_nin<data_T, res_T, CONFIG_T>;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

struct config3 : nnet::conv2d_config {
    static const unsigned pad_top = 0;
    static const unsigned pad_bottom = 0;
    static const unsigned pad_left = 0;
    static const unsigned pad_right = 0;
    static const unsigned in_height = 34;
    static const unsigned in_width = 34;
    static const unsigned n_chan = 3;
    static const unsigned filt_height = 3;
    static const unsigned filt_width = 3;
    static const unsigned kernel_size = filt_height * filt_width;
    static const unsigned n_filt = 16;
    static const unsigned stride_height = 1;
    static const unsigned stride_width = 1;
    static const unsigned out_height = 32;
    static const unsigned out_width = 32;
    static const unsigned reuse_factor = 27;
    static const unsigned n_zeros = 17;
    static const unsigned multiplier_limit =
        DIV_ROUNDUP(kernel_size * n_chan * n_filt, reuse_factor) - n_zeros / reuse_factor;
    static const bool store_weights_in_bram = false;
    static const unsigned strategy = nnet::resource;
    static const nnet::conv_implementation implementation = nnet::conv_implementation::linebuffer;
    static const unsigned min_height = 34;
    static const unsigned min_width = 34;
    static const ap_uint<filt_height * filt_width> pixels[min_height * min_width];
    static const unsigned n_partitions = 1024;
    static const unsigned n_pixels = out_height * out_width / n_partitions;
    template<class data_T, class CONFIG_T>
    using fill_buffer = nnet::FillConv2DBuffer<data_T, CONFIG_T>;
    typedef conv1a_accum_t accum_t;
    typedef bias3_t bias_t;
    typedef weight3_t weight_t;
    typedef config3_mult mult_config;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_height = nnet::scale_index_regular<K, S, W>;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_width = nnet::scale_index_regular<K, S, W>;
};
const ap_uint<config3::filt_height * config3::filt_width> config3::pixels[] = {0};

// bn_conv1a
struct config5 : nnet::batchnorm_config {
    static const unsigned n_in = 32*32*16;
    static const unsigned n_filt = 16;
    static const unsigned n_scale_bias = (n_filt == -1) ? n_in : n_filt;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in, reuse_factor);
    static const bool store_weights_in_bram = false;
    typedef bn_conv1a_bias_t bias_t;
    typedef bn_conv1a_scale_t scale_t;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

// relu_conv1a
struct relu_config6 : nnet::activ_config {
    static const unsigned n_in = 16384;
    static const unsigned table_size = 1024;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    typedef relu_conv1a_table_t table_t;
};

// zp2d_conv1b
struct config37 : nnet::padding2d_config {
    static const unsigned in_height = 32;
    static const unsigned in_width = 32;
    static const unsigned n_chan = 16;
    static const unsigned out_height = 34;
    static const unsigned out_width = 34;
    static const unsigned pad_top = 1;
    static const unsigned pad_bottom = 1;
    static const unsigned pad_left = 1;
    static const unsigned pad_right = 1;
};

// conv1b
struct config7_mult : nnet::dense_config {
    static const unsigned n_in = 144;
    static const unsigned n_out = 16;
    static const unsigned reuse_factor = 72;
    static const unsigned strategy = nnet::resource;
    static const unsigned n_zeros = 125;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in * n_out, reuse_factor) - n_zeros / reuse_factor;
    typedef conv1b_accum_t accum_t;
    typedef bias7_t bias_t;
    typedef weight7_t weight_t;
    template<class data_T, class res_T, class CONFIG_T>
    using kernel = nnet::DenseResource_rf_leq_nin<data_T, res_T, CONFIG_T>;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

struct config7 : nnet::conv2d_config {
    static const unsigned pad_top = 0;
    static const unsigned pad_bottom = 0;
    static const unsigned pad_left = 0;
    static const unsigned pad_right = 0;
    static const unsigned in_height = 34;
    static const unsigned in_width = 34;
    static const unsigned n_chan = 16;
    static const unsigned filt_height = 3;
    static const unsigned filt_width = 3;
    static const unsigned kernel_size = filt_height * filt_width;
    static const unsigned n_filt = 16;
    static const unsigned stride_height = 1;
    static const unsigned stride_width = 1;
    static const unsigned out_height = 32;
    static const unsigned out_width = 32;
    static const unsigned reuse_factor = 72;
    static const unsigned n_zeros = 125;
    static const unsigned multiplier_limit =
        DIV_ROUNDUP(kernel_size * n_chan * n_filt, reuse_factor) - n_zeros / reuse_factor;
    static const bool store_weights_in_bram = false;
    static const unsigned strategy = nnet::resource;
    static const nnet::conv_implementation implementation = nnet::conv_implementation::linebuffer;
    static const unsigned min_height = 34;
    static const unsigned min_width = 34;
    static const ap_uint<filt_height * filt_width> pixels[min_height * min_width];
    static const unsigned n_partitions = 1024;
    static const unsigned n_pixels = out_height * out_width / n_partitions;
    template<class data_T, class CONFIG_T>
    using fill_buffer = nnet::FillConv2DBuffer<data_T, CONFIG_T>;
    typedef conv1b_accum_t accum_t;
    typedef bias7_t bias_t;
    typedef weight7_t weight_t;
    typedef config7_mult mult_config;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_height = nnet::scale_index_regular<K, S, W>;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_width = nnet::scale_index_regular<K, S, W>;
};
const ap_uint<config7::filt_height * config7::filt_width> config7::pixels[] = {0};

// bn_conv1b
struct config9 : nnet::batchnorm_config {
    static const unsigned n_in = 32*32*16;
    static const unsigned n_filt = 16;
    static const unsigned n_scale_bias = (n_filt == -1) ? n_in : n_filt;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in, reuse_factor);
    static const bool store_weights_in_bram = false;
    typedef bn_conv1b_bias_t bias_t;
    typedef bn_conv1b_scale_t scale_t;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

// relu_conv1b
struct relu_config10 : nnet::activ_config {
    static const unsigned n_in = 16384;
    static const unsigned table_size = 1024;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    typedef relu_conv1b_table_t table_t;
};

// pool1
struct config11 : nnet::pooling2d_config {
    static const unsigned in_height = 32;
    static const unsigned in_width = 32;
    static const unsigned n_filt = 16;
    static const unsigned stride_height = 2;
    static const unsigned stride_width = 2;
    static const unsigned pool_height = 2;
    static const unsigned pool_width = 2;

    static const unsigned filt_height = pool_height;
    static const unsigned filt_width = pool_width;
    static const unsigned n_chan = n_filt;

    static const unsigned out_height = 16;
    static const unsigned out_width = 16;
    static const unsigned pad_top = 0;
    static const unsigned pad_bottom = 0;
    static const unsigned pad_left = 0;
    static const unsigned pad_right = 0;
    static const bool count_pad = false;
    static const nnet::Pool_Op pool_op = nnet::Max;
    static const nnet::conv_implementation implementation = nnet::conv_implementation::linebuffer;
    static const unsigned reuse_factor = 27;
    typedef model_default_t accum_t;
};

// zp2d_conv2a
struct config38 : nnet::padding2d_config {
    static const unsigned in_height = 16;
    static const unsigned in_width = 16;
    static const unsigned n_chan = 16;
    static const unsigned out_height = 18;
    static const unsigned out_width = 18;
    static const unsigned pad_top = 1;
    static const unsigned pad_bottom = 1;
    static const unsigned pad_left = 1;
    static const unsigned pad_right = 1;
};

// conv2a
struct config12_mult : nnet::dense_config {
    static const unsigned n_in = 144;
    static const unsigned n_out = 32;
    static const unsigned reuse_factor = 144;
    static const unsigned strategy = nnet::resource;
    static const unsigned n_zeros = 242;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in * n_out, reuse_factor) - n_zeros / reuse_factor;
    typedef conv2a_accum_t accum_t;
    typedef bias12_t bias_t;
    typedef weight12_t weight_t;
    template<class data_T, class res_T, class CONFIG_T>
    using kernel = nnet::DenseResource_rf_leq_nin<data_T, res_T, CONFIG_T>;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

struct config12 : nnet::conv2d_config {
    static const unsigned pad_top = 0;
    static const unsigned pad_bottom = 0;
    static const unsigned pad_left = 0;
    static const unsigned pad_right = 0;
    static const unsigned in_height = 18;
    static const unsigned in_width = 18;
    static const unsigned n_chan = 16;
    static const unsigned filt_height = 3;
    static const unsigned filt_width = 3;
    static const unsigned kernel_size = filt_height * filt_width;
    static const unsigned n_filt = 32;
    static const unsigned stride_height = 1;
    static const unsigned stride_width = 1;
    static const unsigned out_height = 16;
    static const unsigned out_width = 16;
    static const unsigned reuse_factor = 144;
    static const unsigned n_zeros = 242;
    static const unsigned multiplier_limit =
        DIV_ROUNDUP(kernel_size * n_chan * n_filt, reuse_factor) - n_zeros / reuse_factor;
    static const bool store_weights_in_bram = false;
    static const unsigned strategy = nnet::resource;
    static const nnet::conv_implementation implementation = nnet::conv_implementation::linebuffer;
    static const unsigned min_height = 18;
    static const unsigned min_width = 18;
    static const ap_uint<filt_height * filt_width> pixels[min_height * min_width];
    static const unsigned n_partitions = 256;
    static const unsigned n_pixels = out_height * out_width / n_partitions;
    template<class data_T, class CONFIG_T>
    using fill_buffer = nnet::FillConv2DBuffer<data_T, CONFIG_T>;
    typedef conv2a_accum_t accum_t;
    typedef bias12_t bias_t;
    typedef weight12_t weight_t;
    typedef config12_mult mult_config;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_height = nnet::scale_index_regular<K, S, W>;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_width = nnet::scale_index_regular<K, S, W>;
};
const ap_uint<config12::filt_height * config12::filt_width> config12::pixels[] = {0};

// bn_conv2a
struct config14 : nnet::batchnorm_config {
    static const unsigned n_in = 16*16*32;
    static const unsigned n_filt = 32;
    static const unsigned n_scale_bias = (n_filt == -1) ? n_in : n_filt;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in, reuse_factor);
    static const bool store_weights_in_bram = false;
    typedef bn_conv2a_bias_t bias_t;
    typedef bn_conv2a_scale_t scale_t;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

// relu_conv2a
struct relu_config15 : nnet::activ_config {
    static const unsigned n_in = 8192;
    static const unsigned table_size = 1024;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    typedef relu_conv2a_table_t table_t;
};

// zp2d_conv2b
struct config39 : nnet::padding2d_config {
    static const unsigned in_height = 16;
    static const unsigned in_width = 16;
    static const unsigned n_chan = 32;
    static const unsigned out_height = 18;
    static const unsigned out_width = 18;
    static const unsigned pad_top = 1;
    static const unsigned pad_bottom = 1;
    static const unsigned pad_left = 1;
    static const unsigned pad_right = 1;
};

// conv2b
struct config16_mult : nnet::dense_config {
    static const unsigned n_in = 288;
    static const unsigned n_out = 32;
    static const unsigned reuse_factor = 288;
    static const unsigned strategy = nnet::resource;
    static const unsigned n_zeros = 485;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in * n_out, reuse_factor) - n_zeros / reuse_factor;
    typedef conv2b_accum_t accum_t;
    typedef bias16_t bias_t;
    typedef weight16_t weight_t;
    template<class data_T, class res_T, class CONFIG_T>
    using kernel = nnet::DenseResource_rf_leq_nin<data_T, res_T, CONFIG_T>;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

struct config16 : nnet::conv2d_config {
    static const unsigned pad_top = 0;
    static const unsigned pad_bottom = 0;
    static const unsigned pad_left = 0;
    static const unsigned pad_right = 0;
    static const unsigned in_height = 18;
    static const unsigned in_width = 18;
    static const unsigned n_chan = 32;
    static const unsigned filt_height = 3;
    static const unsigned filt_width = 3;
    static const unsigned kernel_size = filt_height * filt_width;
    static const unsigned n_filt = 32;
    static const unsigned stride_height = 1;
    static const unsigned stride_width = 1;
    static const unsigned out_height = 16;
    static const unsigned out_width = 16;
    static const unsigned reuse_factor = 288;
    static const unsigned n_zeros = 485;
    static const unsigned multiplier_limit =
        DIV_ROUNDUP(kernel_size * n_chan * n_filt, reuse_factor) - n_zeros / reuse_factor;
    static const bool store_weights_in_bram = false;
    static const unsigned strategy = nnet::resource;
    static const nnet::conv_implementation implementation = nnet::conv_implementation::linebuffer;
    static const unsigned min_height = 18;
    static const unsigned min_width = 18;
    static const ap_uint<filt_height * filt_width> pixels[min_height * min_width];
    static const unsigned n_partitions = 256;
    static const unsigned n_pixels = out_height * out_width / n_partitions;
    template<class data_T, class CONFIG_T>
    using fill_buffer = nnet::FillConv2DBuffer<data_T, CONFIG_T>;
    typedef conv2b_accum_t accum_t;
    typedef bias16_t bias_t;
    typedef weight16_t weight_t;
    typedef config16_mult mult_config;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_height = nnet::scale_index_regular<K, S, W>;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_width = nnet::scale_index_regular<K, S, W>;
};
const ap_uint<config16::filt_height * config16::filt_width> config16::pixels[] = {0};

// bn_conv2b
struct config18 : nnet::batchnorm_config {
    static const unsigned n_in = 16*16*32;
    static const unsigned n_filt = 32;
    static const unsigned n_scale_bias = (n_filt == -1) ? n_in : n_filt;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in, reuse_factor);
    static const bool store_weights_in_bram = false;
    typedef bn_conv2b_bias_t bias_t;
    typedef bn_conv2b_scale_t scale_t;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

// relu_conv2b
struct relu_config19 : nnet::activ_config {
    static const unsigned n_in = 8192;
    static const unsigned table_size = 1024;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    typedef relu_conv2b_table_t table_t;
};

// pool2
struct config20 : nnet::pooling2d_config {
    static const unsigned in_height = 16;
    static const unsigned in_width = 16;
    static const unsigned n_filt = 32;
    static const unsigned stride_height = 2;
    static const unsigned stride_width = 2;
    static const unsigned pool_height = 2;
    static const unsigned pool_width = 2;

    static const unsigned filt_height = pool_height;
    static const unsigned filt_width = pool_width;
    static const unsigned n_chan = n_filt;

    static const unsigned out_height = 8;
    static const unsigned out_width = 8;
    static const unsigned pad_top = 0;
    static const unsigned pad_bottom = 0;
    static const unsigned pad_left = 0;
    static const unsigned pad_right = 0;
    static const bool count_pad = false;
    static const nnet::Pool_Op pool_op = nnet::Max;
    static const nnet::conv_implementation implementation = nnet::conv_implementation::linebuffer;
    static const unsigned reuse_factor = 27;
    typedef model_default_t accum_t;
};

// zp2d_conv3a
struct config40 : nnet::padding2d_config {
    static const unsigned in_height = 8;
    static const unsigned in_width = 8;
    static const unsigned n_chan = 32;
    static const unsigned out_height = 10;
    static const unsigned out_width = 10;
    static const unsigned pad_top = 1;
    static const unsigned pad_bottom = 1;
    static const unsigned pad_left = 1;
    static const unsigned pad_right = 1;
};

// conv3a
struct config21_mult : nnet::dense_config {
    static const unsigned n_in = 288;
    static const unsigned n_out = 64;
    static const unsigned reuse_factor = 288;
    static const unsigned strategy = nnet::resource;
    static const unsigned n_zeros = 946;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in * n_out, reuse_factor) - n_zeros / reuse_factor;
    typedef conv3a_accum_t accum_t;
    typedef bias21_t bias_t;
    typedef weight21_t weight_t;
    template<class data_T, class res_T, class CONFIG_T>
    using kernel = nnet::DenseResource_rf_leq_nin<data_T, res_T, CONFIG_T>;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

struct config21 : nnet::conv2d_config {
    static const unsigned pad_top = 0;
    static const unsigned pad_bottom = 0;
    static const unsigned pad_left = 0;
    static const unsigned pad_right = 0;
    static const unsigned in_height = 10;
    static const unsigned in_width = 10;
    static const unsigned n_chan = 32;
    static const unsigned filt_height = 3;
    static const unsigned filt_width = 3;
    static const unsigned kernel_size = filt_height * filt_width;
    static const unsigned n_filt = 64;
    static const unsigned stride_height = 1;
    static const unsigned stride_width = 1;
    static const unsigned out_height = 8;
    static const unsigned out_width = 8;
    static const unsigned reuse_factor = 288;
    static const unsigned n_zeros = 946;
    static const unsigned multiplier_limit =
        DIV_ROUNDUP(kernel_size * n_chan * n_filt, reuse_factor) - n_zeros / reuse_factor;
    static const bool store_weights_in_bram = false;
    static const unsigned strategy = nnet::resource;
    static const nnet::conv_implementation implementation = nnet::conv_implementation::linebuffer;
    static const unsigned min_height = 10;
    static const unsigned min_width = 10;
    static const ap_uint<filt_height * filt_width> pixels[min_height * min_width];
    static const unsigned n_partitions = 64;
    static const unsigned n_pixels = out_height * out_width / n_partitions;
    template<class data_T, class CONFIG_T>
    using fill_buffer = nnet::FillConv2DBuffer<data_T, CONFIG_T>;
    typedef conv3a_accum_t accum_t;
    typedef bias21_t bias_t;
    typedef weight21_t weight_t;
    typedef config21_mult mult_config;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_height = nnet::scale_index_regular<K, S, W>;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_width = nnet::scale_index_regular<K, S, W>;
};
const ap_uint<config21::filt_height * config21::filt_width> config21::pixels[] = {0};

// bn_conv3a
struct config23 : nnet::batchnorm_config {
    static const unsigned n_in = 8*8*64;
    static const unsigned n_filt = 64;
    static const unsigned n_scale_bias = (n_filt == -1) ? n_in : n_filt;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in, reuse_factor);
    static const bool store_weights_in_bram = false;
    typedef bn_conv3a_bias_t bias_t;
    typedef bn_conv3a_scale_t scale_t;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

// relu_conv3a
struct relu_config24 : nnet::activ_config {
    static const unsigned n_in = 4096;
    static const unsigned table_size = 1024;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    typedef relu_conv3a_table_t table_t;
};

// zp2d_conv3b
struct config41 : nnet::padding2d_config {
    static const unsigned in_height = 8;
    static const unsigned in_width = 8;
    static const unsigned n_chan = 64;
    static const unsigned out_height = 10;
    static const unsigned out_width = 10;
    static const unsigned pad_top = 1;
    static const unsigned pad_bottom = 1;
    static const unsigned pad_left = 1;
    static const unsigned pad_right = 1;
};

// conv3b
struct config25_mult : nnet::dense_config {
    static const unsigned n_in = 576;
    static const unsigned n_out = 64;
    static const unsigned reuse_factor = 576;
    static const unsigned strategy = nnet::resource;
    static const unsigned n_zeros = 1684;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in * n_out, reuse_factor) - n_zeros / reuse_factor;
    typedef conv3b_accum_t accum_t;
    typedef bias25_t bias_t;
    typedef weight25_t weight_t;
    template<class data_T, class res_T, class CONFIG_T>
    using kernel = nnet::DenseResource_rf_leq_nin<data_T, res_T, CONFIG_T>;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

struct config25 : nnet::conv2d_config {
    static const unsigned pad_top = 0;
    static const unsigned pad_bottom = 0;
    static const unsigned pad_left = 0;
    static const unsigned pad_right = 0;
    static const unsigned in_height = 10;
    static const unsigned in_width = 10;
    static const unsigned n_chan = 64;
    static const unsigned filt_height = 3;
    static const unsigned filt_width = 3;
    static const unsigned kernel_size = filt_height * filt_width;
    static const unsigned n_filt = 64;
    static const unsigned stride_height = 1;
    static const unsigned stride_width = 1;
    static const unsigned out_height = 8;
    static const unsigned out_width = 8;
    static const unsigned reuse_factor = 576;
    static const unsigned n_zeros = 1684;
    static const unsigned multiplier_limit =
        DIV_ROUNDUP(kernel_size * n_chan * n_filt, reuse_factor) - n_zeros / reuse_factor;
    static const bool store_weights_in_bram = false;
    static const unsigned strategy = nnet::resource;
    static const nnet::conv_implementation implementation = nnet::conv_implementation::linebuffer;
    static const unsigned min_height = 10;
    static const unsigned min_width = 10;
    static const ap_uint<filt_height * filt_width> pixels[min_height * min_width];
    static const unsigned n_partitions = 64;
    static const unsigned n_pixels = out_height * out_width / n_partitions;
    template<class data_T, class CONFIG_T>
    using fill_buffer = nnet::FillConv2DBuffer<data_T, CONFIG_T>;
    typedef conv3b_accum_t accum_t;
    typedef bias25_t bias_t;
    typedef weight25_t weight_t;
    typedef config25_mult mult_config;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_height = nnet::scale_index_regular<K, S, W>;
    template<unsigned K, unsigned S, unsigned W>
    using scale_index_width = nnet::scale_index_regular<K, S, W>;
};
const ap_uint<config25::filt_height * config25::filt_width> config25::pixels[] = {0};

// bn_conv3b
struct config27 : nnet::batchnorm_config {
    static const unsigned n_in = 8*8*64;
    static const unsigned n_filt = 64;
    static const unsigned n_scale_bias = (n_filt == -1) ? n_in : n_filt;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    static const unsigned multiplier_limit = DIV_ROUNDUP(n_in, reuse_factor);
    static const bool store_weights_in_bram = false;
    typedef bn_conv3b_bias_t bias_t;
    typedef bn_conv3b_scale_t scale_t;
    template<class x_T, class y_T>
    using product = nnet::product::mult<x_T, y_T>;
};

// relu_conv3b
struct relu_config28 : nnet::activ_config {
    static const unsigned n_in = 4096;
    static const unsigned table_size = 1024;
    static const unsigned io_type = nnet::io_stream;
    static const unsigned reuse_factor = 27;
    typedef relu_conv3b_table_t table_t;
};

// gap
struct config29 : nnet::pooling2d_config {
    static const unsigned in_height = 8;
    static const unsigned in_width = 8;
    static const unsigned n_filt = 64;
    static const nnet::Pool_Op pool_op = nnet::Average;
    static const unsigned reuse_factor = 27;
    typedef gap_accum_t accum_t;
};



#endif
