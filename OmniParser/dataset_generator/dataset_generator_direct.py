"""
Direct dataset generator using PIL image generation

Generates training dataset without HTML rendering:
- Creates images directly with PIL
- Places components randomly with variations
- Handles occlusions
- Creates YOLO annotations
- Much faster than HTML rendering
"""

from PIL import Image, ImageDraw
import random
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
import json
from tqdm import tqdm

from direct_image_generator import WebComponentDrawer, DrawnComponent
from web_components_list import get_all_components, WEB_COMPONENTS


class DatasetGeneratorDirect:
    """Generates training dataset directly from PIL drawing"""

    def __init__(self, output_dir: str = "yolo_dataset"):
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.labels_dir = self.output_dir / "labels"

        for dir_path in [self.images_dir, self.labels_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        self.drawer = WebComponentDrawer(1440, 900)
        self.all_components = get_all_components()

        # Create class mapping
        self.class_mapping = {comp: idx for idx, comp in enumerate(self.all_components)}

        # Save class names
        self._save_class_names()

    def _save_class_names(self):
        """Save class names for YOLO"""
        classes_file = self.output_dir / "classes.txt"
        with open(classes_file, 'w') as f:
            f.write('\n'.join(self.all_components))

        print(f"✓ Saved {len(self.all_components)} class names to {classes_file}")

    def get_available_drawing_methods(self) -> Dict[str, callable]:
        """Get all available component drawing methods"""
        methods = {}
        for attr_name in dir(self.drawer):
            if attr_name.startswith('draw_') and attr_name not in ['draw_rounded_rectangle', 'draw_shadow']:
                component_type = attr_name.replace('draw_', '')
                methods[component_type] = getattr(self.drawer, attr_name)
        return methods

    def place_component_randomly(
        self,
        canvas_width: int,
        canvas_height: int,
        comp_width: int,
        comp_height: int,
        existing_components: List[DrawnComponent],
        margin: int = 20
    ) -> Tuple[int, int]:
        """
        Find random non-overlapping position for component

        Returns (x, y) position
        """
        max_attempts = 50

        for _ in range(max_attempts):
            x = random.randint(margin, max(margin, canvas_width - comp_width - margin))
            y = random.randint(margin, max(margin, canvas_height - comp_height - margin))

            # Check overlap with existing components
            proposed_bbox = (x, y, x + comp_width, y + comp_height)

            overlaps = False
            for existing in existing_components:
                existing_bbox = existing.get_bbox()

                # Check intersection
                intersects = not (
                    proposed_bbox[2] < existing_bbox[0] or
                    proposed_bbox[0] > existing_bbox[2] or
                    proposed_bbox[3] < existing_bbox[1] or
                    proposed_bbox[1] > existing_bbox[3]
                )

                if intersects:
                    overlaps = True
                    break

            if not overlaps:
                return x, y

        # If no space found, place anyway (might overlap)
        return x, y

    def component_to_yolo(self, comp: DrawnComponent, class_id: int) -> str:
        """Convert component to YOLO annotation line"""
        if comp.occluded or not comp.visible:
            return ""

        # Normalize to [0, 1]
        x_center = ((comp.x + comp.x + comp.width) / 2) / self.drawer.width
        y_center = ((comp.y + comp.y + comp.height) / 2) / self.drawer.height
        width = comp.width / self.drawer.width
        height = comp.height / self.drawer.height

        # Validate
        if width <= 0 or height <= 0 or width > 1 or height > 1:
            return ""

        # Clamp
        x_center = max(0.0, min(1.0, x_center))
        y_center = max(0.0, min(1.0, y_center))
        width = max(0.0, min(1.0, width))
        height = max(0.0, min(1.0, height))

        return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"

    def detect_occlusions(self, components: List[DrawnComponent]) -> List[DrawnComponent]:
        """Mark components as occluded if behind high z-index overlays"""
        # Find overlays (z-index >= 900)
        overlays = [c for c in components if c.z_index >= 900]

        if not overlays:
            return components

        # Check each component
        for comp in components:
            if comp in overlays:
                continue

            comp_bbox = comp.get_bbox()

            for overlay in overlays:
                if comp.z_index >= overlay.z_index:
                    continue

                overlay_bbox = overlay.get_bbox()

                # Check intersection
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

    def generate_single_image(
        self,
        page_id: int,
        num_components: int = 15,
        include_overlay_prob: float = 0.3
    ) -> Tuple[Path, Path, int]:
        """
        Generate a single training image with annotations

        Returns:
            (image_path, label_path, num_annotations)
        """
        # Create canvas
        img = Image.new('RGB', (self.drawer.width, self.drawer.height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img, 'RGBA')

        components = []
        drawing_methods = self.get_available_drawing_methods()

        # Randomly select components to draw
        available_types = list(drawing_methods.keys())
        selected_types = random.sample(available_types, min(num_components, len(available_types)))

        # Draw components
        for i, comp_type in enumerate(selected_types):
            draw_method = drawing_methods[comp_type]

            # Try to place component
            # Most methods return approximate size, so we estimate
            try:
                # Draw at temporary position to get actual size
                temp_comp = draw_method(draw, 0, 0)

                # Find non-overlapping position
                x, y = self.place_component_randomly(
                    self.drawer.width,
                    self.drawer.height,
                    temp_comp.width,
                    temp_comp.height,
                    components
                )

                # Redraw at correct position
                # Clear the temp drawing by recreating image
                img = Image.new('RGB', (self.drawer.width, self.drawer.height), color=(255, 255, 255))
                draw = ImageDraw.Draw(img, 'RGBA')

                # Redraw all existing components
                for existing in components:
                    existing_method = drawing_methods[existing.comp_type]
                    existing_method(draw, existing.x, existing.y)

                # Draw new component
                comp = draw_method(draw, x, y)
                comp.comp_id = f"comp_{i}"
                components.append(comp)

            except Exception as e:
                print(f"    Warning: Could not draw {comp_type}: {e}")
                continue

        # Optionally add overlay
        if random.random() < include_overlay_prob:
            if 'modal' in drawing_methods:
                overlay = drawing_methods['modal'](draw, 0, 0)
                overlay.comp_id = "comp_overlay"
                components.append(overlay)

        # Detect occlusions
        components = self.detect_occlusions(components)

        # Create YOLO annotations
        annotations = []
        for comp in components:
            if comp.comp_type in self.class_mapping:
                class_id = self.class_mapping[comp.comp_type]
                yolo_line = self.component_to_yolo(comp, class_id)
                if yolo_line:
                    annotations.append(yolo_line)

        # Save image
        img_path = self.images_dir / f"img_{page_id:06d}.png"
        img.save(img_path)

        # Save annotations
        label_path = self.labels_dir / f"img_{page_id:06d}.txt"
        with open(label_path, 'w') as f:
            f.write('\n'.join(annotations))

        return img_path, label_path, len(annotations)

    def generate_dataset(self, num_images: int = 2000, components_per_image: int = 15):
        """Generate complete dataset"""
        print(f"\nGenerating {num_images} training images...")
        print(f"Components per image: {components_per_image}")
        print(f"Total component types: {len(self.all_components)}")
        print(f"Available drawing methods: {len(self.get_available_drawing_methods())}\n")

        stats = {
            'total_images': 0,
            'total_annotations': 0,
            'avg_annotations_per_image': 0
        }

        for i in tqdm(range(num_images), desc="Generating dataset"):
            try:
                img_path, label_path, num_ann = self.generate_single_image(
                    page_id=i,
                    num_components=random.randint(10, 25),
                    include_overlay_prob=0.3
                )

                stats['total_images'] += 1
                stats['total_annotations'] += num_ann

            except Exception as e:
                print(f"\n  Error on image {i}: {e}")
                continue

        stats['avg_annotations_per_image'] = stats['total_annotations'] / stats['total_images'] if stats['total_images'] > 0 else 0

        # Save stats
        stats_path = self.output_dir / "generation_stats.json"
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)

        print(f"\n{'='*60}")
        print("Dataset Generation Complete!")
        print(f"{'='*60}")
        print(f"Images: {stats['total_images']}")
        print(f"Total annotations: {stats['total_annotations']}")
        print(f"Avg annotations/image: {stats['avg_annotations_per_image']:.2f}")
        print(f"\nOutput directory: {self.output_dir}")


def main():
    """Test with small dataset"""
    generator = DatasetGeneratorDirect("yolo_dataset")

    # Generate small test set
    generator.generate_dataset(num_images=10, components_per_image=12)


if __name__ == "__main__":
    main()
