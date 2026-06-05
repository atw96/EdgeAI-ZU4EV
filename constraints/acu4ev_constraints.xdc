################################################################
# acu4ev_constraints.xdc
# EdgeAI-ZU4EV — Vivado 2020.1 Physical & Timing Constraints
#
# Board  : ALINX ACU4EV (Xilinx Zynq UltraScale+ XCZU4EV-1SFVC784I)
# Tool   : Vivado 2020.1
#
# Implementation Strategy Recommendation:
#   Strategy    : Performance_ExplorePostRoutePhysOpt
#   Directive   : Default
#   Opt Design  : Default
#   Phys Opt    : AggressiveExplore
#   Place Design: Explore
#   Route Design: MoreGlobalIterations
#
# NOTE: This constraints file is intended for the BD revision that
#       exports real PL debug ports to the board top level:
#         - pl_led1
#         - pl_uart_txd / pl_uart_rxd
#         - pl_status_gpio[3:0]
#
# Verified against the following schematic pages:
#   AXU4EVB-P开发板原理图 PAGE03 / PAGE15 / PAGE20
#   ACU4EV核心板原理图   PAGE04 / PAGE19
################################################################

################################################################
# 1. Clock Constraints
################################################################

set pl_clk0_pin [lindex [get_pins -quiet -hier *zynq_ultra_ps_e_0/pl_clk0] 0]
if {$pl_clk0_pin ne "" && [llength [get_clocks -quiet pl_clk0]] == 0} {
    create_clock -name pl_clk0 -period 5.000 $pl_clk0_pin
}

set pl_clk1_pin [lindex [get_pins -quiet -hier *zynq_ultra_ps_e_0/pl_clk1] 0]
if {$pl_clk1_pin ne "" && [llength [get_clocks -quiet pl_clk1]] == 0} {
    create_clock -name pl_clk1 -period 10.000 $pl_clk1_pin
}

################################################################
# 2. Board I/O Pin Constraints
################################################################

# PL LED1
# AXU4EVB-P PAGE20: PL_LED1
# AXU4EVB-P PAGE03: PL_LED1 -> J3 pin 19 -> B44_L1_P
# ACU4EV  PAGE19:   B44_L1_P
# ACU4EV  PAGE04:   B44_L1_P -> FPGA AE15
# BD exports a 1-bit scalar port named pl_led1 (not pl_led1[0])
set_property PACKAGE_PIN AE15 [get_ports pl_led1]
set_property IOSTANDARD  LVCMOS33 [get_ports pl_led1]

# PL UART
# AXU4EVB-P PAGE15/PAGE03:
#   PL_UART_TX -> J3 -> B43_L9_P -> FPGA AA11
#   PL_UART_RX -> J3 -> B43_L9_N -> FPGA AA10
set_property PACKAGE_PIN AA11 [get_ports pl_uart_txd]
set_property IOSTANDARD  LVCMOS33 [get_ports pl_uart_txd]

set_property PACKAGE_PIN AA10 [get_ports pl_uart_rxd]
set_property IOSTANDARD  LVCMOS33 [get_ports pl_uart_rxd]

# Extra debug GPIOs use the camera expansion signals on J23.
# This board only exposes one dedicated PL LED, so the remaining
# status bits are exported on real GPIO nets instead of fabricated LEDs.
# Do not connect an external MIPI camera module while reusing these pins.
#   pl_status_gpio[0] -> CAM_GPIO -> B43_L4_P  -> FPGA AE10
#   pl_status_gpio[1] -> CAM_CLK  -> B43_L4_N  -> FPGA AF10
#   pl_status_gpio[2] -> CAM_SCL  -> B43_L11_P -> FPGA Y9
#   pl_status_gpio[3] -> CAM_SDA  -> B43_L11_N -> FPGA AA8
set_property PACKAGE_PIN AE10 [get_ports {pl_status_gpio[0]}]
set_property IOSTANDARD  LVCMOS33 [get_ports {pl_status_gpio[0]}]

set_property PACKAGE_PIN AF10 [get_ports {pl_status_gpio[1]}]
set_property IOSTANDARD  LVCMOS33 [get_ports {pl_status_gpio[1]}]

set_property PACKAGE_PIN Y9 [get_ports {pl_status_gpio[2]}]
set_property IOSTANDARD  LVCMOS33 [get_ports {pl_status_gpio[2]}]

set_property PACKAGE_PIN AA8 [get_ports {pl_status_gpio[3]}]
set_property IOSTANDARD  LVCMOS33 [get_ports {pl_status_gpio[3]}]

################################################################
# 3. Timing Exceptions
################################################################

# Cross-clock-domain paths between the control domain (100 MHz)
# and datapath domain (200 MHz) are handled by AXI/SmartConnect IP.
if {[llength [get_clocks -quiet pl_clk0]] > 0 && [llength [get_clocks -quiet pl_clk1]] > 0} {
	set_clock_groups -asynchronous \
		-group [get_clocks pl_clk0] \
		-group [get_clocks pl_clk1]
}

# Relax timing for non-critical board debug outputs.
if {[llength [get_clocks -quiet pl_clk0]] > 0} {
	set_output_delay -clock [get_clocks pl_clk0] 0 [get_ports pl_led1]
	set_output_delay -clock [get_clocks pl_clk0] 0 [get_ports {pl_status_gpio[*]}]
}

################################################################
# 4. Bitstream Configuration
################################################################

# Configure SPI flash for boot (ACU4EV uses QSPI)
set_property CONFIG_VOLTAGE       1.8              [current_design]
set_property CFGBVS               GND              [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH    4    [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE      85.0 [current_design]
set_property BITSTREAM.GENERAL.COMPRESS       TRUE [current_design]
set_property BITSTREAM.CONFIG.UNUSEDPIN       Pullnone [current_design]

################################################################
# 5. Implementation Strategy Notes (reference, not Tcl commands)
################################################################
# Recommended Vivado 2020.1 Implementation Settings:
#   Flow_PerfOptimized_high strategy
#   opt_design     -directive   Explore
#   place_design   -directive   Explore
#   phys_opt_design -directive  AggressiveExplore
#   route_design   -directive   AggressiveExplore
#   phys_opt_design -directive  AggressiveExplore  (post-route)
#
# For timing closure on 200 MHz paths:
#   - Enable Multi-Strategy (set in Implementation Settings)
#   - Use block placement constraints (Pblock) if critical
################################################################

puts "INFO: acu4ev_constraints.xdc loaded."
puts "INFO: Applied ACU4EV board pin constraints for PL LED, PL UART, and debug GPIOs."
