#!/usr/bin/env python3
"""Optimized Minecraft Launcher Entry Point"""

import sys
from pathlib import Path

# Pre-load critical imports for startup speed
try:
    import aiohttp  # noqa
    import asyncio  # noqa
    import qasync   # noqa
    from PyQt6.QtWidgets import QApplication  # noqa
    from PyQt6.QtCore import QEventLoop  # noqa
except ImportError as e:
    print(f"Critical import failed: {e}")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)

async def main():
    """Main launcher entry point"""
    from src.ui.main import MainWindow

    app = QApplication(sys.argv)

    # Minimal theme load
    theme_path = Path(__file__).parent / "resources" / "themes" / "dark.qss"
    if theme_path.exists():
        with open(theme_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()

    # Create event loop
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        loop.run_forever()

if __name__ == "__main__":
    # Fast startup
    sys.dont_write_bytecode = True
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
