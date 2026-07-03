################################################################
# mark_debug_s2mm.tcl — post-synth MARK_DEBUG on axi_dma S2MM boundary only
# (never mark cifar10_accel / output_stream — breaks HLS opt_design)
################################################################

proc _mark_debug_nets {filter} {
    set nets [get_nets -hier -quiet -filter $filter]
    set n 0
    foreach net $nets {
        if {[string match *cifar10_accel* $net]} { continue }
        set_property MARK_DEBUG true $net
        incr n
        puts "MARK_DEBUG: $net"
    }
    return $n
}

set total 0
incr total [_mark_debug_nets {NAME =~ system_i/axi_dma_0/s_axis_s2mm_tdata*}]
incr total [_mark_debug_nets {NAME =~ system_i/axi_dma_0/s_axis_s2mm_tvalid}]
incr total [_mark_debug_nets {NAME =~ system_i/axi_dma_0/s_axis_s2mm_tlast*}]

puts "INFO: MARK_DEBUG applied to ${total} axi_dma S2MM nets"
