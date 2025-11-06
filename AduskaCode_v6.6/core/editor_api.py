
from pathlib import Path

class EditorAPI:
    def __init__(self, main_window):
        self._mw = main_window

    def register_menu(self, path: str, callback):
        self._mw.register_menu(path, callback, plugin=True)

    def register_command(self, name: str, callback, shortcut: str = None):
        self._mw.register_command(name, callback, shortcut, plugin=True)

    def register_theme(self, name: str, theme_dict: dict):
        self._mw.register_theme(name, theme_dict, source="plugin")

    def set_theme(self, theme_dict: dict, name: str = None):
        if name:
            self._mw.register_theme(name, theme_dict, source="plugin")
            self._mw.apply_theme(name)

    def add_tab(self, widget, title: str, pane: str = "active"):
        self._mw.add_tab(widget, title, pane)

    def open_file(self, path: str, pane: str = "active", handler: str = None):
        self._mw.open_file(Path(path), pane=pane, handler_name=handler)

    def current_path(self):
        w = self._mw.current_widget()
        return str(getattr(w, "file_path", "")) if w else ""

    def get_workspace(self):
        return str(self._mw.workspace_dir)

    def register_file_handler(self, suffixes, name: str, factory):
        self._mw.register_file_handler(suffixes, name, factory, plugin=True)

    def register_dock(self, title: str, widget, area: str = "left"):
        self._mw.register_dock(title, widget, area, plugin=True)

    def add_status_widget(self, widget):
        self._mw.add_status_widget(widget, plugin=True)

    def show_message(self, text: str, ms: int = 3000):
        self._mw.status.showMessage(text, ms)
