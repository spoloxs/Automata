"""
Detector Factory - Swappable object detection models for UI parsing

Supports multiple detection models:
- YOLO (fast, general UI)
- Pix2Struct (excellent for grids/tables/documents)
- Table Transformer (specialized for tables)
"""

import torch
import numpy as np
from PIL import Image
from typing import List, Tuple, Dict, Any


class BaseDetector:
    """Base class for all detectors"""
    
    def __init__(self, device=None):
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
    
    def detect(self, image: Image.Image, confidence: float = 0.3) -> Tuple[torch.Tensor, torch.Tensor, List[str]]:
        """
        Detect objects in image
        
        Args:
            image: PIL Image
            confidence: Detection confidence threshold
            
        Returns:
            boxes: Tensor of bounding boxes in xyxy format (pixel coords)
            scores: Tensor of confidence scores
            labels: List of label strings
        """
        raise NotImplementedError("Subclasses must implement detect()")
    
    def get_name(self) -> str:
        """Return detector name"""
        return self.__class__.__name__


class YOLODetector(BaseDetector):
    """YOLO-based detector (current default)"""
    
    def __init__(self, model_path: str, device=None):
        super().__init__(device)
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        
    def detect(self, image: Image.Image, confidence: float = 0.3) -> Tuple[torch.Tensor, torch.Tensor, List[str]]:
        """Detect using YOLO"""
        result = self.model.predict(
            source=image,
            conf=confidence,
            iou=0.7,
            verbose=False
        )
        
        boxes = result[0].boxes.xyxy  # Already in pixel space, xyxy format
        scores = result[0].boxes.conf
        labels = [str(i) for i in range(len(boxes))]
        
        return boxes, scores, labels
    
    def get_name(self) -> str:
        return "YOLO"


class YOLOGridDetector(BaseDetector):
    """YOLO Grid Detector - trained specifically for crossword grid cells"""
    
    def __init__(self, model_path: str = "runs/yolo_mega/grid_detector_mega/weights/best.pt", device=None):
        super().__init__(device)
        from ultralytics import YOLO
        
        print(f"Loading YOLO Grid Detector: {model_path}")
        self.model = YOLO(model_path)
        
    def detect(self, image: Image.Image, confidence: float = 0.3) -> Tuple[torch.Tensor, torch.Tensor, List[str]]:
        """Detect grid cells using trained YOLO model"""
        result = self.model.predict(
            source=image,
            conf=confidence,
            iou=0.7,
            verbose=False
        )
        
        boxes = result[0].boxes.xyxy  # Already in pixel space, xyxy format
        scores = result[0].boxes.conf
        
        # Map class IDs to cell types (white_cell, black_cell)
        if hasattr(self.model, 'names'):
            labels = [self.model.names[int(cls)] for cls in result[0].boxes.cls]
        else:
            labels = [str(int(cls)) for cls in result[0].boxes.cls]
        
        return boxes, scores, labels
    
    def get_name(self) -> str:
        return "YOLO Grid Detector"


class Pix2StructDetector(BaseDetector):
    """Pix2Struct detector - excellent for grids, tables, structured UIs"""
    
    def __init__(self, model_name: str = "google/pix2struct-base", device=None):
        super().__init__(device)
        from transformers import Pix2StructForConditionalGeneration, Pix2StructProcessor
        
        print(f"Loading Pix2Struct model: {model_name}")
        self.processor = Pix2StructProcessor.from_pretrained(model_name)
        self.model = Pix2StructForConditionalGeneration.from_pretrained(model_name)
        self.model = self.model.to(self.device)
        self.model.eval()
        
    def detect(self, image: Image.Image, confidence: float = 0.3) -> Tuple[torch.Tensor, torch.Tensor, List[str]]:
        """
        Detect using Pix2Struct
        
        Pix2Struct is designed for document/UI understanding but doesn't directly output boxes.
        We'll use it to identify grid structures and parse them.
        """
        # For now, use a simple grid detection approach
        # TODO: Implement proper Pix2Struct integration for element detection
        
        # Fallback to basic grid detection
        w, h = image.size
        
        # Detect if image contains a grid pattern
        # For demonstration, we'll create a simple grid detector
        boxes_list = []
        scores_list = []
        labels_list = []
        
        # This is a placeholder - real implementation would use Pix2Struct's
        # understanding capabilities to identify UI elements
        
        # For now, return empty (will be enhanced)
        boxes = torch.tensor(boxes_list, dtype=torch.float32)
        scores = torch.tensor(scores_list, dtype=torch.float32)
        
        return boxes, scores, labels_list
    
    def get_name(self) -> str:
        return "Pix2Struct"


class DETRDetector(BaseDetector):
    """DETR (DEtection TRansformer) - Facebook's transformer-based detector"""
    
    def __init__(self, model_name: str = "facebook/detr-resnet-50", device=None):
        super().__init__(device)
        from transformers import DetrImageProcessor, DetrForObjectDetection
        
        print(f"Loading DETR model: {model_name}")
        self.processor = DetrImageProcessor.from_pretrained(model_name)
        self.model = DetrForObjectDetection.from_pretrained(model_name)
        self.model = self.model.to(self.device)
        self.model.eval()
        
    def detect(self, image: Image.Image, confidence: float = 0.5) -> Tuple[torch.Tensor, torch.Tensor, List[str]]:
        """Detect using DETR"""
        
        # Prepare inputs
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Run detection
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Post-process results
        target_sizes = torch.tensor([image.size[::-1]])  # (height, width)
        results = self.processor.post_process_object_detection(
            outputs, 
            target_sizes=target_sizes, 
            threshold=confidence
        )[0]
        
        boxes = results["boxes"]  # Already in xyxy pixel format
        scores = results["scores"]
        
        # Map labels to readable names
        labels = []
        for label_id in results["labels"]:
            label_id = label_id.item()
            label_name = self.model.config.id2label.get(label_id, f"object_{label_id}")
            labels.append(label_name)
        
        return boxes, scores, labels
    
    def get_name(self) -> str:
        return "DETR"


class RTDETRDetector(BaseDetector):
    """RT-DETR - Real-Time Detection Transformer (RECOMMENDED)"""
    
    def __init__(self, model_path: str = "rtdetr-l.pt", device=None):
        super().__init__(device)
        from ultralytics import RTDETR
        
        print(f"Loading RT-DETR model: {model_path}")
        self.model = RTDETR(model_path)
        
    def detect(self, image: Image.Image, confidence: float = 0.3) -> Tuple[torch.Tensor, torch.Tensor, List[str]]:
        """Detect using RT-DETR"""
        result = self.model.predict(
            source=image,
            conf=confidence,
            iou=0.7,
            verbose=False
        )
        
        boxes = result[0].boxes.xyxy  # Already in pixel space, xyxy format
        scores = result[0].boxes.conf
        
        # Map class IDs to names if available
        if hasattr(self.model, 'names'):
            labels = [self.model.names[int(cls)] for cls in result[0].boxes.cls]
        else:
            labels = [str(int(cls)) for cls in result[0].boxes.cls]
        
        return boxes, scores, labels
    
    def get_name(self) -> str:
        return "RT-DETR"


class OWLViTDetector(BaseDetector):
    """OWL-ViT - Open-vocabulary object detector from Google"""
    
    def __init__(self, model_name: str = "google/owlvit-base-patch32", device=None):
        super().__init__(device)
        from transformers import OwlViTProcessor, OwlViTForObjectDetection
        
        print(f"Loading OWL-ViT model: {model_name}")
        self.processor = OwlViTProcessor.from_pretrained(model_name)
        self.model = OwlViTForObjectDetection.from_pretrained(model_name)
        self.model = self.model.to(self.device)
        self.model.eval()
        
        # Default UI-relevant text queries
        self.text_queries = [
            "button", "icon", "text field", "checkbox", "menu", 
            "link", "image", "dropdown", "tab", "widget"
        ]
        
    def detect(self, image: Image.Image, confidence: float = 0.1) -> Tuple[torch.Tensor, torch.Tensor, List[str]]:
        """Detect using OWL-ViT with text queries"""
        
        # Prepare inputs with text queries
        inputs = self.processor(
            text=self.text_queries, 
            images=image, 
            return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Run detection
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Post-process results
        target_sizes = torch.tensor([image.size[::-1]])
        results = self.processor.post_process_object_detection(
            outputs, 
            target_sizes=target_sizes, 
            threshold=confidence
        )[0]
        
        boxes = results["boxes"]
        scores = results["scores"]
        
        # Map to query labels
        labels = [self.text_queries[label_id.item()] for label_id in results["labels"]]
        
        return boxes, scores, labels
    
    def get_name(self) -> str:
        return "OWL-ViT"


class TableTransformerDetector(BaseDetector):
    """Table Transformer - specialized for grid/table cell detection"""
    
    def __init__(self, model_name: str = "microsoft/table-transformer-structure-recognition", device=None):
        super().__init__(device)
        from transformers import AutoImageProcessor, TableTransformerForObjectDetection
        
        print(f"Loading Table Transformer: {model_name}")
        self.processor = AutoImageProcessor.from_pretrained(model_name)
        self.model = TableTransformerForObjectDetection.from_pretrained(model_name)
        self.model = self.model.to(self.device)
        self.model.eval()
        
    def detect(self, image: Image.Image, confidence: float = 0.5) -> Tuple[torch.Tensor, torch.Tensor, List[str]]:
        """Detect table cells using Table Transformer"""
        
        # Prepare inputs
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Run detection
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Post-process results
        target_sizes = torch.tensor([image.size[::-1]])  # (height, width)
        results = self.processor.post_process_object_detection(
            outputs, 
            target_sizes=target_sizes, 
            threshold=confidence
        )[0]
        
        boxes = results["boxes"]  # Already in xyxy pixel format
        scores = results["scores"]
        
        # Map labels to readable names
        labels = []
        for label_id in results["labels"]:
            label_id = label_id.item()
            label_name = self.model.config.id2label.get(label_id, f"label_{label_id}")
            labels.append(label_name)
        
        return boxes, scores, labels
    
    def get_name(self) -> str:
        return "Table Transformer"


def get_detector(detector_type: str = "yolo", **kwargs) -> BaseDetector:
    """
    Factory function to create detector instance
    
    Args:
        detector_type: One of "yolo", "yolo_grid", "rtdetr", "detr", "owlvit", "table_transformer", "pix2struct"
        **kwargs: Detector-specific parameters
        
    Returns:
        BaseDetector instance
    """
    detectors = {
        "yolo": YOLODetector,
        "yolo_grid": YOLOGridDetector,
        "rtdetr": RTDETRDetector,
        "detr": DETRDetector,
        "owlvit": OWLViTDetector,
        "table_transformer": TableTransformerDetector,
        "pix2struct": Pix2StructDetector,
    }
    
    detector_type = detector_type.lower()
    
    if detector_type not in detectors:
        available = ", ".join(detectors.keys())
        raise ValueError(f"Unknown detector type: {detector_type}. Available: {available}")
    
    return detectors[detector_type](**kwargs)


def list_available_detectors() -> List[str]:
    """List all available detector types"""
    return ["yolo", "yolo_grid", "rtdetr", "detr", "owlvit", "table_transformer", "pix2struct"]
