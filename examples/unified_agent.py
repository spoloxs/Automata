#!/usr/bin/env python3
"""Unified Agent - Controls both desktop and browser"""
import os
from dotenv import load_dotenv
from desktop_control import DesktopAgent
from web_agent import WebAgent

load_dotenv()

class UnifiedAgent:
    """Agent that can control both desktop and browser"""
    
    def __init__(self, gemini_api_key: str):
        self.api_key = gemini_api_key
        self.desktop_agent = None
        self.web_agent = None
    
    def run_desktop_task(self, task: str):
        """Run task on desktop"""
        if not self.desktop_agent:
            print("Initializing Desktop Agent...")
            self.desktop_agent = DesktopAgent(self.api_key)
        self.desktop_agent.run_task(task)
    
    def run_web_task(self, task: str, start_url: str = "https://www.google.com"):
        """Run task in browser"""
        if not self.web_agent:
            print("Initializing Web Agent...")
            self.web_agent = WebAgent(self.api_key, headless=False)
        self.web_agent.run_task(task, start_url)
    
    def cleanup(self):
        """Cleanup resources"""
        if self.web_agent:
            self.web_agent.driver.quit()


def main():
    """Interactive menu"""
    agent = UnifiedAgent(gemini_api_key=os.getenv("GEMINI_API_KEY"))
    
    while True:
        print("\n" + "="*60)
        print("UNIFIED AGENT - Desktop & Browser Control")
        print("="*60)
        print("1. Desktop task (control entire desktop)")
        print("2. Web task (browser automation)")
        print("3. Exit")
        print("="*60)
        
        choice = input("Select (1-3): ").strip()
        
        if choice == "1":
            task = input("Desktop task: ").strip()
            if task:
                agent.run_desktop_task(task)
        
        elif choice == "2":
            url = input("Start URL (or Enter for Google): ").strip() or "https://www.google.com"
            task = input("Web task: ").strip()
            if task:
                agent.run_web_task(task, url)
        
        elif choice == "3":
            agent.cleanup()
            print("Goodbye!")
            break


if __name__ == "__main__":
    main()
