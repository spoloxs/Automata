#!/usr/bin/env python3
"""
Example tasks for the Web Agent
Demonstrates various automation scenarios
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


from web_agent import WebAgent


def example_google_search():
    """Example: Search on Google"""
    load_dotenv()

    agent = WebAgent(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        headless=False,
        window_size=(1280, 720),
    )

    try:
        task = (
            "Search for 'Python Selenium tutorial' on Google and click the first result"
        )
        agent.run_task(task, start_url="https://www.google.com")

        input("\nPress Enter to close browser...")
    finally:
        agent.close()


def example_amazon_search():
    """Example: Search on Amazon"""
    load_dotenv()

    agent = WebAgent(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        headless=False,
        window_size=(1280, 720),
    )

    try:
        task = "Search for 'wireless headphones' and sort by price low to high"
        agent.run_task(task, start_url="https://www.amazon.com")

        input("\nPress Enter to close browser...")
    finally:
        agent.close()


def example_github_navigate():
    """Example: Navigate GitHub"""
    load_dotenv()

    agent = WebAgent(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        headless=False,
        window_size=(1280, 720),
    )

    try:
        task = "Go to the Explore page and find trending Python repositories"
        agent.run_task(task, start_url="https://github.com")

        input("\nPress Enter to close browser...")
    finally:
        agent.close()


def example_wikipedia_read():
    """Example: Read Wikipedia article"""
    load_dotenv()

    agent = WebAgent(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        headless=False,
        window_size=(1280, 720),
    )

    try:
        task = "Search for 'Artificial Intelligence' and open the article"
        agent.run_task(task, start_url="https://www.wikipedia.org")

        input("\nPress Enter to close browser...")
    finally:
        agent.close()


def example_youtube_search():
    """Example: Search YouTube"""
    load_dotenv()

    agent = WebAgent(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        headless=False,
        window_size=(1280, 720),
    )

    try:
        task = "Search for 'Python programming tutorial' and click on the first video"
        agent.run_task(task, start_url="https://www.youtube.com")

        input("\nPress Enter to close browser...")
    finally:
        agent.close()


def example_form_filling():
    """Example: Fill out a form"""
    load_dotenv()

    agent = WebAgent(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        headless=False,
        window_size=(1280, 720),
    )

    try:
        # Using a test form website
        task = (
            "Fill in the name field with 'John Doe' and email with 'john@example.com'"
        )
        agent.run_task(task, start_url="https://www.w3schools.com/html/html_forms.asp")

        input("\nPress Enter to close browser...")
    finally:
        agent.close()


def example_custom_task():
    """Example: Custom task from user input"""
    load_dotenv()

    print("=" * 60)
    print("Custom Web Agent Task")
    print("=" * 60)

    url = input("\nEnter starting URL (or press Enter for Google): ").strip()
    if not url:
        url = "https://www.google.com"

    task = input("Enter your task: ").strip()
    if not task:
        print("No task provided. Exiting.")
        return

    agent = WebAgent(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        headless=False,
        window_size=(1280, 720),
    )

    try:
        agent.run_task(task, start_url=url)

        input("\nPress Enter to close browser...")
    finally:
        agent.close()


def main():
    """Main menu"""
    examples = {
        "1": ("Google Search", example_google_search),
        "2": ("Amazon Product Search", example_amazon_search),
        "3": ("GitHub Explore", example_github_navigate),
        "4": ("Wikipedia Article", example_wikipedia_read),
        "5": ("YouTube Search", example_youtube_search),
        "6": ("Form Filling", example_form_filling),
        "7": ("Custom Task", example_custom_task),
    }

    print("\n" + "=" * 60)
    print("Web Agent Examples")
    print("=" * 60)
    print("\nChoose an example:")

    for key, (name, _) in examples.items():
        print(f"{key}. {name}")

    print("0. Exit")

    choice = input("\nEnter your choice: ").strip()

    if choice == "0":
        print("Goodbye!")
        return

    if choice in examples:
        _, func = examples[choice]
        try:
            func()
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback

            traceback.print_exc()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
