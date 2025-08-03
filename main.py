import sys
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt5.QtGui import QClipboard, QImage, QPixmap
from PyQt5.QtCore import QBuffer, QIODevice, QByteArray, QUrl, QMimeData

class ClipVault:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.clipboard = QApplication.clipboard()
        self.history = []
        
        self.tray = QSystemTrayIcon()
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        
        self.db = sqlite3.connect('clipvault.db')
        self.ensure_schema()
        self.load_history()
        
        self.clipboard.dataChanged.connect(self.check_clipboard)
        
    def ensure_schema(self):
        """Ensure database schema is correct with all required columns"""
        self.db.execute('''CREATE TABLE IF NOT EXISTS clips(
            id INTEGER PRIMARY KEY,
            content BLOB,
            type TEXT
        )''')
        
        columns_to_add = [
            ('created', 'TIMESTAMP', 'DEFAULT CURRENT_TIMESTAMP'),
            ('pinned', 'INTEGER', 'DEFAULT 0')
        ]
        
        cursor = self.db.execute("PRAGMA table_info(clips)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        for col, col_type, extras in columns_to_add:
            if col not in existing_columns:
                try:
                    self.db.execute(f"ALTER TABLE clips ADD COLUMN {col} {col_type} {extras}")
                except sqlite3.OperationalError:
                    pass
        
        self.db.commit()
    
    def load_history(self):
        """Load history from database"""
        cur = self.db.execute('''SELECT content, type 
                              FROM clips 
                              ORDER BY COALESCE(created, '1970-01-01') DESC 
                              LIMIT 50''')
        self.history = []
        for row in cur.fetchall():
            self.history.append((row[0], row[1]))
        self.update_menu()
    
    def check_clipboard(self):
        """Capture clipboard content"""
        mime = self.clipboard.mimeData()
        content = None
        ctype = None
        
        if mime.hasText():
            content = mime.text()
            ctype = 'text'
        elif mime.hasImage():
            img = self.clipboard.image()
            buffer = QBuffer()
            buffer.open(QBuffer.ReadWrite)
            img.save(buffer, "PNG")
            content = bytes(buffer.data())
            ctype = 'image'
        elif mime.hasUrls():
            urls = [url.toString() for url in mime.urls()]
            content = "\n".join(urls)
            ctype = 'file'
        
        if content and ctype:
            self.db.execute('''INSERT INTO clips (content, type, created) 
                            VALUES (?, ?, ?)''', 
                           (content, ctype, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.db.commit()
            self.load_history()
    
    def update_menu(self):
        """Update tray menu with history"""
        self.menu.clear()
        for i, (content, ctype) in enumerate(self.history[:10]):
            if ctype == 'text':
                preview = content[:20] + '...' if len(content) > 20 else content
            elif ctype == 'file':
                preview = "File: " + content.split("\n")[0][:20] + '...'
            else: 
                preview = f"Image ({len(content)//1024} KB)"
                
            action = self.menu.addAction(f"{i+1}: {preview}")
            action.triggered.connect(lambda checked, c=content, t=ctype: self.paste(c, t))
        
        self.menu.addSeparator()
        self.menu.addAction("Exit", self.app.quit)
    
    def paste(self, content, ctype):
        """Paste item back to clipboard"""
        if ctype == 'text':
            self.clipboard.setText(content)
        elif ctype == 'file':
            urls = [QUrl(path.strip()) for path in content.split("\n")]
            mime = QMimeData()
            mime.setUrls(urls)
            self.clipboard.setMimeData(mime)
        else:  
            img = QImage()
            img.loadFromData(content)
            self.clipboard.setImage(img)
    
    def run(self):
        """Start application"""
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    vault = ClipVault()
    vault.run()