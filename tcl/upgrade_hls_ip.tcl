# Force refresh HLS IP from latest export (same VLNV, new RTL).
set SCRIPT_DIR [file dirname [file normalize [info script]]]
set REPO_ROOT  [file dirname ${SCRIPT_DIR}]
set HLS_IP_REPO [file normalize [file join ${REPO_ROOT} notebooks hls4ml_prj myproject_prj solution1 impl ip]]

open_project [file join ${REPO_ROOT} vivado_project EdgeAI_ZU4EV.xpr]
set_property IP_REPO_PATHS [list ${HLS_IP_REPO}] [current_project]
update_ip_catalog -rebuild
open_bd_design [get_files system.bd]

set ip [get_ips -quiet system_cifar10_accel_0_0]
if {$ip eq ""} {
    set ip [get_ips -quiet cifar10_accel_0]
}
if {$ip eq ""} {
    error "cifar10_accel HLS IP instance not found"
}
puts "INFO: upgrading IP ${ip}"
upgrade_ip ${ip}
validate_bd_design
save_bd_design
generate_target all [get_files system.bd]
puts "INFO: upgrade_hls_ip.tcl done"
