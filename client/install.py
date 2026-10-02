"""
Finding and starting Astral Ascent (Windows): Epic Games Store first, then Steam, then a folder the client
remembered from a running game.
"""
from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass

GAME_EXE = "Astral Ascent.exe"
STEAM_APP_ID = "1280930"
EPIC_MANIFESTS = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                              "Epic", "EpicGamesLauncher", "Data", "Manifests")


@dataclass
class Install:
    folder: str
    store: str        # "epic", "steam" or "folder"
    launch_uri: str   # what to open to start the game ("" = run the exe directly)

    @property
    def exe(self) -> str:
        return os.path.join(self.folder, GAME_EXE)


def find_epic() -> Install | None:
    for path in glob.glob(os.path.join(EPIC_MANIFESTS, "*.item")):
        try:
            with open(path, encoding="utf-8") as f:
                item = json.load(f)
        except (OSError, ValueError):
            continue
        folder = item.get("InstallLocation", "")
        if item.get("DisplayName") != "Astral Ascent" or not os.path.isfile(os.path.join(folder, GAME_EXE)):
            continue
        app = f"{item.get('CatalogNamespace')}%3A{item.get('CatalogItemId')}%3A{item.get('AppName')}"
        return Install(folder, "epic", f"com.epicgames.launcher://apps/{app}?action=launch&silent=true")
    return None


def _steam_root() -> str | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            return winreg.QueryValueEx(key, "SteamPath")[0]
    except OSError:
        return None


def find_steam() -> Install | None:
    root = _steam_root()
    if not root:
        return None
    libraries = [root]
    try:
        with open(os.path.join(root, "steamapps", "libraryfolders.vdf"), encoding="utf-8") as f:
            libraries += [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', f.read())]
    except OSError:
        pass
    for library in libraries:
        manifest = os.path.join(library, "steamapps", f"appmanifest_{STEAM_APP_ID}.acf")
        try:
            with open(manifest, encoding="utf-8") as f:
                match = re.search(r'"installdir"\s+"([^"]+)"', f.read())
        except OSError:
            continue
        if match:
            folder = os.path.join(library, "steamapps", "common", match.group(1))
            if os.path.isfile(os.path.join(folder, GAME_EXE)):
                return Install(folder, "steam", f"steam://rungameid/{STEAM_APP_ID}")
    return None


def find_install(remembered: str | None = None) -> Install | None:
    for finder in (find_epic, find_steam):
        try:
            found = finder()
        except Exception:
            found = None
        if found:
            return found
    if remembered and os.path.isfile(os.path.join(remembered, GAME_EXE)):
        return Install(remembered, "folder", "")
    return None


def launch(install: Install) -> None:
    """Start the game through its store (keeps DRM and cloud saves working), or the exe as a fallback."""
    if install.launch_uri:
        os.startfile(install.launch_uri)  # type: ignore[attr-defined]  (Windows only)
    else:
        import subprocess

        subprocess.Popen([install.exe], cwd=install.folder)
