
# -*- coding: utf-8 -*-
import sys, json, os, shlex, subprocess
from pathlib import Path
from PyQt5.QtCore import Qt, QDir, QSettings, QSize, QTimer, QUrl
from PyQt5.QtGui import QKeySequence, QPalette, QColor, QFont, QDesktopServices
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QAction, QTreeView, QFileSystemModel,
    QSplitter, QWidget, QVBoxLayout, QTabWidget, QMessageBox, QToolBar, QStatusBar,
    QInputDialog, QShortcut, QDockWidget, QDialog, QFormLayout, QSpinBox, QComboBox,
    QPushButton, QLabel, QLineEdit, QListWidget, QListWidgetItem, QHBoxLayout, QTextEdit, QFileDialog
)
from core.delegates import SizeDelegate, TypeDelegate, DateDelegate
from core.code_editor import CodeEditor
from core.terminal import TerminalWidget
from core.plugin_manager import PluginManager
from core.editor_api import EditorAPI
from core.tabs import DetachableTabWidget

APP_NAME = "AduskaCode"
ORG = "Aduska"
DOMAIN = "aduska.dev"


class SettingsDialog(QDialog):
    def __init__(self, parent, themes: dict):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(420, 260)
        lay = QFormLayout(self)

        self.cmb_theme = QComboBox(); self.cmb_theme.addItems(sorted(themes.keys()))
        self.spin_font = QSpinBox(); self.spin_font.setRange(8, 32); self.spin_font.setValue(11)
        self.spin_tabs = QSpinBox(); self.spin_tabs.setRange(2, 12); self.spin_tabs.setValue(4)
        self.spin_autosave = QSpinBox(); self.spin_autosave.setRange(0, 600); self.spin_autosave.setValue(0)
        self.txt_workspace = QLineEdit()

        lay.addRow("Theme", self.cmb_theme)
        lay.addRow("Font size", self.spin_font)
        lay.addRow("Tab size (spaces)", self.spin_tabs)
        lay.addRow("Autosave (sec, 0=off)", self.spin_autosave)
        lay.addRow("Default workspace", self.txt_workspace)

        b = QHBoxLayout()
        ok = QPushButton("OK"); cancel = QPushButton("Cancel")
        ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        b.addStretch(1); b.addWidget(ok); b.addWidget(cancel)
        lay.addRow(b)

    def get_values(self):
        return {
            "theme": self.cmb_theme.currentText(),
            "font_size": self.spin_font.value(),
            "tab_spaces": self.spin_tabs.value(),
            "autosave": self.spin_autosave.value(),
            "workspace": self.txt_workspace.text().strip(),
        }

    def set_values(self, data: dict):
        if "theme" in data:
            idx = self.cmb_theme.findText(data["theme"])
            if idx >= 0: self.cmb_theme.setCurrentIndex(idx)
        if "font_size" in data: self.spin_font.setValue(int(data["font_size"]))
        if "tab_spaces" in data: self.spin_tabs.setValue(int(data["tab_spaces"]))
        if "autosave" in data: self.spin_autosave.setValue(int(data["autosave"]))
        if "workspace" in data: self.txt_workspace.setText(str(data["workspace"]))


class SearchDock(QDockWidget):
    def __init__(self, main):
        super().__init__("Search")
        self.main = main
        w = QWidget(); self.setWidget(w)
        lay = QVBoxLayout(w); lay.setContentsMargins(4,4,4,4)
        top = QHBoxLayout()
        self.q = QLineEdit(); self.q.setPlaceholderText("Find in workspace…")
        self.btn = QPushButton("Search")
        self.btn.clicked.connect(self.do_search)
        self.q.returnPressed.connect(self.do_search)
        top.addWidget(self.q); top.addWidget(self.btn)
        lay.addLayout(top)
        self.list = QListWidget(); lay.addWidget(self.list)
        self.list.itemActivated.connect(self.open_hit)

    def do_search(self):
        self.list.clear()
        text = self.q.text().strip()
        if not text: return
        root = self.main.workspace_dir
        for p, _, files in os.walk(root):
            for fn in files:
                fp = Path(p)/fn
                try:
                    data = fp.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for ln, line in enumerate(data.splitlines(), 1):
                    if text.lower() in line.lower():
                        item = QListWidgetItem(f"{fp} : {ln}  —  {line.strip()}")
                        item.setData(Qt.UserRole, (str(fp), ln))
                        self.list.addItem(item)

    def open_hit(self, item: QListWidgetItem):
        path, ln = item.data(Qt.UserRole)
        self.main.open_file(Path(path))
        w = self.main.current_widget()
        if isinstance(w, CodeEditor):
            w.goto_line(ln)


class ExtensionManager(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Extension Manager")
        self.resize(560, 400)
        lay = QVBoxLayout(self)
        self.info = QLabel("Installed extensions (.extend):")
        self.list = QListWidget()
        self.btn_reload = QPushButton("Reload")
        self.btn_toggle = QPushButton("Disable/Enable")
        self.btn_uninstall = QPushButton("Uninstall (Delete file)")
        self.btn_install = QPushButton("Install…")
        self.btn_open_dir = QPushButton("Show Extensions Folder")

        row = QHBoxLayout()
        for b in (self.btn_reload, self.btn_toggle, self.btn_uninstall, self.btn_install, self.btn_open_dir):
            row.addWidget(b)
        row.addStretch(1)

        lay.addWidget(self.info); lay.addWidget(self.list); lay.addLayout(row)

        self.btn_reload.clicked.connect(self._reload)
        self.btn_toggle.clicked.connect(self._toggle)
        self.btn_uninstall.clicked.connect(self._uninstall)
        self.btn_install.clicked.connect(self._install)
        self.btn_open_dir.clicked.connect(self._open_dir)

        self._refresh()

    def _refresh(self):
        self.list.clear()
        ext_dir = Path(__file__).resolve().parent.parent / "extensions"
        disabled = set(self.main.settings.value("disabled_extensions", [], type=list))
        if ext_dir.exists():
            for child in sorted(ext_dir.iterdir()):
                if child.suffix == ".extend" or child.name.endswith(".extend"):
                    item = QListWidgetItem(child.name)
                    state = "[disabled]" if (child.name in disabled) else "[enabled]"
                    item.setText(f"{child.name}  {state}")
                    item.setData(Qt.UserRole, child.name)
                    self.list.addItem(item)

    def _reload(self):
        self.main.reload_extensions()
        self._refresh()

    def _toggle(self):
        item = self.list.currentItem(); 
        if not item: return
        name = item.data(Qt.UserRole)
        disabled = set(self.main.settings.value("disabled_extensions", [], type=list))
        if name in disabled: disabled.remove(name)
        else: disabled.add(name)
        self.main.settings.setValue("disabled_extensions", list(disabled))
        self._refresh()

    def _uninstall(self):
        item = self.list.currentItem()
        if not item: return
        name = item.data(Qt.UserRole)
        ext_dir = Path(__file__).resolve().parent.parent / "extensions"
        try:
            (ext_dir/name).unlink(missing_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Uninstall", f"Failed to delete: {e}")
        self._refresh()

    def _install(self):
        ext_dir = Path(__file__).resolve().parent.parent / "extensions"
        ext_dir.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "Install Extension", str(ext_dir), "Extensions (*.extend)")
        if not path: return
        try:
            dst = ext_dir / Path(path).name
            if str(Path(path)) != str(dst):
                data = Path(path).read_bytes()
                dst.write_bytes(data)
            QMessageBox.information(self, "Install", f"Installed {dst.name}")
        except Exception as e:
            QMessageBox.critical(self, "Install", f"Failed: {e}")
        self._refresh()

    def _open_dir(self):
        ext_dir = Path(__file__).resolve().parent.parent / "extensions"
        ext_dir.mkdir(parents=True, exist_ok=True)
        url = QUrl.fromLocalFile(str(ext_dir))
        if not QDesktopServices.openUrl(url):
            QMessageBox.information(self, "Extensions Folder", str(ext_dir))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1360, 900)

        self.settings = QSettings(ORG, APP_NAME)
        stored_workspace = self.settings.value("workspace_dir", str(Path.home()))
        try:
            workspace = Path(stored_workspace).expanduser()
        except Exception:
            workspace = Path.home()
        try:
            workspace = workspace.resolve()
        except Exception:
            pass
        if not workspace.exists():
            workspace = Path.home()
        self.workspace_dir = workspace
        self.themes = {}
        self.current_theme = None
        self.custom_menus = {}
        self.commands = {}
        self.file_handlers = {}
        self.menu_panels = None
        self.panel_actions = {}
        self.docks = {}
        self.plugin_docks = []
        self.plugin_menu_actions = []
        self.plugin_commands = []
        self.plugin_file_handlers = []
        self.plugin_themes = set()
        self.plugin_status_widgets = []

        self._build_ui()

        self.api = EditorAPI(self)
        self.plugin_manager = PluginManager(self)

        self._register_builtin_commands()

        self._rebuild_theme_menu()
        self.reload_extensions()

        pref = self.settings.value("pref_theme", "")
        if pref and pref in self.themes:
            self.apply_theme(pref)
        elif self.themes:
            self.apply_theme(next(iter(self.themes.keys())))

        self.set_workspace(self.workspace_dir)

        QTimer.singleShot(50, self._restore_session)

        self.autosave_sec = int(self.settings.value("autosave", 0))
        self._autosave_timer = QTimer(self); self._autosave_timer.timeout.connect(self.save_all)
        if self.autosave_sec > 0:
            self._autosave_timer.start(self.autosave_sec * 1000)

    def _build_ui(self):
        menubar = self.menuBar()
        self.menu_file = menubar.addMenu("&File")
        self.menu_edit = menubar.addMenu("&Edit")
        self.menu_view = menubar.addMenu("&View")
        self.menu_panels = self.menu_view.addMenu("Panels")
        self.menu_theme = menubar.addMenu("&Theme")
        self.menu_tools = menubar.addMenu("&Tools")
        self.menu_ext = menubar.addMenu("&Extensions")
        self.menu_help = menubar.addMenu("&Help")
        self.custom_menus["Tools"] = self.menu_tools
        self._init_splits()
        self.setCentralWidget(self.splitter)


        # File
        self.act_new = QAction("New File", self, shortcut=QKeySequence.New, triggered=self.new_file)
        self.act_open = QAction("Open File...", self, shortcut=QKeySequence.Open, triggered=self.open_file_dialog)
        self.act_open_with = QAction("Open File With…", self, triggered=self.open_file_with_dialog)
        self.act_open_ws = QAction("Open Workspace...", self, triggered=self.open_workspace_dialog)
        self.act_save = QAction("Save", self, shortcut=QKeySequence.Save, triggered=self.save_current)
        self.act_save_as = QAction("Save As...", self, shortcut=QKeySequence.SaveAs, triggered=self.save_current_as)
        self.act_save_all = QAction("Save All", self, triggered=self.save_all)
        self.act_close_tab = QAction("Close Tab", self, shortcut=QKeySequence("Ctrl+W"), triggered=lambda: self._close_tab(self.active_tabs().currentIndex()))
        self.act_exit = QAction("Exit", self, shortcut=QKeySequence.Quit, triggered=self.close)
        self.menu_file.addActions([self.act_new, self.act_open, self.act_open_with, self.act_open_ws])
        self.menu_file.addSeparator()
        self.menu_file.addActions([self.act_save, self.act_save_as, self.act_save_all])
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_close_tab)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_exit)

        # Edit
        self._act_undo = QAction("Undo", self, shortcut=QKeySequence.Undo, triggered=lambda: self._do('undo'))
        self._act_redo = QAction("Redo", self, shortcut=QKeySequence.Redo, triggered=lambda: self._do('redo'))
        self._act_cut  = QAction("Cut",  self, shortcut=QKeySequence.Cut,  triggered=lambda: self._do('cut'))
        self._act_copy = QAction("Copy", self, shortcut=QKeySequence.Copy, triggered=lambda: self._do('copy'))
        self._act_paste= QAction("Paste",self, shortcut=QKeySequence.Paste,triggered=lambda: self._do('paste'))
        self.menu_edit.addActions([self._act_undo, self._act_redo])
        self.menu_edit.addSeparator()
        self.menu_edit.addActions([self._act_cut, self._act_copy, self._act_paste])

        # View toggles
        self.act_toggle_term = QAction("Toggle Terminal", self, checkable=True, checked=True, triggered=lambda ch: self.panel_actions.get('Terminal').setChecked(ch))
        self.act_toggle_explorer = QAction("Toggle Explorer", self, checkable=True, checked=True, triggered=lambda ch: self.panel_actions.get('Explorer').setChecked(ch))
        self.menu_view.addActions([self.act_toggle_term, self.act_toggle_explorer])

        # Pane actions
        self.act_move_to_other = QAction("Move Tab to Other Pane", self, shortcut=QKeySequence("Ctrl+\\"), triggered=self.move_tab_to_other_pane)
        self.act_detach_tab = QAction("Detach Tab to Window", self, shortcut=QKeySequence("Ctrl+Shift+D"), triggered=self.detach_tab_to_window)
        self.menu_view.addActions([self.act_move_to_other, self.act_detach_tab])

        # Extensions menu
        self.menu_ext.addAction(QAction("Extension Manager…", self, triggered=self.open_extension_manager))
        self.menu_ext.addAction(QAction("Settings…", self, triggered=self.open_settings))

        # Help
        self.menu_help.addAction(QAction("About", self, triggered=lambda: QMessageBox.information(self, "About", f"{APP_NAME}\nPyQt5 mini-IDE ❤️")))

        # Toolbar
        self.toolbar = QToolBar("Main")
        self.toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(self.toolbar)
        self.toolbar.addAction("New").triggered.connect(self.new_file)
        self.toolbar.addAction("Open").triggered.connect(self.open_file_dialog)
        self.toolbar.addAction("Save").triggered.connect(self.save_current)

        # Explorer (dock)
        self.fs_model = QFileSystemModel(self)
        self.fs_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Files)
        self.explorer = QTreeView()
        self.explorer.setModel(self.fs_model)
        self.explorer.doubleClicked.connect(self._on_explorer_double_click)
        self.explorer.setHeaderHidden(True)
        self.explorer.setAlternatingRowColors(True)
        self.explorer.setHeaderHidden(False)  # ať jsou vidět názvy sloupců
        # lidský formát pro sloupce
        try:
            self.explorer.setItemDelegateForColumn(1, SizeDelegate(self.explorer))  # Size
            self.explorer.setItemDelegateForColumn(2, TypeDelegate(self.explorer))  # Type
            self.explorer.setItemDelegateForColumn(3, DateDelegate(self.explorer))  # Date Modified
        except Exception:
            pass

        # rozumné šířky
        self.explorer.setColumnWidth(0, 240)
        self.explorer.setColumnWidth(1, 110)
        self.explorer.setColumnWidth(2, 140)
        self.explorer.setColumnWidth(3, 150)

        self.explorer_dock = QDockWidget("Explorer", self)
        self.explorer_dock.setObjectName("ExplorerDock")
        self.explorer_dock.setWidget(self.explorer)
        self.explorer_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.explorer_dock)
        self._register_panel_toggle("Explorer", self.explorer_dock)

        # Terminal (dock)
        self.terminal = TerminalWidget(self)
        self.terminal_dock = QDockWidget("Terminal", self)
        self.terminal_dock.setObjectName("TerminalDock")
        self.terminal_dock.setWidget(self.terminal)
        self.terminal_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.terminal_dock)
        self._register_panel_toggle("Terminal", self.terminal_dock)

        # Search (dock)
        self.search_dock = SearchDock(self)
        self.search_dock.setObjectName("SearchDock")
        self.addDockWidget(Qt.RightDockWidgetArea, self.search_dock)
        self._register_panel_toggle("Search", self.search_dock)

        # Central split panes
        self.left_tabs.tabCloseRequested.connect(lambda i: self._close_tab(i, pane="left"))
        self.right_tabs.tabCloseRequested.connect(lambda i: self._close_tab(i, pane="right"))
        self.left_tabs.currentChanged.connect(lambda _: self._update_status())
        self.right_tabs.currentChanged.connect(lambda _: self._update_status())

        self.status = QStatusBar(); self.setStatusBar(self.status)

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+B"), self, activated=lambda: self.act_toggle_explorer.trigger())
        QShortcut(QKeySequence("Ctrl+J"), self, activated=lambda: self.act_toggle_term.trigger())
        QShortcut(QKeySequence("Alt+1"), self, activated=lambda: self.left_tabs.setFocus())
        QShortcut(QKeySequence("Alt+2"), self, activated=lambda: self.right_tabs.setFocus())
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, activated=lambda: self._focus_search())

        # Command palette
        self.act_cmd_palette = QAction("Command Palette…", self, triggered=self.show_command_palette)
        self.act_cmd_palette.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.menu_tools.addAction(self.act_cmd_palette)
        QShortcut(QKeySequence("F1"), self, activated=self.show_command_palette)

        # Find/Replace/GoTo
        self.act_find = QAction("Find…", self, shortcut=QKeySequence.Find, triggered=self.find_dialog)
        self.act_replace = QAction("Replace…", self, shortcut=QKeySequence("Ctrl+H"), triggered=self.replace_dialog)
        self.act_goto = QAction("Go to Line…", self, shortcut=QKeySequence("Ctrl+G"), triggered=self.goto_line_dialog)
        self.menu_edit.addSeparator(); self.menu_edit.addActions([self.act_find, self.act_replace, self.act_goto])

        # Run current file
        self.act_run = QAction("Run Current .py", self, shortcut=QKeySequence("F5"), triggered=self.run_current_file)
        self.menu_tools.addAction(self.act_run)

    def _register_panel_toggle(self, title: str, dock):
        act = self.panel_actions.get(title)
        if act is None:
            act = QAction(title, self, checkable=True)
            self.panel_actions[title] = act
            self.menu_panels.addAction(act)
        key = f"panel_visible/{title}"
        visible = self.settings.value(key, True, type=bool)
        dock.setVisible(visible); act.setChecked(visible)
        def on_toggle(ch):
            dock.setVisible(ch); self.settings.setValue(key, ch)
        act.toggled.connect(on_toggle)
        dock.visibilityChanged.connect(lambda v: (act.setChecked(v), self.settings.setValue(key, v)))
        self.docks[title] = dock


    def add_status_widget(self, widget, plugin=False):
        self.status.addPermanentWidget(widget)
        if plugin:
            self.plugin_status_widgets.append(widget)
        # ---------- dirty indicator ----------
    def _attach_editor_signals(self, editor_widget):
        """Attach dirty-change tracking to the editor tab once."""
        if getattr(editor_widget, "_dirty_hooked", False):
            return
        try:
            doc = editor_widget.document()
        except Exception:
            return
        doc.modificationChanged.connect(
            lambda dirty, w=editor_widget: self._update_tab_dirty(w, dirty)
        )
        editor_widget._dirty_hooked = True

    def _update_tab_dirty(self, editor_widget, dirty: bool):
        containers = (self.left_tabs, self.right_tabs)
        for tw in containers:
            if not tw:
                continue
            try:
                idx = tw.indexOf(editor_widget)
            except Exception:
                idx = -1
            if idx != -1:
                base = tw.tabText(idx).lstrip('* ').strip()
                tw.setTabText(idx, f"* {base}" if dirty else base)
                break

        any_dirty = False
        for tw in containers:
            if not tw:
                continue
            for i in range(tw.count()):
                w = tw.widget(i)
                if isinstance(w, CodeEditor) and w.document().isModified():
                    any_dirty = True
                    break
            if any_dirty:
                break
        if not any_dirty and isinstance(editor_widget, CodeEditor) and dirty:
            any_dirty = True
        try:
            self.setWindowModified(any_dirty)
        except Exception:
            pass

    # ---------- Split view & detached windows ----------
    def _init_splits(self):
        self.splitter = QSplitter(self)
        self.splitter.setOrientation(Qt.Horizontal)

        self.tabs_left = DetachableTabWidget(self)
        self.tabs_right = DetachableTabWidget(self)

        self.tabs_left.setMainWindow(self)
        self.tabs_right.setMainWindow(self)
        # maintain compatibility with existing code paths that expect left/right tabs
        self.left_tabs = self.tabs_left
        self.right_tabs = self.tabs_right

        self.splitter.addWidget(self.tabs_left)
        self.splitter.addWidget(self.tabs_right)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        # defaultně zobraz jen levý panel; pravý se ukáže až při přesunu tabu
        self.tabs_right.setVisible(False)

    def ensure_right_split_visible(self):
        if not self.right_tabs.isVisible():
            self.right_tabs.setVisible(True)

    def _maybe_hide_right_split(self):
        if self.right_tabs.count() == 0:
            self.right_tabs.setVisible(False)

    def create_editor_window(self, widget, title="Untitled", icon=None):
        win = QMainWindow(self)
        tw = DetachableTabWidget(win)
        tw.setMainWindow(self)
        if icon is not None and not icon.isNull():
            tw.addTab(widget, icon, title)
        else:
            tw.addTab(widget, title)
        win.setCentralWidget(tw)
        win.resize(900, 600)
        win.show()

    # ---------- helpers ----------
    def _focus_search(self):
        self.search_dock.raise_(); self.search_dock.activateWindow(); self.search_dock.q.setFocus()

    def active_tabs(self) -> QTabWidget:
        return self.left_tabs if self.left_tabs.hasFocus() or (not self.right_tabs.hasFocus() and self.left_tabs.count()>0) else self.right_tabs

    def other_tabs(self, pane=None) -> QTabWidget:
        if pane == "left": return self.right_tabs
        if pane == "right": return self.left_tabs
        return self.right_tabs if self.active_tabs() is self.left_tabs else self.left_tabs

    def add_tab(self, widget, title: str, pane: str = "active"):
        tabs = self.left_tabs if pane=="left" else self.right_tabs if pane=="right" else self.active_tabs()
        if tabs is self.right_tabs:
            self.ensure_right_split_visible()
        i = tabs.addTab(widget, title)
        tabs.setCurrentIndex(i)
        if isinstance(widget, CodeEditor):
            self._attach_editor_signals(widget)
            try:
                self._update_tab_dirty(widget, widget.document().isModified())
            except Exception:
                pass

    def current_widget(self):
        tabs = self.active_tabs()
        return tabs.currentWidget()

    def move_tab_to_other_pane(self):
        src = self.active_tabs(); dst = self.other_tabs()
        i = src.currentIndex()
        if i < 0: return
        w = src.widget(i); text = src.tabText(i); icon = src.tabIcon(i)
        src.removeTab(i)
        if src is self.right_tabs:
            self._maybe_hide_right_split()
        if dst is self.right_tabs:
            self.ensure_right_split_visible()
        if icon is not None and not icon.isNull():
            j = dst.addTab(w, icon, text)
        else:
            j = dst.addTab(w, text)
        dst.setCurrentIndex(j)

    def detach_tab_to_window(self):
        src = self.active_tabs(); i = src.currentIndex()
        if i < 0: return
        w = src.widget(i); text = src.tabText(i); icon = src.tabIcon(i)
        src.removeTab(i)
        if src is self.right_tabs:
            self._maybe_hide_right_split()
        win = QMainWindow(); win.setWindowTitle(text)
        if icon is not None and not icon.isNull():
            win.setWindowIcon(icon)
        win.setCentralWidget(w); win.resize(800, 600); win.show()

    def _register_builtin_commands(self):
        self.register_command("New File", self.new_file, "Ctrl+N")
        self.register_command("Open File…", self.open_file_dialog, "Ctrl+O")
        self.register_command("Open File With…", self.open_file_with_dialog)
        self.register_command("Save", self.save_current, "Ctrl+S")
        self.register_command("Toggle Explorer", lambda: self.act_toggle_explorer.trigger(), "Ctrl+B")
        self.register_command("Toggle Terminal", lambda: self.act_toggle_term.trigger(), "Ctrl+J")
        self.register_command("Find…", self.find_dialog, "Ctrl+F")
        self.register_command("Replace…", self.replace_dialog, "Ctrl+H")
        self.register_command("Go to Line…", self.goto_line_dialog, "Ctrl+G")
        self.register_command("Run Current .py", self.run_current_file, "F5")
        self.register_command("Move Tab to Other Pane", self.move_tab_to_other_pane, "Ctrl+\\")
        self.register_command("Detach Tab to Window", self.detach_tab_to_window, "Ctrl+Shift+D")
        self.register_command("Reload Extensions", self.reload_extensions)
        self.register_command("Settings…", self.open_settings)
        self.register_command("Extension Manager…", self.open_extension_manager)

    def show_command_palette(self):
        items = sorted(self.commands.keys())
        if not items:
            QMessageBox.information(self, "Command Palette", "No commands available."); return
        action, ok = QInputDialog.getItem(self, "Command Palette", "Run command:", items, 0, False)
        if ok and action:
            self.commands[action][0]()

    def register_command(self, name: str, callback, shortcut: str = None, plugin=False):
        # overwrite if exists
        if name in self.commands:
            old_cb, old_act = self.commands[name]
            if old_act:
                self.removeAction(old_act)
        act = None
        if shortcut:
            act = QAction(name, self, shortcut=QKeySequence(shortcut), triggered=callback)
            self.addAction(act)
        self.commands[name] = (callback, act)
        if plugin:
            self.plugin_commands.append(name)

    def register_file_handler(self, suffixes, name: str, factory, plugin=False):
        for s in suffixes:
            s = s.lower()
            lst = self.file_handlers.setdefault(s, [])
            # remove any existing handler with same name to avoid duplicates
            lst[:] = [(n,f) for (n,f) in lst if n != name]
            lst.append((name, factory))
            if plugin:
                self.plugin_file_handlers.append((s, name))

    def _handler_for_suffix(self, suffix: str, name: str = None):
        items = self.file_handlers.get(suffix.lower(), [])
        if not items: return None
        if name:
            for n,f in items:
                if n == name: return (n,f)
            return None
        return items[0]

    def register_menu(self, path: str, callback, plugin=False):
        parts = [p for p in path.split("/") if p]
        if not parts: return
        top_text = parts[0]
        top_menu = self.menuBar().addMenu(top_text) if top_text not in self.custom_menus else self.custom_menus[top_text]
        self.custom_menus[top_text] = top_menu
        menu = top_menu
        for p in parts[1:-1]:
            sub = None
            for act in menu.actions():
                if act.menu() and act.text() == p:
                    sub = act.menu(); break
            if not sub:
                sub = menu.addMenu(p)
            menu = sub
        action_name = parts[-1]
        # avoid duplicate identical actions
        for a in menu.actions():
            if a.text() == action_name:
                menu.removeAction(a)
        act = QAction(action_name, self, triggered=callback)
        menu.addAction(act)
        if plugin:
            self.plugin_menu_actions.append((menu, act))

    def register_dock(self, title: str, widget, area: str = "left", plugin=False):
        # remove previous dock with same title if it was plugin-provided
        old = self.docks.get(title)
        if old and old in self.plugin_docks:
            self.removeDockWidget(old)
            try:
                self.panel_actions.get(title).setChecked(False)
            except Exception:
                pass
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        area_map = {"left": Qt.LeftDockWidgetArea, "right": Qt.RightDockWidgetArea, "bottom": Qt.BottomDockWidgetArea, "top": Qt.TopDockWidgetArea}
        self.addDockWidget(area_map.get(area, Qt.LeftDockWidgetArea), dock)
        self._register_panel_toggle(title, dock)
        if plugin:
            self.plugin_docks.append(dock)

    def new_file(self):
        ed = CodeEditor(self); ed.file_path = None
        self.add_tab(ed, "untitled", pane="active")

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", str(self.workspace_dir))
        if path: self.open_file(Path(path))

    def open_file_with_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File With", str(self.workspace_dir))
        if not path: return
        suffix = Path(path).suffix.lower()
        handlers = self.file_handlers.get(suffix, [])
        if not handlers:
            self.open_file(Path(path)); return
        names = [n for n,_ in handlers]
        name, ok = QInputDialog.getItem(self, "Open With", "Handler:", names, 0, False)
        if ok and name:
            self.open_file(Path(path), handler_name=name)

    def open_file(self, path: Path, pane: str = "active", handler_name: str = None):
        suffix = path.suffix.lower()
        handler = self._handler_for_suffix(suffix, name=handler_name)
        if handler:
            name, factory = handler
            try:
                w = factory(path, self.api)
                if getattr(w, "file_path", None) is None:
                    setattr(w, "file_path", path)
                self.add_tab(w, path.name, pane=pane)
                self.status.showMessage(f"Opened {path} with {name}", 3000)
                return
            except Exception as e:
                QMessageBox.critical(self, "Handler Error", str(e))
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            QMessageBox.critical(self, "Open Error", str(e)); return
        ed = CodeEditor(self); ed.file_path = Path(path); ed.setPlainText(text)
        self.add_tab(ed, ed.file_path.name, pane=pane)

    def save_current(self):
        w = self.current_widget()
        if not w: return
        if hasattr(w, "save") and callable(getattr(w, "save")):
            try:
                w.save(); self.status.showMessage("Saved", 2000); return
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e)); return
        if isinstance(w, CodeEditor):
            if getattr(w, "file_path", None) is None: return self.save_current_as()
            try:
                w.file_path.write_text(w.toPlainText(), encoding="utf-8")
                w.document().setModified(False)
                self._refresh_tab_title(self.active_tabs(), w)
                self.status.showMessage(f"Saved {w.file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))

    def save_current_as(self):
        w = self.current_widget()
        if not w: return
        path, _ = QFileDialog.getSaveFileName(self, "Save As", str(self.workspace_dir))
        if not path: return
        if hasattr(w, "save_as") and callable(getattr(w, "save_as")):
            try:
                w.save_as(Path(path)); self.status.showMessage(f"Saved {path}", 2000); return
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e)); return
        if isinstance(w, CodeEditor):
            try:
                w.file_path = Path(path)
                w.file_path.write_text(w.toPlainText(), encoding="utf-8")
                w.document().setModified(False)
                self._refresh_tab_title(self.active_tabs(), w)
                self.status.showMessage(f"Saved {w.file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))

    def save_all(self):
        for tabs in (self.left_tabs, self.right_tabs):
            for i in range(tabs.count()):
                w = tabs.widget(i)
                if hasattr(w, "save"):
                    try: w.save()
                    except Exception: pass
                elif isinstance(w, CodeEditor) and getattr(w, "file_path", None):
                    try:
                        w.file_path.write_text(w.toPlainText(), encoding="utf-8")
                        w.document().setModified(False)
                    except Exception: pass

    def open_workspace_dialog(self):
        d = QFileDialog.getExistingDirectory(self, "Open Workspace", str(self.workspace_dir))
        if d: self.set_workspace(Path(d))

    def set_workspace(self, path: Path):
        try:
            resolved = Path(path).expanduser().resolve()
        except Exception:
            resolved = Path(path).expanduser()
        self.workspace_dir = resolved
        self.settings.setValue("workspace_dir", str(self.workspace_dir))
        self.fs_model.setRootPath(str(self.workspace_dir))
        self.explorer.setRootIndex(self.fs_model.index(str(self.workspace_dir)))
        self.setWindowTitle(f"{APP_NAME} — {self.workspace_dir}")

    def _on_explorer_double_click(self, idx):
        p = Path(self.fs_model.filePath(idx))
        if p.is_file(): self.open_file(p)

    def _close_tab(self, i: int, pane=None):
        tabs = self.left_tabs if pane=="left" else self.right_tabs if pane=="right" else self.active_tabs()
        if i < 0 or not tabs:
            return
        widget = tabs.widget(i)
        if hasattr(tabs, "close_tab"):
            tabs.close_tab(i)
        else:
            tabs.removeTab(i)
            if widget:
                widget.deleteLater()
        if tabs is self.right_tabs:
            self._maybe_hide_right_split()
        self._update_status()

    def _refresh_tab_title(self, tabs, w):
        i = tabs.indexOf(w)
        if i >= 0:
            name = getattr(w, "file_path", None)
            if name: name = Path(name).name
            else: name = "untitled"
            tabs.setTabText(i, name)

    def _update_status(self):
        w = self.current_widget()
        if not w: return
        path = str(getattr(w, "file_path", "untitled"))
        if isinstance(w, CodeEditor):
            self.status.showMessage(f"{path} — Ln {w.current_line()}, Col {w.current_column()}")
        else:
            self.status.showMessage(path)

    def _do(self, op):
        w = self.current_widget()
        if isinstance(w, CodeEditor):
            getattr(w, op)()

    def toggle_terminal(self, checked):
        act = self.panel_actions.get('Terminal')
        if act: act.setChecked(checked)

    def toggle_explorer(self, checked):
        act = self.panel_actions.get('Explorer')
        if act: act.setChecked(checked)

    def register_theme(self, name, theme_dict, source="plugin"):
        self.themes[name] = theme_dict
        if source in ("plugin","manifest"):
            self.plugin_themes.add(name)
        self._rebuild_theme_menu()

    def _rebuild_theme_menu(self):
        self.menu_theme.clear()
        for name in sorted(self.themes.keys()):
            act = QAction(name, self, checkable=True, checked=(name == self.current_theme))
            act.triggered.connect(lambda checked, n=name: self.apply_theme(n))
            self.menu_theme.addAction(act)

    def apply_theme(self, name):
        theme = self.themes.get(name)
        if not theme: return
        self.current_theme = name
        pal = QApplication.instance().palette()
        bg = QColor(theme.get("background", "#1e1e1e"))
        fg = QColor(theme.get("foreground", "#eaeaea"))
        alt= QColor(theme.get("alternateBase", theme.get("background", "#222")))
        sel= QColor(theme.get("selection", "#3574f0"))
        pal.setColor(QPalette.Window, bg); pal.setColor(QPalette.WindowText, fg)
        pal.setColor(QPalette.Base, bg); pal.setColor(QPalette.AlternateBase, alt)
        pal.setColor(QPalette.Text, fg); pal.setColor(QPalette.Highlight, sel)
        QApplication.instance().setPalette(pal)
        self.explorer.setStyleSheet(f"QTreeView {{ background: {theme.get('sidebar_bg', theme.get('background','#111'))}; color: {fg.name()}; }}")
        for tabs in (self.left_tabs, self.right_tabs):
            for i in range(tabs.count()):
                w = tabs.widget(i)
                if isinstance(w, CodeEditor):
                    w.apply_theme(theme)
        self._rebuild_theme_menu()
        self.settings.setValue("pref_theme", name)


    def _clear_plugin_contributions(self):
        # remove plugin docks
        for d in list(self.plugin_docks):
            try:
                self.removeDockWidget(d)
            except Exception:
                pass
        self.plugin_docks.clear()
        # remove panel actions for removed docks (keep core ones)
        for title, act in list(self.panel_actions.items()):
            if title not in ("Explorer","Terminal","Search") and title in self.docks:
                try:
                    self.menu_panels.removeAction(act)
                except Exception:
                    pass
                self.panel_actions.pop(title, None)
                self.docks.pop(title, None)
        # remove plugin menu actions
        for menu, act in self.plugin_menu_actions:
            try:
                menu.removeAction(act)
            except Exception:
                pass
        self.plugin_menu_actions.clear()
        # remove plugin commands
        for name in self.plugin_commands:
            cb, act = self.commands.get(name, (None, None))
            if act:
                try: self.removeAction(act)
                except Exception: pass
            self.commands.pop(name, None)
        self.plugin_commands.clear()
        # reset file handlers (they're plugin-supplied)
        self.file_handlers = {}
        self.plugin_file_handlers.clear()
        # remove plugin themes
        for t in list(self.plugin_themes):
            if t in self.themes:
                self.themes.pop(t, None)
        self.plugin_themes.clear()
        self._rebuild_theme_menu()
        # remove plugin status widgets
        for w in self.plugin_status_widgets:
            try:
                self.status.removeWidget(w)
            except Exception:
                pass
        self.plugin_status_widgets.clear()
    def reload_extensions(self):
        ext_path = Path(__file__).resolve().parent.parent / "extensions"
        disabled = self.settings.value("disabled_extensions", [], type=list)
        # clear previous plugin UI to avoid duplicates
        self._clear_plugin_contributions()
        count, names = self.plugin_manager.load_plugins(str(ext_path), disabled=disabled)
        self.status.showMessage(f"Loaded {count} extension(s)", 3000)

    def open_settings(self):
        dlg = SettingsDialog(self, self.themes)
        current = {"theme": self.current_theme or "", "font_size": int(self.settings.value("font_size", 11)),
                   "tab_spaces": int(self.settings.value("tab_spaces", 4)), "autosave": int(self.settings.value("autosave", 0)),
                   "workspace": str(self.settings.value("workspace_dir", str(self.workspace_dir)))}
        dlg.set_values(current)
        if dlg.exec_() == QDialog.Accepted:
            vals = dlg.get_values()
            self.settings.setValue("font_size", vals["font_size"])
            self.settings.setValue("tab_spaces", vals["tab_spaces"])
            self.settings.setValue("autosave", vals["autosave"])
            if vals["workspace"]:
                self.set_workspace(Path(vals["workspace"]))
            if vals["theme"] in self.themes:
                self.apply_theme(vals["theme"])
            f = QFont("Fira Code, Consolas, Monospace"); f.setStyleHint(QFont.Monospace)
            f.setPointSize(int(vals["font_size"])); QApplication.instance().setFont(f)
            for tabs in (self.left_tabs, self.right_tabs):
                for i in range(tabs.count()):
                    w = tabs.widget(i)
                    if isinstance(w, CodeEditor):
                        w.setTabStopDistance(int(vals["tab_spaces"]) * w.fontMetrics().horizontalAdvance(' '))
            self.autosave_sec = int(vals["autosave"])
            if self.autosave_sec > 0: self._autosave_timer.start(self.autosave_sec * 1000)
            else: self._autosave_timer.stop()

    def open_extension_manager(self):
        ExtensionManager(self).exec_()

    def run_current_file(self):
        w = self.current_widget()
        path = getattr(w, "file_path", None)
        if not path or str(path).lower().endswith(".py") is False:
            QMessageBox.information(self, "Run", "Open a .py file to run (F5)."); return
        if isinstance(w, CodeEditor) and w.document().isModified():
            self.save_current()
        python_exe = sys.executable if sys.executable else "python"
        if os.name == "nt":
            cmd = subprocess.list2cmdline([python_exe, str(path)])
        else:
            cmd = shlex.join([python_exe, str(path)])
        self.terminal.run_command(cmd)
        self.status.showMessage(f"Running: {cmd}", 3000)

    def find_dialog(self): self._focus_search()

    def replace_dialog(self):
        w = self.current_widget()
        if isinstance(w, CodeEditor):
            old, ok = QInputDialog.getText(self, "Replace", "Find:")
            if not ok or not old: return
            new, ok = QInputDialog.getText(self, "Replace", "Replace with:")
            if not ok: return
            txt = w.toPlainText().replace(old, new)
            w.setPlainText(txt)

    def goto_line_dialog(self):
        w = self.current_widget()
        if isinstance(w, CodeEditor):
            ln, ok = QInputDialog.getInt(self, "Go to Line", "Line number:", value=w.current_line(), min=1)
            if ok: w.goto_line(ln)

    def _restore_session(self):
        raw = self.settings.value("session_files", "[]")
        try: files = json.loads(raw)
        except Exception: files = []
        for entry in files:
            try:
                p = Path(entry.get("path", "")); pane = entry.get("pane", "left")
                if p.exists(): self.open_file(p, pane=pane)
            except Exception: pass

    def closeEvent(self, e):
        lst = []
        for pane, tabs in (("left", self.left_tabs), ("right", self.right_tabs)):
            for i in range(tabs.count()):
                w = tabs.widget(i); p = getattr(w, "file_path", None)
                if p: lst.append({"path": str(p), "pane": pane})
        self.settings.setValue("session_files", json.dumps(lst))
        return super().closeEvent(e)


def run():
    app = QApplication(sys.argv)
    app.setOrganizationName(ORG); app.setOrganizationDomain(DOMAIN); app.setApplicationName(APP_NAME)
    font = QFont("Fira Code, Consolas, Monospace"); font.setStyleHint(QFont.Monospace); app.setFont(font)
    w = MainWindow(); w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run()
