"""
Renders HTML pages to images and creates YOLO format annotations

Handles:
- Rendering with Playwright
- Bounding box extraction via JavaScript
- Occlusion detection (elements behind popups)
- YOLO format annotation files
"""

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Tuple
from playwright.async_api import async_playwright, Page
import cv2
import numpy as np

from webpage_generator import WebpageGenerator, BoundingBox


class WebpageRenderer:
    """Renders webpages and extracts component bounding boxes"""

    def __init__(self, output_dir: str = "generated_dataset"):
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.labels_dir = self.output_dir / "labels"
        self.generator = WebpageGenerator(output_dir)

        # Image dimensions
        self.width = 1440
        self.height = 900

    async def get_element_bbox(self, page: Page, element_id: str) -> Tuple[int, int, int, int, bool]:
        """
        Get bounding box for an element and check if it's visible

        Returns:
            (x_min, y_min, x_max, y_max, is_visible)
        """
        bbox_script = f"""
        () => {{
            const element = document.getElementById('{element_id}');
            if (!element) return null;

            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);

            // Check if actually visible
            const isVisible = (
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                style.opacity !== '0' &&
                rect.width > 0 &&
                rect.height > 0
            );

            // Check if occluded by checking z-index and position
            const zIndex = parseInt(style.zIndex) || 0;

            return {{
                x: Math.round(rect.left),
                y: Math.round(rect.top),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
                visible: isVisible,
                zIndex: zIndex
            }};
        }}
        """

        result = await page.evaluate(bbox_script)

        if not result:
            return 0, 0, 0, 0, False

        x_min = max(0, result['x'])
        y_min = max(0, result['y'])
        x_max = min(self.width, result['x'] + result['width'])
        y_max = min(self.height, result['y'] + result['height'])

        return x_min, y_min, x_max, y_max, result['visible']

    async def check_occlusion(self, page: Page) -> Dict[str, bool]:
        """
        Check which elements are occluded by modals/popups

        Returns:
            Dictionary mapping element_id to is_occluded status
        """
        occlusion_script = """
        () => {
            // Find all modals/popups with high z-index
            const overlays = Array.from(document.querySelectorAll('[class*="modal"], [class*="popup"], [class*="overlay"]'))
                .filter(el => {
                    const style = window.getComputedStyle(el);
                    const zIndex = parseInt(style.zIndex) || 0;
                    const isVisible = style.display !== 'none' && style.visibility !== 'hidden';
                    return zIndex >= 900 && isVisible;
                })
                .map(el => {
                    const rect = el.getBoundingClientRect();
                    return {
                        id: el.id,
                        rect: {x: rect.left, y: rect.top, width: rect.width, height: rect.height},
                        zIndex: parseInt(window.getComputedStyle(el).zIndex) || 0
                    };
                });

            // Check all elements
            const allElements = Array.from(document.querySelectorAll('[id^="comp_"]'));
            const occlusions = {};

            allElements.forEach(el => {
                const rect = el.getBoundingClientRect();
                const elZIndex = parseInt(window.getComputedStyle(el).zIndex) || 0;

                // Check if element intersects with any higher z-index overlay
                const isOccluded = overlays.some(overlay => {
                    if (elZIndex >= overlay.zIndex) return false;

                    // Check intersection
                    const intersects = !(
                        rect.right < overlay.rect.x ||
                        rect.left > overlay.rect.x + overlay.rect.width ||
                        rect.bottom < overlay.rect.y ||
                        rect.top > overlay.rect.y + overlay.rect.height
                    );

                    return intersects;
                });

                occlusions[el.id] = isOccluded;
            });

            return occlusions;
        }
        """

        return await page.evaluate(occlusion_script)

    def bbox_to_yolo_format(self, bbox: BoundingBox, img_width: int, img_height: int, class_id: int) -> str:
        """
        Convert bounding box to YOLO format

        YOLO format: <class_id> <x_center> <y_center> <width> <height>
        All values normalized to [0, 1]
        """
        if not bbox.visible:
            return ""  # Skip occluded/invisible elements

        # Calculate center and dimensions
        x_center = ((bbox.x_min + bbox.x_max) / 2) / img_width
        y_center = ((bbox.y_min + bbox.y_max) / 2) / img_height
        width = (bbox.x_max - bbox.x_min) / img_width
        height = (bbox.y_max - bbox.y_min) / img_height

        # Validate
        if width <= 0 or height <= 0:
            return ""

        # Clamp to [0, 1]
        x_center = max(0.0, min(1.0, x_center))
        y_center = max(0.0, min(1.0, y_center))
        width = max(0.0, min(1.0, width))
        height = max(0.0, min(1.0, height))

        return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"

    async def render_page(self, html_path: Path, page_id: int, class_mapping: Dict[str, int]):
        """
        Render HTML page to image and create YOLO annotations

        Args:
            html_path: Path to HTML file
            page_id: Unique page identifier
            class_mapping: Mapping from component name to class ID
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={'width': self.width, 'height': self.height})

            # Load page
            await page.goto(f'file://{html_path.absolute()}')
            await page.wait_for_timeout(1000)  # Wait for page to settle

            # Take screenshot
            screenshot_path = self.images_dir / f"page_{page_id}.png"
            await page.screenshot(path=screenshot_path)

            # Get occlusion information
            occlusions = await self.check_occlusion(page)

            # Extract all component bounding boxes
            annotations = []
            comp_elements = await page.query_selector_all('[id^="comp_"]')

            for element in comp_elements:
                element_id = await element.get_attribute('id')
                class_name = await element.get_attribute('class')

                # Parse component type from class or ID
                # comp_0, comp_1, etc - we need to track what type each is
                # For now, extract from class attribute
                if not class_name:
                    continue

                component_type = class_name

                # Get bounding box
                x_min, y_min, x_max, y_max, visible = await self.get_element_bbox(page, element_id)

                # Check if occluded
                is_occluded = occlusions.get(element_id, False)

                # Create bbox object
                bbox = BoundingBox(
                    x_min=x_min,
                    y_min=y_min,
                    x_max=x_max,
                    y_max=y_max,
                    label=component_type,
                    visible=visible and not is_occluded
                )

                # Convert to YOLO format
                if component_type in class_mapping:
                    class_id = class_mapping[component_type]
                    yolo_line = self.bbox_to_yolo_format(bbox, self.width, self.height, class_id)

                    if yolo_line:  # Only add if valid
                        annotations.append(yolo_line)

            # Save annotations
            annotation_path = self.labels_dir / f"page_{page_id}.txt"
            with open(annotation_path, 'w') as f:
                f.write('\n'.join(annotations))

            await browser.close()

            return screenshot_path, annotation_path, len(annotations)


async def generate_dataset(num_pages: int = 1000, components_per_page: int = 20):
    """
    Generate complete dataset with images and YOLO annotations

    Args:
        num_pages: Number of pages to generate
        components_per_page: Average number of components per page
    """
    generator = WebpageGenerator()
    renderer = WebpageRenderer()

    # Create class mapping
    all_components = generator.all_components
    class_mapping = {comp: idx for idx, comp in enumerate(all_components)}

    # Save class names
    classes_file = renderer.output_dir / "classes.txt"
    with open(classes_file, 'w') as f:
        f.write('\n'.join(all_components))

    print(f"Generating {num_pages} pages...")
    print(f"Total classes: {len(all_components)}")

    for page_id in range(num_pages):
        # Randomly vary number of components
        num_comps = np.random.randint(10, min(30, len(all_components)))

        # 30% chance of popup/modal
        include_popup = np.random.random() < 0.3

        # Generate HTML
        html_content = generator.create_full_page(num_comps, include_popup)
        html_path = generator.save_page(html_content, page_id)

        # Render and annotate
        img_path, ann_path, num_annotations = await renderer.render_page(html_path, page_id, class_mapping)

        if (page_id + 1) % 100 == 0:
            print(f"Progress: {page_id + 1}/{num_pages} pages generated")
            print(f"  Latest: {num_annotations} annotations")

    print(f"\nDataset generation complete!")
    print(f"Images: {renderer.images_dir}")
    print(f"Labels: {renderer.labels_dir}")
    print(f"Classes: {classes_file}")


if __name__ == "__main__":
    # Generate smaller test dataset first
    asyncio.run(generate_dataset(num_pages=10, components_per_page=15))
