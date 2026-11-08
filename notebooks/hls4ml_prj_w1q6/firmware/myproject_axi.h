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
