#!/bin/bash

# Comprehensive Memory Leak Test Suite
# Tests each component in isolation to identify RAM usage patterns

echo "=========================================="
echo "MEMORY LEAK DIAGNOSTIC TEST SUITE"
echo "=========================================="
echo ""
echo "Testing components individually to isolate RAM leaks:"
echo "  1. ScreenParser (OmniParser)"
echo "  2. GeminiAgent (chat_histories)"
echo "  3. PIL Images (screenshots)"
echo "  4. DAG/Plan objects"
echo ""
echo "=========================================="
echo ""

# Activate conda environment
source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || source /opt/anaconda/etc/profile.d/conda.sh 2>/dev/null
conda activate omni

cd /home/stoxy/automata/web-agent

# Test 1: ScreenParser
echo ""
echo "==================== TEST 1: ScreenParser ===================="
echo "Testing OmniParser memory usage over 5 parses..."
echo ""
python test_memory_simple.py 2>&1 | tee test_results_screenparser.log
echo ""
echo "✓ ScreenParser test complete - see test_results_screenparser.log"
echo ""

# Test 2: PIL Images
echo ""
echo "==================== TEST 2: PIL Images ===================="
echo "Testing Image object memory usage..."
echo ""
python test_image_memory.py 2>&1 | tee test_results_images.log
echo ""
echo "✓ Image memory test complete - see test_results_images.log"
echo ""

# Test 3: DAG/Plan objects
echo ""
echo "==================== TEST 3: DAG/Plan Objects ===================="
echo "Testing DAG and Plan memory accumulation..."
echo ""
python test_dag_memory.py 2>&1 | tee test_results_dag.log
echo ""
echo "✓ DAG/Plan test complete - see test_results_dag.log"
echo ""

# Test 4: GeminiAgent (requires API key)
echo ""
echo "==================== TEST 4: GeminiAgent ===================="
echo "Testing GeminiAgent chat_histories accumulation..."
echo ""
if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  GEMINI_API_KEY not set - skipping GeminiAgent test"
    echo "   Set it with: export GEMINI_API_KEY=your_key"
else
    python test_gemini_memory.py 2>&1 | tee test_results_gemini.log
    echo ""
    echo "✓ GeminiAgent test complete - see test_results_gemini.log"
fi
echo ""

# Generate summary report
echo ""
echo "=========================================="
echo "GENERATING SUMMARY REPORT"
echo "=========================================="
echo ""

python << 'PYEOF'
import re

def extract_memory_stats(log_file):
    """Extract initial and final RAM usage from test log"""
    try:
        with open(log_file, 'r') as f:
            content = f.read()
        
        # Find all RAM measurements
        pattern = r'Process=(\d+)MB'
        matches = re.findall(pattern, content)
        
        if not matches:
            return None, None, "No measurements found"
        
        initial = int(matches[0])
        final = int(matches[-1])
        increase = final - initial
        
        return initial, final, increase
    except Exception as e:
        return None, None, str(e)

tests = [
    ("ScreenParser", "test_results_screenparser.log"),
    ("PIL Images", "test_results_images.log"),
    ("DAG/Plan", "test_results_dag.log"),
    ("GeminiAgent", "test_results_gemini.log"),
]

print("="*70)
print("MEMORY LEAK TEST SUMMARY")
print("="*70)
print()
print(f"{'Component':<20} {'Initial RAM':>12} {'Final RAM':>12} {'Increase':>12}")
print("-"*70)

total_leaks = []
for name, log_file in tests:
    initial, final, increase = extract_memory_stats(log_file)
    
    if initial is None:
        print(f"{name:<20} {'N/A':>12} {'N/A':>12} {str(increase):<12}")
    else:
        increase_str = f"+{increase}MB" if increase > 0 else f"{increase}MB"
        status = "⚠️ LEAK" if increase > 100 else "✓ OK"
        print(f"{name:<20} {initial:>11}MB {final:>11}MB {increase_str:>11} {status}")
        
        if increase > 100:
            total_leaks.append((name, increase))

print("="*70)
print()

if total_leaks:
    print("🔴 MEMORY LEAKS DETECTED:")
    print()
    for name, increase in sorted(total_leaks, key=lambda x: x[1], reverse=True):
        print(f"  • {name}: +{increase}MB")
    print()
    print("Recommendation: Focus optimization efforts on components above.")
else:
    print("✅ No significant memory leaks detected across components.")

print()
print("Detailed logs saved to test_results_*.log files")
print("="*70)
PYEOF

echo ""
echo "=========================================="
echo "TEST SUITE COMPLETE"
echo "=========================================="
