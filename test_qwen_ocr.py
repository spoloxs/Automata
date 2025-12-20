"""
Test Qwen2-VL HTML-based text extraction
Tests extracting text from HTML using Qwen2-VL instead of OCR on images
"""

import sys
import os

# Add web-agent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import psutil
import gc
import torch

def get_ram_mb():
    """Get current RAM usage in MB"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

def create_test_html():
    """Create a simple test HTML page"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <style>
            body { margin: 20px; font-family: Arial; background: white; }
            .text1 { position: absolute; left: 100px; top: 100px; font-size: 40px; }
            .text2 { position: absolute; left: 100px; top: 200px; font-size: 40px; }
            .text3 { position: absolute; left: 100px; top: 300px; font-size: 40px; }
            .icon1 { position: absolute; left: 500px; top: 100px; width: 100px; height: 100px; border: 3px solid blue; }
            .icon2 { position: absolute; left: 700px; top: 100px; width: 100px; height: 100px; border: 3px solid red; border-radius: 50%; }
        </style>
    </head>
    <body>
        <div class="text1">Hello World</div>
        <div class="text2">Test OCR</div>
        <div class="text3">Games</div>
        <div class="icon1"></div>
        <div class="icon2"></div>
    </body>
    </html>
    """
    
    # Save HTML file
    html_path = "/tmp/test_qwen_html.html"
    with open(html_path, 'w') as f:
        f.write(html)
    
    return html_path, html

def main():
    print("=" * 60)
    print("Testing Qwen2-VL HTML Text Extraction")
    print("=" * 60)
    
    # Initial RAM
    ram_start = get_ram_mb()
    print(f"\n1. Initial RAM: {ram_start:.0f} MB")
    
    # Create test HTML
    print("\n2. Creating test HTML...")
    html_path, html_content = create_test_html()
    print(f"   Saved test HTML to {html_path}")
    print(f"   HTML length: {len(html_content)} chars")
    
    # Test with Qwen2-VL HTML text extraction
    print("\n3. Testing Qwen2-VL HTML text extraction...")
    from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
    
    ram_before_load = get_ram_mb()
    print(f"   RAM before loading model: {ram_before_load:.0f} MB")
    
    # Load Qwen2-VL
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        "Qwen/Qwen2-VL-2B-Instruct",
        torch_dtype=torch.float16,
        device_map="auto"
    )
    processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-2B-Instruct")
    
    ram_after_load = get_ram_mb()
    print(f"   RAM after loading: {ram_after_load:.0f} MB (+{ram_after_load - ram_before_load:.0f} MB)")
    
    # Extract text from HTML using Qwen2-VL
    print("\n4. Extracting text from HTML...")
    ram_before_extract = get_ram_mb()
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"Extract all visible text from this HTML and provide bounding boxes. HTML:\n{html_content}"}
            ]
        }
    ]
    
    text_prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text_prompt], padding=True, return_tensors="pt")
    inputs = inputs.to(model.device)
    
    with torch.no_grad():
        output_ids = model.generate(**inputs, max_new_tokens=256, do_sample=False)
    
    response = processor.batch_decode(output_ids, skip_special_tokens=True)[0]
    
    ram_after_extract = get_ram_mb()
    ram_spike = ram_after_extract - ram_before_extract
    print(f"   RAM after extraction: {ram_after_extract:.0f} MB (+{ram_spike:.0f} MB)")
    
    # Show results
    print(f"\n5. Extraction Results:")
    print(f"   Response:\n{response}")
    
    # Check RAM spike
    print(f"\n6. Memory Analysis:")
    print(f"   ✅ RAM spike during extraction: {ram_spike:.0f} MB")
    print(f"   ✅ No OCR models needed!")
    
    # Clean up
    print(f"\n7. Cleaning up...")
    del model
    del processor
    del inputs
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    ram_final = get_ram_mb()
    print(f"   Final RAM: {ram_final:.0f} MB")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
