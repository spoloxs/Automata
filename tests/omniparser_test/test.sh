#!/bin/bash

echo "🚀 OmniParser Cache Test Runner"
echo "================================"
echo ""

# Check if GEMINI_API_KEY is set
if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ Error: GEMINI_API_KEY not set"
    echo "   Set it with: export GEMINI_API_KEY='your-key'"
    exit 1
fi

echo "✅ GEMINI_API_KEY found"
echo ""

# Check if test HTML exists
if [ ! -f "test_html.html" ]; then
    echo "❌ Error: test_html.html not found"
    echo "   Make sure you're in the correct directory"
    exit 1
fi

echo "✅ Test HTML found"
echo ""

# Menu
echo "Select test to run:"
echo "  1) Simple cache test (visual, ~2 minutes)"
echo "  2) Full performance test (comprehensive, ~5 minutes)"
echo "  3) Both tests"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo ""
        echo "Running simple cache test..."
        python3 test_vis.py
        ;;
    2)
        echo ""
        echo "Running full performance test..."
        python3 test_py.py
        ;;
    3)
        echo ""
        echo "Running simple test first..."
        python3 test_vis.py
        echo ""
        echo "Press Enter to run full performance test..."
        read
        python3 test_py.py
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Tests complete!"
