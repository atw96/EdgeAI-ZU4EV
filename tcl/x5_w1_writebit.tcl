# Write the W1 bitstream from the already routed checkpoint.
# Does not open a project, does not reset any run, and does not touch
# vivado_project/ or vivado_project_a2l/.
# The LUT<60000 line is waived once, for W1 only: placed LUT as Logic is 61034.
set H [file normalize [file join [file dirname [info script]] ..]]
set dcp $H/vivado_project_w1/EdgeAI_ZU4EV.runs/impl_w1/system_wrapper_routed.dcp
set outdir $H/results/opt_v3
file mkdir $outdir
set rpt [open [file join $outdir w1_writebit_status.txt] w]
proc note {msg} {
    puts $msg
    puts $::rpt $msg
    flush $::rpt
}
if {![file exists $dcp]} {
    note "NO_DCP $dcp"
    close $rpt
    exit 3
}
note "OPEN $dcp"
open_checkpoint $dcp
report_timing_summary -max_paths 3 -file [file join $outdir w1_writebit_timing.rpt]
report_utilization -file [file join $outdir w1_writebit_util.rpt]
set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1 -nworst 1]]
note "WNS $wns"
if {![string is double -strict $wns] || $wns < 0} {
    note "TIMING_FAIL"
    close $rpt
    close_project
    exit 5
}
set fh [open [file join $outdir w1_writebit_util.rpt] r]
set txt [read $fh]
close $fh
set lut -1
if {[regexp {LUT as Logic\s*\|\s*([0-9,]+)} $txt -> raw]} {
    set lut [string map {, ""} $raw]
}
note "LUT_AS_LOGIC $lut"
if {$lut != 61034} {
    note "LUT_UNEXPECTED expected 61034"
    close $rpt
    close_project
    exit 6
}
write_bitstream -force [file join $outdir cifar10_accel_w1.bit]
note "BIT_WRITTEN"
close $rpt
close_project
exit 0
