################################################################
# replace_hls_ip.tcl
# EdgeAI-ZU4EV — Replace placeholder IP with real hls4ml-generated IP
#
# Run AFTER Phase 1C (hls4ml synthesis) completes and exports the IP.
# Source this script from the already-open Vivado 2020.1 project:
#   Tcl Console → source tcl/replace_hls_ip.tcl
################################################################

# Path to hls4ml-exported IP (relative to repo root, same as create_block_design.tcl)
set SCRIPT_DIR [file dirname [file normalize [info script]]]
set REPO_ROOT  [file dirname ${SCRIPT_DIR}]
set HLS_IP_REPO [file normalize [file join ${REPO_ROOT} notebooks hls4ml_prj myproject_prj solution1 impl ip]]

# ── Step 1: Register new IP repository ──────────────────────
puts "INFO: Registering HLS IP repository..."
if {![file exists ${HLS_IP_REPO}]} {
    error "HLS IP not found at: ${HLS_IP_REPO}\nRun Phase 1C (hls4ml build) first."
}

set_property IP_REPO_PATHS [list ${HLS_IP_REPO}] [current_project]
update_ip_catalog -rebuild
puts "INFO: IP catalog updated."

# ── Step 2: Find the real HLS IP VLNV ───────────────────────
set hls_ip_list [get_ipdefs -filter {VLNV =~ *myproject_axi*}]
if {[llength $hls_ip_list] == 0} {
    error "Could not find hls4ml IP in catalog. Check HLS_IP_REPO path."
}
set HLS_VLNV [lindex $hls_ip_list 0]
puts "INFO: Found HLS IP: ${HLS_VLNV}"

# ── Step 3: Open Block Design ────────────────────────────────
open_bd_design [get_files system.bd]
current_bd_design system

# ── Step 4: Check what cifar10_accel_0 currently is ─────────
set accel_cell [get_bd_cells cifar10_accel_0]
set current_vlnv [get_property VLNV $accel_cell]
puts "INFO: Current placeholder IP: ${current_vlnv}"

if {$current_vlnv eq $HLS_VLNV} {
    puts "INFO: Real HLS IP already instantiated. Nothing to replace."
} else {
    # ── Step 5: Record existing interface connections ────────
    # Interfaces to reconnect after replacement:
    #   S_AXIS_DATA  ← axi_dma_0/M_AXIS_MM2S
    #   M_AXIS_RESULT → axi_dma_0/S_AXIS_S2MM
    #   aclk         ← zynq_ultra_ps_e_0/pl_clk0
    #   aresetn      ← proc_sys_reset_200mhz/peripheral_aresetn

    # ── Step 6: Delete placeholder ──────────────────────────
    puts "INFO: Deleting placeholder IP: cifar10_accel_0"
    delete_bd_objs [get_bd_cells cifar10_accel_0]

    # ── Step 7: Instantiate real HLS IP ─────────────────────
    puts "INFO: Instantiating real HLS IP..."
    set new_accel [create_bd_cell -type ip \
        -vlnv ${HLS_VLNV} \
        cifar10_accel_0]

    # ── Step 8: Reconnect interfaces ────────────────────────
    puts "INFO: Reconnecting interfaces..."

    # Clock / reset (myproject_axi uses ap_clk / ap_rst_n)
    connect_bd_net \
        [get_bd_pins zynq_ultra_ps_e_0/pl_clk0] \
        [get_bd_pins cifar10_accel_0/ap_clk]

    connect_bd_net \
        [get_bd_pins proc_sys_reset_200mhz/peripheral_aresetn] \
        [get_bd_pins cifar10_accel_0/ap_rst_n]

    # AXI4-Stream: myproject_axi uses input_stream / output_stream (16-bit TDATA)
    set accel_in  [get_bd_intf_pins -quiet cifar10_accel_0/input_stream]
    set accel_out [get_bd_intf_pins -quiet cifar10_accel_0/output_stream]
    if {$accel_in eq "" || $accel_out eq ""} {
        error "myproject_axi must expose input_stream and output_stream interfaces."
    }
    connect_bd_intf_net \
        [get_bd_intf_pins axi_dma_0/M_AXIS_MM2S] \
        $accel_in
    connect_bd_intf_net \
        $accel_out \
        [get_bd_intf_pins axi_dma_0/S_AXIS_S2MM]

    puts "INFO: IP replacement complete."
}

# ── Step 9: Validate & Save ──────────────────────────────────
puts "INFO: Validating Block Design..."
validate_bd_design
save_bd_design
puts "INFO: Block Design saved."

# ── Step 10: Regenerate output products ─────────────────────
puts "INFO: Regenerating output products..."
generate_target all [get_files system.bd]

puts ""
puts "================================================================"
puts "  HLS IP replacement complete!"
puts "  Next steps:"
puts "  1. Review and close any remaining connection warnings"
puts "  2. Run synthesis: launch_runs synth_1 -jobs 8"
puts "  3. Run implementation: launch_runs impl_1 -jobs 8"
puts "  4. Generate bitstream: launch_runs impl_1 -to_step write_bitstream"
puts "================================================================"
