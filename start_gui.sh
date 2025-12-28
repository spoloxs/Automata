#!/usr/bin/env bash
# Start the Web Automation Agent GUI

echo "🚀 Starting AI Web Automation Agent GUI..."
echo ""
echo "The GUI will open in your browser at: http://localhost:7860"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the GUI
python3 "$SCRIPT_DIR/app.py"
