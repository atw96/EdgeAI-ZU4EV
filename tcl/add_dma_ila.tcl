################################################################
# add_dma_ila.tcl — System ILA (AXIS) + Native ILA (reset only)
#
# Per Xilinx UG994 / AR65254:
#   - Stale per-pin nets from prior Native-ILA taps break AXIS intf
#     (single-pin override removes signal from bundle → tie-off 0).
#   - Use System ILA SLOT_0_AXIS on the intf net (tee, non-intrusive).
################################################################

set PROJECT_DIR "./vivado_project"
set PROJECT_NAME "EdgeAI_ZU4EV"
set SYS_ILA_NAME "system_ila_output"
set RST_ILA_NAME "ila_reset_debug"

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

proc remove_ila_cell {name} {
    set cell [get_bd_cells -quiet ${name}]
    if {$cell ne ""} {
        puts "INFO: Removing existing ${name}"
        delete_bd_objs $cell
    }
}

# Delete orphan per-pin nets left by failed Native-ILA attempts (AR65254).
proc cleanup_stale_axis_nets {} {
    set stale_net_names {
        cifar10_accel_0_output_stream_TDATA
        cifar10_accel_0_output_stream_TVALID
        cifar10_accel_0_output_stream_TLAST
        cifar10_accel_0_input_stream_TDATA
        cifar10_accel_0_input_stream_TVALID
        cifar10_accel_0_input_stream_TLAST
        cifar10_accel_0_input_stream_TREADY
        axi_dma_0_s_axis_s2mm_tdata
        axi_dma_0_s_axis_s2mm_tvalid
        axi_dma_0_s_axis_s2mm_tlast
        axi_dma_0_s_axis_s2mm_tready
        axi_dma_0_m_axis_mm2s_tdata
        axi_dma_0_m_axis_mm2s_tvalid
        axi_dma_0_m_axis_mm2s_tlast
        axi_dma_0_m_axis_mm2s_tready
        axi_dma_0_m_axis_mm2s_tkeep
    }
    foreach nname $stale_net_names {
        set n [get_bd_nets -quiet $nname]
        if {$n ne ""} {
            puts "INFO: Deleting stale net ${nname}"
            delete_bd_objs $n
        }
    }
    foreach pin {
        cifar10_accel_0/output_stream_TDATA
        cifar10_accel_0/output_stream_TVALID
        cifar10_accel_0/output_stream_TREADY
        cifar10_accel_0/output_stream_TLAST
        cifar10_accel_0/input_stream_TDATA
        cifar10_accel_0/input_stream_TVALID
        cifar10_accel_0/input_stream_TREADY
        cifar10_accel_0/input_stream_TLAST
        cifar10_accel_0/input_stream_TKEEP
        axi_dma_0/s_axis_s2mm_tdata
        axi_dma_0/s_axis_s2mm_tvalid
        axi_dma_0/s_axis_s2mm_tready
        axi_dma_0/s_axis_s2mm_tlast
        axi_dma_0/m_axis_mm2s_tdata
        axi_dma_0/m_axis_mm2s_tvalid
        axi_dma_0/m_axis_mm2s_tready
        axi_dma_0/m_axis_mm2s_tlast
        axi_dma_0/m_axis_mm2s_tkeep
    } {
        set p [get_bd_pins -quiet $pin]
        if {$p eq ""} { continue }
        foreach n [get_bd_nets -quiet -of_objects $p] {
            set ports [get_bd_pins -quiet -of_objects $n]
            if {[llength $ports] <= 1} {
                set nname [get_property NAME $n]
                puts "INFO: Deleting single-pin orphan net ${nname} on ${pin}"
                delete_bd_objs $n
            }
        }
    }
}

proc disconnect_intf_pin {intf_pin {label ""}} {
    if {$intf_pin eq ""} { return }
    foreach in [get_bd_intf_nets -quiet -of_objects $intf_pin] {
        set nname [get_property NAME $in]
        puts "INFO: Removing intf net ${nname} from ${label}"
        delete_bd_objs $in
    }
}

proc restore_output_stream_intf {} {
    set accel_out [get_bd_intf_pins -quiet cifar10_accel_0/output_stream]
    set dma_s2mm [get_bd_intf_pins -quiet axi_dma_0/S_AXIS_S2MM]
    if {$accel_out eq "" || $dma_s2mm eq ""} {
        error "output_stream or S_AXIS_S2MM intf pin missing"
    }
    disconnect_intf_pin $accel_out "cifar10_accel_0/output_stream"
    disconnect_intf_pin $dma_s2mm "axi_dma_0/S_AXIS_S2MM"
    connect_bd_intf_net $accel_out $dma_s2mm
    puts "INFO: Restored cifar10_accel_0/output_stream <-> axi_dma_0/S_AXIS_S2MM"
}

proc restore_input_stream_intf {} {
    set accel_in [get_bd_intf_pins -quiet cifar10_accel_0/input_stream]
    set dma_mm2s [get_bd_intf_pins -quiet axi_dma_0/M_AXIS_MM2S]
    if {$accel_in eq "" || $dma_mm2s eq ""} {
        error "input_stream or M_AXIS_MM2S intf pin missing"
    }
    disconnect_intf_pin $dma_mm2s "axi_dma_0/M_AXIS_MM2S"
    disconnect_intf_pin $accel_in "cifar10_accel_0/input_stream"
    connect_bd_intf_net $dma_mm2s $accel_in
    puts "INFO: Restored axi_dma_0/M_AXIS_MM2S <-> cifar10_accel_0/input_stream"
}

proc assert_axis_intf_healthy {} {
    if {[get_bd_nets -quiet axi_dma_0_m_axis_mm2s_tvalid] ne ""} {
        error "orphan mm2s_tvalid net still present after cleanup"
    }
    foreach {label intf_pin expect_ports} {
        {M_AXIS_MM2S input} {axi_dma_0/M_AXIS_MM2S cifar10_accel_0/input_stream} 2
        {output_stream pre-ILA} {cifar10_accel_0/output_stream axi_dma_0/S_AXIS_S2MM} 2
    } {
        set nets [get_bd_intf_nets -quiet -of_objects [get_bd_intf_pins $intf_pin]]
        if {[llength $nets] != 1} {
            error "${label}: expected 1 intf net on ${intf_pin}, got [llength $nets]"
        }
        set ports [get_bd_intf_pins -quiet -of_objects [lindex $nets 0]]
        if {[llength $ports] != $expect_ports} {
            error "${label}: intf net has [llength $ports] ports, expected ${expect_ports}"
        }
    }
    puts "INFO: AXIS intf health check passed (MM2S + output_stream)"
}

cleanup_stale_axis_nets

foreach legacy {ila_dma_debug ila_dma_debug_0} {
    remove_ila_cell $legacy
}
remove_ila_cell ${SYS_ILA_NAME}
remove_ila_cell ${RST_ILA_NAME}

restore_output_stream_intf
restore_input_stream_intf
assert_axis_intf_healthy

# ── System ILA: monitor output_stream (AXIS tee) ─────────────────
set sys_ila [create_bd_cell -type ip -vlnv xilinx.com:ip:system_ila:1.1 ${SYS_ILA_NAME}]
set_property -dict [list \
    CONFIG.C_MON_TYPE {Interface} \
    CONFIG.C_NUM_MONITOR_SLOTS {1} \
    CONFIG.C_SLOT_0_INTF_TYPE {xilinx.com:interface:axis_rtl:1.0} \
    CONFIG.C_SLOT_0_AXIS_TDATA_WIDTH {32} \
    CONFIG.C_DATA_DEPTH {4096} \
    CONFIG.C_ENABLE_ILA_AXI_MON {false} \
] $sys_ila

set clk_pin [ila_clk_pin]
set rst_ps [ila_reset_ps]
connect_bd_net $clk_pin [get_bd_pins ${SYS_ILA_NAME}/clk]
connect_bd_net [get_bd_pins ${rst_ps}/peripheral_aresetn] [get_bd_pins ${SYS_ILA_NAME}/resetn]

connect_bd_intf_net [get_bd_intf_pins ${SYS_ILA_NAME}/SLOT_0_AXIS] \
    [get_bd_intf_pins cifar10_accel_0/output_stream]
puts "INFO: ${SYS_ILA_NAME} SLOT_0_AXIS tee on output_stream intf"

# ── Native ILA: reset / clock-health only ────────────────────────
set rst_ila [create_bd_cell -type ip -vlnv xilinx.com:ip:ila:6.2 ${RST_ILA_NAME}]
set_property -dict [list \
    CONFIG.C_MONITOR_TYPE {Native} \
    CONFIG.C_NUM_OF_PROBES {4} \
    CONFIG.C_PROBE0_WIDTH {1} \
    CONFIG.C_PROBE1_WIDTH {1} \
    CONFIG.C_PROBE2_WIDTH {1} \
    CONFIG.C_PROBE3_WIDTH {1} \
    CONFIG.C_DATA_DEPTH {4096} \
] $rst_ila

connect_bd_net $clk_pin [get_bd_pins ${RST_ILA_NAME}/clk]

set pl_rst [get_bd_pins -quiet zynq_ultra_ps_e_0/pl_resetn0]
if {$pl_rst ne ""} {
    connect_bd_net $pl_rst [get_bd_pins ${RST_ILA_NAME}/probe0]
}
connect_bd_net [get_bd_pins ${rst_ps}/peripheral_aresetn] [get_bd_pins ${RST_ILA_NAME}/probe1]
connect_bd_net [get_bd_pins axi_dma_0/axi_resetn] [get_bd_pins ${RST_ILA_NAME}/probe2]

set locked_pin [get_bd_pins -quiet pl_ref_clk/locked]
if {$locked_pin ne ""} {
    connect_bd_net $locked_pin [get_bd_pins ${RST_ILA_NAME}/probe3]
} else {
    connect_bd_net [get_bd_pins xlconstant_dcm_locked/dout] [get_bd_pins ${RST_ILA_NAME}/probe3]
}

puts "INFO: ${RST_ILA_NAME} added (4 reset/lock probes)"

validate_bd_design

# Post-ILA tee: output_stream intf should have HLS + DMA + System ILA (3 ports).
set out_nets [get_bd_intf_nets -quiet -of_objects [get_bd_intf_pins cifar10_accel_0/output_stream]]
if {[llength $out_nets] != 1} {
    error "output_stream: expected 1 intf net after ILA tee, got [llength $out_nets]"
}
set out_ports [get_bd_intf_pins -quiet -of_objects [lindex $out_nets 0]]
if {[llength $out_ports] != 3} {
    error "output_stream intf net has [llength $out_ports] ports, expected 3 (HLS+DMA+ILA)"
}
if {[get_bd_nets -quiet axi_dma_0_m_axis_mm2s_tvalid] ne ""} {
    error "orphan mm2s_tvalid net still present after ILA insert"
}
set in_nets [get_bd_intf_nets -quiet -of_objects [get_bd_intf_pins cifar10_accel_0/input_stream]]
if {[llength $in_nets] != 1} {
    error "input_stream: expected 1 intf net, got [llength $in_nets]"
}
set in_ports [get_bd_intf_pins -quiet -of_objects [lindex $in_nets 0]]
if {[llength $in_ports] != 2} {
    error "input_stream intf net has [llength $in_ports] ports, expected 2 (DMA+HLS)"
}
puts "INFO: Post-ILA AXIS intf health check passed"

save_bd_design
generate_target all [get_files system.bd]

puts "INFO: Next: FORCE_REBUILD=1 vivado -mode batch -source tcl/run_impl_and_bitstream.tcl"
