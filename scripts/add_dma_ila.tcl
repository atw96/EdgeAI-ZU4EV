################################################################
# add_dma_ila.tcl — ILA: DMA + cifar10_accel output_stream (JTAG / Hardware Manager)
#
# Probes (ila_dma_debug):
#   probe0  pl_resetn0
#   probe1  proc_sys_reset_pl/peripheral_aresetn
#   probe2  axi_dma_0/axi_resetn
#   probe3  pl_ref_clk/locked
#   probe4  axi_dma_0/m_axis_mm2s_tvalid
#   probe5  axi_dma_0/s_axis_s2mm_tready
#   probe6  cifar10_accel_0/output_stream_TDATA[31:0]
#   probe7  cifar10_accel_0/output_stream_TVALID
#   probe8  cifar10_accel_0/output_stream_TLAST
#   (TREADY: use probe5 = axi_dma_0/s_axis_s2mm_tready — same net, HLS TREADY not debug-routable)
#
# Usage:
#   vivado -mode batch -source tcl/add_dma_ila.tcl
#   FORCE_REBUILD=1 vivado -mode batch -source tcl/run_impl_and_bitstream.tcl
#
# Or: bash scripts/run_ila_output_rebuild.sh
################################################################

set PROJECT_DIR "./vivado_project"
set PROJECT_NAME "EdgeAI_ZU4EV"
set ILA_NAME "ila_dma_debug"
set ILA_PROBES 9

open_project ${PROJECT_DIR}/${PROJECT_NAME}.xpr
open_bd_design [get_files system.bd]

proc ila_clk_pin {} {
    set clk_pin [get_bd_pins -quiet pl_ref_clk/clk_out1]
    if {$clk_pin eq ""} {
        set clk_pin [get_bd_pins zynq_ultra_ps_e_0/pl_clk0]
    }
    return $clk_pin
}

proc ila_reset_ps {} {
    set rst_ps [get_bd_cells -quiet proc_sys_reset_pl]
    if {$rst_ps eq ""} {
        set rst_ps [get_bd_cells proc_sys_reset_200mhz]
    }
    return $rst_ps
}

# Always recreate ILA so probe wiring matches CONFIG (reuse skipped connections → Chipscope 16-213)
set ila_cell [get_bd_cells -quiet ${ILA_NAME}]
if {$ila_cell ne ""} {
    puts "INFO: Removing existing ${ILA_NAME} for clean 10-probe wiring"
    delete_bd_objs $ila_cell
}

set ila [create_bd_cell -type ip -vlnv xilinx.com:ip:ila:6.2 ${ILA_NAME}]
set_property -dict [list \
    CONFIG.C_MONITOR_TYPE {Native} \
    CONFIG.C_NUM_OF_PROBES ${ILA_PROBES} \
    CONFIG.C_PROBE0_WIDTH {1} \
    CONFIG.C_PROBE1_WIDTH {1} \
    CONFIG.C_PROBE2_WIDTH {1} \
    CONFIG.C_PROBE3_WIDTH {1} \
    CONFIG.C_PROBE4_WIDTH {1} \
    CONFIG.C_PROBE5_WIDTH {1} \
    CONFIG.C_PROBE6_WIDTH {32} \
    CONFIG.C_PROBE7_WIDTH {1} \
    CONFIG.C_PROBE8_WIDTH {1} \
    CONFIG.C_DATA_DEPTH {4096} \
] $ila

set clk_pin [ila_clk_pin]
connect_bd_net $clk_pin [get_bd_pins ${ILA_NAME}/clk]

set rst_ps [ila_reset_ps]

set pl_rst [get_bd_pins -quiet zynq_ultra_ps_e_0/pl_resetn0]
if {$pl_rst ne ""} {
    connect_bd_net $pl_rst [get_bd_pins ${ILA_NAME}/probe0]
}
connect_bd_net [get_bd_pins ${rst_ps}/peripheral_aresetn] \
    [get_bd_pins ${ILA_NAME}/probe1]
connect_bd_net [get_bd_pins axi_dma_0/axi_resetn] \
    [get_bd_pins ${ILA_NAME}/probe2]

set locked_pin [get_bd_pins -quiet pl_ref_clk/locked]
if {$locked_pin ne ""} {
    connect_bd_net $locked_pin [get_bd_pins ${ILA_NAME}/probe3]
} else {
    connect_bd_net [get_bd_pins xlconstant_dcm_locked/dout] \
        [get_bd_pins ${ILA_NAME}/probe3]
}

connect_bd_net [get_bd_pins axi_dma_0/m_axis_mm2s_tvalid] \
    [get_bd_pins ${ILA_NAME}/probe4]
connect_bd_net [get_bd_pins axi_dma_0/s_axis_s2mm_tready] \
    [get_bd_pins ${ILA_NAME}/probe5]

set out_tdata [get_bd_pins -quiet cifar10_accel_0/output_stream_TDATA]
set out_tvalid [get_bd_pins -quiet cifar10_accel_0/output_stream_TVALID]
set out_tlast [get_bd_pins -quiet cifar10_accel_0/output_stream_TLAST]
if {$out_tdata eq "" || $out_tvalid eq "" || $out_tlast eq ""} {
    error "output_stream pins missing on cifar10_accel_0 (TDATA/TVALID/TLAST)"
}

connect_bd_net $out_tdata [get_bd_pins ${ILA_NAME}/probe6]
connect_bd_net $out_tvalid [get_bd_pins ${ILA_NAME}/probe7]
connect_bd_net $out_tlast [get_bd_pins ${ILA_NAME}/probe8]

puts "INFO: ${ILA_NAME} added (${ILA_PROBES} probes; TREADY on probe5=s2mm_tready)"

validate_bd_design
save_bd_design
generate_target all [get_files system.bd]

puts "INFO: Next: FORCE_REBUILD=1 vivado -mode batch -source tcl/run_impl_and_bitstream.tcl"
