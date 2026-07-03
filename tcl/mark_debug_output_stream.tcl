################################################################
# mark_debug_output_stream.tcl — post-synth MARK_DEBUG on HLS output_stream (no BD ILA tap)
################################################################

proc _mark_debug_nets {filter} {
    set nets [get_nets -hier -quiet -filter $filter]
    set n 0
    foreach net $nets {
        set_property MARK_DEBUG true $net
        incr n
        puts "MARK_DEBUG: $net"
    }
    return $n
}

set total 0
incr total [_mark_debug_nets {NAME =~ *output_stream*TDATA*}]
incr total [_mark_debug_nets {NAME =~ *output_stream*TVALID*}]
incr total [_mark_debug_nets {NAME =~ *output_stream*TLAST*}]
incr total [_mark_debug_nets {NAME =~ *s_axis_s2mm_tready*}]

puts "INFO: MARK_DEBUG applied to ${total} output-path nets"
