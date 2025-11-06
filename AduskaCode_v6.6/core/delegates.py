from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtCore import QDateTime

def human_size(n: int) -> str:
    try:
        n = int(n)
    except Exception:
        return str(n)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units) - 1:
        f /= 1024.0
        i += 1
    return f"{f:.2f} {units[i]}" if i > 0 else f"{int(f)} {units[i]}"

def pretty_type(name: str) -> str:
    s = (name or "").lower()
    mapping = {
        "py file": "Python file",
        "sh file": "Shell script",
        "json file": "JSON file",
        "yaml file": "YAML file",
        "yml file": "YAML file",
        "png file": "PNG image",
        "jpg file": "JPEG image",
        "jpeg file": "JPEG image",
        "bmp file": "Bitmap image",
        "gif file": "GIF image",
        "webp file": "WebP image",
        "pdf file": "PDF document",
        "text file": "Text file",
    }
    return mapping.get(s, name)

class SizeDelegate(QStyledItemDelegate):
    # QFileSystemModel column 1
    def displayText(self, value, locale):
        return human_size(value)

class TypeDelegate(QStyledItemDelegate):
    # QFileSystemModel column 2
    def displayText(self, value, locale):
        return pretty_type(str(value))

class DateDelegate(QStyledItemDelegate):
    # QFileSystemModel column 3
    def displayText(self, value, locale):
        try:
            dt = QDateTime.fromString(str(value), locale.dateTimeFormat())
            if not dt.isValid():
                dt = QDateTime.fromString(str(value))
            if dt.isValid():
                return dt.toString("yyyy-MM-dd HH:mm")
        except Exception:
            pass
        return str(value)
