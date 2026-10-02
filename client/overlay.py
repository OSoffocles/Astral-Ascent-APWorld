"""
In-game overlay (Windows): a transparent, click-through, always-on-top window in the top-right corner of the
game. It keeps the 8 most recent messages (what you send and receive, hints, other players' goals) on screen,
newest at the bottom, plus one line with how many checks are in logic.

Astral Ascent runs in borderless fullscreen, so a normal window can sit on top of it. The overlay runs its
own tkinter loop in a background thread; the client only calls post() and set_status().
"""
from __future__ import annotations

import logging
import queue
import sys
import threading
import time

logger = logging.getLogger("Client")  # shows up in the client window and its log file

MAX_MESSAGES = 8  # the most recent messages stay on screen (nothing disappears before it's read)
WIDTH = 460
MARGIN = 24
TRANSPARENT = "#010203"  # this colour is see-through
COLOURS = {
    "received": "#ffd479",
    "sent": "#8fd3ff",
    "found": "#d8d8d8",
    "hint": "#d7a6ff",
    "goal": "#7dffa0",
    "status": "#c8c8c8",
}


class Overlay:
    def __init__(self) -> None:
        self.messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self.status = ""
        self.game_pid = 0
        self.enabled = sys.platform == "win32"
        self.thread: threading.Thread | None = None
        self.stopping = False
        self.last_error = ""
        self.foreground_pid = 0   # for /overlay test: which process owns the window in front
        self.visible = False
        self.solid = False        # test mode: grey background instead of see-through

    # ------------------------------------------------------------------ used by the client (any thread)

    def start(self) -> None:
        if not self.enabled or self.thread is not None:
            return
        self.thread = threading.Thread(target=self._run, name="Astral Ascent overlay", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stopping = True

    def post(self, text: str, kind: str = "received") -> None:
        if self.enabled:
            self.messages.put((text, kind))

    def set_status(self, text: str) -> None:
        self.status = text

    # ------------------------------------------------------------------ overlay thread

    def _run(self) -> None:
        try:
            self._loop()
        except Exception as e:  # never take the client down with it
            import traceback

            self.last_error = f"{type(e).__name__}: {e}"
            logger.warning(f"The in-game overlay stopped: {self.last_error}\n{traceback.format_exc()}")
            self.thread = None

    def _loop(self) -> None:
        import ctypes
        import tkinter as tk
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        background = "#303040" if self.solid else TRANSPARENT
        root.configure(bg=background)
        if not self.solid:
            try:
                root.attributes("-transparentcolor", TRANSPARENT)
            except tk.TclError:  # only exists on Windows
                pass
        root.update_idletasks()

        def make_click_through() -> None:
            """Clicks go to the game, no taskbar button, never takes focus. Only the outer (frame) window gets
            these styles: a layered style on Tk's inner child window makes everything invisible."""
            GWL_EXSTYLE = -20
            extra = 0x80000 | 0x20 | 0x80 | 0x08000000  # LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE
            hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if style & extra != extra:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | extra)
                # Changing the style drops the layered colour key: set it (and topmost) again.
                try:
                    if not self.solid:
                        root.attributes("-transparentcolor", TRANSPARENT)
                    root.attributes("-alpha", 0.95)
                except tk.TclError:  # -transparentcolor only exists on Windows
                    pass
                root.attributes("-topmost", True)

        make_click_through()

        font = ("Segoe UI", 12, "bold")
        status_label = tk.Label(root, text="", font=font, fg=COLOURS["status"], bg="#141420",
                                anchor="e", justify="right", padx=10, pady=4, wraplength=WIDTH - 20)
        shown: list[tuple[tk.Label, float]] = []

        def game_rect() -> tuple[int, int, int, int] | None:
            """(left, top, right, bottom) of the game's foreground window, or None when it isn't in front."""
            front = user32.GetForegroundWindow()
            if not front or not self.game_pid:
                return None
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(front, ctypes.byref(pid))
            self.foreground_pid = pid.value
            if pid.value != self.game_pid:
                return None
            rect = wintypes.RECT()
            user32.GetWindowRect(front, ctypes.byref(rect))
            return rect.left, rect.top, rect.right, rect.bottom

        visible = False

        def tick() -> None:
            nonlocal visible
            if self.stopping:
                root.destroy()
                return
            now = time.monotonic()
            while not self.messages.empty():
                text, kind = self.messages.get_nowait()
                label = tk.Label(root, text=text, font=font, fg=COLOURS.get(kind, "#ffffff"), bg="#141420",
                                 anchor="e", justify="right", padx=10, pady=4, wraplength=WIDTH - 20)
                label.pack(side="top", anchor="e", pady=2)
                shown.append((label, now))
            while len(shown) > MAX_MESSAGES:
                shown.pop(0)[0].destroy()
            if status_label.cget("text") != self.status:
                status_label.configure(text=self.status)
                if self.status:
                    status_label.pack(side="top", anchor="e", pady=(0, 6), before=shown[0][0] if shown else None)
                else:
                    status_label.pack_forget()

            rect = game_rect()
            self.visible = rect is not None
            if rect is None:
                if visible:
                    root.withdraw()
                    visible = False
            else:
                left, top, right, _ = rect
                root.geometry(f"{WIDTH}x{root.winfo_reqheight()}+{right - WIDTH - MARGIN}+{top + MARGIN}")
                if not visible:
                    root.deiconify()
                    root.attributes("-topmost", True)
                    make_click_through()
                    visible = True
            root.after(200, tick)

        root.after(200, tick)
        root.mainloop()
        # Free every Tk object in this thread: Tcl aborts the process if they're collected from another one.
        shown.clear()
        del tick, game_rect, make_click_through, status_label, root
        import gc

        gc.collect()


def describe(args: dict, me: int, player_name, item_name, location_name) -> tuple[str, str] | None:
    """Turn a PrintJSON packet into (overlay text, kind), or None if it isn't for the overlay.
    player_name(slot), item_name(item_id, receiving_slot) and location_name(location_id, slot) look up names."""
    kind = args.get("type")
    if kind == "Goal":
        slot = args.get("slot")
        return (f"{player_name(slot)} completed their goal!" if slot != me else "You completed your goal!"), "goal"
    item = args.get("item")
    if item is None:
        return None
    item_id, location_id, finder, _flags = (item if isinstance(item, (tuple, list))
                                            else (item["item"], item["location"], item["player"], item["flags"]))
    receiver = args.get("receiving")
    if kind == "ItemSend":
        if receiver == me and finder == me:
            return f"You found your {item_name(item_id, me)}", "found"
        if receiver == me:
            return f"Received {item_name(item_id, me)} from {player_name(finder)}", "received"
        if finder == me:
            return f"Sent {item_name(item_id, receiver)} to {player_name(receiver)}", "sent"
        return None
    if kind == "Hint" and not args.get("found") and me in (receiver, finder):
        whose = "Your" if receiver == me else f"{player_name(receiver)}'s"
        where = "your world" if finder == me else f"{player_name(finder)}'s world"
        return f"Hint: {whose} {item_name(item_id, receiver)} is at {location_name(location_id, finder)} " \
               f"in {where}", "hint"
    return None
