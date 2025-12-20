#!/usr/bin/env python3
"""
Quick Start Script for Web Agent
Simple interface to test the web automation agent
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
from web_agent import WebAgent


def main():
    """Quick start demo"""
    load_dotenv()

    # Check for API key
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ Error: GEMINI_API_KEY not found in environment variables")
        print("\nPlease create a .env file with:")
        print("GEMINI_API_KEY=your_api_key_here")
        print("\nGet your API key from: https://aistudio.google.com/app/apikey")
        return

    print("\n" + "=" * 70)
    print("🚀 WEB AGENT - QUICK START")
    print("=" * 70)
    print("\nThis agent uses:")
    print("  • OmniParser for visual understanding")
    print("  • Gemini AI for decision making")
    print("  • Selenium for browser control")
    print("\n" + "=" * 70)

    # Get user input
    print("\nEnter the task you want to automate:")
    print("Examples:")
    print("  - Search for 'Python tutorials' on Google")
    print("  - Go to GitHub and find trending Python repos")
    print("  - Search for 'laptop' on Amazon")
    print()

    task = input("Your task: ").strip()
    if not task:
        print("No task provided. Using default task.")
        task = "Search for 'OpenAI' on Google and click the first result"

    print(f"\n✓ Task: {task}")

    # Get starting URL
    url = input("\nStarting URL (press Enter for Google): ").strip()
    if not url:
        url = "https://www.google.com"

    print(f"✓ Starting URL: {url}")

    # Ask about headless mode
    headless_input = input("\nRun in headless mode? (y/N): ").strip().lower()
    headless = headless_input == "y"

    print("\n" + "=" * 70)
    print("🤖 Initializing Web Agent...")
    print("=" * 70 + "\n")

    # Create and run agent with GPU parser
    agent = WebAgent(
        gemini_api_key=gemini_api_key,
        headless=headless,
        window_size=(1280, 720),
        show_pointer=False,
        pointer_delay=0.8,
        thread_id="quick_start",
        enable_ocr=True,  # GPU-accelerated OCR enabled
        use_gpu_parser=True,  # Use GPU parser (EasyOCR + YOLO)
    )

    try:
        agent.run_task(task, start_url=url)

        if not headless:
            print("\n" + "=" * 70)
            input("Press Enter to close browser...")

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        agent.close()
        print("\n✅ Done!")


if __name__ == "__main__":
    main()
