# Force replace HLS IP cell to pick up re-exported RTL (same VLNV).
set SCRIPT_DIR [file dirname [file normalize [info script]]]
set REPO_ROOT  [file dirname ${SCRIPT_DIR}]
set HLS_IP_REPO [file normalize [file join ${REPO_ROOT} notebooks hls4ml_prj myproject_prj solution1 impl ip]]

open_project [file join ${REPO_ROOT} vivado_project EdgeAI_ZU4EV.xpr]
set_property IP_REPO_PATHS [list ${HLS_IP_REPO}] [current_project]
update_ip_catalog -rebuild

open_bd_design [get_files system.bd]

set hls_ip_list [get_ipdefs -filter {VLNV =~ *myproject_axi*}]
if {[llength $hls_ip_list] == 0} {
    error "myproject_axi not in IP catalog"
}
set HLS_VLNV [lindex $hls_ip_list 0]
puts "INFO: HLS VLNV = ${HLS_VLNV}"

# Remove ILA tee on output_stream before deleting HLS cell
set sys_ila [get_bd_cells -quiet system_ila_output]
if {$sys_ila ne ""} {
    puts "INFO: removing system_ila_output for HLS replace"
    delete_bd_objs $sys_ila
}

set accel_cell [get_bd_cells -quiet cifar10_accel_0]
if {$accel_cell ne ""} {
    puts "INFO: deleting cifar10_accel_0"
    delete_bd_objs $accel_cell
}

puts "INFO: creating fresh cifar10_accel_0"
create_bd_cell -type ip -vlnv ${HLS_VLNV} cifar10_accel_0

connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_clk0] [get_bd_pins cifar10_accel_0/ap_clk]
set rst_ps [get_bd_cells -quiet proc_sys_reset_pl]
if {$rst_ps eq ""} { set rst_ps [get_bd_cells proc_sys_reset_200mhz] }
connect_bd_net [get_bd_pins ${rst_ps}/peripheral_aresetn] [get_bd_pins cifar10_accel_0/ap_rst_n]

connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXIS_MM2S] [get_bd_intf_pins cifar10_accel_0/input_stream]
connect_bd_intf_net [get_bd_intf_pins cifar10_accel_0/output_stream] [get_bd_intf_pins axi_dma_0/S_AXIS_S2MM]

validate_bd_design
save_bd_design
generate_target all [get_files system.bd]
puts "INFO: force_replace_hls_ip.tcl done — run add_dma_ila.tcl + impl next"
