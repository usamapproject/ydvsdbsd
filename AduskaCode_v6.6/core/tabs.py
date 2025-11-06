from PyQt5.QtWidgets import QTabWidget, QMenu, QAction
from PyQt5.QtCore import Qt

class DetachableTabWidget(QTabWidget):
    """QTabWidget s možností odtržení tabu do nového okna a přesunu mezi levým/pravým splitem."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self._drag_start_pos = None
        self._main = None  # nastaví MainWindow po konstrukci

    def setMainWindow(self, mw):
        self._main = mw

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start_pos = e.pos()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        # jednoduché "drag out": táhneš tab dost daleko -> nové okno
        if self._drag_start_pos and (e.pos() - self._drag_start_pos).manhattanLength() > 24:
            idx = self.currentIndex()
            if idx >= 0 and self._main:
                w = self.widget(idx)
                text = self.tabText(idx)
                icon = self.tabIcon(idx)
                self.removeTab(idx)
                if self is getattr(self._main, "right_tabs", None):
                    self._main._maybe_hide_right_split()
                self._main.create_editor_window(w, title=text, icon=icon)
                self._drag_start_pos = None
                return
        super().mouseMoveEvent(e)

    def contextMenuEvent(self, e):
        idx = self.tabBar().tabAt(e.pos())
        if idx < 0 or not self._main:
            return
        m = QMenu(self)
        act_left  = QAction("Move to Left Split", self)
        act_right = QAction("Move to Right Split", self)
        act_win   = QAction("Open in New Window", self)
        m.addAction(act_left)
        m.addAction(act_right)
        m.addSeparator()
        m.addAction(act_win)

        def move_to(target):
            w = self.widget(idx)
            text = self.tabText(idx)
            icon = self.tabIcon(idx)
            self.removeTab(idx)
            if self is getattr(self._main, "right_tabs", None):
                self._main._maybe_hide_right_split()
            if target is self._main.tabs_right:
                self._main.ensure_right_split_visible()
            target.addTab(w, icon, text)
            target.setCurrentWidget(w)

        act_left.triggered.connect(lambda: move_to(self._main.tabs_left))
        act_right.triggered.connect(lambda: move_to(self._main.tabs_right))
        def open_in_window():
            w = self.widget(idx)
            text = self.tabText(idx)
            icon = self.tabIcon(idx)
            self.removeTab(idx)
            if self is getattr(self._main, "right_tabs", None):
                self._main._maybe_hide_right_split()
            self._main.create_editor_window(w, title=text, icon=icon)

        act_win.triggered.connect(open_in_window)
        m.exec_(e.globalPos())

    def close_tab(self, idx):
        w = self.widget(idx)
        self.removeTab(idx)
        if w:
            w.deleteLater()
