#!/bin/bash
# One-shot cleanup: redundant debug scripts, run caches, hls4ml backups.
# Safe to re-run; only removes known ephemeral / obsolete paths.
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"

log() { echo "[cleanup] $*"; }

# ── Obsolete Plan B / duplicate v19 scripts ──
OBSOLETE_SCRIPTS=(
  scripts/patch_notebook_precision_v17_qat.py
  scripts/patch_notebook_precision_from_profiling.py
  scripts/patch_notebook_precision_conv1ab.py
  scripts/patch_notebook_plan_b_extras.py
  scripts/patch_notebook_precision_v19.py
  scripts/patch_notebook_precision_cprime.py
  scripts/patch_notebook_step5_gap.py
  scripts/run_v19_plan_a_bitexact.sh
  scripts/run_v19_plan_b_reconvert.sh
  scripts/run_v19_plan_b_profiling_gpu.sh
  scripts/run_v19_conv1ab_reconvert.sh
  scripts/v19_plan_b_profiling_gpu.py
  scripts/v19_profiling_compare.py
  scripts/run_v19_bitexact_gates.sh
  scripts/run_v19_profiling_and_reconvert.sh
  scripts/run_v19_route1_full.sh
  scripts/run_v19_qat_pipeline.sh
  scripts/hls_csim_accuracy_gate.py
  scripts/run_v18_experiment_a.sh
  scripts/run_v18_experiment_b.sh
  scripts/run_v18_experiment_c.sh
  scripts/run_v18_experiment_c_prime.sh
  scripts/run_v18_experiment_c_prime_resume.sh
  scripts/run_v18_gates_only.sh
  scripts/run_v18_step5_fix.sh
  scripts/run_v8_resume_hls.sh
  scripts/run_v8_optimized_rebuild.sh
  scripts/run_v9_resource_fit_rebuild.sh
  scripts/run_v10_lowmem_rebuild.sh
  scripts/run_v11_resource_fit_rebuild.sh
  scripts/run_v12_synth_fix_rebuild.sh
  scripts/run_v13_accuracy_rebuild.sh
  scripts/run_v14_resource_accuracy_rebuild.sh
  scripts/run_v15_lut_fit_rebuild.sh
  scripts/run_v15_force_export_vivado.sh
  scripts/run_v16_dma_fix_rebuild.sh
  scripts/run_v17_dma_csim_fix.sh
  scripts/start_axis32_monitor.sh
  scripts/start_serial32_pipeline.sh
  scripts/start_slot32_pipeline.sh
  scripts/start_gap_only_pipeline.sh
  scripts/run_axis32_out_pipeline.sh
  scripts/run_serial32_out_pipeline.sh
  scripts/run_slot32_out_pipeline.sh
  scripts/run_dataflow0_rebuild.sh
  scripts/run_bd_fix_pipeline.sh
  scripts/run_bd_fix_v2.sh
  scripts/run_axi_fix_pipeline.sh
  scripts/run_clean_rebuild_pipeline.sh
  scripts/run_hls_rebuild_pipeline.sh
  scripts/run_post_hls_pipeline.sh
  scripts/run_post_axis32_success.sh
  scripts/run_strategy_pipeline.sh
  scripts/run_head_latency_pipeline.sh
  scripts/run_gap_only_pipeline.sh
  scripts/monitor_axis32_live.sh
  scripts/poll_axis32_status.sh
  scripts/audit_ip_cache.sh
)

for f in "${OBSOLETE_SCRIPTS[@]}"; do
  if [[ -f "$f" ]]; then
    rm -f "$f"
    log "removed $f"
  fi
done

# ── Run logs & lock files ──
rm -f results/*.log results/.v19_qat_pipeline.lock 2>/dev/null || true
log "removed results/*.log"

# ── Large / intermediate result artifacts (keep summaries in git) ──
rm -f results/gap_csim_keras_align.json
rm -f results/gap_axi_csim_board_align.json
rm -f results/gap_csim_board_compare.json
rm -f results/axis32_debug_analysis.json
rm -f results/v19_conv1ab_reconvert_summary.json
rm -f results/v19_plan_b_profiling_summary.json
rm -f results/v19_plan_a_bitexact_summary.json
rm -f results/v19_csim_keras_layer_align.json
rm -f results/v19_csim_keras_layer_align.md
rm -f results/hls_csim_accuracy_gate.json
rm -f results/plan_b_*.png 2>/dev/null || true
log "removed intermediate result JSON/plots"

# ── hls4ml project backups (rebuild from notebooks) ──
if compgen -G "notebooks/hls4ml_prj.bak*" > /dev/null; then
  rm -rf notebooks/hls4ml_prj.bak*
  log "removed notebooks/hls4ml_prj.bak*"
fi
rm -rf notebooks/hls4ml_prj_v19_plan_b_tmp 2>/dev/null || true

# ── Model h5 backups from finetune ──
rm -f notebooks/model_int8_qkeras.h5.bak_* 2>/dev/null || true
rm -f notebooks/model_int8_qkeras.h5.bak_before_input_qact_* 2>/dev/null || true

# ── Python cache ──
find scripts -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

log "cleanup done: $REPO"
