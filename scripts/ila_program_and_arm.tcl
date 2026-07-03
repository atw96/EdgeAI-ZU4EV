################################################################
# ila_program_and_arm.tcl — Program bit with ILA and arm trigger (needs JTAG cable)
################################################################

set PROJECT_DIR "./vivado_project"
set PROJECT_NAME "EdgeAI_ZU4EV"
set BIT_FILE "./deploy/cifar10_accel.bit"
set LTX_FILE "./deploy/cifar10_accel.ltx"

open_hw_manager
connect_hw_server
open_hw_target

set dev [lindex [get_hw_devices] 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes -quiet

if {![file exists $BIT_FILE]} {
    puts "ERROR: Missing $BIT_FILE — run impl + bitstream first"
    exit 1
}

set_property PROGRAM.FILE [file normalize $BIT_FILE] [get_hw_devices $dev]
if {[file exists $LTX_FILE]} {
    set_property PROBES.FILE [file normalize $LTX_FILE] [get_hw_devices $dev]
}

program_hw_devices [get_hw_devices $dev]

set ila [get_hw_ilas -quiet hw_ila_1]
if {$ila eq ""} {
    set ila [lindex [get_hw_ilas] 0]
}
if {$ila eq ""} {
    puts "WARN: No ILA found in programmed design"
    exit 0
}

puts "INFO: Arming ILA $ila — trigger: probe2 (axi_resetn) == 0"
set_property CONTROL.TRIGGER_POSITION 512 $ila
set_property CONTROL.DATA_DEPTH 4096 $ila

# probe2 = axi_resetn active-low; capture when reset asserted
set_property TRIGGER_COMPARE_VALUE eq0'b0 [get_hw_probes probe2 -of_objects $ila]

run_hw_ila $ila
wait_on_hw_ila -timeout 10000 $ila

set csv "./deploy/ila_dma_capture.csv"
open $csv w
write_hw_ila_data -csv_file $csv -force $ila
close [open $csv a]
puts "INFO: ILA capture written to $csv"
puts "INFO: In Vivado HW Manager, open hw_ila_1 waveform for visual check"

exit 0
