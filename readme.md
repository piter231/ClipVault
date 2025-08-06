# ClipVault - Lightweight Clipboard Manager

[![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/piter231/ClipVault/blob/main/LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
![Memory Usage](https://img.shields.io/badge/memory-50MB-44cc11)

ClipVault is a lightweight clipboard manager that saves text, images, and files across sessions while keeping memory usage low. Retrieve important clipboard items you thought were lost.

## Key Features

- Stores text, images, and file paths
- Low memory usage (50-80MB during normal operation)
- Saves items between application restarts
- Pin important items permanently
- Search through clipboard history
- Adjustable cache size and image quality
- System tray access
- Automatically removes old unpinned items

## Memory Efficiency

ClipVault uses several techniques to minimize memory usage:

1. **Intelligent Caching**:

   - Keeps frequently accessed items in memory
   - Configurable cache size
   - Automatic cache clearing on restart

2. **Image Compression**:

   - Converts images to JPEG format
   - Adjustable quality setting (default 85%)
   - Reduces image memory usage significantly

3. **Large File Handling**:

   - Stores files over 1MB on disk
   - Uses memory mapping for files over 10MB
   - Minimal memory impact for large files

4. **Efficient Storage**:
   - SQLite database backend
   - Binary storage format
   - Previews instead of full content in UI

## Installation

### Requirements

- Python 3.8+
- pip package manager

### Install from Source

```bash
git clone https://github.com/piter231/ClipVault.git
cd ClipVault
pip install -r requirements.txt
```

## Usage

Run the application:

```bash
python main.py
```

### Accessing Clipboard History

1. Find the clipboard icon in your system tray
2. Open the main window by double-clicking the tray icon
3. Right-click the tray icon for quick access to:
   - Pinned items
   - Recent clipboard history
   - Application options

### Interface Overview

The application has three main sections:

1. **History**:

   - Browse all clipboard items
   - Search through past entries
   - Clear unpinned items

2. **Pinned Items**:

   - View permanently saved items
   - Manage important snippets

3. **Settings**:
   - Adjust memory cache size
   - Set image quality
   - Toggle automatic cleanup

## Memory Usage

| Scenario    | Memory Usage | Notes            |
| ----------- | ------------ | ---------------- |
| Startup     | 45-55 MB     | Initial load     |
| Typical use | 50-80 MB     | Normal operation |

## Building Executable

Create a standalone version:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed  main.py
```

Find the executable in the `dist/` directory.

## Contributing

Contributions are welcome:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your branch
5. Open a pull request

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

---
