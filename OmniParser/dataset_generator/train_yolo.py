"""
Train YOLO model for webpage component detection

Optimized for 8GB VRAM:
- Uses YOLOv11l (largest that fits)
- Appropriate batch size
- Mixed precision training
- Gradient accumulation if needed
"""

import torch
from ultralytics import YOLO
from pathlib import Path
import yaml


def check_gpu_memory():
    """Check available GPU memory"""
    if torch.cuda.is_available():
        total_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"Total VRAM: {total_memory:.2f} GB")
        return total_memory
    else:
        print("No CUDA GPU detected!")
        return 0


def create_dataset_yaml(dataset_dir: Path, output_path: Path):
    """
    Create dataset.yaml for YOLO training

    Format:
    path: /path/to/dataset
    train: images
    val: images  (we'll use same for now, or split later)

    names:
      0: navbar
      1: sidebar
      ...
    """
    # Read classes
    classes_file = dataset_dir / "classes.txt"
    with open(classes_file, 'r') as f:
        class_names = [line.strip() for line in f.readlines()]

    # Create config
    config = {
        'path': str(dataset_dir.absolute()),
        'train': 'images',
        'val': 'images',  # TODO: Split into train/val
        'names': {i: name for i, name in enumerate(class_names)}
    }

    # Save YAML
    with open(output_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

    print(f"Created dataset config: {output_path}")
    print(f"Number of classes: {len(class_names)}")

    return output_path


def train_model(
    dataset_yaml: Path,
    model_size: str = "11l",  # 11x, 11l, 11m, 11s, 11n
    epochs: int = 100,
    batch_size: int = 8,
    img_size: int = 640,
    device: int = 0
):
    """
    Train YOLO model

    Args:
        dataset_yaml: Path to dataset configuration
        model_size: Model size (11x=xlarge, 11l=large, 11m=medium, 11s=small, 11n=nano)
        epochs: Number of training epochs
        batch_size: Batch size (adjust based on VRAM)
        img_size: Input image size
        device: GPU device ID
    """
    # Check GPU
    vram_gb = check_gpu_memory()

    # Auto-adjust batch size based on VRAM and model size
    if vram_gb < 8.5:
        print("WARNING: Less than 8GB VRAM detected!")
        if model_size in ["11x", "11l"]:
            print(f"Reducing batch size for {model_size}")
            batch_size = min(batch_size, 4)

    print(f"\nTraining Configuration:")
    print(f"  Model: YOLOv{model_size}")
    print(f"  Epochs: {epochs}")
    print(f"  Batch Size: {batch_size}")
    print(f"  Image Size: {img_size}")
    print(f"  Device: cuda:{device}")

    # Initialize model
    model_name = f"yolo{model_size}.pt"
    print(f"\nLoading base model: {model_name}")

    try:
        model = YOLO(model_name)
    except Exception as e:
        print(f"Error loading {model_name}: {e}")
        print("Falling back to yolo11l.pt")
        model = YOLO("yolo11l.pt")

    # Training arguments
    train_args = {
        'data': str(dataset_yaml),
        'epochs': epochs,
        'batch': batch_size,
        'imgsz': img_size,
        'device': device,
        'project': 'runs/webpage_detection',
        'name': f'yolo{model_size}_webpage',
        'exist_ok': True,

        # Performance optimizations for 8GB VRAM
        'amp': True,  # Automatic Mixed Precision
        'workers': 8,  # Data loading workers
        'patience': 50,  # Early stopping patience

        # Data augmentation
        'hsv_h': 0.015,
        'hsv_s': 0.7,
        'hsv_v': 0.4,
        'degrees': 0.0,  # No rotation for UI elements
        'translate': 0.1,
        'scale': 0.5,
        'shear': 0.0,  # No shear for UI
        'perspective': 0.0,
        'flipud': 0.0,  # No vertical flip for web pages
        'fliplr': 0.5,  # Horizontal flip OK
        'mosaic': 1.0,
        'mixup': 0.0,

        # Optimizer
        'optimizer': 'AdamW',
        'lr0': 0.001,
        'lrf': 0.01,
        'momentum': 0.937,
        'weight_decay': 0.0005,

        # Other
        'verbose': True,
        'save': True,
        'save_period': 10,
        'plots': True,
        'val': True,
    }

    # Train
    print(f"\n{'='*60}")
    print("Starting Training...")
    print(f"{'='*60}\n")

    results = model.train(**train_args)

    print(f"\n{'='*60}")
    print("Training Complete!")
    print(f"{'='*60}\n")

    # Save final model
    model_save_path = Path(f"runs/yolo_mega/grid_detector_mega/weights/best.pt")
    model_save_path.parent.mkdir(parents=True, exist_ok=True)

    # Copy best weights
    import shutil
    best_weights = Path(model.trainer.save_dir) / "weights" / "best.pt"
    if best_weights.exists():
        shutil.copy(best_weights, model_save_path)
        print(f"Model saved to: {model_save_path}")
    else:
        print(f"Warning: Could not find best weights at {best_weights}")

    return results


def main():
    """Main training pipeline"""
    dataset_dir = Path("generated_dataset")

    # Check if dataset exists
    if not (dataset_dir / "images").exists():
        print(f"Error: Dataset not found at {dataset_dir}")
        print("Please run render_and_annotate.py first to generate the dataset")
        return

    # Create dataset config
    dataset_yaml = dataset_dir / "dataset.yaml"
    create_dataset_yaml(dataset_dir, dataset_yaml)

    # Train model
    # For 8GB VRAM, use:
    # - yolo11l (large) with batch=4-8
    # - yolo11m (medium) with batch=8-16
    # - yolo11s (small) with batch=16-32

    print("\nRecommended configurations for 8GB VRAM:")
    print("  1. YOLOv11l: batch=4-6, img=640 (best accuracy, slower)")
    print("  2. YOLOv11m: batch=8-12, img=640 (balanced)")
    print("  3. YOLOv11s: batch=16-24, img=640 (fastest, lower accuracy)")

    # User can modify these
    MODEL_SIZE = "11l"  # Change to 11m or 11s if VRAM issues
    BATCH_SIZE = 6  # Adjust based on VRAM availability
    IMG_SIZE = 640
    EPOCHS = 100

    train_model(
        dataset_yaml=dataset_yaml,
        model_size=MODEL_SIZE,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        img_size=IMG_SIZE,
        device=0
    )


if __name__ == "__main__":
    main()
