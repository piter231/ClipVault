import sys
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QClipboard

class ClipVault:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.clipboard = QApplication.clipboard()
        self.history = [] 
        
        self.tray = QSystemTrayIcon()
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        
        self.clipboard.dataChanged.connect(self.check_clipboard)
    def check_clipboard(self):
        text = self.clipboard.text()
        if text and text not in self.history:
            self.history.append(text)
            self.update_menu()
            print(f"Captured: {text[:20]}...") 
    
    def update_menu(self):
        self.menu.clear()
        for i, item in enumerate(self.history[-5:]): 
            self.menu.addAction(f"{i+1}: {item[:10]}...")
    
    def run(self):
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    vault = ClipVault()
    vault.run()