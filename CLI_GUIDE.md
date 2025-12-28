# CLI Usage Guide

## Interactive Mode

The easiest way to use the Web Automation Agent:

```bash
python cli.py
```

### What You'll Be Asked

1. **Target URL**: The website you want to automate
   - Example: `https://www.google.com`
   - Must include `http://` or `https://`

2. **Task Description**: What you want the agent to do
   - Be specific and clear
   - Examples:
     - `Search for 'Python asyncio' and click the first result`
     - `Fill the contact form with name 'John Doe' and email 'john@example.com'`
     - `Find the pricing page and extract the premium plan cost`

3. **Max Parallel Workers**: How many tasks to run simultaneously
   - Default: 2
   - Range: 1-8
   - Higher = faster but more resource-intensive

## Command Line Mode

Perfect for scripts and automation:

### Basic Usage

```bash
python cli.py --url "https://example.com" --task "Your task here"
```

### With All Options

```bash
python cli.py \
  --url "https://www.google.com" \
  --task "Search for 'Machine Learning' and click Wikipedia" \
  --workers 4 \
  --headless
```

## Real-World Examples

### 1. Web Search
```bash
python cli.py \
  --url "https://www.google.com" \
  --task "Search for 'best pizza near me' and show results"
```

### 2. Form Filling
```bash
python cli.py \
  --url "https://example.com/contact" \
  --task "Fill name with 'Alice', email with 'alice@test.com', message with 'Hello', and submit"
```

### 3. Data Extraction
```bash
python cli.py \
  --url "https://news.ycombinator.com" \
  --task "Extract the top 5 story headlines"
```

### 4. Navigation
```bash
python cli.py \
  --url "https://github.com" \
  --task "Navigate to Trending repositories and find the top Python project"
```

### 5. E-commerce
```bash
python cli.py \
  --url "https://example-shop.com" \
  --task "Find the cheapest laptop under $1000"
```

## CLI Output

### Success Example
```
✓ Automation completed successfully! ✨

Statistics:
  • Duration: 12.5s
  • Tasks completed: 3/3
  • Success rate: 100.0%
```

### With Extracted Data
```
✓ Automation completed successfully! ✨

Statistics:
  • Duration: 8.2s
  • Tasks completed: 2/2
  • Success rate: 100.0%

Extracted Data:
  ["Story 1: AI breakthrough", "Story 2: New framework released", ...]
```

## Troubleshooting

### "web_agent package not installed"
```bash
# Install in development mode
pip install -e .
```

### "Invalid URL"
Make sure your URL starts with `http://` or `https://`:
- ✅ `https://www.google.com`
- ❌ `www.google.com`
- ❌ `google.com`

### Browser Not Found
```bash
# Install Playwright browsers
playwright install chromium
```

### Redis Connection Error
```bash
# Start Redis
redis-server

# Or on Linux
sudo systemctl start redis-server
```

### Gemini API Error
Check your `.env` file has valid API key:
```env
GEMINI_API_KEY=your_actual_api_key_here
```

Get your key at: https://aistudio.google.com/app/apikey

## Advanced Usage

### Run in Headless Mode (No Browser Window)
```bash
python cli.py --headless --url "..." --task "..."
```

### Use More Workers for Parallel Tasks
```bash
python cli.py --workers 6 --url "..." --task "..."
```

### Wrapper Script
```bash
# Make it even easier
./automate

# Or add to PATH
export PATH="$PATH:/path/to/web-agent"
automate
```

## Integration with Scripts

### Bash Script
```bash
#!/bin/bash

RESULTS=$(python cli.py \
  --url "https://example.com" \
  --task "Extract product prices" \
  --headless)

echo "Automation results: $RESULTS"
```

### Python Script
```python
import subprocess
import json

result = subprocess.run([
    'python', 'cli.py',
    '--url', 'https://example.com',
    '--task', 'Get all product names',
    '--headless'
], capture_output=True, text=True)

if result.returncode == 0:
    print("Success!")
else:
    print("Failed:", result.stderr)
```

## Exit Codes

- `0`: Success
- `1`: Failure or error

Use exit codes in scripts:
```bash
if python cli.py --url "..." --task "..."; then
    echo "Automation succeeded"
else
    echo "Automation failed"
fi
```

## Tips for Better Results

1. **Be Specific**: Instead of "click the button", say "click the Submit button"
2. **Break Complex Tasks**: For multi-step workflows, be explicit about each step
3. **Use Context**: Mention visual details like "the blue Login button in the top right"
4. **Test Incrementally**: Start with simple tasks, then build complexity
5. **Check Results**: Review the statistics and extracted data

## Need Help?

```bash
# Show all options
python cli.py --help

# Check version
python cli.py --version
```

For issues or questions:
- GitHub Issues: https://github.com/spoloxs/automata/issues
- Documentation: https://github.com/spoloxs/automata/tree/main/web-agent
