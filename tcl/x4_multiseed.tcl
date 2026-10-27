set H [file normalize [file join [file dirname [info script]] ..]]
# X4 multi-strategy timing on the existing 5 ns RC1 design.
# Does not reset impl_1, does not write a bitstream, does not touch deploy/.
set proj $H/vivado_project/EdgeAI_ZU4EV.xpr
set outdir $H/results/opt_v2
file mkdir $outdir
set rpt [open [file join $outdir x4_multiseed.txt] w]
open_project $proj
puts $rpt "synth_status [get_property STATUS [get_runs synth_1]]"
puts $rpt "impl_1_status [get_property STATUS [get_runs impl_1]]"
puts $rpt "impl_1_strategy [get_property STRATEGY [get_runs impl_1]]"
puts $rpt "impl_1_WNS [get_property STATS.WNS [get_runs impl_1]]"
puts $rpt "impl_1_WHS [get_property STATS.WHS [get_runs impl_1]]"
puts $rpt "impl_1_TNS [get_property STATS.TNS [get_runs impl_1]]"

set jobs 8
if {[info exists ::env(VIVADO_JOBS)] && [string is integer -strict $::env(VIVADO_JOBS)]} {
    set jobs $::env(VIVADO_JOBS)
}
foreach {name strategy} {
    impl_x4_explore Performance_Explore
    impl_x4_spread Congestion_SpreadLogic_high
} {
    if {[llength [get_runs $name]] == 0} {
        create_run $name -parent_run synth_1 -flow {Vivado Implementation 2020} -strategy $strategy
    }
    reset_run $name
    launch_runs $name -to_step route_design -jobs $jobs
    wait_on_run $name
    set st [get_property STATUS [get_runs $name]]
    set wns [get_property STATS.WNS [get_runs $name]]
    set whs [get_property STATS.WHS [get_runs $name]]
    set tns [get_property STATS.TNS [get_runs $name]]
    puts $rpt "$name status $st strategy $strategy WNS $wns WHS $whs TNS $tns"
    puts "$name status $st WNS $wns"
}
close $rpt
close_project
exit 0
