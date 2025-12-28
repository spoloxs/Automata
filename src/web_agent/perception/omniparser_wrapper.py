"""
Clean wrapper for OmniParser using proper importlib.
Works with fixed Qwen2-VL implementation.
"""

from web_agent.util.logger import log_info, log_warn, log_error, log_debug, log_success

import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional

import torch
from PIL import Image

from web_agent.config.paths import OMNIPARSER_ROOT, PROJECT_ROOT
from web_agent.config.settings import (
    BOX_THRESHOLD,
    ICON_CAPTION_MODEL,
    ICON_DETECT_MODEL,
    IOU_THRESHOLD,
    OMNIPARSER_BATCH_SIZE,
    OMNIPARSER_IMGSZ,
    USE_PADDLE_OCR,
)


def _load_omniparser_utils():
    """
    Load OmniParser utils module using importlib.util.

    Returns:
        Module object with OmniParser utilities

    Raises:
        ImportError: If OmniParser utils cannot be loaded
    """
    if not OMNIPARSER_ROOT or not OMNIPARSER_ROOT.exists():
        log_error(
            f"OmniParser directory not found at: {OMNIPARSER_ROOT}\nClone OmniParser repository to project root."
        )
        raise ImportError(
            f"OmniParser directory not found at: {OMNIPARSER_ROOT}\n"
            f"Clone OmniParser repository to project root."
        )

    utils_path = OMNIPARSER_ROOT / "util" / "utils.py"

    if not utils_path.exists():
        log_error(
            f"OmniParser utils.py not found at: {utils_path}\nEnsure OmniParser/util/utils.py exists."
        )
        raise ImportError(
            f"OmniParser utils.py not found at: {utils_path}\n"
            f"Ensure OmniParser/util/utils.py exists."
        )

    # Add OmniParser root to sys.path so internal imports work
    if str(OMNIPARSER_ROOT) not in sys.path:
        log_debug(f"Adding OMNIPARSER_ROOT to sys.path: {OMNIPARSER_ROOT}")
        sys.path.append(str(OMNIPARSER_ROOT))

    # Load module from file path using importlib
    spec = importlib.util.spec_from_file_location("omniparser_utils", utils_path)

    if spec is None or spec.loader is None:
        log_error(f"Failed to create module spec from {utils_path}")
        raise ImportError(f"Failed to create module spec from {utils_path}")

    module = importlib.util.module_from_spec(spec)
    log_debug(f"Loading OmniParser utils module from {utils_path}")
    spec.loader.exec_module(module)

    return module


# Load OmniParser utilities at module level
try:
    log_info("Loading OmniParser utilities...")
    _omniparser_utils = _load_omniparser_utils()
    check_ocr_box = _omniparser_utils.check_ocr_box
    get_yolo_model = _omniparser_utils.get_yolo_model
    get_caption_model_processor = _omniparser_utils.get_caption_model_processor
    get_som_labeled_img = _omniparser_utils.get_som_labeled_img
    OMNIPARSER_AVAILABLE = True
    log_success("OmniParser utilities loaded successfully.")
except ImportError as e:
    log_warn(f"⚠️  OmniParser not available: {e}")
    OMNIPARSER_AVAILABLE = False
    check_ocr_box = None
    get_yolo_model = None
    get_caption_model_processor = None
    get_som_labeled_img = None


class OmniParserWrapper:
    """
    Wrapper for OmniParser vision model.
    Handles icon detection and OCR for screen parsing with Qwen2-VL.
    """

    def __init__(self):
        """Initialize OmniParser models"""
        if not OMNIPARSER_AVAILABLE:
            log_error(
                "OmniParser utilities not available.\nEnsure OmniParser directory exists at project root with util/utils.py"
            )
            raise ImportError(
                "OmniParser utilities not available.\n"
                "Ensure OmniParser directory exists at project root with util/utils.py"
            )

        if not ICON_DETECT_MODEL or not Path(ICON_DETECT_MODEL).exists():
            log_error(
                f"Icon detection model not found: {ICON_DETECT_MODEL}\nDownload model weights from OmniParser repository:\n  weights/icon_detect/model.pt"
            )
            raise FileNotFoundError(
                f"Icon detection model not found: {ICON_DETECT_MODEL}\n"
                f"Download model weights from OmniParser repository:\n"
                f"  weights/icon_detect/model.pt"
            )

        if not ICON_CAPTION_MODEL or not Path(ICON_CAPTION_MODEL).exists():
            log_error(
                f"Icon caption model not found: {ICON_CAPTION_MODEL}\nDownload model weights from OmniParser repository:\n  weights/icon_caption_qwen/"
            )
            raise FileNotFoundError(
                f"Icon caption model not found: {ICON_CAPTION_MODEL}\n"
                f"Download model weights from OmniParser repository:\n"
                f"  weights/icon_caption_qwen/"
            )

        log_info("🔧 Loading OmniParser models...")

        # Determine device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        log_info(f"Using device: {self.device}")

        # Load YOLO icon detection model
        log_info(f"Loading YOLO icon detection model from: {ICON_DETECT_MODEL}")
        self.som_model = get_yolo_model(model_path=str(ICON_DETECT_MODEL))

        # Load Qwen2-VL caption model (direct from Hugging Face repo)
        log_info(
            "Loading Qwen2-VL caption model from Hugging Face repo: Qwen/Qwen2-VL-2B-Instruct"
        )
        self.caption_model_processor = get_caption_model_processor(
            "qwen2vl", "Qwen/Qwen2-VL-2B-Instruct"
        )

        log_success(f"✅ OmniParser loaded (device: {self.device})")

    def parse_screen(
        self,
        image: Image.Image,
        box_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        imgsz: Optional[int] = None,
        output_coord_in_ratio: bool = True,
    ) -> tuple:
        """
        Parse screenshot using OmniParser.

        Args:
            image: PIL Image to parse
            box_threshold: Detection confidence threshold (default from config)
            iou_threshold: IoU threshold for NMS (default from config)
            imgsz: Image size for model input (default from config)
            output_coord_in_ratio: If True, return normalized coords (0-1)

        Returns:
            Tuple of (labeled_image, label_coordinates, parsed_content_list)
        """
        # Use defaults from config if not provided
        box_threshold = box_threshold or BOX_THRESHOLD
        iou_threshold = iou_threshold or IOU_THRESHOLD
        imgsz = imgsz or OMNIPARSER_IMGSZ

        # Run OCR detection using EasyOCR (more accurate for form fields)
        log_info("Running OCR detection on input image using EasyOCR...")
        ocr_bbox_rslt, is_goal_filtered = check_ocr_box(
            image,
            display_img=False,
            output_bb_format="xyxy",
            goal_filtering=None,
            easyocr_args=None,  # Use default EasyOCR settings
            use_paddleocr=False,  # Don't use PaddleOCR
            use_qwen_ocr=False,  # Use EasyOCR instead of Qwen2-VL
            qwen_model_processor=None,  # Not needed for EasyOCR
        )

        text, ocr_bbox = ocr_bbox_rslt

        # Calculate overlay ratio for drawing
        box_overlay_ratio = max(image.size) / 3200

        draw_bbox_config = {
            "text_scale": 0.8 * box_overlay_ratio,
            "text_thickness": max(int(2 * box_overlay_ratio), 1),
            "text_padding": max(int(3 * box_overlay_ratio), 1),
            "thickness": max(int(3 * box_overlay_ratio), 1),
        }

        # Get SOM labeled image with coordinates
        # CRITICAL: Match gradio_demo.py EXACTLY - no extra parameters!
        log_info(
            f"--- [OmniParserWrapper] Calling get_som_labeled_img with image size: {image.size} ---"
        )
        dino_labeled_img, label_coordinates, parsed_content_list = get_som_labeled_img(
            image,
            self.som_model,
            BOX_TRESHOLD=box_threshold,
            output_coord_in_ratio=output_coord_in_ratio,
            ocr_bbox=ocr_bbox,
            draw_bbox_config=draw_bbox_config,
            caption_model_processor=self.caption_model_processor,
            ocr_text=text,
            # REMOVED: use_local_semantics=True (not in gradio demo!)
            # REMOVED: batch_size=OMNIPARSER_BATCH_SIZE (not in gradio demo!)
            iou_threshold=iou_threshold,
            imgsz=imgsz,
        )

        log_success("Screen parsed and elements extracted successfully.")
        return dino_labeled_img, label_coordinates, parsed_content_list

    def parse(self, screenshot: Image.Image) -> Dict:
        """
        Simplified parse method that returns a dictionary.

        Args:
            screenshot: PIL Image to parse

        Returns:
            Dict with 'label_coordinates', 'parsed_content_list', and 'labeled_image'
        """
        labeled_img, coordinates, content_list = self.parse_screen(screenshot)

        return {
            "label_coordinates": coordinates,
            "parsed_content_list": content_list,
            "labeled_image": labeled_img,
        }

    def parse_screen_simple(
        self,
        image: Image.Image,
        box_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        imgsz: Optional[int] = None,
    ) -> List[Dict]:
        """
        Simplified parsing that returns only parsed elements as list of dicts.
        OPTIMIZED: Does NOT create base64 annotated image to save 2GB+ RAM.

        Args:
            image: PIL Image object
            box_threshold: Detection confidence threshold (default from config)
            iou_threshold: IoU threshold for NMS (default from config)
            imgsz: Image size for model input (default from config)

        Returns:
            List of element dicts with structure:
            {
                'id': int,
                'type': 'text' | 'icon',
                'bbox': [x1, y1, x2, y2],  # normalized 0-1
                'center': [cx, cy],         # normalized 0-1
                'content': str,
                'interactivity': bool,
                'source': str
            }
        """
        # Use defaults from config if not provided
        box_threshold = box_threshold or BOX_THRESHOLD
        iou_threshold = iou_threshold or IOU_THRESHOLD
        imgsz = imgsz or OMNIPARSER_IMGSZ
        
        # CRITICAL FIX: Don't call parse_screen() which creates huge base64 image
        # Instead, call get_som_labeled_img directly and discard image immediately
        
        from web_agent.util.memory_monitor import get_memory_monitor
        mem_monitor = get_memory_monitor()
        
        # Run OCR detection using EasyOCR (more accurate for form fields)
        mem_monitor.log_ram("OmniParser: before OCR")
        log_info("Running OCR detection on input image using EasyOCR...")
        
        # Use EasyOCR for text detection (better for form fields)
        ocr_bbox_rslt, _ = check_ocr_box(
            image,
            display_img=False,
            output_bb_format="xyxy",
            goal_filtering=None,
            easyocr_args=None,  # Use default EasyOCR settings
            use_paddleocr=False,  # Don't use PaddleOCR
            use_qwen_ocr=False,  # Use EasyOCR instead of Qwen2-VL
            qwen_model_processor=None,  # Not needed for EasyOCR
        )
        text, ocr_bbox = ocr_bbox_rslt
        mem_monitor.log_ram("OmniParser: after OCR")

        # Get parsed content WITHOUT creating annotated image
        # CRITICAL: Match gradio_demo.py EXACTLY - no extra parameters!
        log_info(f"--- [OmniParserWrapper] Calling get_som_labeled_img with image size: {image.size} ---")
        
        # Call get_som_labeled_img but immediately discard the base64 image
        dino_labeled_img, _, parsed_content_list = get_som_labeled_img(
            image,
            self.som_model,
            BOX_TRESHOLD=box_threshold,
            output_coord_in_ratio=True,
            ocr_bbox=ocr_bbox,
            draw_bbox_config=None,  # No drawing = smaller output
            caption_model_processor=self.caption_model_processor,
            ocr_text=text,
            # REMOVED: use_local_semantics=True (not in gradio demo!)
            # REMOVED: batch_size=OMNIPARSER_BATCH_SIZE (not in gradio demo!)
            iou_threshold=iou_threshold,
            imgsz=imgsz,
        )
        
        # CRITICAL: Immediately delete the base64 image
        del dino_labeled_img
        mem_monitor.log_ram("OmniParser: after get_som_labeled_img")
        
        log_success("Screen parsed and elements extracted successfully.")

        # Build element list from parsed_content_list
        # CRITICAL: Extract data WITHOUT keeping references
        elements = []
        for idx, item in enumerate(parsed_content_list):
            bbox = item.get("bbox")
            if not bbox:
                continue

            x1, y1, x2, y2 = bbox
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            content = item.get("content", "")

            # Use type from OmniParser if available
            element_type = item.get("type", "icon")
            if not element_type:
                element_type = "icon" if (not content or len(content) < 3) else "text"

            elements.append(
                {
                    "id": idx,
                    "type": element_type,
                    "bbox": [x1, y1, x2, y2],
                    "center": [cx, cy],
                    "content": content,
                    "interactivity": item.get("interactivity", True),
                    "source": item.get("source", "omniparser"),
                }
            )
        
        # Delete loop variables to break references
        try:
            del idx, item, bbox, x1, y1, x2, y2, cx, cy, content, element_type
        except UnboundLocalError:
            pass
        
        # Free parsed_content_list after extracting elements
        del parsed_content_list
        
        # Force aggressive garbage collection
        import gc
        gc.collect()
        gc.collect()  # Call twice for cyclic references
        
        mem_monitor.log_ram("OmniParser: after cleanup")

        return elements

    def get_element_by_id(
        self, elements: List[Dict], element_id: int
    ) -> Optional[Dict]:
        """
        Get specific element by ID.

        Args:
            elements: List of parsed elements
            element_id: Element ID to retrieve

        Returns:
            Element dict or None if not found
        """
        for elem in elements:
            if elem.get("id") == element_id:
                return elem
        return None

    def filter_elements(
        self,
        elements: List[Dict],
        element_type: Optional[str] = None,
        interactive_only: bool = False,
        min_area: Optional[float] = None,
    ) -> List[Dict]:
        """
        Filter elements by criteria.

        Args:
            elements: List of parsed elements
            element_type: Filter by 'text' or 'icon' (None = all)
            interactive_only: Only return interactive elements
            min_area: Minimum bbox area (in normalized coords)

        Returns:
            Filtered list of elements
        """
        filtered = elements

        if element_type:
            filtered = [e for e in filtered if e.get("type") == element_type]

        if interactive_only:
            filtered = [e for e in filtered if e.get("interactivity", False)]

        if min_area is not None:
            filtered = [
                e
                for e in filtered
                if (e["bbox"][2] - e["bbox"][0]) * (e["bbox"][3] - e["bbox"][1])
                >= min_area
            ]

        return filtered

    def find_element_at_point(
        self, elements: List[Dict], x: float, y: float
    ) -> Optional[Dict]:
        """
        Find element at specific coordinates.

        Args:
            elements: List of parsed elements
            x: X coordinate (normalized 0-1)
            y: Y coordinate (normalized 0-1)

        Returns:
            Element at point or None
        """
        for elem in elements:
            bbox = elem["bbox"]
            if bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                return elem
        return None


# Singleton instance
_omniparser_instance: Optional[OmniParserWrapper] = None


def get_omniparser() -> OmniParserWrapper:
    """
    Get singleton OmniParser instance (lazy loading).

    Returns:
        OmniParserWrapper instance

    Raises:
        ImportError: If OmniParser not available
        FileNotFoundError: If model weights not found
    """
    global _omniparser_instance

    if _omniparser_instance is None:
        _omniparser_instance = OmniParserWrapper()

    return _omniparser_instance


def reset_omniparser():
    """
    Reset singleton instance and free ALL OmniParser memory.
    CRITICAL: Also clears module-level OCR readers (1GB+ RAM leak!)
    """
    global _omniparser_instance
    
    if _omniparser_instance is not None:
        try:
            # Delete Qwen2-VL model (on GPU)
            if hasattr(_omniparser_instance, 'caption_model_processor'):
                try:
                    del _omniparser_instance.caption_model_processor
                    log_debug("   🧹 Qwen2-VL model deleted from VRAM")
                except Exception as e:
                    log_warn(f"   ⚠️ Caption model cleanup error: {e}")
            
            # Delete YOLO model
            if hasattr(_omniparser_instance, 'som_model'):
                try:
                    del _omniparser_instance.som_model
                    log_debug("   🧹 YOLO model deleted")
                except Exception as e:
                    log_warn(f"   ⚠️ YOLO model cleanup error: {e}")
            
            # Clear CUDA cache to free VRAM
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                log_debug("   🧹 CUDA cache cleared")
            
            # CRITICAL: Delete module-level OCR readers (THE BIG LEAK!)
            # These are ~1GB and stay in memory forever
            try:
                import sys
                if 'omniparser_utils' in sys.modules:
                    utils_module = sys.modules['omniparser_utils']
                    if hasattr(utils_module, 'reader'):
                        del utils_module.reader
                        log_debug("   🧹 EasyOCR reader deleted (freed ~500 MB)")
                    if hasattr(utils_module, 'paddle_ocr'):
                        del utils_module.paddle_ocr
                        log_debug("   🧹 PaddleOCR reader deleted (freed ~500 MB)")
            except Exception as e:
                log_warn(f"   ⚠️ OCR cleanup error: {e}")
            
            # Garbage collection for any RAM references
            import gc
            gc.collect()
            gc.collect()
            
            log_debug("   🧹 OmniParser cleanup complete")
        except Exception as e:
            log_warn(f"   ⚠️ OmniParser cleanup error: {e}")
    
    _omniparser_instance = None
