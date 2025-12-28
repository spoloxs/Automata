"""
Renders HTML pages and creates YOLO annotations with visual validation

Features:
- Extracts actual bounding boxes from rendered pages
- Detects occlusion (elements hidden by popups/modals)
- Creates visual validation images with drawn boxes
- Validates coordinates are correct
- Generates YOLO format annotations
"""

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Tuple
from playwright.async_api import async_playwright, Page
import cv2
import numpy as np
from dataclasses import dataclass

from fixed_webpage_generator import FixedWebpageGenerator, ComponentMetadata


@dataclass
class AnnotatedBox:
    """Bounding box with all metadata"""
    comp_id: str
    comp_type: str
    category: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    is_visible: bool  # Actually visible (not display:none, etc.)
    is_occluded: bool  # Hidden by modal/popup
    z_index: int
    area: int

    @property
    def should_annotate(self) -> bool:
        """Whether this box should be in YOLO annotations"""
        return self.is_visible and not self.is_occluded and self.area > 100


class WebpageRendererWithValidation:
    """Renders pages and creates validated annotations"""

    def __init__(self, output_dir: str = "test_output"):
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.labels_dir = self.output_dir / "labels"
        self.visual_dir = self.output_dir / "visual_validation"
        self.metadata_dir = self.output_dir / "metadata"

        for dir_path in [self.images_dir, self.labels_dir, self.visual_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Image dimensions
        self.width = 1440
        self.height = 900

    async def extract_bbox_from_browser(
        self,
        page: Page,
        component_id: str
    ) -> Tuple[int, int, int, int, bool, int]:
        """
        Extract bounding box from actual rendered element

        Returns:
            (x_min, y_min, x_max, y_max, is_visible, z_index)
        """
        script = f"""
        () => {{
            const element = document.getElementById('{component_id}');
            if (!element) {{
                return {{error: 'Element not found', id: '{component_id}'}};
            }}

            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);

            // Check actual visibility
            const isVisible = (
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                parseFloat(style.opacity) > 0 &&
                rect.width > 0 &&
                rect.height > 0
            );

            const zIndex = parseInt(style.zIndex) || 0;

            return {{
                x: Math.round(rect.left),
                y: Math.round(rect.top),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
                visible: isVisible,
                zIndex: zIndex,
                display: style.display,
                visibility: style.visibility,
                opacity: style.opacity
            }};
        }}
        """

        try:
            result = await page.evaluate(script)

            if 'error' in result:
                print(f"  ⚠️  {result['error']}: {result['id']}")
                return 0, 0, 0, 0, False, 0

            # Clamp to viewport
            x_min = max(0, min(self.width, result['x']))
            y_min = max(0, min(self.height, result['y']))
            x_max = max(0, min(self.width, result['x'] + result['width']))
            y_max = max(0, min(self.height, result['y'] + result['height']))

            return x_min, y_min, x_max, y_max, result['visible'], result['zIndex']

        except Exception as e:
            print(f"  ❌ Error extracting bbox for {component_id}: {e}")
            return 0, 0, 0, 0, False, 0

    async def detect_occlusions(self, page: Page, all_boxes: List[AnnotatedBox]) -> List[AnnotatedBox]:
        """
        Detect which elements are occluded by higher z-index overlays

        Returns updated boxes with is_occluded flag set correctly
        """
        # Find all high z-index overlays (modals, popups, etc.)
        overlays = [box for box in all_boxes if box.z_index >= 900 and box.is_visible]

        if not overlays:
            return all_boxes  # No occlusion possible

        print(f"  Found {len(overlays)} overlay(s) that may occlude elements:")
        for overlay in overlays:
            print(f"    - {overlay.comp_type} (z-index: {overlay.z_index})")

        # Check each box for occlusion
        updated_boxes = []
        for box in all_boxes:
            is_occluded = False

            # Check if box intersects with any higher z-index overlay
            for overlay in overlays:
                if box.z_index >= overlay.z_index:
                    continue  # Box is above or same level as overlay

                # Check intersection
                intersects = not (
                    box.x_max < overlay.x_min or
                    box.x_min > overlay.x_max or
                    box.y_max < overlay.y_min or
                    box.y_min > overlay.y_max
                )

                if intersects:
                    is_occluded = True
                    print(f"  🔒 {box.comp_type} occluded by {overlay.comp_type}")
                    break

            # Update box
            box.is_occluded = is_occluded
            updated_boxes.append(box)

        return updated_boxes

    def bbox_to_yolo(
        self,
        box: AnnotatedBox,
        class_id: int
    ) -> str:
        """Convert bbox to YOLO format (normalized)"""
        if not box.should_annotate:
            return ""

        # Calculate center and size (normalized)
        x_center = ((box.x_min + box.x_max) / 2) / self.width
        y_center = ((box.y_min + box.y_max) / 2) / self.height
        width = (box.x_max - box.x_min) / self.width
        height = (box.y_max - box.y_min) / self.height

        # Validate
        if width <= 0 or height <= 0 or width > 1 or height > 1:
            return ""

        # Clamp
        x_center = max(0.0, min(1.0, x_center))
        y_center = max(0.0, min(1.0, y_center))
        width = max(0.0, min(1.0, width))
        height = max(0.0, min(1.0, height))

        return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"

    def draw_validation_image(
        self,
        image_path: Path,
        boxes: List[AnnotatedBox],
        output_path: Path
    ):
        """
        Draw bounding boxes on image for visual validation

        Colors:
        - Green: Visible, not occluded (will be annotated)
        - Red: Occluded (won't be annotated)
        - Yellow: Invisible (display:none, etc.)
        """
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"  ❌ Could not load image: {image_path}")
            return

        for box in boxes:
            # Choose color based on status
            if box.should_annotate:
                color = (0, 255, 0)  # Green - will be annotated
                thickness = 2
            elif box.is_occluded:
                color = (0, 0, 255)  # Red - occluded
                thickness = 2
            elif not box.is_visible:
                color = (0, 255, 255)  # Yellow - invisible
                thickness = 1
            else:
                color = (128, 128, 128)  # Gray - other reason
                thickness = 1

            # Draw box
            cv2.rectangle(
                img,
                (box.x_min, box.y_min),
                (box.x_max, box.y_max),
                color,
                thickness
            )

            # Add label
            label = f"{box.comp_type}"
            if box.is_occluded:
                label += " [OCCLUDED]"
            elif not box.is_visible:
                label += " [HIDDEN]"

            # Label background
            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(
                img,
                (box.x_min, box.y_min - label_h - 8),
                (box.x_min + label_w + 8, box.y_min),
                color,
                -1
            )

            # Label text
            cv2.putText(
                img,
                label,
                (box.x_min + 4, box.y_min - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

        # Save
        cv2.imwrite(str(output_path), img)
        print(f"  ✓ Validation image saved: {output_path.name}")

    async def render_and_annotate(
        self,
        html_path: Path,
        metadata_path: Path,
        page_id: int,
        class_mapping: Dict[str, int]
    ) -> Dict:
        """
        Render page and create annotations with validation

        Returns statistics dict
        """
        print(f"\n{'='*60}")
        print(f"Rendering page_{page_id}")
        print(f"{'='*60}")

        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        component_metas = [ComponentMetadata(**c) for c in metadata['components']]
        print(f"Expected components: {len(component_metas)}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={'width': self.width, 'height': self.height})

            # Load page
            await page.goto(f'file://{html_path.absolute()}')
            await page.wait_for_timeout(1500)  # Wait for rendering

            # Take screenshot
            screenshot_path = self.images_dir / f"page_{page_id}.png"
            await page.screenshot(path=screenshot_path)
            print(f"  ✓ Screenshot: {screenshot_path.name}")

            # Extract bounding boxes for each component
            boxes = []
            for meta in component_metas:
                x_min, y_min, x_max, y_max, visible, z_idx = await self.extract_bbox_from_browser(
                    page,
                    meta.component_id
                )

                area = (x_max - x_min) * (y_max - y_min)

                box = AnnotatedBox(
                    comp_id=meta.component_id,
                    comp_type=meta.component_type,
                    category=meta.category,
                    x_min=x_min,
                    y_min=y_min,
                    x_max=x_max,
                    y_max=y_max,
                    is_visible=visible,
                    is_occluded=False,  # Will be updated
                    z_index=z_idx,
                    area=area
                )
                boxes.append(box)

            print(f"  Extracted {len(boxes)} bounding boxes")

            # Detect occlusions
            boxes = await self.detect_occlusions(page, boxes)

            await browser.close()

        # Create YOLO annotations
        annotations = []
        annotated_count = 0
        occluded_count = 0
        invisible_count = 0

        for box in boxes:
            if not box.is_visible:
                invisible_count += 1
                continue

            if box.is_occluded:
                occluded_count += 1
                continue

            if box.comp_type in class_mapping:
                class_id = class_mapping[box.comp_type]
                yolo_line = self.bbox_to_yolo(box, class_id)

                if yolo_line:
                    annotations.append(yolo_line)
                    annotated_count += 1

        # Save YOLO annotations
        annotation_path = self.labels_dir / f"page_{page_id}.txt"
        with open(annotation_path, 'w') as f:
            f.write('\n'.join(annotations))

        print(f"  ✓ Annotations: {annotated_count} valid")
        print(f"    - Invisible: {invisible_count}")
        print(f"    - Occluded: {occluded_count}")

        # Create visual validation
        visual_path = self.visual_dir / f"page_{page_id}_validation.png"
        self.draw_validation_image(screenshot_path, boxes, visual_path)

        # Statistics
        stats = {
            "page_id": page_id,
            "total_components": len(boxes),
            "annotated": annotated_count,
            "invisible": invisible_count,
            "occluded": occluded_count,
            "boxes": [
                {
                    "id": b.comp_id,
                    "type": b.comp_type,
                    "bbox": [b.x_min, b.y_min, b.x_max, b.y_max],
                    "visible": b.is_visible,
                    "occluded": b.is_occluded,
                    "annotated": b.should_annotate
                }
                for b in boxes
            ]
        }

        # Save detailed stats
        stats_path = self.output_dir / "metadata" / f"page_{page_id}_render.json"
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)

        return stats


async def test_rendering():
    """Test the rendering pipeline with validation"""
    print("\n" + "="*60)
    print("TESTING RENDERER WITH VISUAL VALIDATION")
    print("="*60 + "\n")

    # Generate test pages
    generator = FixedWebpageGenerator("test_output")

    print("Step 1: Generating test HTML pages...\n")

    # Page without popup
    html1, meta1 = generator.create_full_page(num_components=10, include_popup=False)
    html_path1, meta_path1 = generator.save_page_with_metadata(html1, meta1, 0)

    # Page WITH popup (occlusion test)
    html2, meta2 = generator.create_full_page(num_components=15, include_popup=True)
    html_path2, meta_path2 = generator.save_page_with_metadata(html2, meta2, 1)

    print("\n" + "="*60)
    print("Step 2: Rendering pages and extracting bounding boxes...\n")
    print("="*60)

    # Create class mapping
    all_components = generator.all_components
    class_mapping = {comp: idx for idx, comp in enumerate(all_components)}

    # Render
    renderer = WebpageRendererWithValidation("test_output")

    # Render both pages
    stats1 = await renderer.render_and_annotate(html_path1, meta_path1, 0, class_mapping)
    stats2 = await renderer.render_and_annotate(html_path2, meta_path2, 1, class_mapping)

    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60 + "\n")

    print("Page 0 (no popup):")
    print(f"  Total: {stats1['total_components']}")
    print(f"  Annotated: {stats1['annotated']}")
    print(f"  Occluded: {stats1['occluded']}")
    print(f"  Invisible: {stats1['invisible']}")

    print("\nPage 1 (with popup/modal):")
    print(f"  Total: {stats2['total_components']}")
    print(f"  Annotated: {stats2['annotated']}")
    print(f"  Occluded: {stats2['occluded']} 👈 Should be > 0 if occlusion works!")
    print(f"  Invisible: {stats2['invisible']}")

    print("\n" + "="*60)
    print("VALIDATION IMAGES")
    print("="*60)
    print(f"\n✓ Check these images to verify bounding boxes:")
    print(f"  {renderer.visual_dir / 'page_0_validation.png'}")
    print(f"  {renderer.visual_dir / 'page_1_validation.png'}")
    print("\n  Legend:")
    print("    🟢 Green boxes = Visible & annotated (good)")
    print("    🔴 Red boxes = Occluded by popup (correctly excluded)")
    print("    🟡 Yellow boxes = Invisible (correctly excluded)")

    print("\n" + "="*60)
    print("✓ TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_rendering())
