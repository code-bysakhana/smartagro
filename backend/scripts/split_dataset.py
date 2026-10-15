"""
split_dataset.py — Split PlantVillage into train/val
Run once after downloading from Kaggle.

Download: https://www.kaggle.com/datasets/abdallahalidev/plantvillage-dataset
Extract so:  backend/plantvillage/color/<class_name>/*.jpg

Usage:
  cd backend
  python scripts/split_dataset.py
"""
import os, shutil, random
from pathlib import Path

SRC   = "./plantvillage/color"
TRAIN = "./plantvillage/train"
VAL   = "./plantvillage/val"
SPLIT = 0.80
random.seed(42)

def run():
    src = Path(SRC)
    if not src.exists():
        print(f"✗ Not found: {SRC}")
        print("  Download PlantVillage from Kaggle and extract to backend/plantvillage/color/")
        return

    classes = [d for d in src.iterdir() if d.is_dir()]
    print(f"Found {len(classes)} classes\n")
    total_tr = total_va = 0

    for cls in sorted(classes):
        imgs = list(cls.glob("*.jpg")) + list(cls.glob("*.JPG")) + list(cls.glob("*.png"))
        if not imgs: continue
        random.shuffle(imgs)
        cut = int(len(imgs)*SPLIT)
        tr, va = imgs[:cut], imgs[cut:]

        (Path(TRAIN)/cls.name).mkdir(parents=True,exist_ok=True)
        (Path(VAL)  /cls.name).mkdir(parents=True,exist_ok=True)

        for i in tr: shutil.copy2(i, Path(TRAIN)/cls.name/i.name)
        for i in va: shutil.copy2(i, Path(VAL)  /cls.name/i.name)

        print(f"  {cls.name:<55} train={len(tr):4d}  val={len(va):3d}")
        total_tr+=len(tr); total_va+=len(va)

    print(f"\n  Total → train:{total_tr:,}  val:{total_va:,}")
    print("✓ Done! Run: python train_cnn.py")

if __name__=="__main__":
    run()
