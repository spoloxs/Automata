#!/usr/bin/env python3
"""
Verify that all required files exist and are properly configured.
"""
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Required files structure
REQUIRED_FILES = {
    'config': ['__init__.py', 'settings.py', 'agent_config.py'],
    'core': ['__init__.py', 'master_agent.py', 'worker_agent.py', 'task.py', 'result.py'],
    'planning': ['__init__.py', 'planner.py', 'plan_structures.py', 'dag_converter.py'],
    'scheduling': ['__init__.py', 'scheduler.py', 'dependency_resolver.py'],
    'execution': ['__init__.py', 'action_loop.py', 'action_handler.py', 'browser_controller.py'],
    'perception': ['__init__.py', 'omniparser_wrapper.py', 'screen_parser.py', 'element_formatter.py'],
    'intelligence': ['__init__.py', 'gemini_agent.py', 'prompt_builder.py', 'tool_definitions.py'],
    'verification': ['__init__.py', 'task_verifier.py', 'verification_prompts.py'],
    'storage': ['__init__.py', 'result_store.py', 'worker_memory.py', 'cache.py'],
    'utils': ['__init__.py', 'screenshot.py', 'element_utils.py', 'logging.py', 'metrics.py'],
    'tests/unit': ['__init__.py', 'test_task_dag.py', 'test_worker_memory.py', 
                   'test_planner.py', 'test_scheduler.py', 'test_master_agent.py',
                   'test_worker_agent.py', 'test_omniparser_wrapper.py'],
    'tests/integration': ['__init__.py', 'test_simple_workflow.py'],
    'examples': ['simple_search.py', 'form_filling.py', 'data_extraction.py'],
}

ROOT_FILES = [
    'main.py',
    'requirements.txt',
    'README.md',
    '.env.example',
    '.gitignore',
    'tests/conftest.py'
]


def check_files():
    """Check if all required files exist"""
    missing_files = []
    
    print("🔍 Checking project structure...\n")
    
    # Check directory structure
    for directory, files in REQUIRED_FILES.items():
        dir_path = PROJECT_ROOT / directory
        
        if not dir_path.exists():
            print(f"❌ Missing directory: {directory}/")
            missing_files.append(f"{directory}/")
            continue
        
        print(f"✅ {directory}/")
        
        for file in files:
            file_path = dir_path / file
            if not file_path.exists():
                print(f"   ❌ Missing: {file}")
                missing_files.append(f"{directory}/{file}")
            else:
                print(f"   ✅ {file}")
    
    # Check root files
    print("\n📄 Root files:")
    for file in ROOT_FILES:
        file_path = PROJECT_ROOT / file
        if not file_path.exists():
            print(f"❌ Missing: {file}")
            missing_files.append(file)
        else:
            print(f"✅ {file}")
    
    return missing_files


def check_config():
    """Check if configuration is valid"""
    print("\n⚙️  Checking configuration...")
    
    issues = []
    
    # Check .env
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print("⚠️  No .env file found (using .env.example)")
        issues.append("Create .env from .env.example")
    else:
        with open(env_file) as f:
            content = f.read()
            if 'GEMINI_API_KEY=' not in content or 'GEMINI_API_KEY=your_api_key' in content:
                print("⚠️  GEMINI_API_KEY not configured in .env")
                issues.append("Set GEMINI_API_KEY in .env")
            else:
                print("✅ GEMINI_API_KEY configured")
    
    # Check OmniParser
    omniparser_weights = PROJECT_ROOT / "OmniParser" / "weights"
    if not omniparser_weights.exists():
        print("⚠️  OmniParser weights not found")
        issues.append("Download OmniParser weights")
    else:
        print("✅ OmniParser weights directory exists")
    
    return issues


def main():
    """Main verification"""
    print("="*60)
    print("WEB AUTOMATION SYSTEM - SETUP VERIFICATION")
    print("="*60 + "\n")
    
    # Check files
    missing_files = check_files()
    
    # Check config
    config_issues = check_config()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if not missing_files and not config_issues:
        print("✅ All files present and configuration looks good!")
        print("\nYou can now run:")
        print("  python main.py")
        return 0
    else:
        print(f"❌ Found {len(missing_files)} missing files")
        print(f"⚠️  Found {len(config_issues)} configuration issues")
        
        if missing_files:
            print("\nMissing files:")
            for f in missing_files:
                print(f"  - {f}")
        
        if config_issues:
            print("\nConfiguration issues:")
            for issue in config_issues:
                print(f"  - {issue}")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
