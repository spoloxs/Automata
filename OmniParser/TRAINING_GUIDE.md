# 🎯 Training Guide: Custom UI/Grid Detection Models

## 📊 Current Performance Summary

Based on testing on your crossword screenshot (816x721):

| Model | Detections | Grid Detection | Notes |
|-------|-----------|----------------|-------|
| **YOLO** | 19 | ❌ Poor | General UI only |
| **DETR** | ~0-5 | ❌ Poor | COCO-trained, no grids |
| **OWL-ViT** | Variable | ⚠️ Limited | Text-based queries |
| **Table Transformer** | 50 ✅ | ✅ Good | Best so far! |

**Key Finding:** Table Transformer is currently the BEST with 50 detections including rows, cells, and columns.

---

## 🔬 Better Model Options (Research-Backed)

### Option 1: **YOLOv8 Fine-tuned on UI Data** ⭐ RECOMMENDED
**Why**: Fast, accurate, easy to train

**Pretrained Models to Try:**
```python
# 1. UI-focused YOLO
from ultralytics import YOLO

# Try these pretrained models:
model = YOLO("yolov8n.pt")  # Nano - fastest
model = YOLO("yolov8s.pt")  # Small - balanced
model = YOLO("yolov8m.pt")  # Medium - accurate
```

**Training Data Sources:**
1. **RICO Dataset** (UI components)
   - 66k+ mobile UI screens
   - Labeled bounding boxes
   - Download: http://interactionmining.org/rico

2. **WebUI Dataset**
   - 400k+ web UI screenshots
   - Element bounding boxes
   - GitHub: microsoft/webui-dataset

3. **Your Crossword Data** (Custom)
   - Annotate 50-100 crossword puzzles
   - Label: `cell`, `row`, `column`, `black_square`
   - Tool: LabelImg or Roboflow

**Training Script:**
```python
from ultralytics import YOLO

# Load pretrained YOLO
model = YOLO("yolov8n.pt")

# Train on custom data
results = model.train(
    data="crossword_grid.yaml",  # Your dataset config
    epochs=50,
    imgsz=640,
    batch=16,
    name="yolo_crossword"
)
```

---

### Option 2: **RT-DETR** (Real-Time DETR) ⚡
**Why**: Faster than DETR, transformer benefits

```python
from ultralytics import RTDETR

model = RTDETR("rtdetr-l.pt")
model.train(data="ui_data.yaml", epochs=100)
```

**Advantages:**
- 3x faster than regular DETR
- Better small object detection
- End-to-end trainable

---

### Option 3: **Segment Anything (SAM) + Classification**
**Why**: Universal segmentation, then classify

```python
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator

sam = sam_model_registry["vit_h"](checkpoint="sam_vit_h_4b8939.pth")
mask_generator = SamAutomaticMaskGenerator(sam)

# Generates all possible segments
masks = mask_generator.generate(image)

# Then classify each segment
for mask in masks:
    # Grid cell vs non-cell classification
    ...
```

**Best for:** Finding ALL grid cells automatically

---

### Option 4: **LayoutLMv3** (Document Understanding)
**Why**: Specifically designed for structured documents

```python
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification

processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base")
model = LayoutLMv3ForTokenClassification.from_pretrained("microsoft/layoutlmv3-base")
```

**Best for:** Grid-based documents, forms, tables

---

## 📦 Ready-to-Use Datasets

### 1. **For Crossword Grids:**
Create custom dataset (I'll provide tools below)

### 2. **For General UI:**

**RICO Dataset:**
```bash
# Download RICO
wget http://interactionmining.org/rico/semantic_annotations.json
```

**PubLayNet** (Document layouts):
```bash
# 360k+ document images with layout annotations
https://github.com/ibm-aur-nlp/PubLayNet
```

**DocLayNet** (Document layouts):
```bash
# 80k+ document pages, table annotations
https://github.com/DS4SD/DocLayNet
```

**WebUI-Dataset:**
```bash
git clone https://github.com/mingyaulee/WebUI-Dataset
```

### 3. **Synthetic Data Generation:**

```python
# Generate crossword grids programmatically
import numpy as np
from PIL import Image, ImageDraw

def generate_crossword_grid(size=15):
    """Generate synthetic crossword grid"""
    img = Image.new('RGB', (size*40, size*40), 'white')
    draw = ImageDraw.Draw(img)
    
    # Draw grid
    for i in range(size+1):
        # Vertical lines
        draw.line([(i*40, 0), (i*40, size*40)], fill='black', width=2)
        # Horizontal lines
        draw.line([(0, i*40), (size*40, i*40)], fill='black', width=2)
    
    # Add random black squares
    for _ in range(size*2):
        x, y = np.random.randint(0, size, 2)
        draw.rectangle([x*40, y*40, (x+1)*40, (y+1)*40], fill='black')
    
    return img

# Generate 1000 synthetic crosswords
for i in range(1000):
    img = generate_crossword_grid()
    img.save(f"synthetic_crossword_{i}.png")
```

---

## 🛠️ Training Pipeline (Step-by-Step)

### Step 1: Data Annotation

**Option A: Use Roboflow (Easiest)**
```bash
# 1. Sign up at roboflow.com
# 2. Upload your images
# 3. Draw bounding boxes
# 4. Export in YOLO format
```

**Option B: Use LabelImg (Free)**
```bash
pip install labelImg
labelImg  # Opens GUI
# Draw boxes, save as YOLO txt files
```

**Option C: Auto-annotation with SAM**
```python
# Use Segment Anything to generate initial annotations
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator

sam = sam_model_registry["vit_h"](checkpoint="sam_vit_h.pth")
mask_generator = SamAutomaticMaskGenerator(sam)

masks = mask_generator.generate(crossword_image)
# Convert masks to bounding boxes
# Manual review and correction
```

### Step 2: Dataset Structure

```
crossword_dataset/
├── images/
│   ├── train/
│   │   ├── img1.png
│   │   ├── img2.png
│   ├── val/
│   │   ├── img3.png
│   └── test/
│       └── img4.png
├── labels/
│   ├── train/
│   │   ├── img1.txt  # YOLO format
│   │   ├── img2.txt
│   ├── val/
│   └── test/
└── data.yaml
```

**data.yaml:**
```yaml
train: ../crossword_dataset/images/train
val: ../crossword_dataset/images/val
test: ../crossword_dataset/images/test

nc: 4  # number of classes
names: ['cell', 'row', 'column', 'black_square']
```

### Step 3: Training

```python
from ultralytics import YOLO

# Load pretrained model
model = YOLO("yolov8n.pt")

# Train
results = model.train(
    data="crossword_dataset/data.yaml",
    epochs=100,
    imgsz=640,
    batch=16,
    lr0=0.01,
    device=0,  # GPU 0
    workers=8,
    project="crossword_detection",
    name="yolov8n_crossword"
)

# Validate
metrics = model.val()

# Export
model.export(format="onnx")  # Or TorchScript, TFLite, etc.
```

### Step 4: Integration

Once trained, add to detector_factory:

```python
class CustomYOLODetector(BaseDetector):
    """Custom trained YOLO for crossword grids"""
    
    def __init__(self, model_path: str = "best_crossword.pt", device=None):
        super().__init__(device)
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        
    def detect(self, image, confidence=0.25):
        result = self.model.predict(
            source=image,
            conf=confidence,
            iou=0.45,
            verbose=False
        )
        
        boxes = result[0].boxes.xyxy
        scores = result[0].boxes.conf
        
        # Map class IDs to names
        class_names = self.model.names
        labels = [class_names[int(cls)] for cls in result[0].boxes.cls]
        
        return boxes, scores, labels
```

---

## 🎯 Quick Start: Train in 1 Hour

### Minimal Viable Dataset (50 images)

1. **Collect 50 crossword images**
   ```bash
   # Download from NYT, Guardian, etc.
   # Or use your screenshot x50 with variations
   ```

2. **Auto-annotate with Table Transformer**
   ```python
   from util.detector_factory import get_detector
   
   # Use Table Transformer to get initial boxes
   detector = get_detector("table_transformer")
   boxes, scores, labels = detector.detect(image)
   
   # Convert to YOLO format
   # Save as training data
   ```

3. **Manual correction (15 min per image)**
   - Use LabelImg
   - Fix any mistakes from auto-annotation

4. **Train YOLOv8**
   ```python
   model = YOLO("yolov8n.pt")
   model.train(data="crossword.yaml", epochs=50, imgsz=640)
   ```

5. **Test and iterate**

---

## 📈 Expected Results

**With 50 images:**
- mAP@0.5: ~70-80%
- Good enough for basic detection

**With 200 images:**
- mAP@0.5: ~85-90%
- Production-ready

**With 1000 images:**
- mAP@0.5: ~95%+
- State-of-the-art

---

## 🚀 Recommended Path

### For YOU (Crossword Grid Detection):

1. **Short-term (Today):**
   - Use **Table Transformer** (already working with 50 detections)
   - Adjust confidence threshold to get more/fewer boxes

2. **Medium-term (This Week):**
   - Collect 50-100 crossword images
   - Auto-annotate with Table Transformer
   - Fine-tune YOLOv8n on this data
   - Should get 90%+ accuracy

3. **Long-term (If needed):**
   - Expand dataset to 500+ images
   - Train larger YOLO model (yolov8m)
   - Create specialized "CrosswordNet"

---

## 💾 Pre-trained Models to Try (No training needed)

1. **DinoV2 + Linear Probe**
   ```python
   # Facebook's vision foundation model
   from transformers import AutoImageProcessor, Dinov2Model
   model = Dinov2Model.from_pretrained("facebook/dinov2-base")
   # Train small detection head on top
   ```

2. **YOLOv8 pretrained on COCO**
   - Already has cell-like objects
   - May work better than current YOLO with lower threshold

3. **Segment Anything (SAM)**
   - No training needed
   - Auto-segments everything
   - Filter for grid-like segments

---

## 📚 Resources

**Papers:**
- YOLO: https://arxiv.org/abs/2304.00501
- Table Transformer: https://arxiv.org/abs/2110.00061
- SAM: https://arxiv.org/abs/2304.02643

**Tools:**
- Roboflow: https://roboflow.com
- LabelImg: https://github.com/tzutalin/labelImg
- Ultralytics: https://docs.ultralytics.com

**Datasets:**
- RICO: http://interactionmining.org/rico
- PubLayNet: https://github.com/ibm-aur-nlp/PubLayNet
- DocLayNet: https://github.com/DS4SD/DocLayNet

---

## ✅ Action Items

**For immediate improvement:**
1. [ ] Lower Table Transformer threshold to 0.1-0.2 (may find more cells)
2. [ ] Try YOLOv8 with lower confidence (0.01)

**For custom training:**
1. [ ] Collect 50 crossword images
2. [ ] Use Table Transformer for auto-annotation
3. [ ] Manually correct 50 annotations
4. [ ] Train YOLOv8n for 50 epochs
5. [ ] Integrate trained model

**I can help with:**
- Creating annotation scripts
- Synthetic data generation
- Training scripts
- Model integration

Let me know which path you'd like to take!
