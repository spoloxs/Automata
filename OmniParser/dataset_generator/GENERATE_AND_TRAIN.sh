#!/bin/bash
# Complete pipeline to generate dataset and train YOLO model

echo "======================================================================"
echo "  YOLO Webpage Component Detection - Full Pipeline"
echo "======================================================================"
echo ""

# Step 1: Generate dataset
echo "Step 1: Generating 2000 training images..."
echo "----------------------------------------------------------------------"
python -c "
from generate_full_dataset import FullDatasetGenerator
gen = FullDatasetGenerator('yolo_webpage_dataset')
gen.generate(num_images=2000)
"

# Step 2: Split train/val
echo ""
echo "Step 2: Splitting into train/val sets..."
echo "----------------------------------------------------------------------"
python - << 'PYTHON'
from pathlib import Path
import shutil
import random

dataset_dir = Path("yolo_webpage_dataset")
images = list(dataset_dir.glob("images/*.png"))

random.seed(42)
random.shuffle(images)

split_idx = int(len(images) * 0.8)
train_imgs = images[:split_idx]
val_imgs = images[split_idx:]

# Create dirs
(dataset_dir / "images" / "train").mkdir(parents=True, exist_ok=True)
(dataset_dir / "images" / "val").mkdir(parents=True, exist_ok=True)
(dataset_dir / "labels" / "train").mkdir(parents=True, exist_ok=True)
(dataset_dir / "labels" / "val").mkdir(parents=True, exist_ok=True)

# Move files
for img in train_imgs:
    lbl = dataset_dir / "labels" / f"{img.stem}.txt"
    shutil.move(str(img), str(dataset_dir / "images" / "train" / img.name))
    if lbl.exists():
        shutil.move(str(lbl), str(dataset_dir / "labels" / "train" / lbl.name))

for img in val_imgs:
    lbl = dataset_dir / "labels" / f"{img.stem}.txt"
    shutil.move(str(img), str(dataset_dir / "images" / "val" / img.name))
    if lbl.exists():
        shutil.move(str(lbl), str(dataset_dir / "labels" / "val" / lbl.name))

print(f"Train: {len(train_imgs)} images")
print(f"Val: {len(val_imgs)} images")
PYTHON

# Step 3: Create dataset.yaml
echo ""
echo "Step 3: Creating YOLO dataset config..."
echo "----------------------------------------------------------------------"
python - << 'PYTHON'
import yaml
from pathlib import Path

dataset_dir = Path("yolo_webpage_dataset").absolute()

# Read classes
with open(dataset_dir / "classes.txt") as f:
    classes = [line.strip() for line in f]

config = {
    'path': str(dataset_dir),
    'train': 'images/train',
    'val': 'images/val',
    'names': {i: name for i, name in enumerate(classes)}
}

with open(dataset_dir / "dataset.yaml", 'w') as f:
    yaml.dump(config, f)

print(f"Created dataset.yaml with {len(classes)} classes")
PYTHON

# Step 4: Train YOLO
echo ""
echo "Step 4: Training YOLO model (this will take a while)..."
echo "----------------------------------------------------------------------"
python - << 'PYTHON'
import torch
from ultralytics import YOLO
from pathlib import Path
import shutil

# Check GPU
if torch.cuda.is_available():
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {vram:.2f} GB")
else:
    print("WARNING: No CUDA GPU found!")

# Load model (YOLOv11-Large for 8GB VRAM)
print("\nLoading YOLOv11-Large...")
model = YOLO("yolo11l.pt")

# Train
print("\nStarting training...")
results = model.train(
    data="yolo_webpage_dataset/dataset.yaml",
    epochs=100,
    batch=6,  # Optimized for 8GB VRAM
    imgsz=640,
    device=0,
    project="../runs/yolo_mega",
    name="grid_detector_mega",
    exist_ok=True,
    amp=True,  # Mixed precision
    patience=50,
    save=True,
    save_period=10,
    plots=True,
    val=True,
    verbose=True
)

print("\n✓ Training complete!")

# Copy to expected location
best_weights = Path(model.trainer.save_dir) / "weights" / "best.pt"
target = Path("../runs/yolo_mega/grid_detector_mega/weights/best.pt")

if best_weights.exists():
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(best_weights, target)
    print(f"✓ Model saved to: {target}")
else:
    print("WARNING: best.pt not found!")
PYTHON

echo ""
echo "======================================================================"
echo "  PIPELINE COMPLETE!"
echo "======================================================================"
echo ""
echo "Model saved to: runs/yolo_mega/grid_detector_mega/weights/best.pt"
echo ""
