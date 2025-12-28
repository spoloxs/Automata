"""
Direct Image Generator - Creates training images without HTML rendering

Advantages:
- Much faster (no browser needed)
- Complete control over exact positioning
- Perfect bounding box accuracy
- Can generate thousands of images quickly
- Exact replication of web component appearance

Uses PIL/Pillow to draw components that look identical to real HTML elements
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random
from typing import List, Tuple, Dict
from dataclasses import dataclass
import numpy as np
from pathlib import Path
import colorsys

from web_components_list import WEB_COMPONENTS, FONT_FAMILIES, COLOR_SCHEMES


@dataclass
class DrawnComponent:
    """Component that has been drawn on canvas"""
    comp_id: str
    comp_type: str
    category: str
    x: int
    y: int
    width: int
    height: int
    z_index: int
    visible: bool = True
    occluded: bool = False

    def get_bbox(self) -> Tuple[int, int, int, int]:
        """Get bounding box coords"""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def get_area(self) -> int:
        """Get area in pixels"""
        return self.width * self.height


class WebComponentDrawer:
    """Draws realistic web components directly to image"""

    def __init__(self, width=1440, height=900):
        self.width = width
        self.height = height

        # Color palette
        self.colors = {
            'primary': [(52, 152, 219), (41, 128, 185), (26, 188, 156), (22, 160, 133)],
            'success': [(39, 174, 96), (34, 153, 84), (46, 204, 113)],
            'danger': [(231, 76, 60), (192, 57, 43), (230, 126, 34)],
            'warning': [(243, 156, 18), (241, 196, 15), (230, 126, 34)],
            'dark': [(44, 62, 80), (52, 73, 94), (127, 140, 141)],
            'light': [(236, 240, 241), (189, 195, 199), (149, 165, 166)],
            'white': [(255, 255, 255)],
            'black': [(0, 0, 0)],
            'gray': [(149, 165, 166), (127, 140, 141), (108, 122, 137)],
        }

        # Try to load fonts (fallback to default if not available)
        self.fonts = self._load_fonts()

    def _load_fonts(self) -> Dict:
        """Load fonts with fallbacks"""
        fonts = {}
        try:
            fonts['small'] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            fonts['regular'] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            fonts['medium'] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            fonts['large'] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            fonts['xlarge'] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            fonts['mono'] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
        except:
            # Fallback to default
            fonts = {k: ImageFont.load_default() for k in ['small', 'regular', 'medium', 'large', 'xlarge', 'mono']}

        return fonts

    def draw_rounded_rectangle(self, draw: ImageDraw, bbox: Tuple[int, int, int, int], fill, outline=None, radius=0, width=1):
        """Draw rounded rectangle"""
        if radius == 0:
            draw.rectangle(bbox, fill=fill, outline=outline, width=width)
            return

        x1, y1, x2, y2 = bbox
        draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)

    def draw_shadow(self, draw: ImageDraw, bbox: Tuple[int, int, int, int], offset=4, blur=8):
        """Draw shadow effect"""
        x1, y1, x2, y2 = bbox
        shadow_bbox = (x1 + offset, y1 + offset, x2 + offset, y2 + offset)
        # Simple shadow approximation
        for i in range(blur):
            alpha = int(255 * (1 - i/blur) * 0.3)
            color = (0, 0, 0, alpha)
            inflate = i
            draw.rectangle(
                (shadow_bbox[0] - inflate, shadow_bbox[1] - inflate,
                 shadow_bbox[2] + inflate, shadow_bbox[3] + inflate),
                outline=color
            )

    # ========== NAVIGATION COMPONENTS ==========

    def draw_navbar(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw navigation bar"""
        width = self.width
        height = 60
        bg_color = random.choice(self.colors['dark'])

        # Background
        draw.rectangle((x, y, x + width, y + height), fill=bg_color)

        # Logo
        draw.text((x + 40, y + height//2), "LOGO", fill=self.colors['white'][0], font=self.fonts['large'], anchor="lm")

        # Menu items
        menu_x = x + 200
        for item in ["Home", "Products", "About", "Contact"]:
            draw.text((menu_x, y + height//2), item, fill=self.colors['white'][0], font=self.fonts['regular'], anchor="lm")
            menu_x += 120

        # Sign in button
        btn_x = x + width - 120
        btn_y = y + height//2 - 16
        self.draw_rounded_rectangle(
            draw,
            (btn_x, btn_y, btn_x + 100, btn_y + 32),
            fill=random.choice(self.colors['primary']),
            radius=6
        )
        draw.text((btn_x + 50, btn_y + 16), "Sign In", fill=self.colors['white'][0], font=self.fonts['regular'], anchor="mm")

        return DrawnComponent(
            comp_id="",  # Will be set by caller
            comp_type="navbar",
            category="navigation",
            x=x, y=y, width=width, height=height,
            z_index=100
        )

    def draw_sidebar(self, draw: ImageDraw, x: int, y: int, is_right=False) -> DrawnComponent:
        """Draw sidebar"""
        width = 250
        height = 600
        bg_color = (248, 249, 250)

        # Background
        draw.rectangle((x, y, x + width, y + height), fill=bg_color, outline=(224, 224, 224), width=1)

        # Title
        draw.text((x + 20, y + 30), "Navigation", fill=self.colors['dark'][0], font=self.fonts['medium'], anchor="lm")

        # Menu items with icons
        menu_y = y + 70
        items = [("📊", "Dashboard"), ("👤", "Profile"), ("⚙️", "Settings"), ("📁", "Files"), ("📈", "Analytics")]

        for icon, text in items:
            # Hover state for first item
            if menu_y == y + 70:
                draw.rectangle((x + 10, menu_y - 8, x + width - 10, menu_y + 28), fill=(230, 240, 250), outline=None)

            draw.text((x + 20, menu_y + 10), f"{icon}  {text}", fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="lm")
            menu_y += 50

        return DrawnComponent("", "sidebar", "navigation", x, y, width, height, 0)

    def draw_breadcrumbs(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw breadcrumbs"""
        width = 400
        height = 40
        bg_color = (236, 240, 241)

        # Background
        self.draw_rounded_rectangle(draw, (x, y, x + width, y + height), fill=bg_color, radius=6)

        # Breadcrumb items
        text = "Home › Category › Subcategory › Page"
        draw.text((x + 16, y + height//2), text, fill=(108, 117, 125), font=self.fonts['small'], anchor="lm")

        return DrawnComponent("", "breadcrumbs", "navigation", x, y, width, height, 0)

    # ========== BUTTONS ==========

    def draw_primary_button(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw primary button"""
        width = 140
        height = 44
        bg_color = random.choice(self.colors['primary'])

        # Shadow
        shadow_offset = 2
        draw.rectangle(
            (x + shadow_offset, y + shadow_offset, x + width + shadow_offset, y + height + shadow_offset),
            fill=(0, 0, 0, 30)
        )

        # Button
        self.draw_rounded_rectangle(draw, (x, y, x + width, y + height), fill=bg_color, radius=6)

        # Text
        draw.text((x + width//2, y + height//2), "Click Me", fill=self.colors['white'][0], font=self.fonts['regular'], anchor="mm")

        return DrawnComponent("", "primary_button", "buttons", x, y, width, height, 0)

    def draw_icon_button(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw icon button"""
        size = 48
        bg_color = random.choice(self.colors['success'])

        # Circle button with shadow
        draw.ellipse((x + 2, y + 2, x + size + 2, y + size + 2), fill=(0, 0, 0, 40))
        draw.ellipse((x, y, x + size, y + size), fill=bg_color)

        # Icon (star)
        draw.text((x + size//2, y + size//2), "★", fill=self.colors['white'][0], font=self.fonts['large'], anchor="mm")

        return DrawnComponent("", "icon_button", "buttons", x, y, size, size, 0)

    def draw_toggle_button(self, draw: ImageDraw, x: int, y: int, checked=None) -> DrawnComponent:
        """Draw toggle switch"""
        width = 60
        height = 32
        checked = random.choice([True, False]) if checked is None else checked

        # Track
        track_color = random.choice(self.colors['primary']) if checked else (189, 195, 199)
        self.draw_rounded_rectangle(draw, (x, y, x + width, y + height), fill=track_color, radius=height//2)

        # Thumb
        thumb_x = x + width - 28 if checked else x + 4
        thumb_y = y + 4
        draw.ellipse((thumb_x, thumb_y, thumb_x + 24, thumb_y + 24), fill=self.colors['white'][0], outline=None)

        return DrawnComponent("", "toggle_button", "buttons", x, y, width, height, 0)

    # ========== FORMS ==========

    def draw_text_input(self, draw: ImageDraw, x: int, y: int, label="Name") -> DrawnComponent:
        """Draw text input field"""
        width = 350
        height = 70

        # Label
        draw.text((x, y + 10), label, fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="lt")

        # Input box
        input_y = y + 35
        self.draw_rounded_rectangle(
            draw,
            (x, input_y, x + width, input_y + 44),
            fill=self.colors['white'][0],
            outline=(220, 220, 220),
            radius=6,
            width=2
        )

        # Placeholder text
        draw.text((x + 16, input_y + 22), "Enter your " + label.lower(), fill=(180, 180, 180), font=self.fonts['regular'], anchor="lm")

        return DrawnComponent("", "text_input", "forms", x, y, width, height, 0)

    def draw_textarea(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw textarea"""
        width = 400
        height = 140

        # Label
        draw.text((x, y + 10), "Message", fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="lt")

        # Textarea box
        textarea_y = y + 35
        self.draw_rounded_rectangle(
            draw,
            (x, textarea_y, x + width, textarea_y + 100),
            fill=self.colors['white'][0],
            outline=(220, 220, 220),
            radius=6,
            width=2
        )

        # Placeholder
        draw.text((x + 16, textarea_y + 16), "Enter your message...", fill=(180, 180, 180), font=self.fonts['regular'], anchor="lt")

        return DrawnComponent("", "textarea", "forms", x, y, width, height, 0)

    def draw_checkbox(self, draw: ImageDraw, x: int, y: int, checked=None) -> DrawnComponent:
        """Draw checkbox"""
        width = 300
        height = 32
        checked = random.choice([True, False]) if checked is None else checked

        # Checkbox box
        box_size = 20
        box_color = random.choice(self.colors['primary']) if checked else self.colors['white'][0]
        box_outline = random.choice(self.colors['primary']) if checked else (200, 200, 200)

        self.draw_rounded_rectangle(
            draw,
            (x, y + 6, x + box_size, y + 6 + box_size),
            fill=box_color,
            outline=box_outline,
            radius=4,
            width=2
        )

        # Checkmark
        if checked:
            # Draw checkmark
            draw.line([(x + 6, y + 16), (x + 9, y + 19), (x + 15, y + 11)], fill=self.colors['white'][0], width=2)

        # Label
        draw.text((x + box_size + 12, y + height//2), "I agree to terms and conditions", fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="lm")

        return DrawnComponent("", "checkbox", "forms", x, y, width, height, 0)

    def draw_select_dropdown(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw select dropdown"""
        width = 350
        height = 70

        # Label
        draw.text((x, y + 10), "Country", fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="lt")

        # Select box
        select_y = y + 35
        self.draw_rounded_rectangle(
            draw,
            (x, select_y, x + width, select_y + 44),
            fill=self.colors['white'][0],
            outline=(220, 220, 220),
            radius=6,
            width=2
        )

        # Selected value
        draw.text((x + 16, select_y + 22), "Select a country", fill=(100, 100, 100), font=self.fonts['regular'], anchor="lm")

        # Dropdown arrow
        arrow_x = x + width - 30
        draw.polygon([(arrow_x, select_y + 18), (arrow_x + 12, select_y + 18), (arrow_x + 6, select_y + 26)], fill=(100, 100, 100))

        return DrawnComponent("", "select_dropdown", "forms", x, y, width, height, 0)

    # ========== SPECIAL/COMPLEX COMPONENTS ==========

    def draw_crossword(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw crossword grid"""
        cols, rows = 15, 15
        cell_size = 32
        width = cols * cell_size + 2
        height = rows * cell_size + 2

        # Border
        draw.rectangle((x, y, x + width, y + height), outline=self.colors['black'][0], width=3)

        # Draw grid
        for row in range(rows):
            for col in range(cols):
                cell_x = x + col * cell_size + 1
                cell_y = y + row * cell_size + 1

                # Some cells are black (blocked)
                if random.random() < 0.25:
                    draw.rectangle(
                        (cell_x, cell_y, cell_x + cell_size, cell_y + cell_size),
                        fill=self.colors['black'][0]
                    )
                else:
                    # White cell with border
                    draw.rectangle(
                        (cell_x, cell_y, cell_x + cell_size, cell_y + cell_size),
                        fill=self.colors['white'][0],
                        outline=(200, 200, 200),
                        width=1
                    )

                    # Clue number in some cells
                    if random.random() < 0.15:
                        clue_num = str(random.randint(1, 50))
                        draw.text((cell_x + 3, cell_y + 2), clue_num, fill=(100, 100, 100), font=self.fonts['small'], anchor="lt")

        return DrawnComponent("", "crossword", "specialized", x, y, width, height, 0)

    def draw_sudoku_grid(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw sudoku grid"""
        cell_size = 40
        width = height = 9 * cell_size + 4

        # Background
        draw.rectangle((x, y, x + width, y + height), fill=self.colors['white'][0], outline=self.colors['black'][0], width=3)

        # Draw 9x9 grid
        for row in range(9):
            for col in range(9):
                cell_x = x + col * cell_size + 2
                cell_y = y + row * cell_size + 2

                # Cell border (thicker every 3 cells)
                line_width = 2 if (row % 3 == 0 or col % 3 == 0) else 1
                draw.rectangle(
                    (cell_x, cell_y, cell_x + cell_size, cell_y + cell_size),
                    outline=self.colors['black'][0],
                    width=line_width
                )

                # Some cells have numbers
                if random.random() < 0.4:
                    num = str(random.randint(1, 9))
                    draw.text(
                        (cell_x + cell_size//2, cell_y + cell_size//2),
                        num,
                        fill=self.colors['black'][0] if random.random() < 0.5 else random.choice(self.colors['primary']),
                        font=self.fonts['medium'],
                        anchor="mm"
                    )

        return DrawnComponent("", "sudoku_grid", "specialized", x, y, width, height, 0)

    def draw_video_player(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw video player with controls"""
        width = 640
        height = 400

        # Video area (gradient to simulate video)
        for i in range(height - 60):
            color_val = int(100 + (i / (height - 60)) * 100)
            draw.line([(x, y + i), (x + width, y + i)], fill=(color_val, color_val - 20, color_val + 50))

        # Play button overlay
        play_size = 80
        play_x = x + width//2 - play_size//2
        play_y = y + (height - 60)//2 - play_size//2
        draw.ellipse(
            (play_x, play_y, play_x + play_size, play_y + play_size),
            fill=(255, 255, 255, 200),
            outline=None
        )
        # Play triangle
        points = [(play_x + 30, play_y + 20), (play_x + 30, play_y + 60), (play_x + 55, play_y + 40)]
        draw.polygon(points, fill=(0, 0, 0))

        # Control bar
        control_y = y + height - 60
        draw.rectangle((x, control_y, x + width, y + height), fill=(30, 30, 30))

        # Control buttons
        draw.text((x + 20, control_y + 30), "▶", fill=self.colors['white'][0], font=self.fonts['large'], anchor="lm")
        draw.text((x + 60, control_y + 30), "⏸", fill=self.colors['white'][0], font=self.fonts['large'], anchor="lm")
        draw.text((x + 100, control_y + 30), "🔊", fill=self.colors['white'][0], font=self.fonts['large'], anchor="lm")

        # Progress bar
        progress_x = x + 150
        progress_width = width - 250
        draw.rectangle((progress_x, control_y + 25, progress_x + progress_width, control_y + 35), fill=(80, 80, 80), outline=None)
        draw.rectangle((progress_x, control_y + 25, progress_x + int(progress_width * 0.3), control_y + 35), fill=random.choice(self.colors['primary']), outline=None)

        # Time
        draw.text((x + width - 80, control_y + 30), "1:23 / 4:56", fill=self.colors['white'][0], font=self.fonts['small'], anchor="lm")

        return DrawnComponent("", "video_player", "media", x, y, width, height, 0)

    def draw_modal(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw modal dialog with backdrop"""
        # Full screen backdrop
        backdrop_overlay = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 150))

        # Modal box
        modal_width = 500
        modal_height = 300
        modal_x = (self.width - modal_width) // 2
        modal_y = (self.height - modal_height) // 2

        # Modal background
        self.draw_rounded_rectangle(
            draw,
            (modal_x, modal_y, modal_x + modal_width, modal_y + modal_height),
            fill=self.colors['white'][0],
            radius=12
        )

        # Drop shadow
        for i in range(10):
            alpha = int(40 * (1 - i/10))
            expand = i * 2
            draw.rectangle(
                (modal_x - expand, modal_y - expand, modal_x + modal_width + expand, modal_y + modal_height + expand),
                outline=(0, 0, 0, alpha)
            )

        # Title
        draw.text((modal_x + 30, modal_y + 40), "Important Notice", fill=self.colors['dark'][0], font=self.fonts['large'], anchor="lt")

        # Close button
        close_x = modal_x + modal_width - 40
        draw.text((close_x, modal_y + 20), "×", fill=(150, 150, 150), font=self.fonts['xlarge'], anchor="lt")

        # Content
        content_y = modal_y + 80
        lines = [
            "This is a modal dialog with important information.",
            "Elements behind this modal should be marked as occluded!",
            "",
            "Click outside or press ESC to close."
        ]
        for i, line in enumerate(lines):
            draw.text((modal_x + 30, content_y + i * 24), line, fill=(127, 140, 141), font=self.fonts['regular'], anchor="lt")

        # Buttons
        btn_y = modal_y + modal_height - 60
        # Cancel
        self.draw_rounded_rectangle(
            draw,
            (modal_x + modal_width - 220, btn_y, modal_x + modal_width - 120, btn_y + 40),
            fill=(236, 240, 241),
            radius=6
        )
        draw.text((modal_x + modal_width - 170, btn_y + 20), "Cancel", fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="mm")

        # Confirm
        self.draw_rounded_rectangle(
            draw,
            (modal_x + modal_width - 110, btn_y, modal_x + modal_width - 30, btn_y + 40),
            fill=random.choice(self.colors['primary']),
            radius=6
        )
        draw.text((modal_x + modal_width - 70, btn_y + 20), "Confirm", fill=self.colors['white'][0], font=self.fonts['regular'], anchor="mm")

        # Return full screen bbox for modal (covers everything)
        return DrawnComponent("", "modal", "overlays", 0, 0, self.width, self.height, 1000)

    # ========== CONTENT ==========

    def draw_card(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw content card"""
        width = 320
        height = 380

        # Card background with shadow
        self.draw_shadow(draw, (x, y, x + width, y + height), offset=4, blur=12)
        self.draw_rounded_rectangle(
            draw,
            (x, y, x + width, y + height),
            fill=self.colors['white'][0],
            outline=(230, 230, 230),
            radius=12,
            width=1
        )

        # Image area (gradient)
        img_height = 200
        for i in range(img_height):
            progress = i / img_height
            r = int(102 + progress * 50)
            g = int(126 + progress * 90)
            b = int(234 - progress * 60)
            draw.line([(x, y + i), (x + width, y + i)], fill=(r, g, b))

        # Content area
        content_y = y + img_height + 20
        draw.text((x + 20, content_y), "Card Title", fill=self.colors['dark'][0], font=self.fonts['medium'], anchor="lt")
        draw.text((x + 20, content_y + 35), "This is a description of the card content.", fill=(127, 140, 141), font=self.fonts['small'], anchor="lt")
        draw.text((x + 20, content_y + 55), "It can span multiple lines and provides", fill=(127, 140, 141), font=self.fonts['small'], anchor="lt")
        draw.text((x + 20, content_y + 75), "information about the item.", fill=(127, 140, 141), font=self.fonts['small'], anchor="lt")

        # Button
        btn_y = y + height - 60
        self.draw_rounded_rectangle(
            draw,
            (x + 20, btn_y, x + width - 20, btn_y + 40),
            fill=random.choice(self.colors['primary']),
            radius=6
        )
        draw.text((x + width//2, btn_y + 20), "Learn More", fill=self.colors['white'][0], font=self.fonts['regular'], anchor="mm")

        return DrawnComponent("", "card", "content", x, y, width, height, 0)

    def draw_table(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw data table"""
        width = 700
        height = 240

        # Table border
        draw.rectangle((x, y, x + width, y + height), outline=(220, 220, 220), width=1)

        # Header
        header_height = 48
        draw.rectangle((x, y, x + width, y + header_height), fill=(248, 249, 250))

        # Header columns
        col_width = width // 4
        headers = ["Name", "Email", "Role", "Status"]
        for i, header in enumerate(headers):
            col_x = x + i * col_width
            draw.line([(col_x, y), (col_x, y + height)], fill=(220, 220, 220), width=1)
            draw.text((col_x + 16, y + header_height//2), header, fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="lm")

        # Data rows
        rows_data = [
            ("John Doe", "john@example.com", "Admin", "Active"),
            ("Jane Smith", "jane@example.com", "User", "Active"),
            ("Bob Johnson", "bob@example.com", "Editor", "Inactive"),
        ]

        row_y = y + header_height
        row_height = 64

        for i, row_data in enumerate(rows_data):
            # Alternate row background
            if i % 2 == 1:
                draw.rectangle((x, row_y, x + width, row_y + row_height), fill=(252, 252, 252))

            # Draw cells
            for j, cell_text in enumerate(row_data):
                col_x = x + j * col_width
                draw.text((col_x + 16, row_y + row_height//2), cell_text, fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="lm")

            # Horizontal line
            draw.line([(x, row_y + row_height), (x + width, row_y + row_height)], fill=(220, 220, 220), width=1)
            row_y += row_height

        return DrawnComponent("", "table", "content", x, y, width, height, 0)

    # ==========IFRAME ==========

    def draw_iframe(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw iframe (embedded content)"""
        width = 600
        height = 400

        # Iframe border
        draw.rectangle((x, y, x + width, y + height), fill=(245, 245, 245), outline=(200, 200, 200), width=2)

        # Simulated address bar
        bar_height = 30
        draw.rectangle((x, y, x + width, y + bar_height), fill=(230, 230, 230))
        draw.text((x + 10, y + bar_height//2), "🔒 https://embedded-site.com", fill=(100, 100, 100), font=self.fonts['small'], anchor="lm")

        # Embedded content (simple page simulation)
        content_y = y + bar_height + 20
        draw.text((x + 20, content_y), "Embedded Content", fill=self.colors['dark'][0], font=self.fonts['large'], anchor="lt")
        draw.text((x + 20, content_y + 40), "This is content from another website", fill=(100, 100, 100), font=self.fonts['regular'], anchor="lt")

        # Mini elements inside iframe
        mini_btn_y = content_y + 80
        self.draw_rounded_rectangle(
            draw,
            (x + 20, mini_btn_y, x + 120, mini_btn_y + 32),
            fill=random.choice(self.colors['primary']),
            radius=4
        )
        draw.text((x + 70, mini_btn_y + 16), "Click", fill=self.colors['white'][0], font=self.fonts['small'], anchor="mm")

        return DrawnComponent("", "iframe", "media", x, y, width, height, 0)

    # ========== CANVAS/SVG ==========

    def draw_canvas(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw HTML5 canvas element"""
        width = 500
        height = 300

        # Canvas background
        draw.rectangle((x, y, x + width, y + height), fill=(250, 250, 250), outline=(200, 200, 200), width=2)

        # Draw some graphics (simulate canvas content)
        # Circles
        for i in range(5):
            cx = x + random.randint(50, width - 50)
            cy = y + random.randint(50, height - 50)
            radius = random.randint(20, 50)
            color = random.choice(self.colors['primary'] + self.colors['success'] + self.colors['danger'])
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color + (150,), outline=None)

        # Lines
        for i in range(3):
            start_x = x + random.randint(0, width)
            start_y = y + random.randint(0, height)
            end_x = x + random.randint(0, width)
            end_y = y + random.randint(0, height)
            draw.line([(start_x, start_y), (end_x, end_y)], fill=random.choice(self.colors['dark']), width=3)

        return DrawnComponent("", "canvas", "media", x, y, width, height, 0)

    def draw_svg_graphic(self, draw: ImageDraw, x: int, y: int) -> DrawnComponent:
        """Draw SVG graphic"""
        width = 200
        height = 200

        # SVG icon simulation - draw a complex shape
        center_x = x + width // 2
        center_y = y + height // 2

        # Star shape
        points = []
        for i in range(10):
            angle = (i * 36 - 90) * np.pi / 180
            radius = 80 if i % 2 == 0 else 40
            px = center_x + int(radius * np.cos(angle))
            py = center_y + int(radius * np.sin(angle))
            points.append((px, py))

        draw.polygon(points, fill=random.choice(self.colors['warning']), outline=random.choice(self.colors['danger']), width=3)

        return DrawnComponent("", "svg_graphic", "media", x, y, width, height, 0)

    # Continue with more components...
    # This shows the pattern - I need to implement ALL 317


def get_all_drawing_methods():
    """List all available drawing methods"""
    drawer = WebComponentDrawer()
    methods = [method for method in dir(drawer) if method.startswith('draw_') and method != 'draw_rounded_rectangle' and method != 'draw_shadow']
    return methods


if __name__ == "__main__":
    print(f"Drawing methods implemented: {len(get_all_drawing_methods())}")
    for method in get_all_drawing_methods():
        print(f"  - {method}")
