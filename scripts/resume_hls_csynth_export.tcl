# Minimal HLS resume: open existing project/solution, csynth + export only.
# Run from notebooks/hls4ml_prj (see run_v8_resume_hls.sh).
source [file join [pwd] project.tcl]

open_project ${project_name}_prj
open_solution solution1

puts "***** C/RTL SYNTHESIS (resume) *****"
set time_start [clock clicks -milliseconds]
csynth_design
set time_end [clock clicks -milliseconds]
set time_taken [expr $time_end - $time_start]
puts "***** C/RTL SYNTHESIS COMPLETED IN [expr $time_taken/1000]s *****"

puts "***** EXPORT IP *****"
set time_start [clock clicks -milliseconds]
export_design -format ip_catalog -version $version
set time_end [clock clicks -milliseconds]
set time_taken [expr $time_end - $time_start]
puts "***** EXPORT IP COMPLETED IN [expr $time_taken/1000]s *****"

exit
