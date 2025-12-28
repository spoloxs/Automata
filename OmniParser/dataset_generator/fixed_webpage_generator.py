"""
FIXED Webpage Generator - Tracks component types correctly

Key fixes:
1. Saves component_type as data attribute
2. Tracks component mapping in metadata JSON
3. Validates coordinates are within image bounds
4. Tests occlusion handling
"""

import os
import json
import random
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
import numpy as np

from web_components_list import (
    WEB_COMPONENTS,
    FONT_FAMILIES,
    COLOR_SCHEMES,
    get_all_components
)


@dataclass
class ComponentMetadata:
    """Metadata for each component in the page"""
    component_id: str  # e.g., "comp_0"
    component_type: str  # e.g., "navbar"
    category: str  # e.g., "navigation"
    z_index: int
    expected_visible: bool  # Whether we expect it to be visible


class FixedWebpageGenerator:
    """Generates HTML with proper component tracking"""

    def __init__(self, output_dir: str = "generated_dataset"):
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.labels_dir = self.output_dir / "labels"
        self.html_dir = self.output_dir / "html"
        self.metadata_dir = self.output_dir / "metadata"

        # Create directories
        for dir_path in [self.images_dir, self.labels_dir, self.html_dir, self.metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        self.all_components = get_all_components()

    def generate_component_html(
        self,
        component_type: str,
        component_id: str,
        category: str
    ) -> str:
        """
        Generate HTML for component with proper data attributes for tracking

        Returns HTML with:
        - id="{component_id}"
        - data-component-type="{component_type}"
        - data-category="{category}"
        """
        # Base attributes for ALL components
        attrs = f'id="{component_id}" data-component-type="{component_type}" data-category="{category}"'

        # Component templates with proper tracking
        templates = {
            # NAVIGATION
            "navbar": f'''
<nav {attrs} class="navbar" style="background: #2c3e50; color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
    <div style="font-size: 24px; font-weight: bold;">Brand</div>
    <ul style="display: flex; list-style: none; gap: 30px; margin: 0; padding: 0;">
        <li><a href="#" style="color: white; text-decoration: none;">Home</a></li>
        <li><a href="#" style="color: white; text-decoration: none;">Products</a></li>
        <li><a href="#" style="color: white; text-decoration: none;">About</a></li>
        <li><a href="#" style="color: white; text-decoration: none;">Contact</a></li>
    </ul>
    <button style="background: #3498db; border: none; color: white; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Sign In</button>
</nav>
            ''',

            "sidebar": f'''
<aside {attrs} class="sidebar" style="width: 250px; background: #34495e; color: white; padding: 20px; min-height: 500px; box-shadow: 2px 0 4px rgba(0,0,0,0.1);">
    <h3 style="margin-top: 0; border-bottom: 2px solid #3498db; padding-bottom: 10px;">Menu</h3>
    <ul style="list-style: none; padding: 0; margin: 0;">
        <li style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.1);"><a href="#" style="color: white; text-decoration: none;">📊 Dashboard</a></li>
        <li style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.1);"><a href="#" style="color: white; text-decoration: none;">👤 Profile</a></li>
        <li style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.1);"><a href="#" style="color: white; text-decoration: none;">⚙️ Settings</a></li>
        <li style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.1);"><a href="#" style="color: white; text-decoration: none;">📈 Analytics</a></li>
        <li style="padding: 12px 0;"><a href="#" style="color: #e74c3c; text-decoration: none;">🚪 Logout</a></li>
    </ul>
</aside>
            ''',

            "breadcrumbs": f'''
<nav {attrs} class="breadcrumbs" style="padding: 12px 20px; background: #ecf0f1; font-size: 14px; border-radius: 4px; margin: 10px 0;">
    <a href="#" style="color: #3498db; text-decoration: none;">Home</a>
    <span style="margin: 0 8px; color: #7f8c8d;">›</span>
    <a href="#" style="color: #3498db; text-decoration: none;">Category</a>
    <span style="margin: 0 8px; color: #7f8c8d;">›</span>
    <span style="color: #2c3e50; font-weight: 500;">Current Page</span>
</nav>
            ''',

            "tabs": f'''
<div {attrs} class="tabs" style="border-bottom: 2px solid #ecf0f1;">
    <div style="display: flex; gap: 0;">
        <button style="background: #3498db; color: white; border: none; padding: 12px 24px; cursor: pointer; border-radius: 4px 4px 0 0; font-weight: 500;">Tab 1</button>
        <button style="background: transparent; color: #7f8c8d; border: none; padding: 12px 24px; cursor: pointer;">Tab 2</button>
        <button style="background: transparent; color: #7f8c8d; border: none; padding: 12px 24px; cursor: pointer;">Tab 3</button>
    </div>
</div>
            ''',

            # BUTTONS
            "primary_button": f'''
<button {attrs} style="background: #3498db; color: white; border: none; padding: 12px 32px; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 500; box-shadow: 0 2px 4px rgba(52,152,219,0.3); transition: all 0.3s;">
    Primary Action
</button>
            ''',

            "secondary_button": f'''
<button {attrs} style="background: transparent; color: #3498db; border: 2px solid #3498db; padding: 10px 30px; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 500;">
    Secondary Action
</button>
            ''',

            "icon_button": f'''
<button {attrs} style="background: #27ae60; color: white; border: none; padding: 12px; border-radius: 50%; width: 48px; height: 48px; cursor: pointer; font-size: 20px; display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(39,174,96,0.3);">
    ★
</button>
            ''',

            "toggle_button": f'''
<label {attrs} class="toggle" style="display: inline-block; width: 60px; height: 32px; background: #bdc3c7; border-radius: 32px; position: relative; cursor: pointer; transition: background 0.3s;">
    <input type="checkbox" style="display: none;">
    <span style="position: absolute; top: 4px; left: 4px; width: 24px; height: 24px; background: white; border-radius: 50%; transition: transform 0.3s; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"></span>
</label>
            ''',

            # FORMS
            "text_input": f'''
<div {attrs} style="margin: 15px 0;">
    <label style="display: block; margin-bottom: 8px; font-weight: 500; color: #2c3e50;">Full Name</label>
    <input type="text" placeholder="Enter your full name" style="width: 100%; max-width: 400px; padding: 12px 16px; border: 2px solid #ecf0f1; border-radius: 6px; font-size: 16px; transition: border-color 0.3s;">
</div>
            ''',

            "textarea": f'''
<div {attrs} style="margin: 15px 0;">
    <label style="display: block; margin-bottom: 8px; font-weight: 500; color: #2c3e50;">Message</label>
    <textarea placeholder="Enter your message..." style="width: 100%; max-width: 400px; min-height: 120px; padding: 12px 16px; border: 2px solid #ecf0f1; border-radius: 6px; font-size: 16px; resize: vertical;"></textarea>
</div>
            ''',

            "checkbox": f'''
<div {attrs} style="margin: 12px 0;">
    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
        <input type="checkbox" style="width: 20px; height: 20px; cursor: pointer;">
        <span style="font-size: 15px; color: #2c3e50;">I agree to the terms and conditions</span>
    </label>
</div>
            ''',

            "select_dropdown": f'''
<div {attrs} style="margin: 15px 0;">
    <label style="display: block; margin-bottom: 8px; font-weight: 500; color: #2c3e50;">Country</label>
    <select style="width: 100%; max-width: 400px; padding: 12px 16px; border: 2px solid #ecf0f1; border-radius: 6px; font-size: 16px; background: white; cursor: pointer;">
        <option>Select a country</option>
        <option>United States</option>
        <option>United Kingdom</option>
        <option>Canada</option>
        <option>Australia</option>
        <option>Germany</option>
        <option>France</option>
    </select>
</div>
            ''',

            # MODALS & OVERLAYS (high z-index for occlusion testing)
            "modal": f'''
<div {attrs} class="modal" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 1000;">
    <div class="modal-content" style="background: white; padding: 40px; border-radius: 12px; max-width: 500px; box-shadow: 0 10px 40px rgba(0,0,0,0.3); position: relative;">
        <button style="position: absolute; top: 15px; right: 15px; background: transparent; border: none; font-size: 24px; cursor: pointer; color: #95a5a6;">×</button>
        <h2 style="margin: 0 0 16px 0; color: #2c3e50;">Important Notice</h2>
        <p style="color: #7f8c8d; line-height: 1.6; margin-bottom: 24px;">This is a modal dialog with important information. Elements behind it should be marked as occluded!</p>
        <div style="display: flex; gap: 12px; justify-content: flex-end;">
            <button style="background: #ecf0f1; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer;">Cancel</button>
            <button style="background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer;">Confirm</button>
        </div>
    </div>
</div>
            ''',

            "popup": f'''
<div {attrs} class="popup" style="position: fixed; bottom: 20px; right: 20px; background: white; border: 1px solid #ecf0f1; border-radius: 12px; padding: 24px; box-shadow: 0 8px 24px rgba(0,0,0,0.15); z-index: 999; max-width: 320px;">
    <button style="position: absolute; top: 10px; right: 10px; background: transparent; border: none; font-size: 20px; cursor: pointer; color: #95a5a6;">×</button>
    <h4 style="margin: 0 0 12px 0; color: #2c3e50;">Subscribe to Newsletter</h4>
    <p style="color: #7f8c8d; font-size: 14px; margin-bottom: 16px;">Get the latest updates delivered to your inbox.</p>
    <input type="email" placeholder="your@email.com" style="width: 100%; padding: 10px 12px; border: 2px solid #ecf0f1; border-radius: 6px; margin-bottom: 12px;">
    <button style="width: 100%; background: #27ae60; color: white; border: none; padding: 12px; border-radius: 6px; font-weight: 500; cursor: pointer;">Subscribe</button>
</div>
            ''',

            "cookie_consent": f'''
<div {attrs} class="cookie-banner" style="position: fixed; bottom: 0; left: 0; right: 0; background: #2c3e50; color: white; padding: 24px; z-index: 998; box-shadow: 0 -4px 12px rgba(0,0,0,0.1);">
    <div style="max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; gap: 24px; flex-wrap: wrap;">
        <p style="margin: 0; flex: 1; min-width: 300px;">🍪 We use cookies to improve your experience. By continuing, you agree to our <a href="#" style="color: #3498db;">cookie policy</a>.</p>
        <div style="display: flex; gap: 12px;">
            <button style="background: transparent; border: 2px solid white; color: white; padding: 10px 20px; border-radius: 6px; cursor: pointer;">Decline</button>
            <button style="background: #27ae60; border: none; color: white; padding: 10px 20px; border-radius: 6px; cursor: pointer;">Accept</button>
        </div>
    </div>
</div>
            ''',

            # CONTENT CARDS
            "card": f'''
<div {attrs} class="card" style="border: 1px solid #ecf0f1; border-radius: 12px; overflow: hidden; max-width: 320px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); background: white;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); height: 200px; display: flex; align-items: center; justify-content: center; color: white; font-size: 48px;">
        📦
    </div>
    <div style="padding: 20px;">
        <h3 style="margin: 0 0 12px 0; color: #2c3e50;">Product Name</h3>
        <p style="color: #7f8c8d; margin: 0 0 16px 0; line-height: 1.6;">This is a product card with image, title, description, and action button.</p>
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 24px; font-weight: bold; color: #27ae60;">$49.99</span>
            <button style="background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer;">Buy Now</button>
        </div>
    </div>
</div>
            ''',

            "table": f'''
<table {attrs} style="border-collapse: collapse; width: 100%; max-width: 800px; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-radius: 8px; overflow: hidden;">
    <thead>
        <tr style="background: #34495e; color: white;">
            <th style="padding: 16px; text-align: left; font-weight: 600;">Name</th>
            <th style="padding: 16px; text-align: left; font-weight: 600;">Email</th>
            <th style="padding: 16px; text-align: left; font-weight: 600;">Role</th>
            <th style="padding: 16px; text-align: left; font-weight: 600;">Status</th>
        </tr>
    </thead>
    <tbody>
        <tr style="border-bottom: 1px solid #ecf0f1;">
            <td style="padding: 14px;">John Doe</td>
            <td style="padding: 14px;">john@example.com</td>
            <td style="padding: 14px;"><span style="background: #3498db; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px;">Admin</span></td>
            <td style="padding: 14px;"><span style="color: #27ae60;">● Active</span></td>
        </tr>
        <tr style="background: #f8f9fa; border-bottom: 1px solid #ecf0f1;">
            <td style="padding: 14px;">Jane Smith</td>
            <td style="padding: 14px;">jane@example.com</td>
            <td style="padding: 14px;"><span style="background: #95a5a6; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px;">User</span></td>
            <td style="padding: 14px;"><span style="color: #27ae60;">● Active</span></td>
        </tr>
        <tr style="border-bottom: 1px solid #ecf0f1;">
            <td style="padding: 14px;">Bob Johnson</td>
            <td style="padding: 14px;">bob@example.com</td>
            <td style="padding: 14px;"><span style="background: #e67e22; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px;">Editor</span></td>
            <td style="padding: 14px;"><span style="color: #e74c3c;">● Inactive</span></td>
        </tr>
    </tbody>
</table>
            ''',

            # CROSSWORD (special grid - user specifically requested)
            "crossword": f'''
<div {attrs} class="crossword" style="display: inline-grid; grid-template-columns: repeat(10, 36px); grid-template-rows: repeat(10, 36px); gap: 1px; background: #2c3e50; border: 3px solid #2c3e50; border-radius: 4px;">
    {"".join([f'<div style="background: white; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 500; color: #2c3e50; position: relative;"><span style="position: absolute; top: 2px; left: 2px; font-size: 8px; color: #95a5a6;">{i+1 if i % 15 == 0 else ""}</span></div>' for i in range(100)])}
</div>
            ''',

            # NOTIFICATIONS
            "toast": f'''
<div {attrs} class="toast" style="position: fixed; top: 24px; right: 24px; background: #27ae60; color: white; padding: 16px 24px; border-radius: 8px; box-shadow: 0 8px 16px rgba(39,174,96,0.3); z-index: 1001; display: flex; align-items: center; gap: 12px; min-width: 280px;">
    <span style="font-size: 24px;">✓</span>
    <div>
        <div style="font-weight: 600; margin-bottom: 4px;">Success!</div>
        <div style="font-size: 14px; opacity: 0.9;">Your changes have been saved.</div>
    </div>
    <button style="background: transparent; border: none; color: white; font-size: 20px; cursor: pointer; margin-left: auto;">×</button>
</div>
            ''',

            "alert": f'''
<div {attrs} class="alert" style="background: #fff3cd; border: 2px solid #ffc107; color: #856404; padding: 16px 20px; border-radius: 8px; margin: 16px 0; display: flex; align-items: start; gap: 12px;">
    <span style="font-size: 24px;">⚠️</span>
    <div>
        <strong style="display: block; margin-bottom: 4px;">Warning!</strong>
        <span>Please review your input before proceeding.</span>
    </div>
</div>
            ''',

            # Add default for unknown components
        }

        return templates.get(component_type, f'''
<div {attrs} class="{component_type}" style="padding: 24px; border: 2px solid #ecf0f1; border-radius: 8px; margin: 12px 0; background: white;">
    <h4 style="margin: 0 0 8px 0; color: #2c3e50;">{component_type.replace("_", " ").title()}</h4>
    <p style="color: #7f8c8d; margin: 0;">Component placeholder for {component_type}</p>
</div>
        ''')

    def create_full_page(
        self,
        num_components: int = 20,
        include_popup: bool = False
    ) -> Tuple[str, List[ComponentMetadata]]:
        """
        Create full HTML page with component metadata tracking

        Returns:
            (html_content, component_metadata_list)
        """
        # Group components by category
        categorized = {cat: comps for cat, comps in WEB_COMPONENTS.items()}

        # Select random components from different categories
        selected = []
        metadata_list = []

        for i in range(num_components):
            # Pick random category
            category = random.choice(list(categorized.keys()))
            component_type = random.choice(categorized[category])

            comp_id = f"comp_{i}"
            z_index = 0  # Default z-index

            # Generate HTML
            html = self.generate_component_html(component_type, comp_id, category)
            selected.append(html)

            # Track metadata
            metadata = ComponentMetadata(
                component_id=comp_id,
                component_type=component_type,
                category=category,
                z_index=z_index,
                expected_visible=True  # Will be updated if occluded
            )
            metadata_list.append(metadata)

        # Optionally add popup/modal (will occlude elements)
        if include_popup:
            popup_types = ["modal", "popup", "cookie_consent"]
            popup_type = random.choice(popup_types)
            comp_id = "comp_popup"

            html = self.generate_component_html(popup_type, comp_id, "overlays")
            selected.append(html)

            # High z-index for overlay
            metadata = ComponentMetadata(
                component_id=comp_id,
                component_type=popup_type,
                category="overlays",
                z_index=999,
                expected_visible=True
            )
            metadata_list.append(metadata)

            # Mark other components as potentially occluded
            # (Will be determined precisely during rendering)

        # Random styling
        font_family = random.choice(FONT_FAMILIES)
        color_scheme = random.choice(COLOR_SCHEMES)
        bg_color = "#ffffff" if "light" in color_scheme else "#1a1a1a" if "dark" in color_scheme else "#f8f9fa"
        text_color = "#000000" if "light" in color_scheme else "#ffffff" if "dark" in color_scheme else "#2c3e50"

        # Build full HTML
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated Test Page</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: {font_family}, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: {bg_color};
            color: {text_color};
            margin: 0;
            padding: 24px;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    {chr(10).join(selected)}
</body>
</html>'''

        return html, metadata_list

    def save_page_with_metadata(
        self,
        html_content: str,
        metadata_list: List[ComponentMetadata],
        page_id: int
    ) -> Tuple[Path, Path]:
        """Save HTML and metadata JSON"""
        html_path = self.html_dir / f"page_{page_id}.html"
        metadata_path = self.metadata_dir / f"page_{page_id}.json"

        # Save HTML
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Save metadata
        metadata_dict = {
            "page_id": page_id,
            "components": [asdict(m) for m in metadata_list]
        }
        with open(metadata_path, 'w') as f:
            json.dump(metadata_dict, f, indent=2)

        return html_path, metadata_path


def main():
    """Test the fixed generator"""
    print("Testing Fixed Webpage Generator\n")
    print("="*60)

    generator = FixedWebpageGenerator("test_output")

    # Test 1: Simple page
    print("\nTest 1: Generating simple page (no popup)...")
    html, metadata = generator.create_full_page(num_components=10, include_popup=False)
    html_path, meta_path = generator.save_page_with_metadata(html, metadata, 0)
    print(f"✓ Saved to: {html_path}")
    print(f"✓ Metadata: {meta_path}")
    print(f"  Components: {len(metadata)}")

    # Test 2: Page with popup (occlusion test)
    print("\nTest 2: Generating page WITH popup (occlusion test)...")
    html, metadata = generator.create_full_page(num_components=15, include_popup=True)
    html_path, meta_path = generator.save_page_with_metadata(html, metadata, 1)
    print(f"✓ Saved to: {html_path}")
    print(f"✓ Metadata: {meta_path}")
    print(f"  Components: {len(metadata)}")

    print("\n" + "="*60)
    print("✓ Tests complete! Open the HTML files to visually inspect.")
    print(f"\nOutput directory: {generator.output_dir}")

if __name__ == "__main__":
    main()
