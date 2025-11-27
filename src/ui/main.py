"""Main UI window for the launcher."""

import sys
import asyncio
from pathlib import Path
from typing import Optional
from qasync import QEventLoop, QThreadExecutor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QTextEdit, QProgressBar, QLabel, QSplitter, QListWidget,
    QStatusBar
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette


class VersionThread(QThread):
    """Thread for loading versions."""
    versions_loaded = pyqtSignal(list)
    versions_failed = pyqtSignal(str)

    def run(self):
        asyncio.run(self.load_versions_async())

    async def load_versions_async(self):
        try:
            from src.versions import VersionManager
            async with VersionManager() as vm:
                manifest = await vm.fetch_manifest()
                versions = [v.id for v in manifest.versions]
                self.versions_loaded.emit(versions)
        except Exception as e:
            self.versions_failed.emit(str(e))


class LauncherThread(QThread):
    """Worker thread for launcher operations."""
    auth_complete = pyqtSignal(dict)
    auth_failed = pyqtSignal(str)

    def __init__(self, auth_type: str, *args):
        super().__init__()
        self.auth_type = auth_type
        self.args = args

    async def run_auth(self):
        """Run authentication in thread."""
        try:
            from src.auth import MicrosoftAuthenticator, OfflineAuthenticator

            if self.auth_type == "microsoft":
                auth = MicrosoftAuthenticator()
                profile = await auth.authenticate_full_flow()
                self.auth_complete.emit(profile)
            elif self.auth_type == "offline":
                username, = self.args
                profile = await OfflineAuthenticator.authenticate(username)
                self.auth_complete.emit(profile)
        except Exception as e:
            self.auth_failed.emit(str(e))

    def run(self):
        asyncio.run(self.run_auth())


class LaunchThread(QThread):
    """Thread for launching Minecraft."""
    launch_started = pyqtSignal()
    launch_progress = pyqtSignal(str, int, int)  # text, current, total
    launch_complete = pyqtSignal()
    launch_failed = pyqtSignal(str)

    def __init__(self, version_id: str, profile: dict):
        super().__init__()
        self.version_id = version_id
        self.profile = profile

    async def launch_game_async(self):
        """Launch the game asynchronously."""
        try:
            self.launch_started.emit()

            from src.runtime import JavaManager
            from src.versions import VersionManager, DownloadManager

            # Step 1: Ensure Java
            self.launch_progress.emit("Checking Java...", 10, 100)
            jm = JavaManager()
            java_path = await jm.ensure_java()

            # Step 2: Get version metadata
            self.launch_progress.emit("Fetching version metadata...", 20, 100)
            async with VersionManager() as vm:
                version_info = await vm.get_version_info(self.version_id)
                metadata = await vm.fetch_version_metadata(version_info)

                # Filter libraries
                applicable_libs = await vm.filter_applicable_libraries(metadata)

            # Step 3: Download dependencies
            self.launch_progress.emit("Downloading libraries...", 30, 100)
            async with DownloadManager() as dm:
                lib_results = await dm.download_libraries(applicable_libs)
                # Check for failures
                failed_libs = [r for r in lib_results if isinstance(r, Exception)]
                if failed_libs:
                    self.launch_failed.emit(f"Failed to download {len(failed_libs)} libraries")
                    return

                # Download client JAR (optional for very old versions)
                jar_success = await dm.download_version_jar(metadata)
                # Don't fail for JAR download - some old versions might not have proper download URLs
                # The launcher will try to find JAR locally or handle it differently

                # Download assets
                self.launch_progress.emit("Downloading assets...", 60, 100)
                if hasattr(dm, 'download_asset_index'):
                    asset_index = await dm.download_asset_index(metadata)
                    if asset_index:
                        asset_results = await dm.download_assets(asset_index)
                        # Assets are optional, continue even if some fail

            # Step 4: Launch game
            self.launch_progress.emit("Launching Minecraft...", 80, 100)
            from src.core import GameLauncher
            launcher = GameLauncher()
            launch_data = launcher.prepare_launch(metadata, applicable_libs, self.profile, str(java_path))

            # Start the process
            game_process = launcher.launch_game(launch_data)

            self.launch_progress.emit("Minecraft started!", 100, 100)
            self.launch_complete.emit()

            # Monitor process (optional)
            # In a full launcher, you'd keep this thread alive to monitor the game process

        except Exception as e:
            self.launch_failed.emit(str(e))

    def run(self):
        asyncio.run(self.launch_game_async())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_profile = None
        self.version_manager = None
        self.version_manifest = None

        self.init_ui()
        self.init_async()
        self.load_versions()
        
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Custom Minecraft Launcher")
        self.setGeometry(100, 100, 1000, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Top bar
        top_layout = QHBoxLayout()
        
        self.account_combo = QComboBox()
        self.account_combo.addItem("Select Account...")
        top_layout.addWidget(QLabel("Account:"))
        top_layout.addWidget(self.account_combo)
        
        self.auth_btn = QPushButton("Login")
        self.auth_btn.clicked.connect(self.start_auth)
        top_layout.addWidget(self.auth_btn)
        
        top_layout.addStretch()
        
        self.launch_btn = QPushButton("Launch Minecraft")
        self.launch_btn.setEnabled(False)
        self.launch_btn.clicked.connect(self.launch_game)
        top_layout.addWidget(self.launch_btn)
        
        layout.addLayout(top_layout)
        
        # Main content splitter
        splitter = QSplitter()
        
        # Left panel - instances/mods
        self.instance_list = QListWidget()
        self.instance_list.addItem("Default Instance")
        splitter.addWidget(self.instance_list)
        
        # Right panel - version selection and log
        right_panel = QVBoxLayout()
        
        version_layout = QHBoxLayout()
        version_layout.addWidget(QLabel("Version:"))
        self.version_combo = QComboBox()
        self.version_combo.addItem("Loading versions...")
        version_layout.addWidget(self.version_combo)
        
        right_panel.addLayout(version_layout)
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        right_panel.addWidget(self.console)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_panel.addWidget(self.progress_bar)
        
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        splitter.addWidget(right_widget)
        
        layout.addWidget(splitter)
        
        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")
    
    def init_async(self):
        """Initialize async components."""
        self.loop = asyncio.new_event_loop()

    def load_versions(self):
        """Load Minecraft versions in background."""
        self.status.showMessage("Loading versions...")
        self.version_combo.clear()
        self.version_combo.addItem("Loading versions...")

        self.version_thread = VersionThread()
        self.version_thread.versions_loaded.connect(self.on_versions_loaded)
        self.version_thread.versions_failed.connect(self.on_versions_failed)
        self.version_thread.start()
    
    def start_auth(self):
        """Start authentication process."""
        # Use offline auth for demo (Microsoft auth requires app registration)
        self.auth_btn.setEnabled(False)
        self.status.showMessage("Authenticating...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        self.auth_thread = LauncherThread("offline", "Player123")  # Demo username
        self.auth_thread.auth_complete.connect(self.on_auth_success)
        self.auth_thread.auth_failed.connect(self.on_auth_error)
        self.auth_thread.start()
    
    def on_auth_success(self, profile):
        self.current_profile = profile
        self.account_combo.clear()
        self.account_combo.addItem(f"{profile['name']}")
        self.launch_btn.setEnabled(True)
        self.auth_btn.setEnabled(True)
        self.status.showMessage(f"Logged in as {profile['name']}")
        self.progress_bar.setVisible(False)

        # Success animation for auth button
        self.animate_button_success(self.auth_btn)
        self.animate_status_bar_color("#38a169", "#2f855a")
    
    def on_auth_error(self, error):
        self.console.append(f"Auth error: {error}")
        self.auth_btn.setEnabled(True)
        self.status.showMessage("Auth failed")
        self.progress_bar.setVisible(False)
    
    def launch_game(self):
        """Launch the game."""
        if not self.current_profile:
            self.console.append("Please log in first")
            return

        selected_version = self.version_combo.currentText()
        if not selected_version or selected_version == "Loading versions..." or selected_version == "Failed to load versions":
            self.console.append("Please select a version to launch")
            return

        self.console.append(f"Launching Minecraft {selected_version}...")
        self.launch_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)

        self.launch_thread = LaunchThread(selected_version, self.current_profile)
        self.launch_thread.launch_started.connect(self.on_launch_started)
        self.launch_thread.launch_progress.connect(self.on_launch_progress)
        self.launch_thread.launch_complete.connect(self.on_launch_complete)
        self.launch_thread.launch_failed.connect(self.on_launch_failed)
        self.launch_thread.start()
    
    def on_versions_loaded(self, versions):
        """Handle loaded versions."""
        self.version_combo.clear()
        for version in sorted(versions, reverse=True)[:20]:  # Top 20 recent versions
            self.version_combo.addItem(version)
        self.status.showMessage("Ready")

    def on_versions_failed(self, error):
        """Handle version loading failure."""
        self.console.append(f"Failed to load versions: {error}")
        self.version_combo.clear()
        self.version_combo.addItem("Failed to load versions")
        self.status.showMessage("Error loading versions")

    def on_launch_started(self):
        """Handle launch started."""
        self.console.append("Launch process started...")

    def on_launch_progress(self, text, current, total):
        """Handle launch progress update."""
        self.status.showMessage(text)
        self.progress_bar.setValue(current)
        self.console.append(text)

    def on_launch_complete(self):
        """Handle launch completion."""
        self.console.append("Minecraft launched successfully!")
        self.status.showMessage("Minecraft Running")
        self.progress_bar.setVisible(False)
        self.launch_btn.setEnabled(True)

    def append_console(self, text):
        """Append text to console with timestamp."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console.append(f"[{timestamp}] {text}")

    def on_launch_failed(self, error):
        """Handle launch failure."""
        self.console.append(f"Launch failed: {error}")
        self.status.showMessage("Launch Failed")
        self.progress_bar.setVisible(False)
        self.launch_btn.setEnabled(True)

    def animate_button_success(self, button: QPushButton):
        """Animate button with success color flash."""
        original_style = button.styleSheet()
        success_style = """
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                        stop:0 #38a169, stop:1 #2f855a);
            border: 2px solid #38a169;
            border-radius: 8px;
            color: #ffffff;
        }
        """

        button.setStyleSheet(success_style)

        # Reset after animation
        QTimer.singleShot(800, lambda: button.setStyleSheet(original_style))

    def animate_status_bar_color(self, start_color: str, end_color: str):
        """Animate status bar color change (placeholder for more complex animation)."""
        # For now, just ensure the status bar updates
        # Full animation would require palette manipulation
        pass

    def closeEvent(self, event):
        self.loop.stop()
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)

    # Apply dark theme
    theme_path = Path(__file__).parent.parent / "resources" / "themes" / "dark.qss"
    if theme_path.exists():
        with open(theme_path, 'r') as f:
            app.setStyleSheet(f.read())

    # Set up event loop
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
