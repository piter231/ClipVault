import sys
import sqlite3
import mmap
import tempfile
import os
from datetime import datetime
from collections import OrderedDict
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QClipboard, QImage, QIcon, QPixmap, QPainter
from PyQt5.QtCore import QBuffer, QIODevice, QUrl, QMimeData, QTimer, Qt
from PIL import Image
import io
import shutil

class ClipVault:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.clipboard = QApplication.clipboard()
        self.history = []
        
        self.data_dir = "clipvault_data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.create_low_memory_icon())
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        
        self.db = sqlite3.connect('clipvault.db')
        self.ensure_schema()
        self.load_history()
        
        self.lru_cache = OrderedDict()
        self.cache_size = 10  
        
        self.clipboard.dataChanged.connect(self.check_clipboard)
        
        self.mem_log = open("memory.log", "w")
        QTimer.singleShot(1000, self.log_memory)
        
    def create_low_memory_icon(self):
        """Create a low-memory icon (16x16 mono)"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        painter.setPen(Qt.darkGray)
        painter.setBrush(Qt.lightGray)
        painter.drawRect(1, 1, 14, 12)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.white)
        painter.drawRect(3, 3, 10, 8)
        
        painter.setPen(Qt.darkGray)
        painter.setBrush(Qt.gray)
        painter.drawEllipse(7, 0, 4, 4)
        
        painter.end()
        return QIcon(pixmap)
    
    def log_memory(self):
        """Log memory usage every second"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem = process.memory_info().rss / 1024 ** 2  # MB
            self.mem_log.write(f"{datetime.now().isoformat()},{mem:.2f}\n")
            self.mem_log.flush()
        except ImportError:
            pass  
        
        QTimer.singleShot(1000, self.log_memory)
    
    def ensure_schema(self):
        """Ensure database schema has all required columns"""
        self.db.execute('''CREATE TABLE IF NOT EXISTS clips(
            id INTEGER PRIMARY KEY,
            content BLOB,
            type TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pinned INTEGER DEFAULT 0
        )''')
        
        columns_to_add = [
            ('preview', 'TEXT'),
            ('storage', 'TEXT'),
            ('size', 'INTEGER')
        ]
        
        cursor = self.db.execute("PRAGMA table_info(clips)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        for col, col_type in columns_to_add:
            if col not in existing_columns:
                try:
                    self.db.execute(f"ALTER TABLE clips ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass  
        
        self.db.commit()
    
    def compress_image(self, img_data):
        """Compress image to JPEG with 85% quality"""
        try:
            img = Image.open(io.BytesIO(img_data))
            output = io.BytesIO()
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            img.save(output, format="JPEG", quality=85)
            return output.getvalue()
        except Exception as e:
            print(f"Image compression error: {e}")
            return img_data  
    
    def store_content(self, content, ctype):
        """Store content with memory optimizations"""
        if isinstance(content, str):
            content = content.encode('utf-8')
        size = len(content)
        preview = ""
        storage = 'db'
        file_path = None
        
        if ctype == 'text':
            try:
                text_content = content.decode('utf-8', errors='replace')
                preview = text_content[:100] + ('...' if len(text_content) > 100 else '')
            except:
                preview = "Text content"
        elif ctype == 'file':
            try:
                file_paths = content.decode('utf-8', errors='replace')
                preview = f"File: {file_paths.splitlines()[0][:30]}..."
            except:
                preview = "File content"
        else:  
            preview = f"Image ({size//1024} KB)"
            
            if size > 1024:
                compressed = self.compress_image(content)
                if len(compressed) < size:
                    content = compressed
                    size = len(content)
                    preview = f"Image ({size//1024} KB compressed)"
        
        if size > 1024 * 1024:
            file_path = os.path.join(self.data_dir, f"temp_{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
            with open(file_path, 'wb') as f:
                f.write(content)
            
            storage = 'file'
            if size > 10 * 1024 * 1024: 
                storage = 'mmap'
            
            self.db.execute('''INSERT INTO clips (preview, type, storage, size, content) 
                            VALUES (?, ?, ?, ?, ?)''', 
                           (preview, ctype, storage, size, file_path))
        else:
            self.db.execute('''INSERT INTO clips (content, preview, type, storage, size) 
                            VALUES (?, ?, ?, ?, ?)''', 
                           (content, preview, ctype, storage, size))
        
        self.db.commit()
        return preview
    
    def get_content(self, id):
        """Retrieve content with LRU caching"""
        if id in self.lru_cache:
            content = self.lru_cache.pop(id)
            self.lru_cache[id] = content
            return content
        
        row = self.db.execute('''SELECT content, type, storage 
                              FROM clips WHERE id = ?''', (id,)).fetchone()
        if not row:
            return None
        
        content, ctype, storage = row
        
        if storage == 'file':
            with open(content, 'rb') as f:
                content = f.read()
        elif storage == 'mmap':
            with open(content, 'rb') as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    content = mm.read()
        
        self.lru_cache[id] = content
        if len(self.lru_cache) > self.cache_size:
            self.lru_cache.popitem(last=False)  
        
        return content
    
    def load_history(self):
        """Load history previews for GUI"""
        cur = self.db.execute('''SELECT id, preview, type 
                              FROM clips 
                              ORDER BY created DESC 
                              LIMIT 50''')
        self.history = []
        for row in cur.fetchall():
            self.history.append((row[0], row[1], row[2])) 
        self.update_menu()
    
    def check_clipboard(self):
        """Capture clipboard content with optimizations"""
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
            preview = self.store_content(content, ctype)
            self.load_history()
            print(f"Captured: {preview}")
    
    def update_menu(self):
        """Update tray menu with history items"""
        self.menu.clear()
        
        for i, (id, preview, ctype) in enumerate(self.history[:10]):
            action = QAction(f"{i+1}: {preview}", self.menu)
            action.triggered.connect(lambda checked, id=id: self.paste_item(id))
            self.menu.addAction(action)
        
        self.menu.addSeparator()
        exit_action = QAction("Exit", self.menu)
        exit_action.triggered.connect(self.app.quit)
        self.menu.addAction(exit_action)
    
    def paste_item(self, id):
        """Paste item back to clipboard"""
        content = self.get_content(id)
        if not content:
            return
        
        ctype = next((t for i, p, t in self.history if i == id), None)
        
        if ctype == 'text':
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')
            self.clipboard.setText(content)
        elif ctype == 'file':
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')
            urls = [QUrl(path.strip()) for path in content.splitlines()]
            mime = QMimeData()
            mime.setUrls(urls)
            self.clipboard.setMimeData(mime)
        else:  
            img = QImage()
            img.loadFromData(content)
            self.clipboard.setImage(img)
    
    def cleanup(self):
        """Clean up resources on exit"""
        self.mem_log.close()
        if os.path.exists(self.data_dir):
            shutil.rmtree(self.data_dir)
    
    def run(self):
        """Start application"""
        self.app.aboutToQuit.connect(self.cleanup)
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "1"
    
    vault = ClipVault()
    vault.run()