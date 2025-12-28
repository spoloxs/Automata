"""
Generates realistic webpages with all possible components for YOLO training

Handles:
- All component types
- Proper occlusion (popups hide elements behind them)
- Multiple fonts, colors, layouts
- Realistic compositions
"""

import os
import json
import random
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
import numpy as np

from web_components_list import (
    WEB_COMPONENTS,
    FONT_FAMILIES,
    ICON_LIBRARIES,
    COLOR_SCHEMES,
    get_all_components
)


@dataclass
class BoundingBox:
    """Bounding box with label"""
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    label: str
    visible: bool = True  # False if occluded by popup/modal
    z_index: int = 0  # For layering

class WebpageGenerator:
    """Generates HTML webpages with components and annotations"""

    def __init__(self, output_dir: str = "generated_dataset"):
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.labels_dir = self.output_dir / "labels"
        self.html_dir = self.output_dir / "html"

        # Create directories
        for dir_path in [self.images_dir, self.labels_dir, self.html_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Component templates
        self.all_components = get_all_components()

    def generate_component_html(self, component_type: str, component_id: str) -> Tuple[str, BoundingBox]:
        """
        Generate HTML for a single component with unique ID for bbox extraction

        Returns:
            (html_string, expected_bbox)
        """
        # Each component gets a unique ID for later bbox extraction
        comp_id = f"comp_{component_id}"

        html_templates = {
            # NAVIGATION
            "navbar": f'''
                <nav id="{comp_id}" class="navbar" style="background: #333; color: white; padding: 15px; display: flex; justify-content: space-between; align-items: center;">
                    <div class="logo">Logo</div>
                    <ul style="display: flex; list-style: none; gap: 20px; margin: 0;">
                        <li><a href="#" style="color: white;">Home</a></li>
                        <li><a href="#" style="color: white;">About</a></li>
                        <li><a href="#" style="color: white;">Services</a></li>
                        <li><a href="#" style="color: white;">Contact</a></li>
                    </ul>
                </nav>
            ''',

            "sidebar": f'''
                <aside id="{comp_id}" class="sidebar" style="width: 250px; background: #f4f4f4; padding: 20px; min-height: 400px;">
                    <h3>Navigation</h3>
                    <ul style="list-style: none; padding: 0;">
                        <li style="padding: 10px 0;"><a href="#">Dashboard</a></li>
                        <li style="padding: 10px 0;"><a href="#">Profile</a></li>
                        <li style="padding: 10px 0;"><a href="#">Settings</a></li>
                        <li style="padding: 10px 0;"><a href="#">Logout</a></li>
                    </ul>
                </aside>
            ''',

            "breadcrumbs": f'''
                <nav id="{comp_id}" class="breadcrumbs" style="padding: 10px; background: #f8f8f8;">
                    <a href="#">Home</a> &gt; <a href="#">Category</a> &gt; <span>Current Page</span>
                </nav>
            ''',

            # BUTTONS
            "primary_button": f'''
                <button id="{comp_id}" style="background: #007bff; color: white; border: none; padding: 12px 24px; border-radius: 4px; cursor: pointer; font-size: 16px;">
                    Click Me
                </button>
            ''',

            "icon_button": f'''
                <button id="{comp_id}" style="background: #28a745; color: white; border: none; padding: 10px; border-radius: 50%; width: 40px; height: 40px; cursor: pointer;">
                    &#9733;
                </button>
            ''',

            "toggle_button": f'''
                <label id="{comp_id}" class="toggle" style="display: inline-block; width: 60px; height: 30px; background: #ccc; border-radius: 30px; position: relative; cursor: pointer;">
                    <input type="checkbox" style="display: none;">
                    <span style="position: absolute; top: 3px; left: 3px; width: 24px; height: 24px; background: white; border-radius: 50%; transition: 0.3s;"></span>
                </label>
            ''',

            # FORMS
            "text_input": f'''
                <div id="{comp_id}" style="margin: 10px 0;">
                    <label style="display: block; margin-bottom: 5px;">Name:</label>
                    <input type="text" placeholder="Enter your name" style="width: 300px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">
                </div>
            ''',

            "textarea": f'''
                <div id="{comp_id}" style="margin: 10px 0;">
                    <label style="display: block; margin-bottom: 5px;">Message:</label>
                    <textarea placeholder="Enter your message" style="width: 300px; height: 100px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;"></textarea>
                </div>
            ''',

            "checkbox": f'''
                <div id="{comp_id}" style="margin: 10px 0;">
                    <label style="display: flex; align-items: center; gap: 8px;">
                        <input type="checkbox">
                        <span>I agree to terms and conditions</span>
                    </label>
                </div>
            ''',

            "select_dropdown": f'''
                <div id="{comp_id}" style="margin: 10px 0;">
                    <label style="display: block; margin-bottom: 5px;">Country:</label>
                    <select style="width: 300px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">
                        <option>Select a country</option>
                        <option>United States</option>
                        <option>United Kingdom</option>
                        <option>Canada</option>
                        <option>Australia</option>
                    </select>
                </div>
            ''',

            # MODALS & POPUPS
            "modal": f'''
                <div id="{comp_id}" class="modal" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000;">
                    <div class="modal-content" style="background: white; padding: 30px; border-radius: 8px; max-width: 500px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
                        <h2>Modal Title</h2>
                        <p>This is a modal dialog with some content.</p>
                        <button style="background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; margin-top: 15px;">Close</button>
                    </div>
                </div>
            ''',

            "popup": f'''
                <div id="{comp_id}" class="popup" style="position: fixed; bottom: 20px; right: 20px; background: white; border: 1px solid #ddd; border-radius: 8px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 999; max-width: 300px;">
                    <h4 style="margin-top: 0;">Subscribe to Newsletter</h4>
                    <input type="email" placeholder="your@email.com" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; margin: 10px 0;">
                    <button style="width: 100%; background: #28a745; color: white; border: none; padding: 10px; border-radius: 4px;">Subscribe</button>
                </div>
            ''',

            "cookie_consent": f'''
                <div id="{comp_id}" class="cookie-banner" style="position: fixed; bottom: 0; left: 0; right: 0; background: #2c3e50; color: white; padding: 20px; z-index: 998;">
                    <div style="max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; gap: 20px;">
                        <p style="margin: 0;">We use cookies to improve your experience. By continuing, you agree to our cookie policy.</p>
                        <div style="display: flex; gap: 10px;">
                            <button style="background: transparent; border: 1px solid white; color: white; padding: 8px 16px; border-radius: 4px;">Decline</button>
                            <button style="background: #27ae60; border: none; color: white; padding: 8px 16px; border-radius: 4px;">Accept</button>
                        </div>
                    </div>
                </div>
            ''',

            # CONTENT
            "card": f'''
                <div id="{comp_id}" class="card" style="border: 1px solid #ddd; border-radius: 8px; overflow: hidden; max-width: 300px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <img src="data:image/svg+xml,%3Csvg width='300' height='200' xmlns='http://www.w3.org/2000/svg'%3E%3Crect width='300' height='200' fill='%23e0e0e0'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' dy='.3em' fill='%23999' font-size='20'%3EImage%3C/text%3E%3C/svg%3E" style="width: 100%; display: block;">
                    <div style="padding: 15px;">
                        <h3 style="margin: 0 0 10px 0;">Card Title</h3>
                        <p style="color: #666; margin: 0 0 15px 0;">This is a card with some description text.</p>
                        <button style="background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px;">Learn More</button>
                    </div>
                </div>
            ''',

            "table": f'''
                <table id="{comp_id}" style="border-collapse: collapse; width: 100%; border: 1px solid #ddd;">
                    <thead>
                        <tr style="background: #f8f8f8;">
                            <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Name</th>
                            <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Email</th>
                            <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Role</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 10px;">John Doe</td>
                            <td style="border: 1px solid #ddd; padding: 10px;">john@example.com</td>
                            <td style="border: 1px solid #ddd; padding: 10px;">Admin</td>
                        </tr>
                        <tr style="background: #f9f9f9;">
                            <td style="border: 1px solid #ddd; padding: 10px;">Jane Smith</td>
                            <td style="border: 1px solid #ddd; padding: 10px;">jane@example.com</td>
                            <td style="border: 1px solid #ddd; padding: 10px;">User</td>
                        </tr>
                    </tbody>
                </table>
            ''',

            # CROSSWORD (as user mentioned specifically)
            "crossword": f'''
                <div id="{comp_id}" class="crossword" style="display: inline-grid; grid-template-columns: repeat(10, 30px); grid-template-rows: repeat(10, 30px); gap: 1px; background: #000; border: 2px solid #000;">
                    {"".join([f'<div style="background: white; display: flex; align-items: center; justify-content: center; font-size: 12px;"></div>' for _ in range(100)])}
                </div>
            ''',

            # NOTIFICATIONS
            "toast": f'''
                <div id="{comp_id}" class="toast" style="position: fixed; top: 20px; right: 20px; background: #28a745; color: white; padding: 15px 20px; border-radius: 4px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 1001;">
                    &#10004; Success! Your action was completed.
                </div>
            ''',

            "alert": f'''
                <div id="{comp_id}" class="alert" style="background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 15px; border-radius: 4px; margin: 10px 0;">
                    <strong>Warning!</strong> Please check your input.
                </div>
            ''',

            # MEDIA
            "video_player": f'''
                <div id="{comp_id}" class="video-player" style="width: 640px; background: #000; border-radius: 8px; overflow: hidden;">
                    <div style="aspect-ratio: 16/9; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; color: white; font-size: 48px;">
                        &#9658;
                    </div>
                    <div style="background: #222; padding: 10px; display: flex; justify-content: space-between; align-items: center;">
                        <div style="display: flex; gap: 15px; color: white;">
                            <span>&#9658;</span>
                            <span>&#9208;</span>
                            <span>&#128266;</span>
                        </div>
                        <div style="flex: 1; margin: 0 15px; height: 4px; background: #555; border-radius: 2px;">
                            <div style="width: 30%; height: 100%; background: #fff; border-radius: 2px;"></div>
                        </div>
                        <span style="color: white;">0:30 / 1:42</span>
                    </div>
                </div>
            ''',

            "audio_player": f'''
                <div id="{comp_id}" class="audio-player" style="background: #f8f8f8; border: 1px solid #ddd; border-radius: 8px; padding: 20px; width: 400px;">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <button style="width: 50px; height: 50px; border-radius: 50%; border: none; background: #007bff; color: white; font-size: 20px;">&#9658;</button>
                        <div style="flex: 1;">
                            <div style="height: 4px; background: #ddd; border-radius: 2px; margin-bottom: 8px;">
                                <div style="width: 45%; height: 100%; background: #007bff; border-radius: 2px;"></div>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #666;">
                                <span>1:23</span>
                                <span>3:07</span>
                            </div>
                        </div>
                    </div>
                </div>
            ''',

            # ADS
            "banner_ad": f'''
                <div id="{comp_id}" class="banner-ad" style="background: linear-gradient(to right, #ff6b6b, #ee5a6f); color: white; padding: 20px; text-align: center; border-radius: 4px;">
                    <h3 style="margin: 0 0 10px 0;">Limited Time Offer!</h3>
                    <p style="margin: 0 0 15px 0;">Get 50% off on all products</p>
                    <button style="background: white; color: #ff6b6b; border: none; padding: 10px 20px; border-radius: 4px; font-weight: bold; cursor: pointer;">Shop Now</button>
                </div>
            ''',

            # ECOMMERCE
            "shopping_cart": f'''
                <div id="{comp_id}" class="cart-icon" style="position: relative; display: inline-block;">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 2L7 6M7 6L3 6L3 18C3 19.1 3.9 20 5 20H19C20.1 20 21 19.1 21 18V6H17M7 6H17M17 6L15 2M10 11V14M14 11V14"/>
                    </svg>
                    <span style="position: absolute; top: -8px; right: -8px; background: #ff4444; color: white; border-radius: 10px; padding: 2px 6px; font-size: 12px; font-weight: bold;">3</span>
                </div>
            ''',

            "product_card": f'''
                <div id="{comp_id}" class="product-card" style="border: 1px solid #ddd; border-radius: 8px; overflow: hidden; width: 250px; background: white;">
                    <div style="position: relative;">
                        <div style="background: #f0f0f0; aspect-ratio: 1; display: flex; align-items: center; justify-content: center;">
                            <div style="width: 80%; height: 80%; background: linear-gradient(45deg, #667eea, #764ba2);"></div>
                        </div>
                        <span style="position: absolute; top: 10px; right: 10px; background: #ff4444; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">SALE</span>
                    </div>
                    <div style="padding: 15px;">
                        <h4 style="margin: 0 0 8px 0;">Product Name</h4>
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                            <span style="color: #ffc107;">&#9733;&#9733;&#9733;&#9733;&#9734;</span>
                            <span style="color: #666; font-size: 14px;">(24)</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
                            <span style="font-size: 20px; font-weight: bold; color: #007bff;">$29.99</span>
                            <span style="text-decoration: line-through; color: #999;">$49.99</span>
                        </div>
                        <button style="width: 100%; background: #28a745; color: white; border: none; padding: 10px; border-radius: 4px; font-weight: bold; cursor: pointer;">Add to Cart</button>
                    </div>
                </div>
            ''',

            # Add more component templates...
        }

        # Get template or create generic one
        html = html_templates.get(component_type, f'<div id="{comp_id}" class="{component_type}" style="padding: 20px; border: 1px solid #ddd; margin: 10px;">{component_type.replace("_", " ").title()}</div>')

        # Bbox will be determined later when rendering
        bbox = BoundingBox(0, 0, 0, 0, component_type)

        return html, bbox

    def create_full_page(self, num_components: int = 20, include_popup: bool = False) -> str:
        """
        Create a full HTML page with random components

        Args:
            num_components: Number of components to include
            include_popup: Whether to add modal/popup that occludes other elements
        """
        # Select random components
        selected_components = random.sample(self.all_components, min(num_components, len(self.all_components)))

        # Random font
        font_family = random.choice(FONT_FAMILIES)

        # Random color scheme
        color_scheme = random.choice(COLOR_SCHEMES)
        bg_color = "#ffffff" if "light" in color_scheme else "#1a1a1a" if "dark" in color_scheme else "#f5f5f5"
        text_color = "#000000" if "light" in color_scheme else "#ffffff" if "dark" in color_scheme else "#333333"

        # Generate components
        components_html = []
        for i, comp_type in enumerate(selected_components):
            html, _ = self.generate_component_html(comp_type, str(i))
            components_html.append(html)

        # Optionally add popup/modal at the end (higher z-index)
        if include_popup:
            popup_type = random.choice(["modal", "popup", "cookie_consent"])
            popup_html, _ = self.generate_component_html(popup_type, "popup")
            components_html.append(popup_html)

        # Full HTML page
        full_html = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated Webpage</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: {font_family}, sans-serif;
            background: {bg_color};
            color: {text_color};
            margin: 0;
            padding: 20px;
        }}
    </style>
</head>
<body>
    {chr(10).join(components_html)}
</body>
</html>
'''
        return full_html

    def save_page(self, html_content: str, page_id: int):
        """Save HTML page to file"""
        html_path = self.html_dir / f"page_{page_id}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return html_path


def main():
    """Test the generator"""
    generator = WebpageGenerator()

    # Generate a test page
    html = generator.create_full_page(num_components=15, include_popup=True)
    html_path = generator.save_page(html, 0)

    print(f"Generated test page: {html_path}")
    print(f"Total components available: {len(generator.all_components)}")

if __name__ == "__main__":
    main()
