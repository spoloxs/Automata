"""
Master script to generate dataset and train YOLO model

Steps:
1. Generate HTML pages with all components
2. Render to images with bounding box annotations
3. Split into train/val sets
4. Train YOLO model
5. Validate on test set
"""

import asyncio
import sys
from pathlib import Path
import shutil
from sklearn.model_selection import train_test_split


async def step1_generate_dataset(num_pages=2000):
    """Generate HTML pages and render to images"""
    print(f"\n{'='*60}")
    print("STEP 1: Generating Dataset")
    print(f"{'='*60}\n")

    from render_and_annotate import generate_dataset

    await generate_dataset(num_pages=num_pages, components_per_page=20)

    print("\n✓ Dataset generation complete!")


def step2_split_dataset(dataset_dir="generated_dataset", train_ratio=0.8):
    """Split dataset into train/val sets"""
    print(f"\n{'='*60}")
    print("STEP 2: Splitting Dataset")
    print(f"{'='*60}\n")

    dataset_path = Path(dataset_dir)
    images_dir = dataset_path / "images"
    labels_dir = dataset_path / "labels"

    # Get all image files
    image_files = list(images_dir.glob("*.png"))

    if not image_files:
        print("Error: No images found!")
        return

    print(f"Total images: {len(image_files)}")

    # Split
    train_imgs, val_imgs = train_test_split(
        image_files,
        train_size=train_ratio,
        random_state=42
    )

    print(f"Train: {len(train_imgs)} images")
    print(f"Val: {len(val_imgs)} images")

    # Create directories
    train_img_dir = dataset_path / "images" / "train"
    val_img_dir = dataset_path / "images" / "val"
    train_lbl_dir = dataset_path / "labels" / "train"
    val_lbl_dir = dataset_path / "labels" / "val"

    for dir_path in [train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Move files
    print("\nMoving files to train/val splits...")

    for img_path in train_imgs:
        label_path = labels_dir / f"{img_path.stem}.txt"

        # Move to train
        shutil.move(str(img_path), str(train_img_dir / img_path.name))
        if label_path.exists():
            shutil.move(str(label_path), str(train_lbl_dir / label_path.name))

    for img_path in val_imgs:
        label_path = labels_dir / f"{img_path.stem}.txt"

        # Move to val
        shutil.move(str(img_path), str(val_img_dir / img_path.name))
        if label_path.exists():
            shutil.move(str(label_path), str(val_lbl_dir / label_path.name))

    print("\n✓ Dataset split complete!")

    # Update dataset.yaml
    import yaml

    yaml_path = dataset_path / "dataset.yaml"
    if yaml_path.exists():
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)

        # Update paths
        config['train'] = 'images/train'
        config['val'] = 'images/val'

        with open(yaml_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        print(f"Updated {yaml_path}")


def step3_train_model():
    """Train YOLO model"""
    print(f"\n{'='*60}")
    print("STEP 3: Training YOLO Model")
    print(f"{'='*60}\n")

    from train_yolo import main as train_main

    train_main()

    print("\n✓ Training complete!")


async def run_full_pipeline(num_pages=2000):
    """Run complete pipeline"""
    print(f"\n{'#'*60}")
    print("#  YOLO Training Pipeline for Webpage Component Detection  #")
    print(f"{'#'*60}\n")

    print(f"Configuration:")
    print(f"  - Total pages to generate: {num_pages}")
    print(f"  - Components per page: 10-30 (random)")
    print(f"  - Total component types: 317")
    print(f"  - Train/Val split: 80/20")

    input("\nPress Enter to start...\n")

    try:
        # Step 1: Generate dataset
        await step1_generate_dataset(num_pages=num_pages)

        # Step 2: Split dataset
        step2_split_dataset()

        # Step 3: Train model
        step3_train_model()

        print(f"\n{'#'*60}")
        print("#  PIPELINE COMPLETE!  #")
        print(f"{'#'*60}\n")

        print("Trained model saved to:")
        print("  runs/yolo_mega/grid_detector_mega/weights/best.pt")

    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Default: 2000 pages (should take 2-3 hours)
    # For testing: use 100 pages (~ 10 minutes)

    NUM_PAGES = 2000  # Change to 100 for quick test

    print("=== WEBPAGE COMPONENT DETECTION - DATASET & TRAINING ===\n")
    print(f"This will:")
    print(f"  1. Generate {NUM_PAGES} synthetic webpages")
    print(f"  2. Render each to 1440x900 images")
    print(f"  3. Create YOLO annotations for all components")
    print(f"  4. Train YOLOv11-Large model")
    print(f"\nEstimated time: {NUM_PAGES // 10} - {NUM_PAGES // 5} minutes")
    print(f"Storage needed: ~{NUM_PAGES * 2} MB\n")

    asyncio.run(run_full_pipeline(num_pages=NUM_PAGES))
