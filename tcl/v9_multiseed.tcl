# R1 multi-strategy timing for RC2 on the copied project only.
# Does not open vivado_project/, does not reset impl_a2l, does not write a bitstream.
set H [file normalize [file join [file dirname [info script]] ..]]
set proj $H/vivado_project_a2l/EdgeAI_ZU4EV.xpr
set outdir $H/results/opt_v2/a2l
file mkdir $outdir
set rpt [open [file join $outdir v9_multiseed.txt] w]
proc note {msg} {
    puts $msg
    puts $::rpt $msg
    flush $::rpt
}
open_project $proj
note "impl_a2l status [get_property STATUS [get_runs impl_a2l]] strategy [get_property STRATEGY [get_runs impl_a2l]] WNS [get_property STATS.WNS [get_runs impl_a2l]] WHS [get_property STATS.WHS [get_runs impl_a2l]] TNS [get_property STATS.TNS [get_runs impl_a2l]]"
foreach {name strategy} [list \
    impl_rc2_default "Vivado Implementation Defaults" \
    impl_rc2_spread Congestion_SpreadLogic_high \
] {
    if {[llength [get_runs $name]] == 0} {
        create_run $name -parent_run synth_a2l -flow {Vivado Implementation 2020} -strategy $strategy
    }
    reset_run $name
    launch_runs $name -to_step route_design -jobs 8
    wait_on_run $name
    set st [get_property STATUS [get_runs $name]]
    set wns [get_property STATS.WNS [get_runs $name]]
    set whs [get_property STATS.WHS [get_runs $name]]
    set tns [get_property STATS.TNS [get_runs $name]]
    note "$name status $st strategy $strategy WNS $wns WHS $whs TNS $tns"
}
set dcp [glob -nocomplain $H/vivado_project_a2l/EdgeAI_ZU4EV.runs/impl_a2l/*routed*.dcp]
note "DCP $dcp"
if {[llength $dcp] > 0} {
    open_checkpoint [lindex $dcp 0]
    set c [get_clocks -quiet clk_out1_system_pl_ref_clk_0]
    note "CLOCK $c PERIOD [get_property PERIOD $c]"
    if {[catch {set_property PERIOD 6.667 $c} err]} {
        note "PERIOD_SET_FAIL $err"
    } else {
        note "PERIOD_AFTER [get_property PERIOD $c]"
        report_timing_summary -delay_type min_max -max_paths 3 -file [file join $outdir v9_timing_6p667.rpt]
        set paths [get_timing_paths -delay_type max -max_paths 1 -nworst 1]
        if {[llength $paths] > 0} {
            note "WNS_6P667 [get_property SLACK [lindex $paths 0]]"
        }
        set holds [get_timing_paths -delay_type min -max_paths 1 -nworst 1]
        if {[llength $holds] > 0} {
            note "WHS_6P667 [get_property SLACK [lindex $holds 0]]"
        }
    }
    close_design
}
close $rpt
close_project
exit 0
