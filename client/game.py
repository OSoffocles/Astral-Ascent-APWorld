"""
Talking to the running game (Windows only): memory reads/writes with pymem, and the XP-track file patch.

Findings this is based on (game v2.6.4):
- Construct globals are doubles at fixed offsets inside Astral Ascent.exe (see GLOBALS).
- Saved dictionaries (arsenal, gameProgress, ...) live on the heap as arrays of 40-byte entries:
  [type:8 (0x02 = number)][value:int64][key char*][key length:u32 + hash:u32][pad:8].
  These are the game's copies of the save slots. Changing the active slot's copy while at the main menu,
  then loading the slot, applies the change. In-game the copy is overwritten on every save.
- The XP requirement per track step is read from array_deathrecap_skillbar.json at game start. The
  level-up itself happens on the end-of-run screen, when the XP bar is full.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import struct

logger = logging.getLogger("AstralAscent")

GAME_EXE = "Astral Ascent.exe"

GLOBALS = {  # name -> offset from the start of Astral Ascent.exe (Epic build; Steam: found by globals_ready)
    # Run values (found with a memory scan during a run; writes confirmed in game)
    "quartz": 0xA2EEBF8,
    "keys": 0xA2EEC00,
    "stars": 0xA2EEC08,
    "life": 0xA2EFCB8,
    "life_max": 0xA2EFCC0,
    "mana": 0xA2EFCD8,
    "mana_max": 0xA2EFCE0,
    "sun_pieces": 0xA2EEC10,
    "yalee_tickets": 0xA2EEC18,
    "destiny_fragments": 0xA2EEC20,  # total collected; recalculated by the game on load
    "track_level": 0xA2EFDA8,         # next XP-track step (1 = nothing revealed yet)
    "track_xp": 0xA2EFDB0,            # XP toward the next step
}

XP_TRACK_FILE = "array_deathrecap_skillbar.json"
LIVE_VALUE_OFFSET = 0x48  # live table: from a key's length byte to its value (a double)
ZIM_CELL = 0x48   # Zim-Zim array cell size
ZIM_ROW = 0x1B0   # 6 cells per row
ENTRY_SIZE = 40
ENTRY_NUMBER = 0x02


class GameNotRunning(Exception):
    pass


class Game:
    def __init__(self) -> None:
        self.pm = None
        self.base = 0
        self.size = 0
        self.pid = 0
        self.globals_address = 0  # where sun_pieces lives in this process (0 = not found yet)
        self.globals_tried = 0.0

    # ------------------------------------------------------------------ process

    def attach(self) -> bool:
        """Attach to the game if it is running. Returns True if (still) attached."""
        import pymem
        import pymem.exception
        import pymem.process

        if self.pm is not None:
            try:
                self.pm.read_bytes(self.base, 2)
                return True
            except Exception:
                self.pm = None
        try:
            pm = pymem.Pymem(GAME_EXE)
        except (pymem.exception.ProcessNotFound, pymem.exception.CouldNotOpenProcess, Exception):
            return False
        module = pymem.process.module_from_name(pm.process_handle, GAME_EXE)
        if module is None:  # the game is still starting up or shutting down
            return False
        self.pm = pm
        self.base = module.lpBaseOfDll
        self.size = module.SizeOfImage
        if pm.process_id != self.pid:
            self.globals_address = 0
            self.globals_tried = 0.0
        self.pid = pm.process_id
        return True

    def install_folder(self) -> str | None:
        """Folder of the running Astral Ascent.exe."""
        if self.pm is None:
            return None
        import ctypes
        from ctypes import wintypes

        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(self.pm.process_handle, 0, buffer, ctypes.byref(size)):
            return os.path.dirname(buffer.value)
        return None

    def process_start_time(self) -> float | None:
        """When the game process started (Unix time), to know whether it has read the patched XP file."""
        if self.pm is None:
            return None
        import ctypes
        from ctypes import wintypes

        creation, exit_, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not ctypes.windll.kernel32.GetProcessTimes(self.pm.process_handle, ctypes.byref(creation),
                                                      ctypes.byref(exit_), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return ticks / 10_000_000 - 11_644_473_600

    # ------------------------------------------------------------------ globals

    def _global_address(self, name: str) -> int:
        return self.globals_address + GLOBALS[name] - GLOBALS["sun_pieces"]

    def read_global(self, name: str) -> float:
        return self.pm.read_double(self._global_address(name))

    def write_global(self, name: str, value: float) -> None:
        self.pm.write_double(self._global_address(name), float(value))

    def _globals_plausible(self, address: int) -> bool:
        """Do the doubles at the globals' positions (relative to sun_pieces = address) look like them?"""
        raw = self._read(address, GLOBALS["track_xp"] - GLOBALS["sun_pieces"] + 8)
        if not raw:
            return False

        def value(name: str) -> float:
            return struct.unpack_from("<d", raw, GLOBALS[name] - GLOBALS["sun_pieces"])[0]

        currencies = [value(n) for n in ("sun_pieces", "yalee_tickets", "destiny_fragments")]
        level, xp = value("track_level"), value("track_xp")
        return (all(v == int(v) and 0 <= v < 1e8 for v in currencies) and level == int(level)
                and 1 <= level <= 200 and 0 <= xp < 1e12)

    def globals_ready(self, saved: dict[str, float]) -> bool:
        """
        Find the game's global values (Sun Pieces, Yalee Tickets, ...). The Epic build has them at fixed offsets
        (GLOBALS). Other builds (Steam) may have them elsewhere: then the client looks for the same layout,
        matching the values in the save (saved: sun_pieces, yalee_tickets, track_level from the linked slot).
        """
        import time

        if self.globals_address:
            return True
        if self.pm is None or time.monotonic() - self.globals_tried < 20:
            return False
        self.globals_tried = time.monotonic()
        default = self.base + GLOBALS["sun_pieces"]
        if self._globals_plausible(default):
            level = self.pm.read_double(default + GLOBALS["track_level"] - GLOBALS["sun_pieces"])
            sun = self.pm.read_double(default)
            if not saved or level == saved.get("track_level") or sun == saved.get("sun_pieces"):
                self.globals_address = default
                return True
        if not {"sun_pieces", "yalee_tickets", "track_level"} <= set(saved) or saved["track_level"] < 1:
            return False
        level_rel = GLOBALS["track_level"] - GLOBALS["sun_pieces"]
        needle = struct.pack("<d", saved["track_level"])
        want = struct.pack("<dd", saved["sun_pieces"], saved["yalee_tickets"])
        candidates = []
        chunk = 0x1000000
        for start, size in self._image_regions():
            for offset in range(0, size, chunk):
                block = self._read(start + offset, min(chunk + 8, size - offset))
                if not block:
                    continue
                i = block.find(needle)
                while i != -1 and i < chunk:
                    address = start + offset + i - level_rel
                    if (start + offset + i) % 8 == 0 and self._read(address, 16) == want and \
                            self._globals_plausible(address):
                        candidates.append(address)
                    i = block.find(needle, i + 1)
        if len(candidates) == 1:
            self.globals_address = candidates[0]
            logger.info(f"Found the game's values at Astral Ascent.exe+{candidates[0] - self.base:X} "
                        "(a different game build than expected).")
            return True
        return False

    # ------------------------------------------------------------------ saved-data copies (heap)

    def _regions(self):
        import pymem.memory

        MEM_COMMIT, MEM_PRIVATE, PAGE_READWRITE = 0x1000, 0x20000, 0x04
        address = 0
        while address < 0x7FFFFFFFFFFF:
            try:
                mbi = pymem.memory.virtual_query(self.pm.process_handle, address)
            except Exception:
                return
            if mbi.RegionSize == 0:
                return
            if mbi.State == MEM_COMMIT and mbi.Type == MEM_PRIVATE and mbi.Protect == PAGE_READWRITE:
                yield mbi.BaseAddress, mbi.RegionSize
            address = mbi.BaseAddress + mbi.RegionSize

    def _image_regions(self):
        """Readable, writable parts of Astral Ascent.exe in memory (where the globals live)."""
        import pymem.memory

        MEM_COMMIT, WRITABLE = 0x1000, 0x04 | 0x08 | 0x40 | 0x80
        address, end = self.base, self.base + self.size
        while address < end:
            try:
                mbi = pymem.memory.virtual_query(self.pm.process_handle, address)
            except Exception:
                return
            if mbi.RegionSize == 0:
                return
            if mbi.State == MEM_COMMIT and mbi.Protect & WRITABLE and not mbi.Protect & 0x100:
                yield mbi.BaseAddress, min(mbi.RegionSize, end - mbi.BaseAddress)
            address = mbi.BaseAddress + mbi.RegionSize

    def _read(self, address: int, size: int) -> bytes | None:
        try:
            return self.pm.read_bytes(address, size)
        except Exception:
            return None

    def find_tables(self, anchor_key: str) -> list[dict[str, tuple[int, int, int]]]:
        """
        Every in-memory dictionary that contains anchor_key, as {key: (entry address, type, value)}.
        Slow (reads all of the game's heap once or twice): only used on request.
        """
        needle = anchor_key.encode("ascii") + b"\0"
        copies: list[int] = []
        chunk = 0x1000000
        regions = list(self._regions())
        for start, size in regions:
            for offset in range(0, size, chunk):
                block = self._read(start + offset, min(chunk + 64, size - offset))
                if not block:
                    continue
                i = block.find(needle)
                while i != -1 and i < chunk:
                    copies.append(start + offset + i)
                    i = block.find(needle, i + 1)
        patterns = [struct.pack("<Q", c) for c in copies]

        anchors: list[int] = []
        for start, size in regions:
            for offset in range(0, size, chunk):
                block = self._read(start + offset, min(chunk, size - offset))
                if not block:
                    continue
                for pattern in patterns:
                    i = block.find(pattern)
                    while i != -1:
                        if i % 8 == 0 and i >= 16:
                            anchors.append(start + offset + i - 16)
                        i = block.find(pattern, i + 1)

        tables = []
        seen: set[int] = set()
        for anchor in anchors:
            if anchor in seen:
                continue
            table = self._walk_table(anchor)
            if anchor_key in table and table[anchor_key][0] == anchor:
                seen.update(entry[0] for entry in table.values())
                tables.append(table)
        return tables

    def _entry(self, address: int) -> tuple[str, int, int] | None:
        raw = self._read(address, ENTRY_SIZE)
        if not raw:
            return None
        tag, value, key_ptr, key_len = struct.unpack_from("<QqQI", raw)
        if not (1 <= key_len <= 96) or key_ptr < 0x10000:
            return None
        key = self._read(key_ptr, key_len)
        if not key or not all(32 <= b < 127 for b in key):
            return None
        return key.decode("ascii"), tag & 0xFF, value

    def _walk_table(self, anchor: int, max_gap: int = 4) -> dict[str, tuple[int, int, int]]:
        table: dict[str, tuple[int, int, int]] = {}
        for direction in (-1, 1):
            address, gap = anchor, 0
            while gap <= max_gap and len(table) < 5000:
                entry = self._entry(address)
                if entry:
                    key, tag, value = entry
                    table.setdefault(key, (address, tag, value))
                    gap = 0
                else:
                    gap += 1
                address += direction * ENTRY_SIZE
        return table

    def write_entry(self, entry_address: int, value: int) -> None:
        self.pm.write_longlong(entry_address + 8, int(value))

    # ------------------------------------------------------------------ live values (what the game uses in play)
    #
    # Found 2026-10-01 (snap test): while a slot is loaded, the game keeps its saved dictionaries in a table of
    # nodes: [hash word, top byte 0x88][2 heap pointers][length byte = 2 x len][key text][0] ... with the value as
    # a DOUBLE 0x48 bytes after the length byte (confirmed in two sessions, 2026-10-01). Writing there takes
    # effect immediately (Arsenal weapons and passives) and is saved by the game at the next room change.

    @staticmethod
    def live_node_ok(raw: bytes) -> bool:
        """raw = the 0x18 bytes before a key's length byte + 0x50 bytes from it. Checks the node header
        (a hash word whose top byte is 0x88, then two heap pointers) and that the value is a sane double.
        (The bytes AFTER the value differ between sessions, so they aren't used.)"""
        if len(raw) < 0x18 + LIVE_VALUE_OFFSET + 8:
            return False
        tag, prev_ptr, next_ptr = struct.unpack_from("<QQQ", raw, 0)
        if tag >> 56 != 0x88:
            return False
        for ptr in (prev_ptr, next_ptr):
            if not (0x10000 <= ptr < 0x7FF000000000) or ptr % 8:
                return False
        value = struct.unpack_from("<d", raw, 0x18 + LIVE_VALUE_OFFSET)[0]
        return value == value and abs(value) < 1e9

    def find_live(self, keys: list[str]) -> dict[str, list[int]]:
        """Value addresses of the live nodes for these keys (one pass over the heap)."""
        import re

        needles = {bytes([2 * len(k)]) + k.encode("ascii") + b"\0": k for k in keys if 0 < len(k) < 120}
        pattern = re.compile(b"|".join(re.escape(n) for n in sorted(needles, key=len, reverse=True)))
        found: dict[str, list[int]] = {}
        chunk = 0x1000000
        for start, size in self._regions():
            for offset in range(0, size, chunk):
                block = self._read(start + offset, min(chunk + 256, size - offset))
                if not block:
                    continue
                for match in pattern.finditer(block):
                    i = match.start()
                    if i >= chunk:
                        break
                    if i < 0x18 or not self.live_node_ok(block[i - 0x18:i + LIVE_VALUE_OFFSET + 8]):
                        continue
                    found.setdefault(needles[match.group()], []).append(start + offset + i + LIVE_VALUE_OFFSET)
        return found

    def live_key_at(self, value_address: int, key: str) -> bool:
        """Is this still the live node for key? (memory can be reused after a slot change)"""
        expected = bytes([2 * len(key)]) + key.encode("ascii") + b"\0"
        raw = self._read(value_address - LIVE_VALUE_OFFSET - 0x18, 0x18 + LIVE_VALUE_OFFSET + 8)
        return bool(raw) and raw[0x18:0x18 + len(expected)] == expected and self.live_node_ok(raw)

    def read_live(self, value_address: int) -> float:
        return self.pm.read_double(value_address)

    def write_live(self, value_address: int, value: float) -> None:
        self.pm.write_double(value_address, float(value))


    # ------------------------------------------------------------------ live tables: text values, keys, links
    #
    # Found 2026-10-01: text values (spell/aura states) sit in the same place as numbers, as a short string
    # [2 x length][characters][0]. The two pointers after a node's hash word point 8 bytes into other nodes of
    # the SAME table, so following them lists the whole table (spell ids and aura ids overlap, so this is how
    # the client tells spellbook_unlocked, relics_unlocked and bannedSpells apart). Renaming a key in place
    # (same length) works too: that's how bans are switched on and off.

    def node(self, header: int) -> tuple[str, str | None, tuple[int, int]] | None:
        """(key, text value or None, links) of the live node whose header starts at header."""
        raw = self._read(header, 0x18 + 0x60)
        if not raw:
            return None
        tag, p1, p2 = struct.unpack_from("<QQQ", raw, 0)
        n = raw[0x18]
        if tag >> 56 != 0x88 or n % 2 or not 2 <= n <= 90 or raw[0x19 + n // 2] != 0:
            return None
        key = raw[0x19:0x19 + n // 2]
        if not all(32 <= c < 127 for c in key):
            return None
        v = 0x18 + LIVE_VALUE_OFFSET
        length = raw[v] // 2
        text = None
        if raw[v] and raw[v] % 2 == 0 and length < 22 and raw[v + 1 + length] == 0 and \
                all(32 <= c < 127 for c in raw[v + 1:v + 1 + length]):
            text = raw[v + 1:v + 1 + length].decode("ascii")
        return key.decode("ascii"), text, (p1, p2)

    def find_nodes(self, keys: list[str]) -> dict[str, list[int]]:
        """Header addresses of every live node with one of these keys (any value type), one pass over the heap."""
        import re

        needles = {bytes([2 * len(k)]) + k.encode("ascii") + b"\0": k for k in keys if 0 < len(k) < 90}
        if not needles:
            return {}
        pattern = re.compile(b"|".join(re.escape(n) for n in sorted(needles, key=len, reverse=True)))
        found: dict[str, list[int]] = {}
        chunk = 0x1000000
        for start, size in self._regions():
            for offset in range(0, size, chunk):
                block = self._read(start + offset, min(chunk + 256, size - offset))
                if not block:
                    continue
                for match in pattern.finditer(block):
                    i = match.start()
                    if i >= chunk:
                        break
                    if i < 0x18:
                        continue
                    tag, p1, p2 = struct.unpack_from("<QQQ", block, i - 0x18)
                    if tag >> 56 == 0x88 and all(0x10000 <= p < 0x7FF000000000 and p % 8 == 0 for p in (p1, p2)):
                        found.setdefault(needles[match.group()], []).append(start + offset + i - 0x18)
        return found

    def walk_table(self, header: int, limit: int = 3000) -> dict[str, int]:
        """Every node of the table this node belongs to, as {key: header address}."""
        seen: set[int] = set()
        queue, keys = [header], {}
        while queue and len(seen) < limit:
            h = queue.pop()
            if h in seen:
                continue
            seen.add(h)
            for guess in (h - 8, h, h - 0x10):  # the links aim 8 bytes into a node
                found = self.node(guess)
                if found:
                    key, _text, links = found
                    if guess != h:
                        if guess in seen:
                            break
                        seen.add(guess)
                    keys.setdefault(key, guess)
                    queue.extend(p for p in links if p)
                    break
        return keys

    def node_key(self, header: int) -> str | None:
        found = self.node(header)
        return found[0] if found else None

    def read_text(self, header: int) -> str | None:
        found = self.node(header)
        return found[1] if found else None

    def write_text(self, header: int, text: str) -> None:
        raw = bytes([2 * len(text)]) + text.encode("ascii") + b"\0"
        self.pm.write_bytes(header + 0x18 + LIVE_VALUE_OFFSET, raw, len(raw))

    def rename(self, header: int, new_key: str) -> None:
        """Rename a live entry (same length only)."""
        key = self.node_key(header)
        if key is None or len(key) != len(new_key):
            raise ValueError(f"can't rename {key!r} to {new_key!r}")
        self.pm.write_bytes(header + 0x19, new_key.encode("ascii"), len(new_key))

    # ------------------------------------------------------------------ Zim-Zim (botanist array)
    #
    # Found 2026-10-01 (Mana Up! snapshots, confirmed in game): an array of 0x48-byte cells, 6 per row (rows
    # 0x1B0 apart): label, prices, tiers bought (double), status ("unlocked" / "" = not revealed), stat tag,
    # stat value. From a row's stat-tag length byte: status -0x48, tiers -0x90, prices -0xD8. The game also
    # keeps an untouched default copy of the array, recognisable by its empty statuses.

    def _short_text(self, length_at: int) -> str | None:
        raw = self._read(length_at, 24)
        if not raw or raw[0] % 2 or raw[0] // 2 > 22:
            return None
        n = raw[0] // 2
        return raw[1:1 + n].decode("ascii", "replace") if n else ""

    def zimzim_arrays(self, tags: dict[int, str]) -> list[dict[int, int]]:
        """Every live Zim-Zim array (the game keeps one per save slot), each as {row: address of its stat tag's
        length byte}. The untouched default copy is left out."""
        arrays: dict[int, dict[int, int]] = {}
        hp_tag = tags[1]
        for text_at in self.find_text(list(tags.values())):
            tag_at = text_at - 1
            for row, tag in tags.items():
                if self._read(tag_at, 1 + len(tag) + 1) != bytes([2 * len(tag)]) + tag.encode("ascii") + b"\0":
                    continue
                prices = self._short_text(tag_at - 3 * ZIM_CELL)
                if not prices or not prices.replace("*", "").isdigit():
                    break
                hp = tag_at + (1 - row) * ZIM_ROW
                if self._short_text(hp) != hp_tag or not self._short_text(hp - ZIM_CELL):
                    break  # the default copy
                tiers = self._read(tag_at - 2 * ZIM_CELL, 8)
                value = struct.unpack("<d", tiers)[0] if tiers else -1
                if value == int(value) and 0 <= value <= 20:
                    arrays.setdefault(hp, {})[row] = tag_at
                break
        return list(arrays.values())

    def find_text(self, texts: list[str]) -> list[int]:
        """Addresses of whole-string copies of these texts (preceded by a length byte), one pass."""
        import re

        pattern = re.compile(b"|".join(re.escape(bytes([2 * len(t)]) + t.encode("ascii") + b"\0")
                                       for t in sorted(texts, key=len, reverse=True)))
        hits: list[int] = []
        chunk = 0x1000000
        for start, size in self._regions():
            for offset in range(0, size, chunk):
                block = self._read(start + offset, min(chunk + 64, size - offset))
                if not block:
                    continue
                for match in pattern.finditer(block):
                    if match.start() >= chunk:
                        break
                    hits.append(start + offset + match.start() + 1)
        return hits

    def zimzim_ok(self, tag_at: int, tag: str) -> bool:
        return self._read(tag_at, len(tag) + 2) == bytes([2 * len(tag)]) + tag.encode("ascii") + b"\0"

    def zimzim_tiers(self, tag_at: int) -> int:
        return int(self.pm.read_double(tag_at - 2 * ZIM_CELL))

    def set_zimzim_tiers(self, tag_at: int, tiers: int) -> None:
        self.pm.write_double(tag_at - 2 * ZIM_CELL, float(tiers))

    def zimzim_status(self, tag_at: int) -> str | None:
        return self._short_text(tag_at - ZIM_CELL)

    def reveal_zimzim(self, tag_at: int) -> None:
        raw = bytes([16]) + b"unlocked\0"
        self.pm.write_bytes(tag_at - ZIM_CELL, raw, len(raw))


def pick_slot_tables(tables: list[dict[str, tuple[int, int, int]]], slot_section: dict,
                     other_sections: list[dict]) -> list[dict[str, tuple[int, int, int]]]:
    """The in-memory tables that belong to the active slot: they match its saved values best."""

    def score(table, section):
        return sum(1 for key, (_, tag, value) in table.items()
                   if tag == ENTRY_NUMBER and isinstance(section.get(key), (int, float)) and section[key] == value)

    chosen = []
    for table in tables:
        mine = score(table, slot_section)
        others = max((score(table, s) for s in other_sections), default=-1)
        if mine > 0 and mine > others:
            chosen.append(table)
    return chosen


# ---------------------------------------------------------------------- game files

def restore_track_file(install_folder: str) -> bool:
    """Put back the original XP-track file (it holds the Merchant's spell prices) from the client's backup."""
    path = os.path.join(install_folder, XP_TRACK_FILE)
    backup = path + ".original"
    if not os.path.exists(backup):
        return False
    shutil.copy2(backup, path)
    return True


# ---------------------------------------------------------------------- spell prices
#
# With Spell Items, spells only come from the multiworld. The Merchant's prices are the "feathers price" column of
# the same XP-track file; an unpayable price makes the spells unbuyable (the client used to take bought spells back,
# but the game re-applied them at the start of a run). The game reads the file at start-up.

SPELL_PRICE_COLUMN = 2
LOCKED_SPELL_PRICE = 9_999_999


def _load_track(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def spell_price_status(install_folder: str) -> str:
    """'locked', 'original' or 'missing'."""
    path = os.path.join(install_folder, XP_TRACK_FILE)
    if not os.path.exists(path):
        return "missing"
    track = _load_track(path)
    ids, prices = track["data"][0], track["data"][SPELL_PRICE_COLUMN]
    spell_prices = [prices[y][0] for y in range(1, len(ids)) if str(ids[y][0]).startswith("spell_")]
    return "locked" if spell_prices and all(v == LOCKED_SPELL_PRICE for v in spell_prices) else "original"


def set_spell_prices(install_folder: str, locked: bool) -> None:
    """Lock (unpayable) or restore (from the backup) the Merchant's spell prices. The XP column is left alone."""
    path = os.path.join(install_folder, XP_TRACK_FILE)
    backup = path + ".original"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    track, original = _load_track(path), _load_track(backup)
    ids, prices = track["data"][0], track["data"][SPELL_PRICE_COLUMN]
    for y in range(1, len(ids)):
        if str(ids[y][0]).startswith("spell_"):
            prices[y][0] = LOCKED_SPELL_PRICE if locked else original["data"][SPELL_PRICE_COLUMN][y][0]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(track, f, indent=4)


# Zim-Zim prices: the save keeps the Zim-Zim table with its prices (the client sets them there), and the
# install folder has the same table (array_botanist.json); both are locked for Zim-Zim items, to be safe.
BOTANIST_FILE = "array_botanist.json"
LOCKED_ZIMZIM_PRICE = 999999


def set_zimzim_file_prices(install_folder: str, locked: bool) -> bool:
    """Lock or restore the prices in array_botanist.json. Returns True when the file changed."""
    path = os.path.join(install_folder, BOTANIST_FILE)
    if not os.path.exists(path):
        return False
    backup = path + ".original"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    table, original = _load_track(path), _load_track(backup)
    prices, before = table["data"][1], json.dumps(table["data"][1])
    for y in range(1, len(prices)):
        source = str(original["data"][1][y][0])
        if source and source.replace("*", "").isdigit():
            prices[y][0] = "*".join(str(LOCKED_ZIMZIM_PRICE) for _ in source.split("*")) if locked else source
    if json.dumps(prices) == before:
        return False
    with open(path, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=4)
    return True


def zimzim_file_locked(install_folder: str) -> bool:
    path = os.path.join(install_folder, BOTANIST_FILE)
    if not os.path.exists(path):
        return False
    prices = [str(row[0]) for row in _load_track(path)["data"][1][1:]]
    return any(p.startswith(str(LOCKED_ZIMZIM_PRICE)) for p in prices)

