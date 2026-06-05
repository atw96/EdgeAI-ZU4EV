#!/usr/bin/env python3
"""
cpu_baseline.py
EdgeAI-ZU4EV — Phase 3B: ARM Cortex-A53 CPU Baseline Inference

Measures TFLite inference latency on the PS-side ARM cores (PetaLinux 2020.1).
Run on the board in Linux terminal:
    python3 cpu_baseline.py

Requirements (install on board):
    PetaLinux 2020.1 / Python 3.7.6 — stock image has no pip3.
    Install tflite_runtime manually (cp37 aarch64 wheel):
        bash scripts/board_install_tflite_and_rerun.sh   # from WSL/host
    See README.md § Getting Started → Board prerequisites.
"""

import os
import sys
import time
import json
import subprocess
import numpy as np

# ── TFLite Runtime ────────────────────────────────────────────
# Prefer lightweight tflite_runtime over full TF on embedded board
try:
    import tflite_runtime.interpreter as tflite
    TF_BACKEND = 'tflite_runtime'
except ImportError:
    try:
        import tensorflow as tf
        tflite = tf.lite
        TF_BACKEND = 'tensorflow_lite'
    except ImportError:
        print('[ERROR] Neither tflite_runtime nor tensorflow found.')
        print('        Install: pip3 install tflite-runtime')
        sys.exit(1)

print(f'TFLite backend: {TF_BACKEND}')

# ── Constants ─────────────────────────────────────────────────
MODEL_PATH  = os.environ.get('MODEL_PATH', 'model_int8.tflite')
BENCH_NPZ   = os.environ.get('BENCH_NPZ', 'cifar10_bench.npz')
N_BENCH     = int(os.environ.get('N_BENCH', '100'))
N_ACCURACY  = int(os.environ.get('N_ACCURACY', '100'))
CLASS_NAMES = ['airplane','automobile','bird','cat','deer',
               'dog','frog','horse','ship','truck']


# ──────────────────────────────────────────────────────────────
# Step 0: Convert .h5 → .tflite (run this on a PC if needed)
# ──────────────────────────────────────────────────────────────

def convert_h5_to_tflite(h5_path='model_fp32.h5',
                          tflite_out='model_int8.tflite',
                          quantize=True):
    """
    Convert Keras .h5 model to INT8 TFLite format using TF 2.x converter.
    Run this function on a PC with full TensorFlow, not on the board.

    Args:
        h5_path    : Path to FP32 Keras model (.h5)
        tflite_out : Output .tflite file path
        quantize   : If True, apply full INT8 post-training quantisation
    """
    import tensorflow as tf

    model = tf.keras.models.load_model(h5_path)

    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    if quantize:
        # Full INT8 quantisation with representative dataset
        def representative_dataset():
            # Load CIFAR-10 data for calibration (100 samples)
            (_, _), (x_test, _) = tf.keras.datasets.cifar10.load_data()
            x_test = x_test.astype('float32') / 255.0
            for i in range(100):
                yield [x_test[i:i+1]]

        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.representative_dataset = representative_dataset
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type  = tf.int8
        converter.inference_output_type = tf.int8

    tflite_model = converter.convert()

    with open(tflite_out, 'wb') as f:
        f.write(tflite_model)

    size_kb = os.path.getsize(tflite_out) / 1024
    print(f'Converted: {tflite_out} ({size_kb:.1f} KB)')
    return tflite_out


# ──────────────────────────────────────────────────────────────
# Step 1: Read CPU Info from /proc/cpuinfo
# ──────────────────────────────────────────────────────────────

def get_cpu_info():
    """Read ARM core info from /proc/cpuinfo."""
    cpu_info = {
        'platform'   : 'Unknown',
        'processor'  : 'Unknown',
        'freq_mhz'   : 'Unknown',
        'num_cores'  : 1,
    }

    try:
        with open('/proc/cpuinfo', 'r') as f:
            content = f.read()

        lines = content.splitlines()
        model_name_lines = [l for l in lines if 'Model name' in l or 'Hardware' in l]
        cpu_info['processor'] = (model_name_lines[0].split(':')[1].strip()
                                 if model_name_lines else 'ARM Cortex-A53')

        core_count = content.count('processor\t:')
        cpu_info['num_cores'] = max(core_count, 1)

        # Read frequency from scaling
        freq_path = '/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq'
        if os.path.exists(freq_path):
            with open(freq_path) as f:
                freq_khz = int(f.read().strip())
            cpu_info['freq_mhz'] = freq_khz // 1000
        else:
            cpu_info['freq_mhz'] = 1333  # ZU4EV A53 default

    except Exception as e:
        print(f'[WARN] Could not read CPU info: {e}')

    cpu_info['platform'] = (
        f"ARM Cortex-A53 x{cpu_info['num_cores']} @ {cpu_info['freq_mhz']} MHz"
    )

    return cpu_info


# ──────────────────────────────────────────────────────────────
# Step 2: Load TFLite Interpreter
# ──────────────────────────────────────────────────────────────

def load_interpreter(model_path):
    """Load TFLite model and allocate tensors."""
    if not os.path.exists(model_path):
        print(f'[ERROR] Model not found: {model_path}')
        print('        Run convert_h5_to_tflite() first (on a PC).')
        sys.exit(1)

    if TF_BACKEND == 'tflite_runtime':
        interpreter = tflite.Interpreter(model_path=model_path, num_threads=4)
    else:
        interpreter = tflite.Interpreter(model_path=model_path, num_threads=4)

    interpreter.allocate_tensors()

    in_detail  = interpreter.get_input_details()[0]
    out_detail = interpreter.get_output_details()[0]

    print(f'Model loaded : {model_path}')
    print(f'  Input  : shape={in_detail["shape"]}  dtype={in_detail["dtype"]}')
    print(f'  Output : shape={out_detail["shape"]} dtype={out_detail["dtype"]}')

    return interpreter, in_detail, out_detail


# ──────────────────────────────────────────────────────────────
# Step 3: Inference Helper
# ──────────────────────────────────────────────────────────────

def run_inference(interpreter, in_detail, out_detail, image_f32):
    """
    Run single inference on ARM CPU via TFLite.

    Args:
        image_f32: np.ndarray shape (32,32,3), float32 [0,1]
    Returns:
        probs: np.ndarray shape (10,), float32
        latency_ms: float
    """
    # Prepare input (INT8 model expects int8)
    inp_dtype = in_detail['dtype']
    if inp_dtype == np.int8:
        scale, zero_point = in_detail['quantization']
        inp = (image_f32 / scale + zero_point).astype(np.int8)
    elif inp_dtype == np.uint8:
        inp = (image_f32 * 255).astype(np.uint8)
    else:
        inp = image_f32.astype(np.float32)

    inp = inp[np.newaxis, ...]  # add batch dim

    t0 = time.perf_counter()
    interpreter.set_tensor(in_detail['index'], inp)
    interpreter.invoke()
    raw_out = interpreter.get_tensor(out_detail['index'])
    t1 = time.perf_counter()

    latency_ms = (t1 - t0) * 1000

    # Dequantise output if INT8
    out_dtype = out_detail['dtype']
    if out_dtype == np.int8:
        scale, zero_point = out_detail['quantization']
        probs = (raw_out.astype(np.float32) - zero_point) * scale
    else:
        probs = raw_out.astype(np.float32)

    # Softmax (in case model outputs logits)
    probs = probs.flatten()
    probs = np.exp(probs - probs.max())
    probs /= probs.sum()

    return probs, latency_ms


# ──────────────────────────────────────────────────────────────
# Step 4: Load CIFAR-10 Data (on-board)
# ──────────────────────────────────────────────────────────────

def load_cifar10():
    """Load test images: prefer deploy/cifar10_bench.npz on board, else TF download."""
    if os.path.isfile(BENCH_NPZ):
        data = np.load(BENCH_NPZ, allow_pickle=True)
        labels = data['labels'].astype(np.int32)
        payloads = data['payloads']
        x_list = []
        for i, raw in enumerate(payloads):
            fixed = np.frombuffer(bytes(raw), dtype=np.int16).reshape(32, 32, 3)
            x_list.append((fixed.astype(np.float32) / 1024.0).clip(0.0, 1.0))
        x_test = np.stack(x_list, axis=0)
        y_test = labels[: len(x_list)]
        print('  Loaded from %s (%d samples)' % (BENCH_NPZ, len(x_test)))
        return x_test, y_test

    try:
        import tensorflow as tf
        (_, _), (x_test, y_test) = tf.keras.datasets.cifar10.load_data()
    except Exception as exc:
        print('[ERROR] No %s and TF unavailable: %s' % (BENCH_NPZ, exc))
        sys.exit(1)

    x_test = x_test.astype('float32') / 255.0
    y_test = y_test.flatten()
    return x_test, y_test


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    print('='*60)
    print('  EdgeAI-ZU4EV: ARM CPU Baseline Benchmark')
    print('='*60)

    # CPU info
    cpu_info = get_cpu_info()
    print(f'\nCPU Platform: {cpu_info["platform"]}')
    print(f'  Cores : {cpu_info["num_cores"]}')
    print(f'  Freq  : {cpu_info["freq_mhz"]} MHz')

    # Load data
    print('\nLoading CIFAR-10 test data...')
    x_test, y_test = load_cifar10()
    print(f'  {len(x_test)} test images loaded.')

    # Load model
    print(f'\nLoading TFLite model: {MODEL_PATH}')
    interpreter, in_detail, out_detail = load_interpreter(MODEL_PATH)
    model_size_kb = os.path.getsize(MODEL_PATH) / 1024

    # Warm-up (5 runs, not counted)
    print('\nWarming up (5 runs)...')
    for i in range(5):
        run_inference(interpreter, in_detail, out_detail, x_test[i])

    # ── Latency Benchmark ──────────────────────────────────────
    print(f'\nBenchmarking latency ({N_BENCH} runs, single image)...')
    latencies = []
    bench_img = x_test[0]

    for i in range(N_BENCH):
        _, lat = run_inference(interpreter, in_detail, out_detail, bench_img)
        latencies.append(lat)

    latencies    = np.array(latencies)
    avg_lat_ms   = float(np.mean(latencies))
    std_lat_ms   = float(np.std(latencies))
    min_lat_ms   = float(np.min(latencies))
    throughput   = 1000.0 / avg_lat_ms

    print(f'  Mean latency : {avg_lat_ms:.3f} ms')
    print(f'  Std  latency : {std_lat_ms:.3f} ms')
    print(f'  Min  latency : {min_lat_ms:.3f} ms')
    print(f'  Throughput   : {throughput:.1f} fps')

    # ── Accuracy Benchmark ────────────────────────────────────
    print(f'\nMeasuring accuracy ({N_ACCURACY} images)...')
    preds = []
    for i in range(N_ACCURACY):
        probs, _ = run_inference(interpreter, in_detail, out_detail, x_test[i])
        preds.append(np.argmax(probs))

    preds      = np.array(preds)
    true_labels = y_test[:N_ACCURACY]
    accuracy   = float(np.mean(preds == true_labels) * 100)
    print(f'  Top-1 Accuracy: {accuracy:.2f}% ({N_ACCURACY} images)')

    # ── Save Results ──────────────────────────────────────────
    result = {
        'platform'        : cpu_info['platform'],
        'model'           : MODEL_PATH,
        'model_size_kb'   : round(model_size_kb, 1),
        'backend'         : TF_BACKEND,
        'num_threads'     : 4,
        'n_benchmark_runs': N_BENCH,
        'avg_latency_ms'  : round(avg_lat_ms, 4),
        'std_latency_ms'  : round(std_lat_ms, 4),
        'min_latency_ms'  : round(min_lat_ms, 4),
        'throughput_fps'  : round(throughput, 1),
        'accuracy_top1'   : round(accuracy, 2),
        'n_accuracy_imgs' : N_ACCURACY,
        'cpu_info'        : cpu_info,
    }

    out_path = 'results/cpu_baseline.json'
    os.makedirs('results', exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f'\nResults saved to: {out_path}')
    print('\n' + '='*60)
    print('  Summary')
    print('='*60)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
