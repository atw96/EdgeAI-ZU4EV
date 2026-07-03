################################################################
# rebuild_after_ila.tcl — reset synth/impl after ILA BD change
################################################################
open_project ./vivado_project/EdgeAI_ZU4EV.xpr
reset_run synth_1
reset_run impl_1
puts "INFO: synth_1 and impl_1 reset for ILA rebuild"
