"""
Click Precision Test - Logs exact intended vs actual click coordinates.
This test captures EXACTLY where clicks are commanded vs where they land.
"""

import asyncio
from web_agent.execution.browser_controller import BrowserController
from web_agent.execution.action_handler import ActionHandler, BrowserAction, ActionType
from web_agent.perception.screen_parser import Element
from web_agent.storage.worker_memory import WorkerMemory


async def test_click_precision():
    """Test that verifies exact click coordinates with detailed logging"""
    print("\n" + "="*80)
    print("🎯 CLICK PRECISION TEST - Exact Coordinate Comparison")
    print("="*80)
    
    # Create test page with clickable targets
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Click Precision Test</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: 'Courier New', monospace;
            background: #1a1a1a;
            color: #00ff00;
        }
        #log {
            position: fixed;
            top: 10px;
            left: 10px;
            background: rgba(0, 0, 0, 0.9);
            color: #00ff00;
            padding: 15px;
            border: 2px solid #00ff00;
            border-radius: 5px;
            font-size: 11px;
            max-width: 400px;
            z-index: 10000;
            font-family: 'Courier New', monospace;
        }
        .target {
            position: absolute;
            background: #333;
            border: 2px solid #666;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            cursor: crosshair;
            transition: all 0.2s;
        }
        .target:hover {
            background: #555;
            border-color: #00ff00;
        }
        .target.hit {
            background: #00ff00;
            color: #000;
            border-color: #00ff00;
            font-weight: bold;
        }
        .crosshair {
            position: absolute;
            width: 20px;
            height: 20px;
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
            width: 2px;
            height: 100%;
            margin-left: -1px;
        }
        .crosshair::after {
            left: 0;
            top: 50%;
            width: 100%;
            height: 2px;
            margin-top: -1px;
        }
    </style>
</head>
<body>
    <div id="log">
        <strong>🎯 CLICK PRECISION TEST</strong><br>
        Waiting for clicks...
    </div>
    
    <!-- Test targets at precise positions -->
    <div class="target" id="t1" style="left: 100px; top: 100px; width: 150px; height: 60px;">
        TARGET 1<br>(175, 130)
    </div>
    <div class="target" id="t2" style="left: 400px; top: 200px; width: 200px; height: 80px;">
        TARGET 2<br>(500, 240)
    </div>
    <div class="target" id="t3" style="left: 700px; top: 150px; width: 120px; height: 100px;">
        TARGET 3<br>(760, 200)
    </div>
    <div class="target" id="t4" style="left: 200px; top: 350px; width: 180px; height: 70px;">
        TARGET 4<br>(290, 385)
    </div>
    <div class="target" id="t5" style="left: 550px; top: 400px; width: 160px; height: 90px;">
        TARGET 5<br>(630, 445)
    </div>
    
    <script>
        const clickData = [];
        let crosshair = null;
        
        // Create crosshair element
        function showCrosshair(x, y) {
            if (crosshair) crosshair.remove();
            crosshair = document.createElement('div');
            crosshair.className = 'crosshair';
            crosshair.style.left = (x - 10) + 'px';
            crosshair.style.top = (y - 10) + 'px';
            document.body.appendChild(crosshair);
        }
        
        // Listen for ALL clicks on the page
        document.addEventListener('click', function(e) {
            const x = e.clientX;
            const y = e.clientY;
            
            // Show crosshair at exact click location
            showCrosshair(x, y);
            
            // Find which element was clicked
            const target = e.target.closest('.target');
            
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
                
                target.classList.add('hit');
            }
            
            clickData.push(info);
            
            // Update log display
            const log = document.getElementById('log');
            if (target) {
                log.innerHTML = `
                    <strong>✅ CLICK REGISTERED</strong><br>
                    <strong>Target:</strong> ${info.targetId}<br>
                    <strong>Click at:</strong> (${x}, ${y})<br>
                    <strong>Center at:</strong> (${info.targetCenterX}, ${info.targetCenterY})<br>
                    <strong>Offset:</strong> (${info.offsetX >= 0 ? '+' : ''}${info.offsetX}, ${info.offsetY >= 0 ? '+' : ''}${info.offsetY}) px<br>
                    <strong>Total clicks:</strong> ${clickData.length}
                `;
            } else {
                log.innerHTML = `
                    <strong>❌ CLICK OUTSIDE TARGET</strong><br>
                    <strong>Click at:</strong> (${x}, ${y})<br>
                    <strong>Total clicks:</strong> ${clickData.length}
                `;
            }
        });
        
        // Make click data accessible
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
        
        # Define viewport
        viewport_size = (1280, 720)
        
        # Create elements matching the HTML targets
        # Target 1: left=100, top=100, width=150, height=60 → center=(175, 130)
        # Target 2: left=400, top=200, width=200, height=80 → center=(500, 240)
        # Target 3: left=700, top=150, width=120, height=100 → center=(760, 200)
        # Target 4: left=200, top=350, width=180, height=70 → center=(290, 385)
        # Target 5: left=550, top=400, width=160, height=90 → center=(630, 445)
        
        test_targets = [
            {
                'id': 1,
                'pixel_center': (175, 130),
                'bbox_pixels': (100, 100, 250, 160),
                'name': 'TARGET 1'
            },
            {
                'id': 2,
                'pixel_center': (500, 240),
                'bbox_pixels': (400, 200, 600, 280),
                'name': 'TARGET 2'
            },
            {
                'id': 3,
                'pixel_center': (760, 200),
                'bbox_pixels': (700, 150, 820, 250),
                'name': 'TARGET 3'
            },
            {
                'id': 4,
                'pixel_center': (290, 385),
                'bbox_pixels': (200, 350, 380, 420),
                'name': 'TARGET 4'
            },
            {
                'id': 5,
                'pixel_center': (630, 445),
                'bbox_pixels': (550, 400, 710, 490),
                'name': 'TARGET 5'
            }
        ]
        
        # Convert to Element objects with normalized coordinates
        mock_elements = []
        for target in test_targets:
            px_center = target['pixel_center']
            px_bbox = target['bbox_pixels']
            
            # Convert to normalized
            norm_center = [px_center[0] / viewport_size[0], px_center[1] / viewport_size[1]]
            norm_bbox = [
                px_bbox[0] / viewport_size[0],
                px_bbox[1] / viewport_size[1],
                px_bbox[2] / viewport_size[0],
                px_bbox[3] / viewport_size[1]
            ]
            
            elem = Element(
                id=target['id'],
                type="button",
                bbox=norm_bbox,
                center=norm_center,
                content=target['name'],
                interactivity=True,
                source="test",
                dom_tag="div",
                dom_id=f"t{target['id']}"
            )
            mock_elements.append(elem)
        
        # Create action handler
        memory = WorkerMemory()
        handler = ActionHandler(
            browser_controller=browser,
            memory=memory,
            viewport_size=viewport_size
        )
        handler.current_elements = mock_elements
        
        print("\n" + "="*80)
        print("🎯 TESTING CLICK PRECISION ON 5 TARGETS")
        print("="*80)
        print("\nFormat: INTENDED → ACTUAL (OFFSET)\n")
        
        results = []
        
        for i, (elem, target) in enumerate(zip(mock_elements, test_targets), 1):
            # Calculate intended click position (what we COMMAND)
            intended_x = int(elem.center[0] * viewport_size[0])
            intended_y = int(elem.center[1] * viewport_size[1])
            expected_center = target['pixel_center']
            
            print(f"\n{'─'*80}")
            print(f"Target {i}: {target['name']}")
            print(f"{'─'*80}")
            print(f"  Normalized center: ({elem.center[0]:.6f}, {elem.center[1]:.6f})")
            print(f"  Calculated pixels: ({intended_x}, {intended_y})")
            print(f"  Expected center:   {expected_center}")
            
            # Verify our calculation is correct
            calc_match = (intended_x, intended_y) == expected_center
            print(f"  Calculation check: {'✅ MATCH' if calc_match else '❌ MISMATCH'}")
            
            # Clear previous clicks
            await browser.evaluate_js("window.clearClickData()")
            
            # Execute click using element ID
            action = BrowserAction(
                action_type=ActionType.CLICK,
                parameters={
                    "element_id": elem.id,
                    "reasoning": f"Testing {target['name']}"
                }
            )
            
            print(f"\n  ⚡ Executing click...")
            await handler.handle_action(action, mock_elements)
            await asyncio.sleep(1.5)
            
            # Get actual click data from browser
            click_data = await browser.evaluate_js("window.getClickData()")
            
            if click_data and len(click_data) > 0:
                last_click = click_data[-1]
                actual_x = last_click['clickX']
                actual_y = last_click['clickY']
                
                # Calculate offset from intended position
                offset_x = actual_x - intended_x
                offset_y = actual_y - intended_y
                
                # If target was hit, also show offset from target center
                target_hit = last_click.get('targetHit', False)
                
                print(f"\n  📍 RESULTS:")
                print(f"     Intended: ({intended_x}, {intended_y})")
                print(f"     Actual:   ({actual_x}, {actual_y})")
                print(f"     Offset:   ({offset_x:+d}, {offset_y:+d}) pixels")
                
                if target_hit:
                    target_offset_x = last_click.get('offsetX', 0)
                    target_offset_y = last_click.get('offsetY', 0)
                    target_center_x = last_click.get('targetCenterX', 0)
                    target_center_y = last_click.get('targetCenterY', 0)
                    
                    print(f"\n  🎯 TARGET HIT:")
                    print(f"     Target center: ({target_center_x}, {target_center_y})")
                    print(f"     Offset from center: ({target_offset_x:+d}, {target_offset_y:+d}) pixels")
                    
                    # Accuracy rating
                    total_offset = abs(target_offset_x) + abs(target_offset_y)
                    if total_offset == 0:
                        accuracy = "🟢 PERFECT (0 offset)"
                    elif total_offset <= 2:
                        accuracy = "🟢 EXCELLENT (≤2px)"
                    elif total_offset <= 5:
                        accuracy = "🟡 GOOD (≤5px)"
                    else:
                        accuracy = "🔴 POOR (>5px)"
                    
                    print(f"     Accuracy: {accuracy}")
                else:
                    print(f"\n  ❌ TARGET MISSED!")
                
                results.append({
                    'target_id': elem.id,
                    'target_name': target['name'],
                    'intended': (intended_x, intended_y),
                    'actual': (actual_x, actual_y),
                    'offset': (offset_x, offset_y),
                    'target_hit': target_hit,
                    'target_offset': (last_click.get('offsetX', None), last_click.get('offsetY', None)) if target_hit else None
                })
            else:
                print(f"\n  ⚠️  No click data captured!")
                results.append({
                    'target_id': elem.id,
                    'target_name': target['name'],
                    'intended': (intended_x, intended_y),
                    'actual': None,
                    'offset': None,
                    'target_hit': False,
                    'target_offset': None
                })
        
        # Final summary
        print("\n" + "="*80)
        print("📊 FINAL SUMMARY")
        print("="*80)
        
        if all(r['actual'] is not None for r in results):
            print("\n✅ All clicks captured successfully!\n")
            
            # Table header
            print(f"{'Target':<12} {'Intended':<15} {'Actual':<15} {'Offset':<12} {'From Center':<15} {'Status':<10}")
            print("─" * 90)
            
            for r in results:
                intended_str = f"({r['intended'][0]}, {r['intended'][1]})"
                actual_str = f"({r['actual'][0]}, {r['actual'][1]})"
                offset_str = f"({r['offset'][0]:+d}, {r['offset'][1]:+d})"
                
                if r['target_hit'] and r['target_offset']:
                    center_offset_str = f"({r['target_offset'][0]:+d}, {r['target_offset'][1]:+d})"
                    total_offset = abs(r['target_offset'][0]) + abs(r['target_offset'][1])
                    if total_offset == 0:
                        status = "PERFECT"
                    elif total_offset <= 2:
                        status = "EXCELLENT"
                    elif total_offset <= 5:
                        status = "GOOD"
                    else:
                        status = "POOR"
                else:
                    center_offset_str = "N/A"
                    status = "MISSED" if not r['target_hit'] else "HIT"
                
                print(f"{r['target_name']:<12} {intended_str:<15} {actual_str:<15} {offset_str:<12} {center_offset_str:<15} {status:<10}")
            
            # Statistics
            print("\n" + "─" * 90)
            hits = sum(1 for r in results if r['target_hit'])
            perfect = sum(1 for r in results if r['target_hit'] and r['target_offset'] and abs(r['target_offset'][0]) + abs(r['target_offset'][1]) == 0)
            
            print(f"\nTargets hit: {hits}/{len(results)}")
            print(f"Perfect centering: {perfect}/{hits if hits > 0 else 1}")
            
            if all(r['offset'] for r in results):
                avg_offset_from_intended_x = sum(abs(r['offset'][0]) for r in results) / len(results)
                avg_offset_from_intended_y = sum(abs(r['offset'][1]) for r in results) / len(results)
                print(f"Avg offset from intended: ({avg_offset_from_intended_x:.1f}, {avg_offset_from_intended_y:.1f}) px")
            
            if any(r['target_offset'] for r in results):
                center_offsets = [r for r in results if r['target_offset']]
                avg_center_x = sum(abs(r['target_offset'][0]) for r in center_offsets) / len(center_offsets)
                avg_center_y = sum(abs(r['target_offset'][1]) for r in center_offsets) / len(center_offsets)
                print(f"Avg offset from target center: ({avg_center_x:.1f}, {avg_center_y:.1f}) px")
        else:
            print("\n⚠️  Some clicks were not captured - check browser console for errors")
        
        print("\n" + "="*80)
        print("\nBrowser will close in 5 seconds...")
        await asyncio.sleep(5)
        
    finally:
        await browser.cleanup()
        print("\n✓ Browser closed\n")


if __name__ == "__main__":
    try:
        asyncio.run(test_click_precision())
        print("✅ Test completed!")
    except KeyboardInterrupt:
        print("\n\n❌ Test cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
