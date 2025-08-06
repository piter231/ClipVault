import sys
import sqlite3
import mmap
import os
import shutil
from datetime import datetime
from collections import OrderedDict
from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QLineEdit, QComboBox, QCheckBox, QSlider, QTabWidget
)
from PyQt5.QtGui import (
    QClipboard, QImage, QIcon, QPixmap, QPainter, QFont, QPalette, QColor
)
from PyQt5.QtCore import (
    QBuffer, QIODevice, QUrl, QMimeData, QTimer, Qt, QSize
)
from PIL import Image
import io

class ClipVaultGUI(QMainWindow):
    def __init__(self, vault):
        super().__init__()
        self.vault = vault
        self.setWindowTitle("ClipVault")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("""
            QMainWindow, QWidget {background-color: #F0F0F0;font-family: Arial;}
            QListWidget {background-color: white;border: 1px solid #CCCCCC;
                font-size: 12px;alternate-background-color: #F9F9F9;}
            QTabWidget::pane {border: 0;}
            QTabBar::tab {background: #E0E0E0;padding: 8px 15px;
                border: 1px solid #CCCCCC;border-bottom: none;
                border-top-left-radius: 4px;border-top-right-radius: 4px;}
            QTabBar::tab:selected {background: white;border-bottom: 2px solid #4CAF50;}
            QPushButton {background-color: #4CAF50;color: white;border: none;
                padding: 5px 10px;border-radius: 3px;}
            QPushButton:hover {background-color: #45a049;}
            QListWidgetItem[pinned=true] {font-weight: bold;color: #d35400;}
        """)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)
        self.history_tab = self._create_history_tab()
        self.pinned_tab = self._create_pinned_tab()
        self.settings_tab = self._create_settings_tab()
        self.tab_widget.addTab(self.history_tab, "History")
        self.tab_widget.addTab(self.pinned_tab, "Pinned")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        self.status_bar = self.statusBar()
        self.update_status("Ready")
        self.refresh_data()
    
    def _create_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search history...")
        self.search_input.textChanged.connect(self.filter_history)
        search_layout.addWidget(self.search_input)
        clear_btn = QPushButton("Clear Unpinned")
        clear_btn.clicked.connect(self.clear_unpinned)
        search_layout.addWidget(clear_btn)
        layout.addLayout(search_layout)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.paste_selected)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_history_context_menu)
        self.history_list.setAlternatingRowColors(True)
        layout.addWidget(self.history_list)
        return tab
    
    def _create_pinned_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.pinned_list = QListWidget()
        self.pinned_list.itemDoubleClicked.connect(self.paste_selected)
        self.pinned_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pinned_list.customContextMenuRequested.connect(self.show_pinned_context_menu)
        self.pinned_list.setAlternatingRowColors(True)
        layout.addWidget(self.pinned_list)
        return tab
    
    def _create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        mem_group = QWidget()
        mem_layout = QVBoxLayout(mem_group)
        mem_layout.addWidget(QLabel("<b>Memory Optimization</b>"))
        cache_layout = QHBoxLayout()
        cache_layout.addWidget(QLabel("Cache Size:"))
        self.cache_size = QSlider(Qt.Horizontal)
        self.cache_size.setMinimum(5)
        self.cache_size.setMaximum(50)
        self.cache_size.setValue(self.vault.cache_size)
        self.cache_size.valueChanged.connect(self.update_cache_size)
        cache_layout.addWidget(self.cache_size)
        self.cache_label = QLabel(f"{self.vault.cache_size} items")
        cache_layout.addWidget(self.cache_label)
        mem_layout.addLayout(cache_layout)
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Image Quality:"))
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setMinimum(50)
        self.quality_slider.setMaximum(100)
        self.quality_slider.setValue(self.vault.image_quality)
        self.quality_slider.valueChanged.connect(self.update_image_quality)
        quality_layout.addWidget(self.quality_slider)
        self.quality_label = QLabel(f"{self.vault.image_quality}%")
        quality_layout.addWidget(self.quality_label)
        mem_layout.addLayout(quality_layout)
        layout.addWidget(mem_group)
        auto_clear = QCheckBox("Auto-clear temporary items after 24 hours")
        auto_clear.setChecked(True)
        layout.addWidget(auto_clear)
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        layout.addStretch()
        return tab
    
    def show_history_context_menu(self, pos):
        item = self.history_list.itemAt(pos)
        if not item: return
        id = item.data(Qt.UserRole)
        menu = QMenu()
        if self.vault.is_pinned(id):
            unpin_action = QAction("Unpin", menu)
            unpin_action.triggered.connect(lambda: self.toggle_pin(id))
            menu.addAction(unpin_action)
        else:
            pin_action = QAction("Pin", menu)
            pin_action.triggered.connect(lambda: self.toggle_pin(id))
            menu.addAction(pin_action)
        delete_action = QAction("Delete", menu)
        delete_action.triggered.connect(lambda: self.delete_item(id))
        menu.addAction(delete_action)
        menu.exec_(self.history_list.mapToGlobal(pos))
    
    def show_pinned_context_menu(self, pos):
        item = self.pinned_list.itemAt(pos)
        if not item: return
        id = item.data(Qt.UserRole)
        menu = QMenu()
        unpin_action = QAction("Unpin", menu)
        unpin_action.triggered.connect(lambda: self.toggle_pin(id))
        menu.addAction(unpin_action)
        delete_action = QAction("Delete", menu)
        delete_action.triggered.connect(lambda: self.delete_item(id))
        menu.addAction(delete_action)
        menu.exec_(self.pinned_list.mapToGlobal(pos))
    
    def toggle_pin(self, id):
        self.vault.toggle_pin(id)
        self.refresh_data()
    
    def delete_item(self, id):
        self.vault.delete_item(id)
        self.refresh_data()
    
    def filter_history(self):
        search_term = self.search_input.text().lower()
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            item.setHidden(search_term not in item.text().lower())
    
    def update_cache_size(self, size):
        self.vault.cache_size = size
        self.cache_label.setText(f"{size} items")
    
    def update_image_quality(self, quality):
        self.vault.image_quality = quality
        self.quality_label.setText(f"{quality}%")
    
    def save_settings(self):
        self.update_status("Settings saved")
    
    def refresh_data(self):
        self.history_list.clear()
        for id, preview, ctype, pinned in self.vault.history:
            item = QListWidgetItem(f"{'📌 ' if pinned else ''}{preview} ({ctype})")
            item.setData(Qt.UserRole, id)
            if pinned:
                item.setData(Qt.UserRole + 1, "pinned")
            self.history_list.addItem(item)
        self.pinned_list.clear()
        for id, preview, ctype in self.vault.get_pinned():
            item = QListWidgetItem(f"📌 {preview} ({ctype})")
            item.setData(Qt.UserRole, id)
            item.setData(Qt.UserRole + 1, "pinned")
            self.pinned_list.addItem(item)
    
    def paste_selected(self, item):
        id = item.data(Qt.UserRole)
        self.vault.paste_item(id)
        self.update_status("Item pasted to clipboard")
    
    def clear_unpinned(self):
        self.vault.clear_unpinned()
        self.refresh_data()
        self.update_status("Unpinned history cleared")
    
    def update_status(self, message):
        self.status_bar.showMessage(message)

class ClipVault:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.clipboard = QApplication.clipboard()
        self.history = []
        self.data_dir = "clipvault_data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self._create_icon())
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()
        self.db = sqlite3.connect('clipvault.db')
        self._ensure_schema()
        self._clear_on_startup()
        self.load_history()
        self.lru_cache = OrderedDict()
        self.cache_size = 10
        self.image_quality = 85
        self.clipboard.dataChanged.connect(self.check_clipboard)
        self.gui = ClipVaultGUI(self)
        self.gui.hide()
        self._setup_tray_menu()
        self.mem_log = open("memory.log", "w")
        QTimer.singleShot(1000, self._log_memory)
    
    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_gui()
    
    def toggle_gui(self):
        if self.gui.isVisible():
            self.gui.hide()
        else:
            self.gui.show()
            self.gui.raise_()
            self.gui.activateWindow()
            self.gui.refresh_data()
    
    def _setup_tray_menu(self):
        self.menu.clear()
        show_action = QAction("Show ClipVault", self.menu)
        show_action.triggered.connect(self.toggle_gui)
        self.menu.addAction(show_action)
        self.menu.addSeparator()
        
        pinned_header = QAction("📌 Pinned Items", self.menu)
        pinned_header.setEnabled(False)
        self.menu.addAction(pinned_header)
        
        pinned_items = self.get_pinned()[:5]
        for i, (id, preview, ctype) in enumerate(pinned_items):
            action = QAction(f"{i+1}: {preview}", self.menu)
            action.triggered.connect(lambda checked, id=id: self.paste_item(id))
            self.menu.addAction(action)
        
        self.menu.addSeparator()
        
        recent_header = QAction("🕒 Recent Items", self.menu)
        recent_header.setEnabled(False)
        self.menu.addAction(recent_header)
        
        recent_items = [item for item in self.history if not item[3]][:5]
        for i, (id, preview, ctype, pinned) in enumerate(recent_items):
            action = QAction(f"{i+1}: {preview}", self.menu)
            action.triggered.connect(lambda checked, id=id: self.paste_item(id))
            self.menu.addAction(action)
        
        self.menu.addSeparator()
        exit_action = QAction("Exit", self.menu)
        exit_action.triggered.connect(self.cleanup_and_exit)
        self.menu.addAction(exit_action)
        
    def _create_icon(self):
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
    
    def _log_memory(self):
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem = process.memory_info().rss / 1024 ** 2
            self.mem_log.write(f"{datetime.now().isoformat()},{mem:.2f}\n")
            self.mem_log.flush()
        except ImportError:
            pass
        QTimer.singleShot(1000, self._log_memory)
    
    def _clear_on_startup(self):
        try:
            cursor = self.db.execute('''SELECT id, content, storage FROM clips 
                                     WHERE pinned = 0 AND 
                                     datetime(created) < datetime('now', '-24 hours')''')
            expired_items = cursor.fetchall()
            for id, content, storage in expired_items:
                if storage in ('file', 'mmap'):
                    if content and os.path.exists(content):
                        try:
                            os.remove(content)
                        except:
                            pass
            self.db.execute('''DELETE FROM clips 
                            WHERE pinned = 0 AND 
                            datetime(created) < datetime('now', '-24 hours')''')
            self.db.commit()
        except Exception:
            pass
        try:
            cursor = self.db.execute("SELECT content FROM clips WHERE storage IN ('file', 'mmap')")
            referenced_files = {row[0] for row in cursor.fetchall()}
            for filename in os.listdir(self.data_dir):
                file_path = os.path.join(self.data_dir, filename)
                if file_path not in referenced_files:
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception:
                        pass
            cursor = self.db.execute("SELECT id, content FROM clips WHERE storage IN ('file', 'mmap')")
            for id, file_path in cursor.fetchall():
                if not os.path.exists(file_path):
                    self.db.execute("DELETE FROM clips WHERE id=?", (id,))
            self.db.commit()
        except Exception:
            pass
    
    def _ensure_schema(self):
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
    
    def _compress_image(self, img_data):
        try:
            img = Image.open(io.BytesIO(img_data))
            output = io.BytesIO()
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            img.save(output, format="JPEG", quality=self.image_quality)
            return output.getvalue()
        except Exception:
            return img_data
    
    def store_content(self, content, ctype):
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
                compressed = self._compress_image(content)
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
            self.db.execute('''INSERT INTO clips (preview, type, storage, size, content, pinned) 
                            VALUES (?, ?, ?, ?, ?, 0)''', 
                           (preview, ctype, storage, size, file_path))
        else:
            self.db.execute('''INSERT INTO clips (content, preview, type, storage, size, pinned) 
                            VALUES (?, ?, ?, ?, ?, 0)''', 
                           (content, preview, ctype, storage, size))
        self.db.commit()
        self.load_history()
        return preview
    
    def get_content(self, id):
        if id in self.lru_cache:
            content = self.lru_cache.pop(id)
            self.lru_cache[id] = content
            return content
        row = self.db.execute('''SELECT content, type, storage 
                              FROM clips WHERE id = ?''', (id,)).fetchone()
        if not row:
            return None
        content, ctype, storage = row
        try:
            if storage == 'file':
                if not os.path.exists(content):
                    self.db.execute("DELETE FROM clips WHERE id=?", (id,))
                    self.db.commit()
                    return None
                with open(content, 'rb') as f:
                    content = f.read()
            elif storage == 'mmap':
                if not os.path.exists(content):
                    self.db.execute("DELETE FROM clips WHERE id=?", (id,))
                    self.db.commit()
                    return None
                with open(content, 'rb') as f:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        content = mm.read()
            else:
                if isinstance(content, str):
                    content = content.encode('utf-8')
        except Exception:
            self.db.execute("DELETE FROM clips WHERE id=?", (id,))
            self.db.commit()
            return None
        self.lru_cache[id] = content
        if len(self.lru_cache) > self.cache_size:
            self.lru_cache.popitem(last=False)
        return content
    
    def load_history(self):
        try:
            cur = self.db.execute('''SELECT id, preview, type, pinned 
                                  FROM clips 
                                  ORDER BY created DESC 
                                  LIMIT 50''')
            self.history = []
            for row in cur.fetchall():
                self.history.append((row[0], row[1], row[2], bool(row[3])))
            self._setup_tray_menu()
        except Exception:
            pass
    
    def get_pinned(self):
        try:
            cur = self.db.execute("SELECT id, preview, type FROM clips WHERE pinned=1")
            return [(row[0], row[1], row[2]) for row in cur.fetchall()]
        except Exception:
            return []
    
    def is_pinned(self, id):
        try:
            row = self.db.execute("SELECT pinned FROM clips WHERE id=?", (id,)).fetchone()
            return bool(row[0]) if row else False
        except Exception:
            return False
    
    def toggle_pin(self, id):
        try:
            pinned = self.is_pinned(id)
            self.db.execute("UPDATE clips SET pinned=? WHERE id=?", (1 - int(pinned), id))
            self.db.commit()
            self.load_history()
            return True
        except Exception:
            return False
    
    def delete_item(self, id):
        try:
            row = self.db.execute("SELECT storage, content FROM clips WHERE id=?", (id,)).fetchone()
            if row:
                storage, content = row
                if storage in ('file', 'mmap'):
                    if os.path.exists(content):
                        try:
                            os.remove(content)
                        except:
                            pass
            self.db.execute("DELETE FROM clips WHERE id=?", (id,))
            self.db.commit()
            if id in self.lru_cache:
                del self.lru_cache[id]
            self.load_history()
            return True
        except Exception:
            return False
    
    def clear_unpinned(self):
        try:
            self.db.execute("DELETE FROM clips WHERE pinned=0")
            self.db.commit()
            self.load_history()
            return True
        except Exception:
            return False
    
    def check_clipboard(self):
        try:
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
                self.store_content(content, ctype)
                if hasattr(self, 'gui') and self.gui.isVisible():
                    self.gui.refresh_data()
        except Exception:
            pass
    
    def paste_item(self, id):
        try:
            content = self.get_content(id)
            if not content:
                return
            row = self.db.execute("SELECT type FROM clips WHERE id=?", (id,)).fetchone()
            if not row: return
            ctype = row[0]
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
        except Exception:
            pass
    
    def cleanup(self):
        try:
            self.mem_log.close()
        except:
            pass
        self.lru_cache.clear()
    
    def cleanup_and_exit(self):
        self.cleanup()
        self.app.quit()
    
    def run(self):
        self.app.aboutToQuit.connect(self.cleanup)
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "1"
    vault = ClipVault()
    vault.run()