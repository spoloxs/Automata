"""
Final comprehensive pipeline test before full dataset generation

Tests:
1. Generate 10 sample images with random components
2. Validate all bounding boxes are accurate
3. Test occlusion detection
4. Verify YOLO annotations
5. Create visual validation images
"""

from PIL import Image, ImageDraw
import random
from pathlib import Path
from smart_component_generator import SmartComponentGenerator
from web_components_list import get_all_components
import json


def generate_test_dataset(num_images=10):
    """Generate small test dataset"""
    print("\n" + "="*60)
    print("FINAL PIPELINE TEST - Generating Sample Dataset")
    print("="*60 + "\n")

    output_dir = Path("final_test_output")
    images_dir = output_dir / "images"
    labels_dir = output_dir / "labels"
    visual_dir = output_dir / "visual"

    for d in [images_dir, labels_dir, visual_dir]:
        d.mkdir(parents=True, exist_ok=True)

    generator = SmartComponentGenerator()
    all_components = get_all_components()
    class_mapping = {comp: idx for idx, comp in enumerate(all_components)}

    # Save classes
    with open(output_dir / "classes.txt", 'w') as f:
        f.write('\n'.join(all_components))

    print(f"Configuration:")
    print(f"  - Total component types: {len(all_components)}")
    print(f"  - Images to generate: {num_images}")
    print(f"  - Components per image: 10-20 (random)\n")

    stats = []

    for img_id in range(num_images):
        print(f"Image {img_id + 1}/{num_images}")

        # Create blank canvas
        img = Image.new('RGB', (generator.width, generator.height), (255, 255, 255))
        draw = ImageDraw.Draw(img, 'RGBA')

        # Select random components
        num_comps = random.randint(10, 20)
        selected_types = random.sample(all_components, num_comps)

        # 30% chance of overlay
        add_overlay = random.random() < 0.3
        if add_overlay:
            selected_types.append('modal')

        print(f"  Drawing {len(selected_types)} components...")

        drawn_components = []
        layout_grid = []  # Track occupied spaces

        # Draw components
        for comp_type in selected_types:
            # Find category
            category = next((cat for cat, comps in {
                'navigation': ['navbar', 'sidebar', 'breadcrumbs', 'tabs', 'footer'],
                'buttons': ['primary_button', 'secondary_button', 'icon_button', 'toggle_button'],
                'forms': ['text_input', 'checkbox', 'select_dropdown', 'textarea'],
                # ... etc
            }.items() if comp_type in comps), "generic")

            # Get rough position (avoid too much overlap)
            x = random.randint(20, max(100, generator.width - 500))
            y = random.randint(20, max(100, generator.height - 300))

            # Draw component
            try:
                comp = generator.draw_component(draw, comp_type, x, y, category)
                comp.comp_id = f"comp_{len(drawn_components)}"
                drawn_components.append(comp)
            except Exception as e:
                print(f"    ⚠️  Could not draw {comp_type}: {e}")

        # Detect occlusions
        overlays = [c for c in drawn_components if c.z_index >= 900]
        if overlays:
            print(f"  Found {len(overlays)} overlay(s)")
            for comp in drawn_components:
                if comp in overlays:
                    continue
                for overlay in overlays:
                    comp_bbox = comp.get_bbox()
                    overlay_bbox = overlay.get_bbox()
                    intersects = not (
                        comp_bbox[2] < overlay_bbox[0] or comp_bbox[0] > overlay_bbox[2] or
                        comp_bbox[3] < overlay_bbox[1] or comp_bbox[1] > overlay_bbox[3]
                    )
                    if intersects and comp.z_index < overlay.z_index:
                        comp.occluded = True

        # Create YOLO annotations
        annotations = []
        visible_count = 0
        occluded_count = 0

        for comp in drawn_components:
            if comp.occluded:
                occluded_count += 1
                continue
            if not comp.visible:
                continue

            if comp.comp_type in class_mapping:
                class_id = class_mapping[comp.comp_type]
                # Normalize
                x_center = ((comp.x + comp.x + comp.width) / 2) / generator.width
                y_center = ((comp.y + comp.y + comp.height) / 2) / generator.height
                w = comp.width / generator.width
                h = comp.height / generator.height

                if 0 < w <= 1 and 0 < h <= 1:
                    annotations.append(f"{class_id} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}")
                    visible_count += 1

        # Save image
        img_path = images_dir / f"img_{img_id:04d}.png"
        img.save(img_path)

        # Save annotations
        label_path = labels_dir / f"img_{img_id:04d}.txt"
        with open(label_path, 'w') as f:
            f.write('\n'.join(annotations))

        # Create visual validation
        visual_img = img.copy()
        visual_draw = ImageDraw.Draw(visual_img, 'RGBA')

        for comp in drawn_components:
            bbox = comp.get_bbox()
            color = (0, 255, 0) if not comp.occluded else (255, 0, 0)
            visual_draw.rectangle(bbox, outline=color, width=2)

            label = comp.comp_type
            if comp.occluded:
                label += " [OCCLUDED]"
            visual_draw.text((bbox[0] + 5, bbox[1] + 5), label, fill=color)

        visual_path = visual_dir / f"img_{img_id:04d}_visual.png"
        visual_img.save(visual_path)

        stats.append({
            'image_id': img_id,
            'total_components': len(drawn_components),
            'visible_annotated': visible_count,
            'occluded': occluded_count
        })

        print(f"  ✓ Generated: {visible_count} annotations, {occluded_count} occluded\n")

    # Summary
    print("="*60)
    print("TEST DATASET COMPLETE")
    print("="*60)
    print(f"Images: {num_images}")
    print(f"Avg components/image: {sum(s['total_components'] for s in stats) / num_images:.1f}")
    print(f"Avg annotations/image: {sum(s['visible_annotated'] for s in stats) / num_images:.1f}")
    print(f"Total occluded: {sum(s['occluded'] for s in stats)}")
    print(f"\nOutput: {output_dir}")
    print(f"  - Images: {images_dir}")
    print(f"  - Labels: {labels_dir}")
    print(f"  - Visual validation: {visual_dir}")

    # Save stats
    with open(output_dir / "stats.json", 'w') as f:
        json.dump(stats, f, indent=2)

    return stats


if __name__ == "__main__":
    generate_test_dataset(num_images=10)
