"""
Comprehensive Shape & Size Test - Tests all element types and sizes from 300px to 1px.
Tests squares, rectangles, circles of various dimensions.
"""

import asyncio
from web_agent.execution.browser_controller import BrowserController
from web_agent.execution.action_handler import ActionHandler, BrowserAction, ActionType
from web_agent.perception.screen_parser import Element
from web_agent.storage.worker_memory import WorkerMemory


async def test_all_shapes_and_sizes():
    """Comprehensive test of all shapes and sizes"""
    print("\n" + "="*80)
    print("🎯 COMPREHENSIVE SHAPE & SIZE TEST")
    print("="*80)
    print("Testing: Squares, Rectangles (wide/tall), Circles")
    print("Sizes: From 300x300px down to 1x1px")
    
    # Create test page with diverse elements
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Shape & Size Test</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: monospace;
            background: #0a0a0a;
            color: #00ff00;
            overflow-x: auto;
        }
        #log {
            position: fixed;
            top: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.95);
            color: #00ff00;
            padding: 12px;
            border: 2px solid #00ff00;
            font-size: 10px;
            max-width: 250px;
            z-index: 10000;
            max-height: 600px;
            overflow-y: auto;
        }
        .element {
            position: absolute;
            border: 2px solid #444;
            background: #222;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 8px;
            cursor: crosshair;
            transition: all 0.1s;
            overflow: hidden;
        }
        .element:hover {
            border-color: #00ff00;
            background: #333;
        }
        .element.hit {
            background: #00ff00 !important;
            color: #000 !important;
            border-color: #00ff00 !important;
            font-weight: bold;
        }
        .circle {
            border-radius: 50%;
        }
        .crosshair {
            position: absolute;
            width: 10px;
            height: 10px;
            pointer-events: none;
            z-index: 9999;
        }
        .crosshair::before,
        .crosshair::after {
            content: '';
            position: absolute;
            background: red;
        }
        .crosshair::before {
            left: 50%;
            top: 0;
            width: 1px;
            height: 100%;
            margin-left: -0.5px;
        }
        .crosshair::after {
            left: 0;
            top: 50%;
            width: 100%;
            height: 1px;
            margin-top: -0.5px;
        }
    </style>
</head>
<body>
    <div id="log">
        <strong>🎯 SHAPE & SIZE TEST</strong><br>
        Click tracking active...
    </div>
    
    <!-- SQUARES: 300px to 1px -->
    <div class="element" id="sq_300" style="left: 50px; top: 50px; width: 300px; height: 300px;">SQ 300x300</div>
    <div class="element" id="sq_100" style="left: 400px; top: 50px; width: 100px; height: 100px;">SQ 100x100</div>
    <div class="element" id="sq_50" style="left: 550px; top: 50px; width: 50px; height: 50px;">SQ 50</div>
    <div class="element" id="sq_20" style="left: 650px; top: 50px; width: 20px; height: 20px;">20</div>
    <div class="element" id="sq_10" style="left: 700px; top: 50px; width: 10px; height: 10px;"></div>
    <div class="element" id="sq_5" style="left: 730px; top: 50px; width: 5px; height: 5px;"></div>
    <div class="element" id="sq_3" style="left: 750px; top: 50px; width: 3px; height: 3px;"></div>
    <div class="element" id="sq_1" style="left: 770px; top: 50px; width: 1px; height: 1px;"></div>
    
    <!-- WIDE RECTANGLES: 300px to 1px height -->
    <div class="element" id="rect_w_300" style="left: 50px; top: 400px; width: 600px; height: 300px;">WIDE 600x300</div>
    <div class="element" id="rect_w_100" style="left: 700px; top: 400px; width: 200px; height: 100px;">W 200x100</div>
    <div class="element" id="rect_w_50" style="left: 950px; top: 400px; width: 150px; height: 50px;">W 150x50</div>
    <div class="element" id="rect_w_20" style="left: 1150px; top: 400px; width: 80px; height: 20px;">W 80x20</div>
    <div class="element" id="rect_w_10" style="left: 50px; top: 750px; width: 50px; height: 10px;">50x10</div>
    <div class="element" id="rect_w_5" style="left: 120px; top: 750px; width: 30px; height: 5px;"></div>
    <div class="element" id="rect_w_3" style="left: 170px; top: 750px; width: 20px; height: 3px;"></div>
    <div class="element" id="rect_w_1" style="left: 210px; top: 750px; width: 15px; height: 1px;"></div>
    
    <!-- TALL RECTANGLES: 300px to 1px width -->
    <div class="element" id="rect_t_300" style="left: 800px; top: 50px; width: 300px; height: 300px;">TALL 300x300</div>
    <div class="element" id="rect_t_100" style="left: 1150px; top: 50px; width: 100px; height: 250px;">T 100x250</div>
    <div class="element" id="rect_t_50" style="left: 700px; top: 200px; width: 50px; height: 150px;">T 50x150</div>
    <div class="element" id="rect_t_20" style="left: 780px; top: 200px; width: 20px; height: 80px;">20x80</div>
    <div class="element" id="rect_t_10" style="left: 250px; top: 750px; width: 10px; height: 50px;">10x50</div>
    <div class="element" id="rect_t_5" style="left: 280px; top: 750px; width: 5px; height: 30px;"></div>
    <div class="element" id="rect_t_3" style="left: 300px; top: 750px; width: 3px; height: 20px;"></div>
    <div class="element" id="rect_t_1" style="left: 320px; top: 750px; width: 1px; height: 15px;"></div>
    
    <!-- CIRCLES: 300px to 5px (circles smaller than 5px are hard to see) -->
    <div class="element circle" id="circ_300" style="left: 400px; top: 200px; width: 300px; height: 300px;">CIRCLE 300</div>
    <div class="element circle" id="circ_100" style="left: 750px; top: 550px; width: 100px; height: 100px;">C 100</div>
    <div class="element circle" id="circ_50" style="left: 900px; top: 550px; width: 50px; height: 50px;">C 50</div>
    <div class="element circle" id="circ_20" style="left: 1000px; top: 550px; width: 20px; height: 20px;"></div>
    <div class="element circle" id="circ_10" style="left: 1050px; top: 550px; width: 10px; height: 10px;"></div>
    <div class="element circle" id="circ_5" style="left: 1080px; top: 550px; width: 5px; height: 5px;"></div>
    
    <script>
        const clickData = [];
        let crosshair = null;
        
        function showCrosshair(x, y) {
            if (crosshair) crosshair.remove();
            crosshair = document.createElement('div');
            crosshair.className = 'crosshair';
            crosshair.style.left = (x - 5) + 'px';
            crosshair.style.top = (y - 5) + 'px';
            document.body.appendChild(crosshair);
        }
        
        document.addEventListener('click', function(e) {
            const x = e.clientX;
            const y = e.clientY;
            
            showCrosshair(x, y);
            
            const target = e.target.closest('.element');
            
            const info = {
                timestamp: Date.now(),
                clickX: x,
                clickY: y,
                targetId: target ? target.id : 'none',
                targetHit: !!target
            };
            
            if (target) {
                const rect = target.getBoundingClientRect();
                const centerX = Math.round(rect.left + rect.width / 2);
                const centerY = Math.round(rect.top + rect.height / 2);
                const offsetX = x - centerX;
                const offsetY = y - centerY;
                
                info.targetCenterX = centerX;
                info.targetCenterY = centerY;
                info.offsetX = offsetX;
                info.offsetY = offsetY;
                info.width = Math.round(rect.width);
                info.height = Math.round(rect.height);
                
                target.classList.add('hit');
            }
            
            clickData.push(info);
            
            const log = document.getElementById('log');
            if (target) {
                const accuracy = (Math.abs(info.offsetX) + Math.abs(info.offsetY)) === 0 ? 'PERFECT' : 
                                 (Math.abs(info.offsetX) + Math.abs(info.offsetY)) <= 2 ? 'EXCELLENT' : 'GOOD';
                log.innerHTML = `
                    <strong>✅ ${info.targetId}</strong><br>
                    Size: ${info.width}x${info.height}px<br>
                    Click: (${x}, ${y})<br>
                    Center: (${info.targetCenterX}, ${info.targetCenterY})<br>
                    Offset: (${info.offsetX >= 0 ? '+' : ''}${info.offsetX}, ${info.offsetY >= 0 ? '+' : ''}${info.offsetY})<br>
                    <strong>${accuracy}</strong><br>
                    Total: ${clickData.length}
                `;
            }
        });
        
        window.getClickData = () => clickData;
        window.clearClickData = () => { clickData.length = 0; };
    </script>
</body>
</html>
"""
    
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
    temp_file.write(html)
    temp_file.close()
    test_url = f"file://{temp_file.name}"
    
    print(f"\n✓ Created test page: {test_url}\n")
    
    # Initialize browser
    import web_agent.config.settings as settings
    original_headless = settings.BROWSER_HEADLESS
    settings.BROWSER_HEADLESS = False
    
    browser = BrowserController()
    await browser.initialize()
    settings.BROWSER_HEADLESS = original_headless
    
    try:
        print("📍 Navigating to test page...")
        await browser.navigate(test_url)
        await asyncio.sleep(1.5)
        
        viewport_size = (1280, 720)
        
        # Define test targets with exact calculations
        test_targets = [
            # SQUARES
            {"id": "sq_300", "left": 50, "top": 50, "width": 300, "height": 300, "shape": "square"},
            {"id": "sq_100", "left": 400, "top": 50, "width": 100, "height": 100, "shape": "square"},
            {"id": "sq_50", "left": 550, "top": 50, "width": 50, "height": 50, "shape": "square"},
            {"id": "sq_20", "left": 650, "top": 50, "width": 20, "height": 20, "shape": "square"},
            {"id": "sq_10", "left": 700, "top": 50, "width": 10, "height": 10, "shape": "square"},
            {"id": "sq_5", "left": 730, "top": 50, "width": 5, "height": 5, "shape": "square"},
            {"id": "sq_3", "left": 750, "top": 50, "width": 3, "height": 3, "shape": "square"},
            {"id": "sq_1", "left": 770, "top": 50, "width": 1, "height": 1, "shape": "square"},
            
            # WIDE RECTANGLES
            {"id": "rect_w_100", "left": 700, "top": 400, "width": 200, "height": 100, "shape": "wide_rect"},
            {"id": "rect_w_50", "left": 950, "top": 400, "width": 150, "height": 50, "shape": "wide_rect"},
            {"id": "rect_w_20", "left": 1150, "top": 400, "width": 80, "height": 20, "shape": "wide_rect"},
            {"id": "rect_w_10", "left": 50, "top": 750, "width": 50, "height": 10, "shape": "wide_rect"},
            {"id": "rect_w_5", "left": 120, "top": 750, "width": 30, "height": 5, "shape": "wide_rect"},
            {"id": "rect_w_3", "left": 170, "top": 750, "width": 20, "height": 3, "shape": "wide_rect"},
            {"id": "rect_w_1", "left": 210, "top": 750, "width": 15, "height": 1, "shape": "wide_rect"},
            
            # TALL RECTANGLES
            {"id": "rect_t_100", "left": 1150, "top": 50, "width": 100, "height": 250, "shape": "tall_rect"},
            {"id": "rect_t_50", "left": 700, "top": 200, "width": 50, "height": 150, "shape": "tall_rect"},
            {"id": "rect_t_20", "left": 780, "top": 200, "width": 20, "height": 80, "shape": "tall_rect"},
            {"id": "rect_t_10", "left": 250, "top": 750, "width": 10, "height": 50, "shape": "tall_rect"},
            {"id": "rect_t_5", "left": 280, "top": 750, "width": 5, "height": 30, "shape": "tall_rect"},
            {"id": "rect_t_3", "left": 300, "top": 750, "width": 3, "height": 20, "shape": "tall_rect"},
            {"id": "rect_t_1", "left": 320, "top": 750, "width": 1, "height": 15, "shape": "tall_rect"},
            
            # CIRCLES
            {"id": "circ_100", "left": 750, "top": 550, "width": 100, "height": 100, "shape": "circle"},
            {"id": "circ_50", "left": 900, "top": 550, "width": 50, "height": 50, "shape": "circle"},
            {"id": "circ_20", "left": 1000, "top": 550, "width": 20, "height": 20, "shape": "circle"},
            {"id": "circ_10", "left": 1050, "top": 550, "width": 10, "height": 10, "shape": "circle"},
            {"id": "circ_5", "left": 1080, "top": 550, "width": 5, "height": 5, "shape": "circle"},
        ]
        
        # Convert to Element objects
        mock_elements = []
        for i, target in enumerate(test_targets, 1):
            center_x = target["left"] + target["width"] // 2
            center_y = target["top"] + target["height"] // 2
            
            norm_center = [center_x / viewport_size[0], center_y / viewport_size[1]]
            norm_bbox = [
                target["left"] / viewport_size[0],
                target["top"] / viewport_size[1],
                (target["left"] + target["width"]) / viewport_size[0],
                (target["top"] + target["height"]) / viewport_size[1]
            ]
            
            elem = Element(
                id=i,
                type="button",
                bbox=norm_bbox,
                center=norm_center,
                content=target["id"],
                interactivity=True,
                source="test",
                dom_tag="div",
                dom_id=target["id"]
            )
            mock_elements.append((elem, target))
        
        # Create action handler
        memory = WorkerMemory()
        handler = ActionHandler(
            browser_controller=browser,
            memory=memory,
            viewport_size=viewport_size
        )
        handler.current_elements = [e[0] for e in mock_elements]
        
        print("\n" + "="*80)
        print("🎯 TESTING ALL SHAPES AND SIZES")
        print("="*80)
        
        results = []
        
        for i, (elem, target) in enumerate(mock_elements, 1):
            intended_x = int(elem.center[0] * viewport_size[0])
            intended_y = int(elem.center[1] * viewport_size[1])
            
            print(f"\n[{i}/{len(mock_elements)}] {target['id']:<15} {target['shape']:<12} {target['width']:>3}x{target['height']:<3}px", end=" ")
            
            # Clear previous clicks
            await browser.evaluate_js("window.clearClickData()")
            
            # Execute click
            action = BrowserAction(
                action_type=ActionType.CLICK,
                parameters={
                    "element_id": elem.id,
                    "reasoning": f"Testing {target['id']}"
                }
            )
            
            await handler.handle_action(action, [e[0] for e in mock_elements])
            await asyncio.sleep(0.8)
            
            # Get click data
            click_data = await browser.evaluate_js("window.getClickData()")
            
            if click_data and len(click_data) > 0:
                last_click = click_data[-1]
                
                if last_click.get('targetHit'):
                    offset_x = last_click['offsetX']
                    offset_y = last_click['offsetY']
                    total_offset = abs(offset_x) + abs(offset_y)
                    
                    if total_offset == 0:
                        status = "🟢 PERFECT"
                    elif total_offset <= 2:
                        status = "🟡 EXCELLENT"
                    elif total_offset <= 5:
                        status = "🟠 GOOD"
                    else:
                        status = "🔴 POOR"
                    
                    print(f"→ ({offset_x:+2d},{offset_y:+2d}) {status}")
                    
                    results.append({
                        'id': target['id'],
                        'shape': target['shape'],
                        'size': f"{target['width']}x{target['height']}",
                        'area': target['width'] * target['height'],
                        'offset': (offset_x, offset_y),
                        'hit': True
                    })
                else:
                    print(f"→ ❌ MISSED")
                    results.append({
                        'id': target['id'],
                        'shape': target['shape'],
                        'size': f"{target['width']}x{target['height']}",
                        'area': target['width'] * target['height'],
                        'offset': None,
                        'hit': False
                    })
            else:
                print(f"→ ⚠️  NO DATA")
        
        # Summary
        print("\n" + "="*80)
        print("📊 FINAL SUMMARY BY CATEGORY")
        print("="*80)
        
        categories = {
            'square': [],
            'wide_rect': [],
            'tall_rect': [],
            'circle': []
        }
        
        for r in results:
            if r['hit']:
                categories[r['shape']].append(r)
        
        for shape_name, items in categories.items():
            if items:
                perfect = sum(1 for r in items if r['offset'] and abs(r['offset'][0]) + abs(r['offset'][1]) == 0)
                excellent = sum(1 for r in items if r['offset'] and 0 < abs(r['offset'][0]) + abs(r['offset'][1]) <= 2)
                
                print(f"\n{shape_name.upper().replace('_', ' ')}:")
                print(f"  Total tested: {len(items)}")
                print(f"  Perfect (0,0): {perfect}/{len(items)} ({perfect/len(items)*100:.0f}%)")
                print(f"  Excellent (≤2px): {excellent}/{len(items)}")
                
                if items:
                    avg_x = sum(abs(r['offset'][0]) for r in items if r['offset']) / len(items)
                    avg_y = sum(abs(r['offset'][1]) for r in items if r['offset']) / len(items)
                    print(f"  Avg offset: ({avg_x:.1f}, {avg_y:.1f})px")
        
        # Overall stats
        hits = [r for r in results if r['hit']]
        perfect_total = sum(1 for r in hits if r['offset'] and abs(r['offset'][0]) + abs(r['offset'][1]) == 0)
        
        print(f"\n{'─'*80}")
        print(f"OVERALL: {len(hits)}/{len(results)} targets hit")
        print(f"PERFECT CENTERING: {perfect_total}/{len(hits)} ({perfect_total/len(hits)*100:.0f}%)")
        print(f"{'─'*80}")
        
        print("\nBrowser will close in 5 seconds...")
        await asyncio.sleep(5)
        
    finally:
        await browser.cleanup()
        print("\n✓ Browser closed\n")


if __name__ == "__main__":
    try:
        asyncio.run(test_all_shapes_and_sizes())
        print("✅ Test completed!")
    except KeyboardInterrupt:
        print("\n\n❌ Test cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
