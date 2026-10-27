# Operating-point timing on the routed RC2 checkpoint, then one more 5 ns strategy.
# PERIOD is read-only on the generated clock, so the 6.667 ns requirement is
# applied as -1.667 ns of setup uncertainty (6.667 - 5.000). No bitstream.
set H [file normalize [file join [file dirname [info script]] ..]]
set outdir $H/results/opt_v2/a2l
set dcp $H/vivado_project_a2l/EdgeAI_ZU4EV.runs/impl_a2l/system_wrapper_routed.dcp
set rpt [open [file join $outdir v9_period.txt] w]
proc note {msg} {
    puts $msg
    puts $::rpt $msg
    flush $::rpt
}
open_checkpoint $dcp
set c [get_clocks clk_out1_system_pl_ref_clk_0]
note "PERIOD [get_property PERIOD $c]"
set_clock_uncertainty -setup -1.667 $c
report_timing_summary -delay_type min_max -max_paths 3 -file [file join $outdir v9_timing_6p667.rpt]
set paths [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
set holds [get_timing_paths -delay_type min -max_paths 1 -nworst 1]
note "WNS_6P667 [get_property SLACK [lindex $paths 0]] REQ [get_property REQUIREMENT [lindex $paths 0]]"
note "WHS_6P667 [get_property SLACK [lindex $holds 0]]"
close_design
open_project $H/vivado_project_a2l/EdgeAI_ZU4EV.xpr
set name impl_rc2_post
set strategy Performance_ExplorePostRoutePhysOpt
if {[llength [get_runs $name]] == 0} {
    create_run $name -parent_run synth_a2l -flow {Vivado Implementation 2020} -strategy $strategy
}
reset_run $name
launch_runs $name -to_step route_design -jobs 8
wait_on_run $name
set st [get_property STATUS [get_runs $name]]
note "$name status $st strategy $strategy WNS [get_property STATS.WNS [get_runs $name]] WHS [get_property STATS.WHS [get_runs $name]] TNS [get_property STATS.TNS [get_runs $name]]"
close $rpt
close_project
exit 0
