"""Authentication dialog placeholder."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton


class AuthDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.username = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Authenticate")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Offline Mode:"))
        self.username_input = QLineEdit()
        layout.addWidget(self.username_input)
        
        btn_layout = QVBoxLayout()
        ms_btn = QPushButton("Microsoft Login")
        btn_layout.addWidget(ms_btn)
        
        offline_btn = QPushButton("Offline Login")
        offline_btn.clicked.connect(self.offline_auth)
        btn_layout.addWidget(offline_btn)
        
        layout.addWidget(QVBoxLayout())  # placeholder
        
        self.setLayout(layout)
    
    def offline_auth(self):
        self.username = self.username_input.text()
        self.accept()
