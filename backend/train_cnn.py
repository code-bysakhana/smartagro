"""
train_cnn.py — Plant Disease CNN (v3 — NO Lambda layers)
=========================================================
FIX: This version deliberately avoids Lambda/TFOpLambda layers that cause
     the 'TrueDivide' error when loading. Preprocessing is done in NumPy
     before passing to the model instead of inside the model graph.

Run:
  pip install tensorflow pillow numpy scikit-learn pandas
  python train_cnn.py

Dataset: PlantVillage
  https://www.kaggle.com/datasets/abdallahalidev/plantvillage-dataset
  After download: python scripts/split_dataset.py

Output:
  plant_disease_cnn.h5   ← place in backend/ folder
  class_indices.json     ← place in backend/ folder
"""

import os, json
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models, callbacks, regularizers
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.utils.class_weight import compute_class_weight

IMG_H, IMG_W = 224, 224     # MobileNetV2 native size
BATCH        = 32
EPOCHS_1     = 15           # Phase 1: frozen base
EPOCHS_2     = 10           # Phase 2: fine-tune top layers
TRAIN_DIR    = "./plantvillage/train"
VAL_DIR      = "./plantvillage/val"
MODEL_OUT    = "plant_disease_cnn.h5"

print(f"TensorFlow version: {tf.__version__}")


def build_model(num_classes):
    """
    Build MobileNetV2 transfer learning model.
    IMPORTANT: NO Lambda layers, NO tf.math operations inside the model graph.
    Preprocessing (division by 255) is done OUTSIDE the model in NumPy.
    MobileNetV2 preprocess_input expects [-1, 1] range — we pass [0,1] from numpy
    and handle the rescaling via rescale=1./255 in ImageDataGenerator.
    """
    base = MobileNetV2(
        input_shape=(IMG_H, IMG_W, 3),
        include_top=False,
        weights="imagenet",
    )
    base.trainable = False   # Freeze for Phase 1

    model = models.Sequential([
        base,
        layers.GlobalAveragePooling2D(),
        layers.BatchNormalization(),
        layers.Dense(512, activation="relu", kernel_regularizer=regularizers.l2(1e-4)),
        layers.Dropout(0.4),
        layers.Dense(256, activation="relu", kernel_regularizer=regularizers.l2(1e-4)),
        layers.Dropout(0.3),
        layers.Dense(num_classes, activation="softmax"),
    ])
    return model, base


def main():
    # ── Data generators ─────────────────────────────────────────
    # rescale=1./255 keeps preprocessing OUTSIDE the model (no Lambda layers)
    train_gen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=30,
        width_shift_range=0.2,
        height_shift_range=0.2,
        horizontal_flip=True,
        zoom_range=0.2,
        brightness_range=[0.7,1.3],
        channel_shift_range=20,
        shear_range=10,
        fill_mode="nearest",
    )
    val_gen = ImageDataGenerator(rescale=1./255)

    train_data = train_gen.flow_from_directory(
        TRAIN_DIR, target_size=(IMG_H,IMG_W),
        batch_size=BATCH, class_mode="categorical", shuffle=True,
    )
    val_data = val_gen.flow_from_directory(
        VAL_DIR, target_size=(IMG_H,IMG_W),
        batch_size=BATCH, class_mode="categorical", shuffle=False,
    )

    num_classes = len(train_data.class_indices)
    print(f"\n✓ {num_classes} classes | {train_data.samples} train | {val_data.samples} val")

    # Save class index map
    with open("class_indices.json","w") as f:
        json.dump(train_data.class_indices, f, indent=2)
    print("✓ class_indices.json saved")

    # ── Class weights (bias fix) ────────────────────────────────
    cw = compute_class_weight("balanced",
                              classes=np.unique(train_data.classes),
                              y=train_data.classes)
    class_weights = dict(enumerate(cw))
    print(f"✓ Class weights computed (max={max(cw):.2f}, min={min(cw):.2f})")

    # ── Build model ─────────────────────────────────────────────
    model, base = build_model(num_classes)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=0.1),
        metrics=["accuracy"],
    )
    model.summary()

    cbs = [
        callbacks.ModelCheckpoint(MODEL_OUT, monitor="val_accuracy",
                                  save_best_only=True, verbose=1),
        callbacks.EarlyStopping(monitor="val_accuracy", patience=5,
                                restore_best_weights=True, verbose=1),
        callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5,
                                    patience=3, verbose=1),
    ]

    # ── Phase 1 ─────────────────────────────────────────────────
    print("\n── Phase 1: Training head (base frozen) ──")
    model.fit(train_data, validation_data=val_data, epochs=EPOCHS_1,
              class_weight=class_weights, callbacks=cbs)

    # ── Phase 2: Fine-tune ───────────────────────────────────────
    print(f"\n── Phase 2: Fine-tuning top 30 layers ──")
    base.trainable = True
    for layer in base.layers[:-30]:
        layer.trainable = False

    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-5),
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=0.1),
        metrics=["accuracy"],
    )
    model.fit(train_data, validation_data=val_data, epochs=EPOCHS_2,
              class_weight=class_weights, callbacks=cbs)

    # ── Final eval ───────────────────────────────────────────────
    loss, acc = model.evaluate(val_data, verbose=0)
    print(f"\n✓ Final val accuracy: {acc*100:.2f}%")
    print(f"✓ Model saved → {MODEL_OUT}")
    print(f"✓ class_indices.json saved")
    print("\nCopy both files to backend/ and restart app.py")


if __name__ == "__main__":
    main()
