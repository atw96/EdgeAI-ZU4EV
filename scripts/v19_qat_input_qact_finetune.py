#!/usr/bin/env python3
"""Fine-tune Q6 student with Input QActivation (Route 1 — required before bit_exact convert)."""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
MODEL_H5 = REPO / 'notebooks' / 'model_int8_qkeras.h5'
TEACHER_H5 = REPO / 'notebooks' / 'model_teacher.h5'
OUT_JSON = REPO / 'results' / 'v19_input_qact_finetune.json'


def _conv_block_q(x, filters, prefix, k_q, b_q, a_q, layers, QConv2D, QActivation):
    """QActivation(quantized_bits) -> hls4ml nnet::linear (same path as input_qact)."""
    for suffix in ('a', 'b'):
        name = f'{prefix}{suffix}'
        x = QConv2D(
            filters, 3, padding='same', use_bias=False,
            kernel_quantizer=k_q, bias_quantizer=b_q, name=name,
        )(x)
        x = layers.BatchNormalization(name=f'bn_{name}')(x)
        x = QActivation(a_q, name=f'relu_{name}')(x)
    return x


def _parse_quant_alpha(raw):
    if raw in ('1', '1.0'):
        return 1
    return raw


def build_q6_input_qact(keras, layers, QConv2D, QDense, QActivation, quantized_bits, quantized_relu,
                        name='VGG_Lite_Q6', quant_alpha='auto_po2'):
    alpha = _parse_quant_alpha(str(quant_alpha))
    k_q = quantized_bits(6, 0, alpha=alpha)
    b_q = quantized_bits(6, 2, alpha=alpha)
    a_q = quantized_relu(6, 2)
    inp_q = quantized_bits(6, 0, alpha=alpha)
    inp = keras.Input((32, 32, 3), name='input_image')
    x = QActivation(inp_q, name='input_qact')(inp)
    x = _conv_block_q(x, 16, 'conv1', k_q, b_q, a_q, layers, QConv2D, QActivation)
    x = layers.MaxPooling2D(2, name='pool1')(x)
    x = _conv_block_q(x, 20, 'conv2', k_q, b_q, a_q, layers, QConv2D, QActivation)
    x = layers.MaxPooling2D(2, name='pool2')(x)
    x = _conv_block_q(x, 24, 'conv3', k_q, b_q, a_q, layers, QConv2D, QActivation)
    x = layers.GlobalAveragePooling2D(name='gap')(x)
    out = QDense(
        10, activation='softmax', kernel_quantizer=k_q, bias_quantizer=b_q, name='predictions',
    )(x)
    return keras.Model(inp, out, name=name)


def make_datasets(tf, keras, batch_size=128):
    (x_train, y_train), (x_test, y_test) = keras.datasets.cifar10.load_data()
    x_train = x_train.astype('float32') / 255.0
    x_test = x_test.astype('float32') / 255.0
    y_train_ohe = keras.utils.to_categorical(y_train, 10)
    y_test_ohe = keras.utils.to_categorical(y_test, 10)
    autotune = tf.data.AUTOTUNE

    def augment(image, label):
        image = tf.image.random_flip_left_right(image)
        image = tf.image.pad_to_bounding_box(image, 4, 4, 40, 40)
        image = tf.image.random_crop(image, size=[32, 32, 3])
        return image, label

    train_ds = (
        tf.data.Dataset.from_tensor_slices((x_train, y_train_ohe))
        .shuffle(50000).map(augment, num_parallel_calls=autotune)
        .batch(batch_size).prefetch(autotune)
    )
    val_ds = (
        tf.data.Dataset.from_tensor_slices((x_test, y_test_ohe))
        .batch(batch_size).prefetch(autotune)
    )
    return train_ds, val_ds


def load_teacher(keras, path):
    if not path.is_file():
        return None
    return keras.models.load_model(str(path), compile=False)


def finetune(student, teacher, train_ds, val_ds, epochs, lr, kd_alpha, kd_temp):
    import tensorflow as tf

    class WarmupCosineDecay(tf.keras.optimizers.schedules.LearningRateSchedule):
        def __init__(self, initial_lr, steps_per_epoch, total_epochs, warmup_epochs=3, min_lr=1e-5):
            self.initial_lr = float(initial_lr)
            self.warmup_steps = int(warmup_epochs * steps_per_epoch)
            self.total_steps = int(total_epochs * steps_per_epoch)
            self.min_lr = float(min_lr)

        def __call__(self, step):
            step = tf.cast(step, tf.float32)
            warmup = self.initial_lr * step / tf.maximum(tf.cast(self.warmup_steps, tf.float32), 1.0)
            progress = tf.clip_by_value(
                (step - tf.cast(self.warmup_steps, tf.float32))
                / tf.maximum(tf.cast(self.total_steps - self.warmup_steps, tf.float32), 1.0),
                0.0, 1.0,
            )
            cosine = self.min_lr + 0.5 * (self.initial_lr - self.min_lr) * (1.0 + tf.cos(np.pi * progress))
            return tf.cond(step < tf.cast(self.warmup_steps, tf.float32), lambda: warmup, lambda: cosine)

    opt = tf.keras.optimizers.SGD(
        learning_rate=WarmupCosineDecay(lr, len(train_ds), epochs, warmup_epochs=3, min_lr=1e-5),
        momentum=0.9, nesterov=True,
    )

    def kd_loss(s_logits, t_logits, y_true):
        ce = tf.reduce_mean(tf.keras.losses.categorical_crossentropy(y_true, s_logits))
        if teacher is None or kd_alpha <= 0:
            return ce
        t_soft = tf.nn.softmax(t_logits / kd_temp, axis=-1)
        s_soft = tf.nn.softmax(s_logits / kd_temp, axis=-1)
        kd = tf.reduce_mean(tf.keras.losses.KLDivergence()(t_soft, s_soft)) * (kd_temp ** 2)
        return kd_alpha * kd + (1.0 - kd_alpha) * ce

    best_val = 0.0
    history = []
    if teacher is not None:
        teacher.trainable = False

    for epoch in range(epochs):
        for xb, yb in train_ds:
            with tf.GradientTape() as tape:
                s_out = student(xb, training=True)
                if teacher is not None:
                    t_out = teacher(xb, training=False)
                    loss = kd_loss(s_out, t_out, yb)
                else:
                    loss = tf.reduce_mean(tf.keras.losses.categorical_crossentropy(yb, s_out))
            grads = tape.gradient(loss, student.trainable_variables)
            opt.apply_gradients(zip(grads, student.trainable_variables))

        accs = []
        for xb, yb in val_ds:
            pred = tf.argmax(student(xb, training=False), axis=1)
            accs.append(float(tf.reduce_mean(tf.cast(tf.equal(tf.argmax(yb, 1), pred), tf.float32))))
        val_acc = float(np.mean(accs))
        history.append({'epoch': epoch + 1, 'val_acc': val_acc})
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print('  finetune ep %d/%d val_acc=%.4f' % (epoch + 1, epochs, val_acc))
        if val_acc > best_val:
            best_val = val_acc
            student.save(str(MODEL_H5), include_optimizer=False)

    return best_val, history


def eval_bench(model, n=100):
    import tensorflow as tf

    npz = REPO / 'deploy' / 'cifar10_bench.npz'
    dense_npz = REPO / 'deploy' / 'dense_head.npz'
    if not npz.is_file():
        return {}
    data = np.load(npz, allow_pickle=True)
    n = min(n, len(data['labels']))
    xs, ys = [], []
    scale = float(os.environ.get('IN_FIXED_SCALE', '1024'))
    for i in range(n):
        raw = bytes(data['payloads'][i])
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / scale
        xs.append(x.reshape(32, 32, 3))
        ys.append(int(data['labels'][i]))
    x = np.stack(xs)
    y = np.asarray(ys, dtype=np.int64)
    full = np.argmax(model.predict(x, verbose=0, batch_size=32), axis=1)
    gap = tf.keras.Model(model.input, model.get_layer('gap').output).predict(x, verbose=0, batch_size=32)
    dense_top1 = None
    if dense_npz.is_file():
        dh = np.load(dense_npz)
        logits = gap @ dh['weight'] + dh['bias']
        dense_top1 = 100.0 * float(np.mean(np.argmax(logits, axis=1) == y))
    return {
        'bench_n': n,
        'full_top1_pct': 100.0 * float(np.mean(full == y)),
        'gap_ps_dense_top1_pct': dense_top1,
    }


def main() -> int:
    os.environ.setdefault('PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION', 'python')

    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=int, default=int(os.environ.get('FT_EPOCHS', '40')))
    ap.add_argument('--lr', type=float, default=float(os.environ.get('FT_LR', '0.01')))
    ap.add_argument('--kd-alpha', type=float, default=0.5)
    ap.add_argument('--kd-temp', type=float, default=3.5)
    ap.add_argument('--skip-if-qact', action='store_true',
                    help='Skip if model already has input_qact layer')
    ap.add_argument('--quant-alpha', default=os.environ.get('QAT_ALPHA', 'auto_po2'),
                    help='QKeras quantizer alpha (use 1 for bit_exact fallback)')
    args = ap.parse_args()

    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from qkeras import QActivation, QConv2D, QDense, quantized_bits, quantized_relu

    tf.random.set_seed(42)

    if not MODEL_H5.is_file():
        print('ERROR: missing %s — run Q6 QAT first' % MODEL_H5, file=sys.stderr)
        return 1

    custom = {
        'QConv2D': QConv2D, 'QDense': QDense, 'QActivation': QActivation,
        'quantized_bits': quantized_bits, 'quantized_relu': quantized_relu,
    }
    existing = keras.models.load_model(str(MODEL_H5), custom_objects=custom, compile=False)
    if any(l.name == 'input_qact' for l in existing.layers):
        if args.skip_if_qact:
            print('Model already has input_qact — skip fine-tune')
            return 0
        print('WARNING: overwriting model that already has input_qact')

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = MODEL_H5.with_suffix('.h5.bak_before_input_qact_%s' % ts)
    shutil.copy2(MODEL_H5, bak)
    print('Backed up %s -> %s' % (MODEL_H5, bak))

    student = build_q6_input_qact(
        keras, layers, QConv2D, QDense, QActivation, quantized_bits, quantized_relu,
        quant_alpha=args.quant_alpha,
    )
    student.load_weights(str(MODEL_H5), by_name=True, skip_mismatch=True)
    print('Loaded weights (skip_mismatch) from', MODEL_H5)
    print('Layers:', [l.name for l in student.layers[:4]])

    train_ds, val_ds = make_datasets(tf, keras)
    teacher = load_teacher(keras, TEACHER_H5)
    if teacher is None:
        print('WARNING: no teacher at %s — CE-only fine-tune' % TEACHER_H5)

    best_val, history = finetune(
        student, teacher, train_ds, val_ds,
        epochs=args.epochs, lr=args.lr,
        kd_alpha=args.kd_alpha if teacher else 0.0,
        kd_temp=args.kd_temp,
    )

    saved = keras.models.load_model(str(MODEL_H5), custom_objects=custom, compile=False)
    bench = eval_bench(saved)

    report = {
        'route': 'input_qact_finetune',
        'quant_alpha': args.quant_alpha,
        'activation_mode': 'quantized_relu_6_2_single_layer',
        'epochs': args.epochs,
        'lr': args.lr,
        'best_val_acc': best_val,
        'backup_h5': str(bak),
        'model_h5': str(MODEL_H5),
        'has_input_qact': any(l.name == 'input_qact' for l in saved.layers),
        'bench': bench,
        'history_tail': history[-5:],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Best val acc: %.4f' % best_val)
    print('Bench:', bench)
    print('Written:', OUT_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
