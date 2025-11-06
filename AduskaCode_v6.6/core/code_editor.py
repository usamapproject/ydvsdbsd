
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtGui import QColor, QPainter, QFont, QPalette, QTextCursor
from PyQt5.QtWidgets import QPlainTextEdit, QWidget
from core.highlighter import PythonHighlighter

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path = None
        self._line_number_area = LineNumberArea(self)
        font = QFont("Fira Code, Consolas, Monospace"); font.setStyleHint(QFont.Monospace); font.setPointSize(11)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(' '))
        self.highlighter = PythonHighlighter(self.document())
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self._emit_status)
        self.update_line_number_area_width(0)

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance('9') * digits
    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    def update_line_number_area(self, rect, dy):
        if dy: self._line_number_area.scroll(0, dy)
        else: self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()): self.update_line_number_area_width(0)
    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
    def line_number_area_paint_event(self, event):
        p = QPainter(self._line_number_area)
        p.fillRect(event.rect(), self.palette().alternateBase())
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(num + 1)
                p.setPen(self.palette().text().color())
                right = self._line_number_area.width() - 6
                p.drawText(0, int(top), right, int(self.fontMetrics().height()), Qt.AlignRight, number)
            block = block.next(); top = bottom
            bottom = top + self.blockBoundingRect(block).height(); num += 1

    def _emit_status(self): pass
    def current_line(self): return self.textCursor().blockNumber() + 1
    def current_column(self): return self.textCursor().positionInBlock() + 1

    def apply_theme(self, theme: dict):
        pal = self.palette()
        pal.setColor(QPalette.Base, QColor(theme.get("background", "#1e1e1e")))
        pal.setColor(QPalette.Text, QColor(theme.get("foreground", "#eeeeee")))
        pal.setColor(QPalette.Highlight, QColor(theme.get("selection", "#3574f0")))
        pal.setColor(QPalette.HighlightedText, QColor(theme.get("selection_text", "#000000")))
        pal.setColor(QPalette.AlternateBase, QColor(theme.get("alternateBase", theme.get("background", "#222"))))
        self.setPalette(pal)
        self.highlighter.set_colors(
            keyword=theme.get("kw"), string=theme.get("str"), comment=theme.get("com"),
            classdef=theme.get("class"), funcdef=theme.get("func"), number=theme.get("num"),
        )
        self.highlighter.rehighlight()

    def find_next(self, text: str):
        if not text: return False
        return self.find(text)
    def replace_selection(self, text: str):
        c = self.textCursor()
        if c.hasSelection(): c.insertText(text)
    def goto_line(self, ln: int):
        ln = max(1, ln)
        cur = self.textCursor()
        cur.movePosition(QTextCursor.Start)
        for _ in range(ln - 1):
            if not cur.movePosition(QTextCursor.Down): break
        self.setTextCursor(cur)
