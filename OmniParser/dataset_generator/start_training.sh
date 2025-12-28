#!/bin/bash
# Start YOLO training in background with logging

cd /home/stoxy/automata/web-agent/OmniParser/dataset_generator

echo "Starting YOLO training..."
echo "This will take approximately 13-15 hours on 8GB VRAM GPU"
echo ""
echo "Monitor progress with:"
echo "  tail -f training.log"
echo "  tensorboard --logdir ../runs/yolo_mega"
echo ""

nohup python - > training.log 2>&1 << 'EOF' &
import torch
from ultralytics import YOLO
from pathlib import Path
import shutil

# Check GPU
print("="*60)
print("GPU Configuration")
print("="*60)
if torch.cuda.is_available():
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {vram:.2f} GB")
else:
    print("WARNING: No CUDA GPU found!")

# Load model
print("\n" + "="*60)
print("Loading YOLOv11-Large")
print("="*60 + "\n")

model = YOLO("yolo11l.pt")

# Train
print("="*60)
print("Starting Training")
print("="*60 + "\n")

results = model.train(
    data="yolo_webpage_dataset/dataset.yaml",
    epochs=100,
    batch=6,  # Optimized for 8GB VRAM
    imgsz=640,
    device=0,
    project="../runs/yolo_mega",
    name="grid_detector_mega",
    exist_ok=True,
    amp=True,
    patience=50,
    save=True,
    save_period=10,
    plots=True,
    val=True,
    verbose=True,
    workers=8,
)

print("\n" + "="*60)
print("Training Complete!")
print("="*60 + "\n")

# Copy to expected location
best_weights = Path(model.trainer.save_dir) / "weights" / "best.pt"
target = Path("../runs/yolo_mega/grid_detector_mega/weights/best.pt")

if best_weights.exists():
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(best_weights, target)
    print(f"✓ Model saved to: {target}")
    print(f"✓ This replaces the deleted model file!")
else:
    print("WARNING: best.pt not found!")

# Save metrics
metrics = {
    'final_map50': float(results.results_dict.get('metrics/mAP50(B)', 0)),
    'final_map50_95': float(results.results_dict.get('metrics/mAP50-95(B)', 0)),
}

import json
with open('training_metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)

print(f"\nFinal mAP@0.5: {metrics['final_map50']:.4f}")
print(f"Final mAP@0.5:0.95: {metrics['final_map50_95']:.4f}")

print("\nNext step: Test on real websites with test_on_real_sites.py")
EOF

echo "Training started in background!"
echo "Check progress: tail -f training.log"
