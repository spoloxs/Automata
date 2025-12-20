#!/bin/bash
# Test each component in FRESH process to isolate leak

cd /home/stoxy/automata/web-agent

echo "========================================"
echo "TESTING EACH COMPONENT IN FRESH PROCESS"
echo "========================================"

# Test 1: All real
echo -e "\n🔬 TEST 1: ALL REAL COMPONENTS"
python -c "
import asyncio
import gc
import psutil
import sys
from pathlib import Path

project_root = Path('.').absolute() / 'src'
sys.path.insert(0, str(project_root))

from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY

def get_ram():
    return psutil.Process().memory_info().rss / 1024 / 1024

async def test():
    baseline = get_ram()
    master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)
    await master.initialize()
    after_init = get_ram()
    
    await master.execute_goal('Navigate to google.com', 'https://www.google.com', timeout=60)
    after_task = get_ram()
    
    await master.cleanup()
    del master
    gc.collect()
    gc.collect()
    after_cleanup = get_ram()
    
    print(f'RESULT 1: Init +{after_init-baseline:.1f} MB, Task +{after_task-after_init:.1f} MB, Leaked {after_cleanup-after_init:.1f} MB')

asyncio.run(test())
" 2>&1 | grep "RESULT 1:"

sleep 3

# Test 2: Mock ScreenParser
echo -e "\n🔬 TEST 2: MOCK ScreenParser (keep others real)"
python -c "
import asyncio
import gc
import psutil
import sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image

project_root = Path('.').absolute() / 'src'
sys.path.insert(0, str(project_root))

from web_agent.perception.screen_parser import Element

class MockScreenParser:
    def __init__(self):
        pass
    
    def parse(self, screenshot: Image.Image):
        return [
            Element(0, 'icon', (0.38, 0.06, 0.60, 0.20), (0.49, 0.13), 'Google', True, 'mock'),
            Element(1, 'icon', (0.29, 0.24, 0.69, 0.30), (0.49, 0.27), 'Search', True, 'mock'),
        ]

from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY

def get_ram():
    return psutil.Process().memory_info().rss / 1024 / 1024

async def test():
    with patch('web_agent.perception.screen_parser.ScreenParser', MockScreenParser):
        baseline = get_ram()
        master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)
        await master.initialize()
        after_init = get_ram()
        
        await master.execute_goal('Navigate to google.com', 'https://www.google.com', timeout=60)
        after_task = get_ram()
        
        await master.cleanup()
        del master
        gc.collect()
        gc.collect()
        after_cleanup = get_ram()
        
        print(f'RESULT 2: Init +{after_init-baseline:.1f} MB, Task +{after_task-after_init:.1f} MB, Leaked {after_cleanup-after_init:.1f} MB')

asyncio.run(test())
" 2>&1 | grep "RESULT 2:"

echo -e "\n========================================"
echo "ANALYSIS"
echo "========================================"
echo "Compare leaked MB between Test 1 and Test 2"
echo "If Test 2 leaked significantly less, ScreenParser is the culprit"
echo "========================================"
