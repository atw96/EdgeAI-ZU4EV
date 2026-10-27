# A2-L implementation on a copied project.
# Does not open vivado_project/, does not reset synth_1 or impl_1, does not write deploy/.
set H [file normalize [file join [file dirname [info script]] ..]]
set proj $H/vivado_project_a2l/EdgeAI_ZU4EV.xpr
set iprepo $H/notebooks/hls4ml_prj_a2l/myproject_prj/solution1/impl/ip
set outdir $H/results/opt_v2/a2l
file mkdir $outdir
set rpt [open [file join $outdir impl_status.txt] w]
proc note {msg} {
    puts $msg
    puts $::rpt $msg
    flush $::rpt
}
open_project $proj
set_property ip_repo_paths [list $iprepo] [current_project]
update_ip_catalog -rebuild
open_bd_design [get_files system.bd]
set ip [get_ips -quiet system_cifar10_accel_0_0]
if {$ip eq ""} {
    set ip [get_ips -quiet cifar10_accel_0]
}
if {$ip eq ""} {
    note "NO_IP"
    close $rpt
    close_project
    exit 4
}
note "UPGRADE $ip"
upgrade_ip $ip
validate_bd_design
save_bd_design
generate_target all [get_files system.bd]
foreach r [get_runs] {
    set nm [get_property NAME $r]
    if {[string match *cifar* $nm] || [string match *myproject* $nm]} {
        note "RESET_OOC $nm"
        reset_run $r
    }
}
if {[llength [get_runs synth_a2l]] == 0} {
    create_run synth_a2l -flow {Vivado Synthesis 2020}
}
if {[llength [get_runs impl_a2l]] == 0} {
    create_run impl_a2l -parent_run synth_a2l -flow {Vivado Implementation 2020} -strategy Performance_Explore
}
reset_run synth_a2l
launch_runs impl_a2l -to_step route_design -jobs 8
wait_on_run impl_a2l
set st [get_property STATUS [get_runs impl_a2l]]
set wns [get_property STATS.WNS [get_runs impl_a2l]]
set whs [get_property STATS.WHS [get_runs impl_a2l]]
set tns [get_property STATS.TNS [get_runs impl_a2l]]
note "A2L_IMPL status $st WNS $wns WHS $whs TNS $tns"
if {![string match *Complete* $st]} {
    close $rpt
    close_project
    exit 4
}
if {![string is double -strict $wns] || $wns < 0} {
    close $rpt
    close_project
    exit 5
}
open_run impl_a2l
report_utilization -file [file join $outdir placed_util.rpt]
report_timing_summary -max_paths 3 -file [file join $outdir placed_timing.rpt]
set fh [open [file join $outdir placed_util.rpt] r]
set txt [read $fh]
close $fh
set lut -1
set dsp -1
set bram -1
if {[regexp {LUT as Logic\s*\|\s*([0-9,]+)} $txt -> raw]} {
    set lut [string map {, ""} $raw]
}
if {[regexp {\|\s*DSPs\s*\|\s*([0-9,]+)} $txt -> raw]} {
    set dsp [string map {, ""} $raw]
}
if {[regexp {Block RAM Tile\s*\|\s*([0-9,]+)} $txt -> raw]} {
    set bram [string map {, ""} $raw]
}
note "PLACED LUT_as_Logic $lut DSP $dsp BRAM_tile $bram"
set area_bad 0
if {$lut < 0 || $lut >= 60000} { set area_bad 1 }
if {$dsp < 0 || $dsp >= 500} { set area_bad 1 }
if {$bram < 0 || $bram >= 80} { set area_bad 1 }
if {$area_bad} {
    note "AREA_RED_PLACED"
    close $rpt
    close_project
    exit 6
}
write_bitstream -force [file join $outdir cifar10_accel.bit]
set hwh [glob -nocomplain $H/vivado_project_a2l/*.srcs/sources_1/bd/system/hw_handoff/system.hwh]
if {[llength $hwh] == 0} {
    set hwh [glob -nocomplain $H/vivado_project_a2l/*/*/bd/system/hw_handoff/system.hwh]
}
if {[llength $hwh] > 0} {
    file copy -force [lindex $hwh 0] [file join $outdir cifar10_accel.hwh]
    note "HWH [lindex $hwh 0]"
}
note "BIT_WRITTEN"
close $rpt
close_project
exit 0
