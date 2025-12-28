"""
Smart Component Generator - Intelligently generates ALL 317 component types

Strategy:
- Explicit drawing for complex/unique components (already done: 19)
- Pattern-based generation for similar components
- Category-aware styling and sizing
- All components get accurate bounding boxes

Key: YOLO needs accurate bboxes and visual distinction,
not perfect pixel-perfect HTML replication.
"""

from PIL import Image, ImageDraw, ImageFont
import random
from typing import Tuple
from pathlib import Path
from direct_image_generator import WebComponentDrawer, DrawnComponent


class SmartComponentGenerator(WebComponentDrawer):
    """Extends WebComponentDrawer with intelligent fallbacks for all 317 components"""

    def draw_component(self, component_type: str, x: int, y: int, category: str = "") -> DrawnComponent:
        """
        Main entry point - draws ANY component type

        Uses explicit method if available, otherwise generates intelligently
        """
        method_name = f"draw_{component_type}"

        # Check if explicit method exists
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            return method(x, y)

        # Generate using smart fallback
        return self._generate_smart_component(component_type, x, y, category)

    def _generate_smart_component(self, comp_type: str, x: int, y: int, category: str) -> DrawnComponent:
        """
        Intelligently generate component based on type and category

        Uses pattern matching and category-aware styling
        """
        # Create temporary canvas for this component
        temp_img = Image.new('RGB', (self.width, self.height), (255, 255, 255))
        draw = ImageDraw.Draw(temp_img, 'RGBA')

        # Determine dimensions based on component type patterns
        width, height = self._estimate_dimensions(comp_type, category)

        # Generate based on category
        if category == "navigation":
            return self._generate_navigation(draw, comp_type, x, y, width, height)
        elif category == "buttons":
            return self._generate_button(draw, comp_type, x, y, width, height)
        elif category == "forms":
            return self._generate_form_element(draw, comp_type, x, y, width, height)
        elif category == "media":
            return self._generate_media(draw, comp_type, x, y, width, height)
        elif category == "overlays":
            return self._generate_overlay(draw, comp_type, x, y, width, height)
        elif category == "notifications":
            return self._generate_notification(draw, comp_type, x, y, width, height)
        elif category == "specialized":
            return self._generate_specialized(draw, comp_type, x, y, width, height)
        elif category == "ads":
            return self._generate_ad(draw, comp_type, x, y, width, height)
        elif category == "ecommerce":
            return self._generate_ecommerce(draw, comp_type, x, y, width, height)
        elif category == "social":
            return self._generate_social(draw, comp_type, x, y, width, height)
        elif category == "typography":
            return self._generate_typography(draw, comp_type, x, y, width, height)
        elif category == "layout":
            return self._generate_layout(draw, comp_type, x, y, width, height)
        elif category == "interactive":
            return self._generate_interactive(draw, comp_type, x, y, width, height)
        else:
            return self._generate_generic(draw, comp_type, x, y, width, height, category)

    def _estimate_dimensions(self, comp_type: str, category: str) -> Tuple[int, int]:
        """Estimate component dimensions based on type"""
        # Buttons and small controls
        if 'button' in comp_type or comp_type in ['checkbox', 'radio_button', 'toggle', 'switch']:
            if 'icon' in comp_type or 'fab' in comp_type:
                return (48, 48)
            return (random.randint(120, 200), random.randint(36, 48))

        # Form inputs
        if category == "forms" or 'input' in comp_type or 'picker' in comp_type:
            return (random.randint(300, 450), random.randint(60, 80))

        # Navigation bars
        if comp_type in ['navbar', 'top_bar', 'header', 'footer']:
            return (self.width, random.randint(60, 100))

        # Sidebars
        if 'sidebar' in comp_type:
            return (random.randint(250, 320), random.randint(400, 700))

        # Modals and overlays
        if comp_type in ['modal', 'popup'] or category == "overlays":
            if 'toast' in comp_type or 'notification' in comp_type:
                return (random.randint(280, 350), random.randint(80, 120))
            return (random.randint(400, 600), random.randint(250, 400))

        # Cards
        if 'card' in comp_type:
            return (random.randint(280, 380), random.randint(320, 450))

        # Tables
        if 'table' in comp_type or 'grid' in comp_type:
            return (random.randint(600, 900), random.randint(200, 400))

        # Media players
        if 'video' in comp_type or 'player' in comp_type:
            return (640, 400)

        # Charts
        if 'chart' in comp_type or comp_type in ['graph', 'diagram']:
            return (random.randint(400, 600), random.randint(300, 450))

        # Default
        return (random.randint(200, 400), random.randint(100, 250))

    def _generate_navigation(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate navigation components"""
        bg_color = random.choice(self.colors['dark'])

        # Background
        draw.rectangle((x, y, x + width, y + height), fill=bg_color)

        # Add nav-specific elements
        if 'footer' in comp_type:
            # Footer columns
            col_width = width // 4
            for i in range(4):
                col_x = x + i * col_width + 20
                draw.text((col_x, y + 20), f"Column {i+1}", fill=self.colors['white'][0], font=self.fonts['regular'])

        else:
            # Regular navigation
            draw.text((x + 30, y + height//2), comp_type.replace('_', ' ').title(), fill=self.colors['white'][0], font=self.fonts['medium'], anchor="lm")

        return DrawnComponent("", comp_type, "navigation", x, y, width, height, 100 if 'sticky' in comp_type else 0)

    def _generate_button(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate button components"""
        # Style based on button type
        if 'primary' in comp_type or comp_type == 'submit':
            bg = random.choice(self.colors['primary'])
            text_color = self.colors['white'][0]
            outline = None
        elif 'secondary' in comp_type or 'outline' in comp_type:
            bg = self.colors['white'][0]
            text_color = random.choice(self.colors['primary'])
            outline = text_color
        elif 'ghost' in comp_type or 'tertiary' in comp_type:
            bg = (0, 0, 0, 0)  # Transparent
            text_color = random.choice(self.colors['primary'])
            outline = None
        else:
            bg = random.choice(self.colors['light'])
            text_color = self.colors['dark'][0]
            outline = None

        # Draw button
        if 'icon' in comp_type or 'fab' in comp_type:
            # Round button
            draw.ellipse((x, y, x + width, y + height), fill=bg, outline=outline, width=2)
            draw.text((x + width//2, y + height//2), "★", fill=text_color, font=self.fonts['large'], anchor="mm")
        else:
            # Rectangle button
            self.draw_rounded_rectangle(draw, (x, y, x + width, y + height), fill=bg, outline=outline, radius=6, width=2)
            draw.text((x + width//2, y + height//2), comp_type[:10], fill=text_color, font=self.fonts['regular'], anchor="mm")

        return DrawnComponent("", comp_type, "buttons", x, y, width, height, 0)

    def _generate_form_element(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate form input components"""
        # Label
        label_text = comp_type.replace('_', ' ').title().replace('Input', '')
        draw.text((x, y + 10), label_text, fill=self.colors['dark'][0], font=self.fonts['regular'])

        # Input box
        input_y = y + 35
        input_height = height - 40

        # Special handling for specific types
        if 'picker' in comp_type:
            # Date/time/color pickers
            self.draw_rounded_rectangle(draw, (x, input_y, x + width, input_y + input_height), fill=self.colors['white'][0], outline=(200, 200, 200), radius=6, width=2)

            if 'date' in comp_type:
                draw.text((x + 16, input_y + input_height//2), "📅 MM/DD/YYYY", fill=(150, 150, 150), font=self.fonts['regular'], anchor="lm")
            elif 'time' in comp_type:
                draw.text((x + 16, input_y + input_height//2), "🕐 HH:MM", fill=(150, 150, 150), font=self.fonts['regular'], anchor="lm")
            elif 'color' in comp_type:
                # Color picker with color swatch
                draw.rectangle((x + 16, input_y + 8, x + 46, input_y + input_height - 8), fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

        elif 'slider' in comp_type or 'range' in comp_type:
            # Slider
            track_y = input_y + input_height // 2
            draw.line([(x, track_y), (x + width, track_y)], fill=(220, 220, 220), width=4)
            thumb_x = x + int(width * random.random())
            draw.ellipse((thumb_x - 8, track_y - 8, thumb_x + 8, track_y + 8), fill=random.choice(self.colors['primary']))

        elif 'rating' in comp_type or 'star' in comp_type:
            # Star rating
            star_y = input_y + input_height // 2
            for i in range(5):
                star_x = x + i * 32 + 16
                filled = i < 3  # 3 stars filled
                draw.text((star_x, star_y), "★" if filled else "☆", fill=(255, 193, 7) if filled else (200, 200, 200), font=self.fonts['large'], anchor="mm")

        elif 'file' in comp_type or 'upload' in comp_type:
            # File upload
            self.draw_rounded_rectangle(draw, (x, input_y, x + width, input_y + input_height), fill=(250, 250, 250), outline=(200, 200, 200), radius=6, width=2)
            draw.text((x + width//2, input_y + input_height//2 - 12), "📁 Choose File", fill=(100, 100, 100), font=self.fonts['regular'], anchor="mm")
            draw.text((x + width//2, input_y + input_height//2 + 12), "or drag and drop", fill=(150, 150, 150), font=self.fonts['small'], anchor="mm")

        elif comp_type == 'captcha':
            # CAPTCHA
            self.draw_rounded_rectangle(draw, (x, input_y, x + width, input_y + input_height), fill=(250, 250, 250), outline=(200, 200, 200), radius=6, width=2)
            # Distorted text
            draw.text((x + 20, input_y + input_height//2), "AbC9XyZ", fill=(random.randint(0, 100), random.randint(0, 100), random.randint(0, 100)), font=self.fonts['large'], anchor="lm")
            # Checkbox
            check_x = x + width - 100
            self.draw_rounded_rectangle(draw, (check_x, input_y + 10, check_x + 24, input_y + 34), fill=self.colors['white'][0], outline=(200, 200, 200), radius=4, width=2)
            draw.text((check_x + 32, input_y + 22), "I'm not a robot", fill=self.colors['dark'][0], font=self.fonts['small'], anchor="lm")

        elif comp_type == 'otp_input':
            # OTP / PIN input (6 boxes)
            box_width = 48
            gap = 12
            for i in range(6):
                box_x = x + i * (box_width + gap)
                self.draw_rounded_rectangle(draw, (box_x, input_y, box_x + box_width, input_y + input_height), fill=self.colors['white'][0], outline=(200, 200, 200), radius=8, width=2)
                if i < 3:  # Some filled
                    draw.text((box_x + box_width//2, input_y + input_height//2), str(random.randint(0, 9)), fill=self.colors['dark'][0], font=self.fonts['large'], anchor="mm")

        else:
            # Generic input
            self.draw_rounded_rectangle(draw, (x, input_y, x + width, input_y + input_height), fill=self.colors['white'][0], outline=(220, 220, 220), radius=6, width=2)
            placeholder = f"Enter {comp_type.replace('_input', '').replace('_', ' ')}"
            draw.text((x + 16, input_y + input_height//2), placeholder, fill=(180, 180, 180), font=self.fonts['regular'], anchor="lm")

        return DrawnComponent("", comp_type, category, x, y, width, height, 0)

    def _generate_media(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate media components"""
        if 'youtube' in comp_type or 'vimeo' in comp_type or 'embed' in comp_type:
            # Video embed
            # Border
            draw.rectangle((x, y, x + width, y + height), fill=(0, 0, 0))
            # Gradient video
            for i in range(height - 50):
                progress = i / (height - 50)
                color = (int(100 * progress), int(50 * progress), int(150 + 100 * progress))
                draw.line([(x, y + i), (x + width, y + i)], fill=color)
            # Play button
            play_x, play_y = x + width//2 - 30, y + height//2 - 30
            draw.ellipse((play_x, play_y, play_x + 60, play_y + 60), fill=(255, 255, 255, 200))
            points = [(play_x + 20, play_y + 15), (play_x + 20, play_y + 45), (play_x + 45, play_y + 30)]
            draw.polygon(points, fill=(0, 0, 0))

        elif 'audio' in comp_type or 'podcast' in comp_type:
            # Audio player
            draw.rectangle((x, y, x + width, y + height), fill=(248, 248, 248), outline=(220, 220, 220), width=1)
            # Play button
            draw.ellipse((x + 20, y + height//2 - 20, x + 60, y + height//2 + 20), fill=random.choice(self.colors['primary']))
            draw.text((x + 40, y + height//2), "▶", fill=self.colors['white'][0], font=self.fonts['medium'], anchor="mm")
            # Progress
            prog_x = x + 80
            prog_width = width - 100
            draw.line([(prog_x, y + height//2), (prog_x + prog_width, y + height//2)], fill=(220, 220, 220), width=4)
            draw.line([(prog_x, y + height//2), (prog_x + int(prog_width * 0.4), y + height//2)], fill=random.choice(self.colors['primary']), width=4)

        elif 'carousel' in comp_type or 'slider' in comp_type or 'slideshow' in comp_type:
            # Carousel
            draw.rectangle((x, y, x + width, y + height), fill=(240, 240, 240), outline=(200, 200, 200), width=2)
            # Slides
            slide_width = width // 3
            for i in range(3):
                slide_x = x + i * slide_width + 10
                slide_color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
                draw.rectangle((slide_x, y + 20, slide_x + slide_width - 20, y + height - 60), fill=slide_color)
            # Nav dots
            for i in range(5):
                dot_x = x + width//2 - 40 + i * 20
                dot_color = random.choice(self.colors['primary']) if i == 2 else (200, 200, 200)
                draw.ellipse((dot_x, y + height - 30, dot_x + 8, y + height - 22), fill=dot_color)

        elif 'avatar' in comp_type or 'profile' in comp_type:
            # Avatar circle
            size = min(width, height)
            draw.ellipse((x, y, x + size, y + size), fill=random.choice(self.colors['primary']))
            draw.text((x + size//2, y + size//2), "AB", fill=self.colors['white'][0], font=self.fonts['large'], anchor="mm")

        else:
            # Generic media box
            draw.rectangle((x, y, x + width, y + height), fill=(230, 230, 230), outline=(200, 200, 200), width=2)
            draw.text((x + width//2, y + height//2), "🎬", fill=(100, 100, 100), font=self.fonts['xlarge'], anchor="mm")

        return DrawnComponent("", comp_type, "media", x, y, width, height, 0)

    def _generate_notification(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate notification/alert components"""
        # Color based on type
        if 'success' in comp_type or comp_type == 'toast':
            bg = (212, 237, 218)
            icon = "✓"
            icon_color = random.choice(self.colors['success'])
        elif 'error' in comp_type or 'danger' in comp_type:
            bg = (248, 215, 218)
            icon = "✗"
            icon_color = random.choice(self.colors['danger'])
        elif 'warning' in comp_type:
            bg = (255, 243, 205)
            icon = "⚠"
            icon_color = random.choice(self.colors['warning'])
        else:
            bg = (217, 237, 247)
            icon = "ℹ"
            icon_color = random.choice(self.colors['primary'])

        # Draw notification
        self.draw_rounded_rectangle(draw, (x, y, x + width, y + height), fill=bg, radius=8)

        # Icon
        draw.text((x + 20, y + height//2), icon, fill=icon_color, font=self.fonts['large'], anchor="mm")

        # Text
        draw.text((x + 50, y + height//2 - 8), comp_type.replace('_', ' ').title(), fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="lm")

        # Close button
        draw.text((x + width - 30, y + height//2), "×", fill=(150, 150, 150), font=self.fonts['large'], anchor="mm")

        z_idx = 1001 if comp_type == 'toast' else 0
        return DrawnComponent("", comp_type, "notifications", x, y, width, height, z_idx)

    def _generate_specialized(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate specialized components (charts, calendars, etc.)"""
        if 'chart' in comp_type:
            # Draw chart
            draw.rectangle((x, y, x + width, y + height), fill=self.colors['white'][0], outline=(200, 200, 200), width=2)

            if 'bar' in comp_type:
                # Bar chart
                bars = 6
                bar_width = width // (bars * 2)
                for i in range(bars):
                    bar_height = random.randint(50, height - 100)
                    bar_x = x + 40 + i * (width - 80) // bars
                    bar_y = y + height - 40 - bar_height
                    draw.rectangle((bar_x, bar_y, bar_x + bar_width, y + height - 40), fill=random.choice(self.colors['primary']))

            elif 'pie' in comp_type or 'donut' in comp_type:
                # Pie chart
                center_x, center_y = x + width//2, y + height//2
                radius = min(width, height) // 3
                colors = [random.choice(self.colors[c]) for c in ['primary', 'success', 'warning', 'danger']]
                for i, color in enumerate(colors):
                    start_angle = i * 90
                    draw.pieslice((center_x - radius, center_y - radius, center_x + radius, center_y + radius),
                                start=start_angle, end=start_angle + 90, fill=color, outline=(255, 255, 255), width=2)

            elif 'line' in comp_type:
                # Line chart
                points = [(x + 40 + i * (width - 80) // 10, y + height - 40 - random.randint(20, height - 100)) for i in range(10)]
                draw.line(points, fill=random.choice(self.colors['primary']), width=3, joint="curve")
                for point in points:
                    draw.ellipse((point[0] - 4, point[1] - 4, point[0] + 4, point[1] + 4), fill=random.choice(self.colors['primary']))

        elif 'calendar' in comp_type:
            # Calendar grid
            draw.rectangle((x, y, x + width, y + height), fill=self.colors['white'][0], outline=(200, 200, 200), width=2)
            # Month header
            draw.rectangle((x, y, x + width, y + 40), fill=random.choice(self.colors['primary']))
            draw.text((x + width//2, y + 20), "January 2025", fill=self.colors['white'][0], font=self.fonts['medium'], anchor="mm")
            # Day grid (7x5)
            cell_w = width // 7
            cell_h = (height - 40) // 6
            for row in range(6):
                for col in range(7):
                    cell_x = x + col * cell_w
                    cell_y = y + 40 + row * cell_h
                    day = row * 7 + col - 2
                    if 1 <= day <= 31:
                        draw.text((cell_x + cell_w//2, cell_y + cell_h//2), str(day), fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="mm")

        elif 'map' in comp_type:
            # Map component
            # Draw simple map visualization
            draw.rectangle((x, y, x + width, y + height), fill=(169, 204, 227))
            # Landmasses
            for _ in range(5):
                blob_x = x + random.randint(0, width - 100)
                blob_y = y + random.randint(0, height - 80)
                draw.ellipse((blob_x, blob_y, blob_x + random.randint(60, 150), blob_y + random.randint(40, 100)), fill=(144, 164, 174))
            # Marker
            marker_x, marker_y = x + width//2, y + height//2
            draw.ellipse((marker_x - 12, marker_y - 12, marker_x + 12, marker_y + 12), fill=(231, 76, 60))
            draw.ellipse((marker_x - 6, marker_y - 6, marker_x + 6, marker_y + 6), fill=self.colors['white'][0])

        elif 'qr' in comp_type or 'barcode' in comp_type:
            # QR code / barcode
            if 'qr' in comp_type:
                # QR code pattern
                module_size = 8
                modules = min(width, height) // module_size
                for row in range(modules):
                    for col in range(modules):
                        if random.random() < 0.5:
                            draw.rectangle((x + col * module_size, y + row * module_size,
                                          x + (col + 1) * module_size, y + (row + 1) * module_size), fill=self.colors['black'][0])
            else:
                # Barcode
                bar_width = 3
                for i in range(width // bar_width):
                    if random.random() < 0.6:
                        draw.rectangle((x + i * bar_width, y + 20, x + (i + 1) * bar_width, y + height - 30), fill=self.colors['black'][0])

        else:
            # Generic specialized component
            draw.rectangle((x, y, x + width, y + height), fill=self.colors['white'][0], outline=(200, 200, 200), width=2)
            draw.text((x + width//2, y + height//2), comp_type.replace('_', ' ').title(), fill=self.colors['dark'][0], font=self.fonts['medium'], anchor="mm")

        return DrawnComponent("", comp_type, "specialized", x, y, width, height, 0)

    # Continue implementing other categories...
    def _generate_ecommerce(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate e-commerce components"""
        # Implement ecommerce patterns...
        return self._generate_generic(draw, comp_type, x, y, width, height, "ecommerce")

    def _generate_ad(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate ad components"""
        # Bright colors for ads
        ad_bg = [(255, 107, 107), (238, 90, 111), (255, 184, 77), (255, 158, 67)]
        bg = random.choice(ad_bg)

        draw.rectangle((x, y, x + width, y + height), fill=bg, outline=None)
        draw.text((x + width//2, y + 30), "SPECIAL OFFER!", fill=self.colors['white'][0], font=self.fonts['large'], anchor="mm")
        draw.text((x + width//2, y + height//2), "50% OFF", fill=self.colors['white'][0], font=self.fonts['xlarge'], anchor="mm")
        draw.text((x + width//2, y + height - 30), "Limited Time Only", fill=self.colors['white'][0], font=self.fonts['small'], anchor="mm")

        return DrawnComponent("", comp_type, "ads", x, y, width, height, 0)

    def _generate_social(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate social components"""
        # Social elements
        return self._generate_generic(draw, comp_type, x, y, width, height, "social")

    def _generate_typography(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate typography elements"""
        # Text elements
        if 'heading' in comp_type:
            level = int(comp_type[-1]) if comp_type[-1].isdigit() else 1
            font = self.fonts['xlarge'] if level <= 2 else self.fonts['large'] if level <= 4 else self.fonts['medium']
            draw.text((x, y), f"Heading Level {level}", fill=self.colors['dark'][0], font=font)
            height = 40 if level <= 2 else 30
            width = 300
        elif 'paragraph' in comp_type:
            lines = ["This is a paragraph of text that contains", "multiple lines and demonstrates the", "paragraph component for training."]
            for i, line in enumerate(lines):
                draw.text((x, y + i * 24), line, fill=self.colors['dark'][0], font=self.fonts['regular'])
            height = 80
            width = 400
        elif 'code' in comp_type:
            draw.rectangle((x, y, x + width, y + height), fill=(40, 44, 52))
            draw.text((x + 10, y + 10), "const x = 10;", fill=(97, 218, 251), font=self.fonts['mono'])
            draw.text((x + 10, y + 30), "console.log(x);", fill=(97, 218, 251), font=self.fonts['mono'])
        else:
            draw.text((x, y), comp_type.replace('_', ' ').title(), fill=self.colors['dark'][0], font=self.fonts['regular'])
            width = 200
            height = 30

        return DrawnComponent("", comp_type, "typography", x, y, width, height, 0)

    def _generate_layout(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate layout components"""
        draw.rectangle((x, y, x + width, y + height), fill=(250, 250, 250), outline=(220, 220, 220), width=2)
        draw.text((x + 20, y + 20), comp_type.replace('_', ' ').title(), fill=self.colors['dark'][0], font=self.fonts['medium'])
        return DrawnComponent("", comp_type, "layout", x, y, width, height, 0)

    def _generate_interactive(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate interactive components"""
        draw.rectangle((x, y, x + width, y + height), fill=self.colors['white'][0], outline=random.choice(self.colors['primary']), width=3)
        draw.text((x + width//2, y + height//2), comp_type.replace('_', ' ').title(), fill=self.colors['dark'][0], font=self.fonts['medium'], anchor="mm")
        return DrawnComponent("", comp_type, "interactive", x, y, width, height, 0)

    def _generate_overlay(self, draw, comp_type, x, y, width, height) -> DrawnComponent:
        """Generate overlay components"""
        z_idx = 999 if 'modal' in comp_type or 'popup' in comp_type else 0
        draw.rectangle((x, y, x + width, y + height), fill=self.colors['white'][0], outline=(200, 200, 200), width=2)
        self.draw_rounded_rectangle(draw, (x + 20, y + 20, x + width - 20, y + height - 20), fill=(240, 240, 240), radius=8)
        draw.text((x + width//2, y + height//2), comp_type.replace('_', ' ').title(), fill=self.colors['dark'][0], font=self.fonts['medium'], anchor="mm")
        return DrawnComponent("", comp_type, "overlays", x, y, width, height, z_idx)

    def _generate_generic(self, draw, comp_type, x, y, width, height, category) -> DrawnComponent:
        """Fallback generator for any component"""
        # Draw styled box based on category
        category_colors = {
            'navigation': self.colors['dark'],
            'buttons': self.colors['primary'],
            'forms': self.colors['light'],
            'ecommerce': self.colors['success'],
            'social': self.colors['primary'],
        }

        border_color = random.choice(category_colors.get(category, self.colors['gray']))

        draw.rectangle((x, y, x + width, y + height), fill=self.colors['white'][0], outline=border_color, width=2)
        self.draw_rounded_rectangle(draw, (x + 10, y + 10, x + width - 10, y + height - 10), fill=(248, 248, 248), radius=6)

        # Label
        label = comp_type.replace('_', ' ').title()
        draw.text((x + width//2, y + height//2), label, fill=self.colors['dark'][0], font=self.fonts['regular'], anchor="mm")

        return DrawnComponent("", comp_type, category, x, y, width, height, 0)


if __name__ == "__main__":
    print("Testing SmartComponentGenerator...")

    generator = SmartComponentGenerator()

    # Test that it can generate ANY component
    test_components = ['footer', 'tertiary_button', 'date_picker', 'carousel', 'pie_chart', 'shopping_cart']

    img = Image.new('RGB', (1440, 900), (255, 255, 255))
    draw = ImageDraw.Draw(img, 'RGBA')

    y_offset = 50
    for comp_type in test_components:
        try:
            comp = generator.draw_component(comp_type, 50, y_offset, category="test")
            bbox = comp.get_bbox()
            draw.rectangle(bbox, outline=(0, 255, 0), width=2)
            print(f"✓ {comp_type}: {comp.width}x{comp.height}")
            y_offset += comp.height + 30
        except Exception as e:
            print(f"✗ {comp_type}: {e}")

    output = Path("test_visual_output") / "smart_generator_test.png"
    img.save(output)
    print(f"\n✓ Test saved: {output}")
