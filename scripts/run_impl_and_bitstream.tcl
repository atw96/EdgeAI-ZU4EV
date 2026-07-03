################################################################
# run_impl_and_bitstream.tcl
# EdgeAI-ZU4EV — One-shot Synthesis → Implementation → Bitstream
#
# Prerequisites:
#   1. Phase 1C complete (hls4ml IP exported to notebooks/hls4ml_prj/.../impl/ip)
#   2. Block Design created: source tcl/create_block_design.tcl
#
# Usage (from repo root, Vivado 2020.1):
#   vivado -mode batch -source tcl/run_impl_and_bitstream.tcl
#
# Or in Vivado Tcl Console (project already open):
#   source tcl/run_impl_and_bitstream.tcl
#
# Optional environment overrides:
#   set ::env(VIVADO_JOBS) 8
#   set ::env(SKIP_SYNTH) 1    ;# only impl + bitstream if synth_1 already done
#
# Outputs:
#   vivado_project/EdgeAI_ZU4EV.runs/impl_1/*.bit
#   deploy/cifar10_accel.{bit,hwh,xsa}  (via export_bitstream.tcl)
################################################################

set SCRIPT_DIR  [file dirname [file normalize [info script]]]
set REPO_ROOT   [file dirname ${SCRIPT_DIR}]

set PROJECT_NAME "EdgeAI_ZU4EV"
set PROJECT_DIR  [file normalize [file join ${REPO_ROOT} vivado_project]]
set PROJECT_XPR  [file join ${PROJECT_DIR} ${PROJECT_NAME}.xpr]
set SYNTH_RUN    "synth_1"
set IMPL_RUN     "impl_1"
set JOBS         8

if {[info exists ::env(VIVADO_JOBS)] && [string is integer -strict $::env(VIVADO_JOBS)]} {
    set JOBS $::env(VIVADO_JOBS)
}
set SKIP_SYNTH 0
if {[info exists ::env(SKIP_SYNTH)] && $::env(SKIP_SYNTH) ne "" && $::env(SKIP_SYNTH) ne "0"} {
    set SKIP_SYNTH 1
}
set FORCE_REBUILD 0
if {[info exists ::env(FORCE_REBUILD)] && $::env(FORCE_REBUILD) ne "" && $::env(FORCE_REBUILD) ne "0"} {
    set FORCE_REBUILD 1
}

proc run_failed {run_name} {
    set status [get_property STATUS [get_runs $run_name]]
    set progress [get_property PROGRESS [get_runs $run_name]]
    error "Run ${run_name} failed. STATUS=${status} PROGRESS=${progress}"
}

proc wait_for_run {run_name {poll_s 15}} {
    puts "INFO: Waiting for ${run_name}..."
    while {1} {
        set status [get_property STATUS [get_runs $run_name]]
        set progress [get_property PROGRESS [get_runs $run_name]]
        puts "  ${run_name}: ${status} (${progress})"
        if {[regexp {Complete|Failed|Cancelled} $status]} {
            break
        }
        after [expr {$poll_s * 1000}]
    }
    if {![string match *Complete* $status]} {
        run_failed $run_name
    }
}

puts "================================================================"
puts " EdgeAI-ZU4EV — Synth → Impl → Bitstream"
puts " Repo   : ${REPO_ROOT}"
puts " Project: ${PROJECT_XPR}"
puts " Jobs   : ${JOBS}"
puts "================================================================"

# ── Open or verify project ─────────────────────────────────────
if {![info exists ::current_proj]} {
    if {![file exists ${PROJECT_XPR}]} {
        error "Project not found: ${PROJECT_XPR}\nRun: vivado -mode batch -source tcl/create_block_design.tcl"
    }
    puts "INFO: Opening project ${PROJECT_XPR}"
    open_project ${PROJECT_XPR}
} else {
    puts "INFO: Using already-open project."
}

set bd_files [get_files -quiet system.bd]
if {[llength $bd_files] == 0} {
    error "system.bd not found. Run create_block_design.tcl first."
}

# ── Ensure impl run exists ───────────────────────────────────────
set synth_run_obj [get_runs -quiet ${SYNTH_RUN}]
if {[llength $synth_run_obj] == 0} {
    error "Run ${SYNTH_RUN} not found. Run create_block_design.tcl first."
}

set impl_run_obj [get_runs -quiet ${IMPL_RUN}]
if {[llength $impl_run_obj] == 0} {
    puts "INFO: Creating ${IMPL_RUN} (parent=${SYNTH_RUN})"
    create_run ${IMPL_RUN} -flow {Vivado Implementation 2020} -parent ${SYNTH_RUN}
}

# ── Optional: aggressive timing closure (LUT ~84% may need this) ─
# Uncomment if default impl fails timing:
# set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs ${IMPL_RUN}]
# set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs ${IMPL_RUN}]
# set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED true [get_runs ${IMPL_RUN}]

# ── Step 1: Synthesis ────────────────────────────────────────────
if {$FORCE_REBUILD} {
    puts "INFO: FORCE_REBUILD=1 — resetting and re-running ${SYNTH_RUN} and ${IMPL_RUN}"
    reset_run ${SYNTH_RUN}
    reset_run ${IMPL_RUN}
}
if {!$SKIP_SYNTH} {
    set synth_status [get_property STATUS [get_runs ${SYNTH_RUN}]]
    if {!$FORCE_REBUILD && [string match *Complete* $synth_status]} {
        puts "INFO: ${SYNTH_RUN} already complete. Set FORCE_REBUILD=1 to force re-run."
    } else {
        puts "INFO: Launching ${SYNTH_RUN} (jobs=${JOBS})..."
        if {!$FORCE_REBUILD} { reset_run ${SYNTH_RUN} }
        launch_runs ${SYNTH_RUN} -jobs ${JOBS}
        wait_for_run ${SYNTH_RUN}
        puts "INFO: ${SYNTH_RUN} finished OK."
    }
} else {
    puts "INFO: Skipping synthesis (SKIP_SYNTH=1)."
}

# ── Step 2: Implementation + Bitstream ───────────────────────────
set impl_status [get_property STATUS [get_runs ${IMPL_RUN}]]
if {!$FORCE_REBUILD && [string match {write_bitstream Complete!} $impl_status]} {
    puts "INFO: ${IMPL_RUN} bitstream already complete. Re-run with FORCE_REBUILD=1 first if needed."
} else {
    puts "INFO: Launching ${IMPL_RUN} through write_bitstream (jobs=${JOBS})..."
    if {!$FORCE_REBUILD} { reset_run ${IMPL_RUN} }
    launch_runs ${IMPL_RUN} -to_step write_bitstream -jobs ${JOBS}
    wait_for_run ${IMPL_RUN}
    puts "INFO: ${IMPL_RUN} + bitstream finished OK."
}

open_run ${IMPL_RUN}

# ── Step 3: Quick timing / util report ─────────────────────────
puts "\nINFO: Post-route timing summary:"
catch {report_timing_summary -max_paths 1 -delay_type max -quiet}

puts "\nINFO: Post-route utilization:"
catch {report_utilization -quiet}

# ── Step 4: Export deploy package ────────────────────────────────
set export_script [file join ${REPO_ROOT} tcl export_bitstream.tcl]
if {[file exists ${export_script}]} {
    puts "\nINFO: Running export_bitstream.tcl ..."
    source ${export_script}
} else {
    puts "WARN: export_bitstream.tcl not found at ${export_script}"
    set bit_glob [glob -nocomplain ${PROJECT_DIR}/${PROJECT_NAME}.runs/${IMPL_RUN}/*.bit]
    if {[llength $bit_glob] > 0} {
        puts "INFO: Bitstream at [lindex $bit_glob 0]"
    }
}

puts ""
puts "================================================================"
puts " All done."
puts " Next: copy deploy/cifar10_accel.bit to board, run PS inference app."
puts "================================================================"
