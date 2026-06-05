#!/usr/bin/env python3
"""Export INT8 TFLite model for ARM baseline (host-side, needs TensorFlow + QKeras)."""
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
H5_PATH = os.environ.get("H5_PATH", os.path.join(REPO, "notebooks", "model_int8_qkeras.h5"))
OUT_PATH = os.environ.get("OUT_PATH", os.path.join(REPO, "deploy", "model_int8.tflite"))


def main():
    import tensorflow as tf
    import qkeras

    if not os.path.isfile(H5_PATH):
        print("[ERROR] missing:", H5_PATH)
        return 1

    custom = {}
    for name in ("QConv2D", "QDense", "QActivation", "quantized_bits", "quantized_relu"):
        obj = getattr(qkeras, name, None)
        if obj is not None:
            custom[name] = obj

    model = tf.keras.models.load_model(H5_PATH, custom_objects=custom, compile=False)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    def rep_dataset():
        (_, _), (x_test, _) = tf.keras.datasets.cifar10.load_data()
        x_test = x_test.astype("float32") / 255.0
        for i in range(100):
            yield [x_test[i : i + 1]]

    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = rep_dataset
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8

    tflite_model = converter.convert()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "wb") as f:
        f.write(tflite_model)

    print("Exported %s (%.1f KB)" % (OUT_PATH, os.path.getsize(OUT_PATH) / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
