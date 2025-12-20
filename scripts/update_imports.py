#!/usr/bin/env python3
"""
Automatically update all imports to use web_agent package.
"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "web_agent"

# Old → New import mappings
IMPORT_MAP = {
    r'from config\.': 'from web_agent.config.',
    r'from core\.': 'from web_agent.core.',
    r'from planning\.': 'from web_agent.planning.',
    r'from scheduling\.': 'from web_agent.scheduling.',
    r'from execution\.': 'from web_agent.execution.',
    r'from perception\.': 'from web_agent.perception.',
    r'from intelligence\.': 'from web_agent.intelligence.',
    r'from verification\.': 'from web_agent.verification.',
    r'from storage\.': 'from web_agent.storage.',
    r'from utils\.': 'from web_agent.utils.',
    r'import config\.': 'import web_agent.config.',
    r'import core\.': 'import web_agent.core.',
    r'import planning\.': 'import web_agent.planning.',
}

def update_file(filepath: Path):
    """Update imports in a single file"""
    content = filepath.read_text()
    original = content
    
    for old_pattern, new_prefix in IMPORT_MAP.items():
        content = re.sub(old_pattern, new_prefix, content)
    
    if content != original:
        filepath.write_text(content)
        return True
    return False

def main():
    print("🔧 Updating imports to web_agent.*...\n")
    
    updated_files = []
    
    # Update src files
    for py_file in SRC_DIR.rglob("*.py"):
        if update_file(py_file):
            updated_files.append(py_file.relative_to(PROJECT_ROOT))
    
    # Update tests
    for py_file in (PROJECT_ROOT / "tests").rglob("*.py"):
        if update_file(py_file):
            updated_files.append(py_file.relative_to(PROJECT_ROOT))
    
    # Update examples
    for py_file in (PROJECT_ROOT / "examples").rglob("*.py"):
        if update_file(py_file):
            updated_files.append(py_file.relative_to(PROJECT_ROOT))
    
    print(f"✅ Updated {len(updated_files)} files:")
    for f in updated_files:
        print(f"   • {f}")
    
    print("\n✅ Import update complete!")

if __name__ == "__main__":
    main()
