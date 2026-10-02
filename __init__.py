# Archipelago finds the world through this file.
from . import components as components  # registers "Astral Ascent Client" in the Archipelago Launcher
from .world import AstralAscentWorld as AstralAscentWorld

__all__ = ["AstralAscentWorld"]
