
import importlib.util, json, sys, subprocess, zipfile, tempfile, traceback
from pathlib import Path

class PluginManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def load_plugins(self, extensions_dir: str, disabled=None):
        count = 0
        disabled = set(disabled or [])
        p = Path(extensions_dir)
        if not p.exists():
            return 0, []
        loaded_names = []
        for child in sorted(p.iterdir()):
            if child.name in disabled:
                continue
            if child.is_dir() and child.name.endswith(".extend"):
                loaded = self._load_from_directory(child, disabled)
            elif child.is_file() and child.suffix == ".extend":
                loaded = self._load_from_zip(child, disabled)
            else:
                loaded = 0
            count += loaded
            if loaded:
                loaded_names.append(child.name)
        return count, loaded_names

    def _load_from_directory(self, folder: Path, disabled):
        mf = folder / "manifest.json"
        entry = folder / "main.py"
        if not (mf.exists() and entry.exists()):
            return 0
        try:
            manifest = json.loads(mf.read_text(encoding="utf-8"))
        except Exception as e:
            print("[EXT] manifest error:", e); return 0
        name = manifest.get("name", folder.name)
        if name in disabled: return 0
        self._ensure_requires(manifest.get("requires", []), name)
        return self._exec_plugin(entry, manifest)

    def _load_from_zip(self, file_path: Path, disabled):
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                namelist = z.namelist()
                manifest_name = next((n for n in namelist if n.endswith("manifest.json")), None)
                entry_name = next((n for n in namelist if n.endswith("main.py")), None)
                if not manifest_name or not entry_name:
                    print(f"[EXT] {file_path.name}: missing manifest.json or main.py")
                    return 0
                manifest = json.loads(z.read(manifest_name).decode("utf-8"))
                name = manifest.get("name", file_path.stem)
                if name in disabled: return 0
                tmp = Path(tempfile.mkdtemp(prefix="aduska_ext_"))
                z.extractall(tmp)
                entry = tmp / entry_name
        except Exception as e:
            print("[EXT] zip error:", e); return 0

        self._ensure_requires(manifest.get("requires", []), manifest.get("name", file_path.stem))
        loaded = self._exec_plugin(entry, manifest)
        return loaded

    def _ensure_requires(self, requires, plugin_name="plugin"):
        missing = []
        # map common pip names -> import module names
        name_map = {
            "Markdown": "markdown",
            "Pillow": "PIL",
            "PyYAML": "yaml",
            "yaml": "yaml",
            "PyMuPDF": "fitz",
            "fitz": "fitz",
        }
        for r in requires or []:
            mod = name_map.get(r, r)
            try:
                __import__(mod)
            except Exception:
                missing.append(r)
        if missing:
            print(f"[EXT] Installing requirements for {plugin_name}: {missing}")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=False)
            except Exception as e:
                print("[EXT] pip failed:", e)

    def _exec_plugin(self, entry_path: Path, manifest: dict) -> int:
        try:
            spec = importlib.util.spec_from_file_location(manifest.get("name", entry_path.stem), str(entry_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            if hasattr(mod, "on_load"):
                mod.on_load(self.main_window.api)
            th = manifest.get("theme")
            if isinstance(th, dict):
                self.main_window.register_theme(manifest.get("name", entry_path.stem), th, source="manifest")
            return 1
        except Exception as e:
            print("[EXT] load failed:", e)
            traceback.print_exc()
            return 0
