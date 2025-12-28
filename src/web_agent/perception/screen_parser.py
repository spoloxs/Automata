from web_agent.perception.omniparser_wrapper import get_omniparser
from web_agent.util.logger import log_debug, log_info, log_warn, log_error, log_success

"""
High-level screen parsing interface.
Converts raw OmniParser output into clean Element objects.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
import gc

from PIL import Image
import torch


@dataclass
class Element:
    """Represents a parsed screen element"""

    id: int
    type: str  # 'text' or 'icon'
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2) normalized
    center: Tuple[float, float]  # (x, y) normalized
    content: str
    interactivity: bool
    source: str  # 'box_ocr_content_ocr', 'box_yolo_content_yolo', etc.
    dom_tag: Optional[str] = None  # HTML tag name (e.g., 'button', 'input', 'div')
    dom_role: Optional[str] = None  # ARIA role (e.g., 'button', 'textbox')
    dom_id: Optional[str] = None  # HTML id attribute
    dom_class: Optional[str] = None  # HTML class attribute
    dom_text: Optional[str] = None  # Inner text from DOM
    dom_placeholder: Optional[str] = None  # Placeholder for inputs

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization"""
        result = {
            "id": self.id,
            "type": self.type,
            "bbox": self.bbox,
            "center": self.center,
            "content": self.content,
            "interactivity": self.interactivity,
            "source": self.source,
        }
        
        # Add DOM info if available
        if self.dom_tag:
            result["dom"] = {
                "tag": self.dom_tag,
                "role": self.dom_role,
                "id": self.dom_id,
                "class": self.dom_class,
                "text": self.dom_text,
                "placeholder": self.dom_placeholder,
            }
        
        return result

    def get_center_pixels(self, width: int, height: int) -> Tuple[int, int]:
        """Get center coordinates in pixel space"""
        return (int(self.center[0] * width), int(self.center[1] * height))


async def enrich_elements_with_dom(elements: List[Element], browser_controller, viewport_size: Tuple[int, int]) -> List[Element]:
    """
    Enrich elements with DOM data by querying at their center coordinates.
    Optimized to use batch querying.
    
    Args:
        elements: List of Element objects to enrich
        browser_controller: BrowserController instance
        viewport_size: (width, height) tuple in pixels
    
    Returns:
        Same list of elements, enriched with DOM data
    """
    log_debug(f"   🔍 Enriching {len(elements)} elements with DOM data (batch)...")
    
    if not elements:
        return elements

    # Prepare coordinates for batch query
    coordinates = []
    
    for elem in elements:
        # Get pixel coordinates
        x_px = int(elem.center[0] * viewport_size[0])
        y_px = int(elem.center[1] * viewport_size[1])
        coordinates.append((x_px, y_px))
        
    try:
        # Check if browser controller supports batch query
        if hasattr(browser_controller, 'query_dom_batch'):
            dom_results = await browser_controller.query_dom_batch(coordinates)
        else:
            # Fallback to sequential query
            dom_results = []
            for x, y in coordinates:
                dom_results.append(await browser_controller.query_dom_at_position(x, y))
        
        enriched_count = 0
        for i, dom_info in enumerate(dom_results):
            if dom_info:
                elem = elements[i]
                
                # Enrich element with DOM data
                elem.dom_tag = dom_info.get('tag', '')
                elem.dom_role = dom_info.get('role', '')
                elem.dom_id = dom_info.get('id', '')
                elem.dom_class = dom_info.get('class', '')
                elem.dom_text = dom_info.get('text', '')[:200]
                elem.dom_placeholder = dom_info.get('placeholder', '')
                enriched_count += 1
                
        log_success(f"   ✅ Enriched {enriched_count}/{len(elements)} elements with DOM data")
        
    except Exception as e:
        log_warn(f"   ⚠️ Batch DOM enrichment failed: {e}")
        
    return elements


class ScreenParser:
    """High-level interface for screen parsing"""

    def __init__(self, use_cache: bool = True, box_threshold: Optional[float] = None, iou_threshold: Optional[float] = None):
        log_debug("ScreenParser.__init__ called")
        self.omniparser = get_omniparser()
        self.use_cache = use_cache
        self.box_threshold = box_threshold  # Custom detection threshold (None = use default)
        self.iou_threshold = iou_threshold  # Custom IoU threshold (None = use default)
        
        # Initialize cache if enabled
        if self.use_cache:
            from web_agent.storage.screen_cache import get_screen_cache
            self.cache = get_screen_cache()
        else:
            self.cache = None
        
        # DIAGNOSTIC: Log instance ID to verify sharing
        log_info(f"📍 ScreenParser instance created: id={id(self)}, omniparser_id={id(self.omniparser)}, cache={'enabled' if self.use_cache else 'disabled'}")
        if box_threshold is not None or iou_threshold is not None:
            log_info(f"   🎯 Custom thresholds: box={box_threshold}, iou={iou_threshold}")

    def parse(self, screenshot: Image.Image) -> List[Element]:
        log_debug("ScreenParser.parse called")
        # DIAGNOSTIC: Log instance ID on every parse to verify same instance is used
        log_debug(f"   📍 Using ScreenParser id={id(self)}, omniparser_id={id(self.omniparser)}")
        """
        Parse screenshot into list of Element objects.

        Args:
            screenshot: PIL Image

        Returns:
            List of Element objects
        """
        # Try cache first
        if self.cache:
            cached_elements = self.cache.get_screen_parser_result(screenshot)
            if cached_elements is not None:
                return cached_elements
        
        # Cache miss - run OmniParser with custom thresholds if provided
        parsed_elements = self.omniparser.parse_screen_simple(
            screenshot,
            box_threshold=self.box_threshold,
            iou_threshold=self.iou_threshold
        )

        elements = []
        for idx, elem in enumerate(parsed_elements):
            bbox = elem["bbox"]
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2

            element = Element(
                id=idx,
                type=elem["type"],
                bbox=tuple(bbox),
                center=(center_x, center_y),
                content=elem.get("content", ""),
                interactivity=elem.get("interactivity", False),
                source=elem.get("source", "unknown"),
            )
            elements.append(element)
        
        # CRITICAL: Free OmniParser output immediately after extraction
        del parsed_elements
        gc.collect()
        
        # Clear CUDA cache if using GPU
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        log_debug(f"   🧹 Freed OmniParser output, {len(elements)} elements extracted")

        # Store in cache
        if self.cache:
            self.cache.store_screen_parser_result(screenshot, elements)

        return elements

    def parse_with_annotation(
        self, screenshot: Image.Image
    ) -> Tuple[str, List[Element]]:
        """
        Parse and return annotated image + elements.

        Args:
            screenshot: PIL Image

        Returns:
            Tuple of (base64_annotated_image, elements)
        """
        encoded_img, _, parsed_elements = self.omniparser.parse_screen(screenshot)

        elements = []
        for idx, elem in enumerate(parsed_elements):
            bbox = elem["bbox"]
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2

            element = Element(
                id=idx,
                type=elem["type"],
                bbox=tuple(bbox),
                center=(center_x, center_y),
                content=elem.get("content", ""),
                interactivity=elem.get("interactivity", False),
                source=elem.get("source", "unknown"),
            )
            elements.append(element)
        
        # CRITICAL: Free OmniParser output immediately after extraction
        del parsed_elements
        gc.collect()
        
        # Clear CUDA cache if using GPU
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        log_debug(f"   🧹 Freed OmniParser output (with annotation), {len(elements)} elements extracted")

        return encoded_img, elements
