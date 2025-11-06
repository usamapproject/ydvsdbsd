
from PyQt5.QtCore import QRegularExpression
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor

def fmt(color: QColor, bold=False, italic=False):
    f = QTextCharFormat()
    f.setForeground(color)
    if bold: f.setFontWeight(QFont.Bold)
    if italic: f.setFontItalic(True)
    return f

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.colors = {
            "keyword": QColor("#c586c0"),
            "string": QColor("#ce9178"),
            "comment": QColor("#6a9955"),
            "classdef": QColor("#4ec9b0"),
            "funcdef": QColor("#dcdcaa"),
            "number": QColor("#b5cea8"),
        }
        self._compile()

    def set_colors(self, **kwargs):
        for k, v in kwargs.items():
            if v:
                self.colors[k] = QColor(v)
        self._compile()

    def _compile(self):
        kw = ('and as assert break class continue def del elif else except False finally for from global '
              'if import in is lambda None nonlocal not or pass raise return True try while with yield').split()
        self.rules = []
        kwf = fmt(self.colors["keyword"], bold=True)
        for w in kw:
            self.rules.append((QRegularExpression(rf"\b{w}\b"), kwf))
        strf = fmt(self.colors["string"])
        self.rules.append((QRegularExpression(r"'[^'\\n]*'"), strf))
        self.rules.append((QRegularExpression(r"\"[^\"\\n]*\""), strf))
        numf = fmt(self.colors["number"])
        self.rules.append((QRegularExpression(r"\b-?\d+(\.\d+)?([eE][+-]?\d+)?\b"), numf))
        classf = fmt(self.colors["classdef"], bold=True)
        funcf = fmt(self.colors["funcdef"], bold=True)
        self.rules.append((QRegularExpression(r"\bclass\s+(\w+)"), classf))
        self.rules.append((QRegularExpression(r"\bdef\s+(\w+)"), funcf))
        self.com_re = QRegularExpression(r"#.*")
        self.com_fmt = fmt(self.colors["comment"], italic=True)

    def highlightBlock(self, text: str):
        for pattern, f in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), f)
        it = self.com_re.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self.com_fmt)


class JSONHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.colors = {
            "key": QColor("#9cdcfe"),
            "string": QColor("#ce9178"),
            "number": QColor("#b5cea8"),
            "bool": QColor("#569cd6"),
            "null": QColor("#569cd6"),
        }
        self._compile()

    def _compile(self):
        self.rules = []
        self.rules.append((QRegularExpression(r'"([^"\\]|\\.)*"(?=\s*:)'), fmt(self.colors["key"], bold=True)))
        self.rules.append((QRegularExpression(r'(?<=:)\s*"([^"\\]|\\.)*"'), fmt(self.colors["string"])))
        self.rules.append((QRegularExpression(r"\b-?\d+(\.\d+)?([eE][+-]?\d+)?\b"), fmt(self.colors["number"])))
        self.rules.append((QRegularExpression(r"\btrue\b|\bfalse\b"), fmt(self.colors["bool"], bold=True)))
        self.rules.append((QRegularExpression(r"\bnull\b"), fmt(self.colors["null"])))

    def highlightBlock(self, text: str):
        for pattern, f in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), f)
