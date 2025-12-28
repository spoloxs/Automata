"""
Iterative Training Loop

1. Generate 20k dataset
2. Train YOLO
3. Test on real sites
4. Identify gaps
5. Augment dataset with missing components
6. Retrain
7. Repeat until all tests pass
"""

import asyncio
import shutil
from pathlib import Path
from ultralytics import YOLO
import torch
import json
from typing import Dict, List

from generate_full_dataset import FullDatasetGenerator
from test_on_real_sites import RealSiteTester
from web_components_list import get_all_components


class IterativeTrainer:
    """Manages iterative training and validation"""

    def __init__(self):
        self.iteration = 0
        self.dataset_dir = Path("yolo_webpage_dataset")
        self.models_dir = Path("../runs/yolo_mega")
        self.test_results_dir = Path("test_results")

    def check_gpu(self):
        """Check GPU availability and VRAM"""
        if not torch.cuda.is_available():
            print("❌ No CUDA GPU found!")
            return False

        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        gpu_name = torch.cuda.get_device_name(0)

        print(f"✓ GPU: {gpu_name}")
        print(f"  VRAM: {vram_gb:.2f} GB")

        if vram_gb < 7.5:
            print("⚠️  Warning: Less than 8GB VRAM detected!")
            print("   Consider using YOLOv11-Medium or reducing batch size")

        return True

    async def step1_generate_dataset(self, num_images: int = 20000):
        """Generate training dataset"""
        print(f"\n{'='*60}")
        print(f"ITERATION {self.iteration} - STEP 1: Dataset Generation")
        print(f"{'='*60}\n")

        generator = FullDatasetGenerator(str(self.dataset_dir))

        # First iteration: full dataset
        # Later iterations: augment with missing components
        if self.iteration == 0:
            print(f"Generating {num_images} images...")
            generator.generate(num_images=num_images)
        else:
            # Load missing components from previous test
            missing_file = self.test_results_dir / "missing_components.json"

            if missing_file.exists():
                with open(missing_file, 'r') as f:
                    missing_counts = json.load(f)

                print(f"Augmenting dataset with {len(missing_counts)} missing components...")

                # Generate additional images emphasizing missing components
                # TODO: Implement targeted generation
                generator.generate(num_images=num_images // 2)
            else:
                print("No missing components found - generating standard dataset")
                generator.generate(num_images=num_images)

    def step2_split_dataset(self):
        """Split into train/val"""
        print(f"\n{'='*60}")
        print(f"ITERATION {self.iteration} - STEP 2: Train/Val Split")
        print(f"{'='*60}\n")

        images = list(self.dataset_dir.glob("images/*.png"))

        if not images:
            print("❌ No images found! Dataset generation may have failed.")
            return False

        # Split 80/20
        import random
        random.seed(42)
        random.shuffle(images)

        split_idx = int(len(images) * 0.8)
        train_imgs = images[:split_idx]
        val_imgs = images[split_idx:]

        print(f"Total images: {len(images)}")
        print(f"Train: {len(train_imgs)}")
        print(f"Val: {len(val_imgs)}")

        # Create directories
        for split in ['train', 'val']:
            (self.dataset_dir / "images" / split).mkdir(parents=True, exist_ok=True)
            (self.dataset_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

        # Move files
        for img_list, split in [(train_imgs, 'train'), (val_imgs, 'val')]:
            for img in img_list:
                lbl = self.dataset_dir / "labels" / f"{img.stem}.txt"

                shutil.move(str(img), str(self.dataset_dir / "images" / split / img.name))
                if lbl.exists():
                    shutil.move(str(lbl), str(self.dataset_dir / "labels" / split / lbl.name))

        # Create dataset.yaml
        import yaml

        with open(self.dataset_dir / "classes.txt") as f:
            classes = [line.strip() for line in f]

        config = {
            'path': str(self.dataset_dir.absolute()),
            'train': 'images/train',
            'val': 'images/val',
            'names': {i: name for i, name in enumerate(classes)}
        }

        with open(self.dataset_dir / "dataset.yaml", 'w') as f:
            yaml.dump(config, f)

        print(f"✓ Created dataset.yaml with {len(classes)} classes")

        return True

    def step3_train_model(self):
        """Train YOLO model"""
        print(f"\n{'='*60}")
        print(f"ITERATION {self.iteration} - STEP 3: Training YOLO")
        print(f"{'='*60}\n")

        # Load base model
        model = YOLO("yolo11l.pt")

        # Training config
        train_config = {
            'data': str(self.dataset_dir / "dataset.yaml"),
            'epochs': 100,
            'batch': 6,
            'imgsz': 640,
            'device': 0,
            'project': str(self.models_dir),
            'name': f"grid_detector_mega_iter{self.iteration}",
            'exist_ok': True,
            'amp': True,
            'patience': 50,
            'save': True,
            'save_period': 10,
            'plots': True,
            'val': True,
            'verbose': True,
        }

        print("Training configuration:")
        for k, v in train_config.items():
            print(f"  {k}: {v}")

        print("\nStarting training...")
        print("This will take 13-15 hours on 8GB VRAM GPU\n")

        results = model.train(**train_config)

        # Copy best weights to expected location
        best_weights = Path(model.trainer.save_dir) / "weights" / "best.pt"
        target = self.models_dir / "grid_detector_mega" / "weights" / "best.pt"

        if best_weights.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(best_weights, target)
            print(f"\n✓ Model saved to: {target}")
            return str(target)
        else:
            print("\n❌ Training failed - best.pt not found!")
            return None

    async def step4_test_on_real_sites(self, model_path: str) -> Dict:
        """Test trained model on real websites"""
        print(f"\n{'='*60}")
        print(f"ITERATION {self.iteration} - STEP 4: Real Website Testing")
        print(f"{'='*60}\n")

        tester = RealSiteTester(model_path)
        results, missing = await tester.run_comprehensive_test()

        return missing

    async def run_iteration(self):
        """Run one complete iteration"""
        print(f"\n{'#'*60}")
        print(f"#  STARTING ITERATION {self.iteration}")
        print(f"{'#'*60}\n")

        # Check GPU
        if not self.check_gpu():
            return False

        # Step 1: Generate dataset
        await self.step1_generate_dataset(num_images=20000)

        # Step 2: Split
        if not self.step2_split_dataset():
            return False

        # Step 3: Train
        model_path = self.step3_train_model()

        if not model_path:
            return False

        # Step 4: Test on real sites
        missing = await self.step4_test_on_real_sites(model_path)

        # Decide if we need another iteration
        if missing:
            print(f"\n⚠️  Found {len(missing)} missing component types")
            print("   Starting next iteration with improved dataset...")
            self.iteration += 1
            return "continue"
        else:
            print("\n✓✓✓ ALL TESTS PASSED! Model is complete!")
            return "done"

    async def run_until_complete(self):
        """Keep iterating until all tests pass"""
        max_iterations = 3  # Safety limit

        while self.iteration < max_iterations:
            result = await self.run_iteration()

            if result == "done":
                break
            elif result == "continue":
                continue
            else:
                print("❌ Iteration failed")
                break

        print(f"\n{'#'*60}")
        print(f"#  TRAINING COMPLETE AFTER {self.iteration + 1} ITERATION(S)")
        print(f"{'#'*60}\n")


if __name__ == "__main__":
    trainer = IterativeTrainer()
    asyncio.run(trainer.run_until_complete())
