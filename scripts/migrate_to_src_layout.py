#!/usr/bin/env python3
"""
Migrate to src layout (Python Packaging Authority recommended).
Run this ONCE to restructure the project.
"""
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "web_agent"

# Directories to move into src/web_agent/
CORE_DIRS = [
    "config", "core", "planning", "scheduling", "execution",
    "perception", "intelligence", "verification", "storage", "utils"
]

# Stay at root
STAY_AT_ROOT = ["tests", "examples", "OmniParser", "logs", "screenshots", "data"]

def migrate():
    print("🔄 Migrating to src layout (PyPA recommended)...\n")
    
    # 1. Create src/web_agent
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✅ Created {SRC_DIR.relative_to(PROJECT_ROOT)}/")
    
    # 2. Move core directories
    for dirname in CORE_DIRS:
        src_path = PROJECT_ROOT / dirname
        dst_path = SRC_DIR / dirname
        
        if src_path.exists() and src_path.is_dir():
            if dst_path.exists():
                shutil.rmtree(dst_path)
            shutil.move(str(src_path), str(dst_path))
            print(f"   📦 Moved {dirname}/ → src/web_agent/{dirname}/")
    
    # 3. Create src/web_agent/__init__.py
    init_content = '''"""
Web Agent - Multi-agent web automation system.

Official Python Packaging Authority src layout.
"""
__version__ = "0.1.0"

from web_agent.core.master_agent import MasterAgent
from web_agent.core.worker_agent import WorkerAgent

__all__ = ["MasterAgent", "WorkerAgent"]
'''
    (SRC_DIR / "__init__.py").write_text(init_content)
    print(f"   ✅ Created src/web_agent/__init__.py")
    
    # 4. Move main.py to src/web_agent/cli.py
    if (PROJECT_ROOT / "main.py").exists():
        shutil.copy(PROJECT_ROOT / "main.py", SRC_DIR / "cli.py")
        print(f"   📄 Copied main.py → src/web_agent/cli.py")
    
    print("\n✅ Migration complete!")
    print("\n📋 Next steps:")
    print("   1. pip install -e .")
    print("   2. Update imports (see update_imports.py)")
    print("   3. pytest -m unit")

if __name__ == "__main__":
    migrate()
