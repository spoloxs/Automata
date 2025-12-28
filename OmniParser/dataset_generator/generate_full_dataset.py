"""
Generate complete YOLO training dataset

Creates 2000+ images with all 317 component types
"""

from PIL import Image, ImageDraw
import random
import numpy as np
from pathlib import Path
from typing import Tuple
from tqdm import tqdm
import json

from simple_working_generator import UnifiedComponentGenerator, Component
from web_components_list import get_all_components, WEB_COMPONENTS


class FullDatasetGenerator:
    """Generates complete YOLO dataset"""

    def __init__(self, output_dir="yolo_webpage_dataset"):
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.labels_dir = self.output_dir / "labels"

        for d in [self.images_dir, self.labels_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.generator = UnifiedComponentGenerator()
        self.all_components = get_all_components()
        self.class_mapping = {comp: idx for idx, comp in enumerate(self.all_components)}

        # Save class names
        with open(self.output_dir / "classes.txt", 'w') as f:
            f.write('\n'.join(self.all_components))

        print(f"✓ Initialized with {len(self.all_components)} component classes")

    def component_to_yolo(self, comp: Component) -> str:
        """Convert component to YOLO annotation"""
        if comp.occluded or not comp.visible:
            return ""

        class_id = self.class_mapping.get(comp.type, -1)
        if class_id == -1:
            return ""

        # Normalize
        x_center = ((comp.x + comp.x + comp.width) / 2) / self.generator.img_width
        y_center = ((comp.y + comp.y + comp.height) / 2) / self.generator.img_height
        width = comp.width / self.generator.img_width
        height = comp.height / self.generator.img_height

        # Validate
        if not (0 < width <= 1 and 0 < height <= 1):
            return ""

        return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"

    def detect_occlusions(self, components: list[Component]) -> list[Component]:
        """Detect occluded components"""
        overlays = [c for c in components if c.z_index >= 900]

        if not overlays:
            return components

        for comp in components:
            if comp in overlays:
                continue

            for overlay in overlays:
                if comp.z_index >= overlay.z_index:
                    continue

                comp_bbox = comp.bbox()
                overlay_bbox = overlay.bbox()

                intersects = not (
                    comp_bbox[2] < overlay_bbox[0] or
                    comp_bbox[0] > overlay_bbox[2] or
                    comp_bbox[3] < overlay_bbox[1] or
                    comp_bbox[1] > overlay_bbox[3]
                )

                if intersects:
                    comp.occluded = True
                    break

        return components

    def generate_single_image(self, img_id: int, num_components: int = 15) -> Tuple[int, int]:
        """
        Generate one training image

        Returns:
            (num_annotations, num_occluded)
        """
        # Create canvas
        img = Image.new('RGB', (self.generator.img_width, self.generator.img_height), (255, 255, 255))
        draw = ImageDraw.Draw(img, 'RGBA')

        # Select random components (ensure variety)
        selected = random.sample(self.all_components, min(num_components, len(self.all_components)))

        # 30% chance add overlay
        if random.random() < 0.3:
            selected.append(random.choice(['modal', 'popup', 'cookie_consent']))

        drawn = []

        # Draw each component at random position
        for comp_type in selected:
            x = random.randint(20, max(50, self.generator.img_width - 700))
            y = random.randint(20, max(50, self.generator.img_height - 500))

            try:
                comp = self.generator.draw(draw, comp_type, x, y)
                comp.id = f"comp_{len(drawn)}"
                drawn.append(comp)
            except Exception as e:
                # Skip if drawing fails
                pass

        # Detect occlusions
        drawn = self.detect_occlusions(drawn)

        # Create YOLO annotations
        annotations = []
        for comp in drawn:
            yolo_line = self.component_to_yolo(comp)
            if yolo_line:
                annotations.append(yolo_line)

        # Save
        img.save(self.images_dir / f"img_{img_id:06d}.png")

        with open(self.labels_dir / f"img_{img_id:06d}.txt", 'w') as f:
            f.write('\n'.join(annotations))

        occluded = sum(1 for c in drawn if c.occluded)
        return len(annotations), occluded

    def generate(self, num_images: int = 2000):
        """Generate full dataset"""
        print(f"\n{'='*60}")
        print(f"Generating YOLO Training Dataset")
        print(f"{'='*60}\n")
        print(f"Total images: {num_images}")
        print(f"Component classes: {len(self.all_components)}")
        print(f"Output: {self.output_dir}\n")

        total_annotations = 0
        total_occluded = 0

        for i in tqdm(range(num_images), desc="Generating"):
            num_ann, num_occ = self.generate_single_image(
                img_id=i,
                num_components=random.randint(10, 25)
            )
            total_annotations += num_ann
            total_occluded += num_occ

        print(f"\n{'='*60}")
        print("Dataset Generation Complete!")
        print(f"{'='*60}")
        print(f"Images: {num_images}")
        print(f"Total annotations: {total_annotations}")
        print(f"Avg annotations/image: {total_annotations / num_images:.1f}")
        print(f"Total occluded: {total_occluded}")
        print(f"\nReady for YOLO training!")


if __name__ == "__main__":
    generator = FullDatasetGenerator()

    # Generate full dataset
    NUM_IMAGES = 20000  # Large dataset for comprehensive training

    generator.generate(num_images=NUM_IMAGES)
