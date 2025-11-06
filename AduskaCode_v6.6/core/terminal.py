
import os, re, html
from PyQt5.QtCore import QProcess
from PyQt5.QtWidgets import QWidget, QTextEdit, QLineEdit, QVBoxLayout

ESC = "\x1b"
OSC_RE = re.compile(r'\x1b\].*?(?:\x07|\x1b\\)', re.DOTALL)  # ESC ] ... BEL | ESC \
SGR_RE = re.compile(r'\x1b\[((?:\d{1,3}(?:;\d{1,3})*)?)m')
CSI_RE = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')

# xterm 256-color palette
def _xterm_comp(v):
    return 0 if v == 0 else 55 + 40 * v

BASIC_COLORS = {
    30: "#000000", 31: "#800000", 32: "#008000", 33: "#808000",
    34: "#000080", 35: "#800080", 36: "#008080", 37: "#c0c0c0",
    90: "#808080", 91: "#ff0000", 92: "#00ff00", 93: "#ffff00",
    94: "#0000ff", 95: "#ff00ff", 96: "#00ffff", 97: "#ffffff",
}
BASIC_BG = {k+10: v for k,v in BASIC_COLORS.items() if k < 50}
BASIC_BG.update({k+10: v for k,v in BASIC_COLORS.items() if k >= 90})

def xterm_256_to_hex(n: int) -> str:
    if n < 16:
        # approximate base colors
        table = [
            "#000000","#800000","#008000","#808000","#000080","#800080","#008080","#c0c0c0",
            "#808080","#ff0000","#00ff00","#ffff00","#0000ff","#ff00ff","#00ffff","#ffffff"
        ]
        return table[n]
    if 16 <= n <= 231:
        n -= 16
        r = n // 36
        g = (n % 36) // 6
        b = n % 6
        return "#{:02x}{:02x}{:02x}".format(_xterm_comp(r), _xterm_comp(g), _xterm_comp(b))
    if 232 <= n <= 255:
        v = 8 + 10 * (n - 232)
        return "#{:02x}{:02x}{:02x}".format(v, v, v)
    return "#ffffff"

def sgr_to_style(codes, state):
    # codes is like "1;31;48;5;240"
    if codes == "":
        return state  # ignore malformed
    parts = [int(x) if x.isdigit() else 0 for x in codes.split(";")]
    i = 0
    while i < len(parts):
        c = parts[i]
        if c == 0:
            state.clear()
        elif c == 1:
            state["bold"] = True
        elif c == 3:
            state["italic"] = True
        elif c == 4:
            state["underline"] = True
        elif c == 22:
            state["bold"] = False
        elif c == 23:
            state["italic"] = False
        elif c == 24:
            state["underline"] = False
        elif c == 39:
            state.pop("fg", None)
        elif c == 49:
            state.pop("bg", None)
        elif c in BASIC_COLORS:
            state["fg"] = BASIC_COLORS[c]
        elif c in BASIC_BG:
            state["bg"] = BASIC_BG[c]
        elif c in (38, 48):
            # extended color
            if i+1 < len(parts) and parts[i+1] == 5 and i+2 < len(parts):
                col = xterm_256_to_hex(parts[i+2])
                (state.__setitem__("fg" if c == 38 else "bg", col))
                i += 2
            elif i+1 < len(parts) and parts[i+1] == 2 and i+3 < len(parts):
                r, g, b = parts[i+2:i+5]
                col = "#{:02x}{:02x}{:02x}".format(r, g, b)
                (state.__setitem__("fg" if c == 38 else "bg", col))
                i += 4
        i += 1
    return state

def make_span(text, state):
    if not text:
        return ""
    style = []
    if "fg" in state: style.append(f"color:{state['fg']}")
    if "bg" in state: style.append(f"background-color:{state['bg']}")
    if state.get("bold"): style.append("font-weight:bold")
    if state.get("italic"): style.append("font-style:italic")
    if state.get("underline"): style.append("text-decoration:underline")
    s = ";".join(style)
    return f"<span style=\"{s}\">{html.escape(text).replace('  ',' &nbsp;').replace('\\t','&nbsp;&nbsp;&nbsp;&nbsp;')}</span>"

def ansi_to_html(s: str, state=None):
    if state is None: state = {}
    # handle CR as overwrite line: keep simplest approach by removing carriage returns
    s = OSC_RE.sub('', s)
    s = s.replace("\r", "")
    out = []
    last = 0
    for m in SGR_RE.finditer(s):
        out.append(make_span(s[last:m.start()], state))
        sgr_to_style(m.group(1), state)
        last = m.end()
    out.append(make_span(s[last:], state))
    html_text = "".join(out)
    # convert newlines
    html_text = html_text.replace("\n", "<br/>")
    return html_text, state

class TerminalWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc = QProcess(self)
        self.out = QTextEdit(self); self.out.setReadOnly(True); self.out.setAcceptRichText(True)
        self.inp = QLineEdit(self); self.inp.returnPressed.connect(self._send)

        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self.out); lay.addWidget(self.inp)

        # environment: allow colors by default
        env = os.environ.copy()
        if hasattr(self.proc, 'setProcessEnvironment'):
            # not available in PyQt5 QProcess easily; we'll rely on inherited env
            pass

        if os.name == "nt":
            program, args = "cmd.exe", []
        else:
            program = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
            args = ["-i"]

        self.proc.setProgram(program); self.proc.setArguments(args)
        self.proc.readyReadStandardOutput.connect(self._stdout)
        self.proc.readyReadStandardError.connect(self._stderr)
        self.proc.start()

        self._ansi_state = {}

    def _append_html(self, html_snippet: str):
        self.out.moveCursor(self.out.textCursor().End)
        self.out.insertHtml(html_snippet)
        self.out.moveCursor(self.out.textCursor().End)

    def _stdout(self):
        data = self.proc.readAllStandardOutput().data().decode(errors="replace")
        html_snip, self._ansi_state = ansi_to_html(data, self._ansi_state)
        self._append_html(html_snip)

    def _stderr(self):
        data = self.proc.readAllStandardError().data().decode(errors="replace")
        html_snip, self._ansi_state = ansi_to_html(data, self._ansi_state)
        self._append_html(html_snip)

    def _send(self):
        t = self.inp.text()
        if not t.endswith("\n"): t += "\n"
        self.proc.write(t.encode()); self.inp.clear()

    def run_command(self, command: str):
        if not command.endswith("\n"): command += "\n"
        self.proc.write(command.encode())
