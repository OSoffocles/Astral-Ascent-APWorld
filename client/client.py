"""
Astral Ascent Archipelago client.

Every second it:
  - reads the save file and sends the checks you've completed,
  - checks your goal,
  - and, while the game runs, delivers items: Sun Pieces / Yalee Tickets / Destiny Fragments straight into
    memory, weapons, passives and heroes into the game's live tables, spells and Zim-Zim tiers (when they're
    items) into the shops, and boons and traps into the current run (they wait while you're not in a run).

The whole XP track is revealed in the save slot, so every spell, aura and Zim-Zim upgrade is in the shops.
When spells or Zim-Zim upgrades are items their prices are out of reach (game files and save slot), and what
you receive is written into the game (sync_shop_items).
Everything only happens for the save slot linked to this seed (set by /newslot or /prepare), so your other
save slots are never touched.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import shutil
import time
from typing import Any

from CommonClient import ClientCommandProcessor, CommonContext, logger, server_loop
from NetUtils import ClientStatus

from collections import Counter

from .. import data
from . import game as game_mod
from . import install as install_mod
from . import logic
from .overlay import Overlay, describe
from . import save

AMOUNTS = {data.SUN_PIECES: ("sun_pieces", 250), data.YALEE_TICKETS: ("yalee_tickets", 5)}
# Stat stones a Stat Stone boon can raise (save run copy section "stones"; player 1)
STAT_STONES = {"1_strength": "strength", "1_armor": "armor", "1_critic": "critical", "1_speed": "speed"}


class AstralAscentCommandProcessor(ClientCommandProcessor):
    ctx: "AstralAscentContext"

    def _cmd_status(self) -> bool:
        """Show what the client sees: game, save slot, game files, pending unlocks."""
        self.ctx.print_status()
        return True

    def _cmd_deliver(self) -> bool:
        """Search the game's memory again and deliver weapons/passives/heroes now (normally automatic)."""
        self.ctx.live_addresses = {}
        logger.info("Searching the game's memory again (this can take a few seconds)...")
        return True

    def _cmd_overlay(self, setting: str = "") -> bool:
        """/overlay on | off - the in-game messages in the top-right corner of the game."""
        if setting not in ("on", "off"):
            logger.info(f"The in-game overlay is {'on' if self.ctx.overlay_wanted() else 'off'}. "
                        "Type /overlay on or /overlay off.")
            return True
        from Utils import persistent_store

        persistent_store("astral_ascent", "overlay", setting == "on")
        if setting == "on":
            self.ctx.overlay.stopping = False
            self.ctx.overlay.start()
        else:
            self.ctx.overlay.stop()
            self.ctx.overlay.thread = None
        logger.info(f"In-game overlay {setting}.")
        return True

    def _cmd_play(self) -> bool:
        """Set everything up (if needed) and start Astral Ascent."""
        asyncio.create_task(self.ctx.auto_setup())
        return True

    def _cmd_prepare(self) -> bool:
        """With the game CLOSED: set up the save slot for Archipelago (run once per new slot)."""
        self.ctx.prepare_save()
        return True

    def _cmd_newslot(self, slot_number: str = "", overwrite: str = "") -> bool:
        """With the game CLOSED: /newslot 1|2|3 - start that save slot in the hub, tutorial done."""
        self.ctx.new_slot(slot_number, overwrite == "overwrite")
        return True

    def _cmd_files(self, action: str = "status") -> bool:
        """/files status | restore - the game files the client changes (spell and Zim-Zim prices); restore = original."""
        self.ctx.files_command(action)
        return True


class AstralAscentContext(CommonContext):
    game = "Astral Ascent"
    items_handling = 0b111
    want_slot_data = True
    command_processor = AstralAscentCommandProcessor

    def __init__(self, server_address: str | None = None, password: str | None = None) -> None:
        super().__init__(server_address, password)
        self.slot_data: dict[str, Any] = {}
        self.game_process = game_mod.Game()
        self.save_folder: str | None = None
        self.last_save_mtime = 0.0
        self.slot_json: dict[str, dict[str, Any]] = {}
        self.save_json: dict[str, Any] = {}
        self.active_slot = "0"
        self.previous_destiny_wins: set[int] | None = None
        self.last_currency: dict[str, float] = {}
        self.last_fragments: float | None = None
        self.live_addresses: dict[str, list[int]] = {}
        self.live_scan_task: asyncio.Task | None = None
        self.live_scan_mtime = -1.0
        self.live_scan_time = 0.0
        self.delivered_unlocks: set[str] = set()
        self.shop_tables: dict[str, dict] | None = None
        self.shop_scan_task: asyncio.Task | None = None
        self.shop_scan_time = 0.0
        self.shop_sun: float | None = None  # Sun Pieces at the last shop check (for spell refunds)
        self.spells_taken_back: set[int] = set()
        self.shop_scan_mtime = -1.0
        self.setup_running = False
        self.setup_done = False
        self.overlay = Overlay()
        self.warned: set[str] = set()
        self.loop_task: asyncio.Task | None = None

    # ------------------------------------------------------------------ connection

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect(game=self.game)

    @property
    def storage_key(self) -> str:
        return f"AstralAscent_{self.team}_{self.slot}"

    @property
    def state(self) -> dict[str, Any] | None:
        """Client bookkeeping kept on the server, so it survives restarts and other PCs."""
        if self.storage_key not in self.stored_data:
            return None
        return self.stored_data[self.storage_key] or {}

    async def save_state(self, new_state: dict[str, Any]) -> None:
        self.stored_data[self.storage_key] = new_state
        await self.send_msgs([{"cmd": "Set", "key": self.storage_key, "default": {}, "want_reply": False,
                               "operations": [{"operation": "replace", "value": new_state}]}])

    room_seed: str | None = None

    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        if cmd == "RoomInfo":
            self.room_seed = args.get("seed_name")
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            asyncio.create_task(self.send_msgs([{"cmd": "Get", "keys": [self.storage_key]}]))
            if self.loop_task is None:
                self.loop_task = asyncio.create_task(self.game_loop(), name="Astral Ascent loop")
            if self.overlay_wanted():
                self.overlay.start()
            # server_seed_name only exists in Archipelago 0.6.8+; 0.6.7 keeps it from RoomInfo (see below).
            seed = getattr(self, "server_seed_name", None) or self.seed_name or self.room_seed
            logger.info(f"Connected to seed {seed} as {self.player_names.get(self.slot, self.auth)}. "
                        "Setting up Astral Ascent... (type /status any time)")

    def on_print_json(self, args: dict) -> None:
        super().on_print_json(args)
        if self.slot is None:
            return
        try:
            message = describe(args, self.slot,
                               lambda slot: self.player_names.get(slot, f"Player {slot}"),
                               lambda item, slot: self.item_names.lookup_in_slot(item, slot),
                               lambda location, slot: self.location_names.lookup_in_slot(location, slot))
        except Exception:
            message = None
        if message:
            self.overlay.post(*message)

    def overlay_wanted(self) -> bool:
        from Utils import persistent_load

        return persistent_load().get("astral_ascent", {}).get("overlay", True)

    def update_overlay_status(self) -> None:
        missing = set(self.missing_locations) - self.locations_checked
        total = len(self.missing_locations) + len(self.checked_locations)
        in_logic = logic.count_in_logic(missing, self.received_names(), self.slot_data)
        self.overlay.set_status(f"Checks in logic: {in_logic}   ·   {total - len(missing)}/{total} done")
        self.overlay.game_pid = self.game_process.pid if self.game_process.pm is not None else 0

    # ------------------------------------------------------------------ helpers

    def received_names(self) -> list[str]:
        return [data.ITEM_ID_TO_NAME.get(item.item, "?") for item in self.items_received]

    def owned_names(self) -> set[str]:
        """Received items, plus the weapons/passives of a seed that doesn't shuffle them (all unlocked)."""
        owned = set(self.received_names())
        if not self.slot_data.get("weapon_items"):
            owned |= data.ITEM_GROUPS["Weapons"]
        if not self.slot_data.get("passive_items"):
            owned |= data.ITEM_GROUPS["Passives"]
        return owned

    def power(self) -> int:
        """Upgrade items received, duplicates not counted (what the logic counts)."""
        return logic.power_count(self.received_names(), self.slot_data)

    def received_spell_ids(self) -> set[int]:
        names = set(self.received_names())
        return {spell_id for name, spell_id in data.SPELL_ITEM_IDS.items() if name in names}

    def received_tiers(self) -> dict[int, int]:
        """Zim-Zim tiers received per row (progressive items)."""
        counts = Counter(self.received_names())
        return {row: min(counts[name], len(data.ZIMZIM[row][1])) for name, row in data.ZIMZIM_ITEM_ROWS.items()}

    def hero_ids(self) -> list[int]:
        return list(self.slot_data.get("hero_ids", data.BASE_HERO_IDS))

    def warn_once(self, key: str, text: str) -> None:
        if key not in self.warned:
            self.warned.add(key)
            logger.warning(text)

    def read_save(self) -> bool:
        """Reload the save file if it changed. Returns True when new data was read."""
        self.save_folder = self.save_folder or save.find_save_folder()
        if not self.save_folder:
            self.warn_once("nosave", "No Astral Ascent save folder found under Saved Games.")
            return False
        path = os.path.join(self.save_folder, "aa_game.sav")
        try:
            mtime = os.path.getmtime(path)
            if mtime == self.last_save_mtime:
                return False
            options = save.read_json(os.path.join(self.save_folder, "aa_options.sav"))
            self.save_json = save.read_json(path)
        except (OSError, ValueError):
            return False  # the game may be writing the file right now; try again next second
        self.last_save_mtime = mtime
        self.active_slot = save.active_slot(options)
        self.slot_json = save.merged_slot(self.save_json, self.active_slot)
        return True

    # ------------------------------------------------------------------ main loop

    async def game_loop(self) -> None:
        while not self.exit_event.is_set():
            try:
                if self.slot is not None and self.slot_data and self.state is not None:
                    if not self.setup_done:
                        self.setup_done = True
                        self.setup_running = True  # set now, so no "no slot linked" warning slips out first
                        asyncio.create_task(self.auto_setup(started=True))
                    changed = self.read_save()
                    if self.on_linked_slot():
                        if changed:
                            await self.send_checks()
                            await self.check_goal()
                        if self.game_process.attach():
                            await self.deliver_live_items()
                            self.sync_unlocks()
                            await self.sync_shop_items()
                    self.game_process.attach()
                    self.update_overlay_status()
            except Exception as e:  # keep the client alive whatever happens
                logger.exception(e)
            await asyncio.sleep(1)

    async def send_checks(self) -> None:
        done = save.checked_locations(self.slot_json, int(self.slot_data.get("destiny_check_levels", 0)),
                                      int(self.slot_data.get("void_boss_checks", 0)),
                                      int(self.slot_data.get("void_bosses_per_check", 1)),
                                      int(self.slot_data.get("yalee_shop_checks", 0)),
                                      int(self.slot_data.get("yalee_shop_purchases_per_check", 1)),
                                      zimzim_from_save=not self.slot_data.get("zimzim_items"),
                                      spells_from_save=not self.slot_data.get("spell_items"),
                                      room_mode=int(self.slot_data.get("room_checks", 0)),
                                      boss_mode=int(self.slot_data.get("boss_checks", 0)))
        await self.send_location_ids(done | self.counted_checks())

    def counted_checks(self) -> set[int]:
        """Checks the client counts itself when Zim-Zim upgrades are items: Zim-Zim tiers bought (they're taken back
        until received). Received items never count; an upgrade's remaining checks complete once you own all of it."""
        sd, state, ids = self.slot_data, self.state or {}, data.LOCATION_NAME_TO_ID
        done: set[int] = set()
        if sd.get("zimzim_items"):
            zim_done = state.get("zim_done", {})
            for row, have in self.received_tiers().items():
                tiers = len(data.ZIMZIM[row][1])
                count = tiers if have >= tiers else min(tiers, int(zim_done.get(str(row), 0)))
                done.update(ids[data.zimzim_location(row, t)] for t in range(1, count + 1))
        return done

    async def send_location_ids(self, done: set[int]) -> None:
        new = (done & self.server_locations) - self.checked_locations - self.locations_checked
        if new:
            self.locations_checked |= new
            await self.check_locations(new)

    async def check_goal(self) -> None:
        if self.finished_game:
            return
        required = int(self.slot_data.get("unique_heroes_required", 1))
        heroes = {data.HEROES[h].lower() for h in self.hero_ids()}
        if int(self.slot_data.get("goal", 0)) == 0:  # final boss
            winners = save.final_boss_winners(self.slot_json) & heroes
        else:
            goal_level = int(self.slot_data.get("goal_destiny_level", 1))
            wins = {lvl for lvl in save.destiny_final_wins(self.slot_json) if lvl >= goal_level}
            state = self.state
            if state is None:
                return
            winners = set(state.get("destiny_winners", []))
            if self.previous_destiny_wins is not None and wins - self.previous_destiny_wins:
                hero = save.current_hero(self.slot_json)
                if hero in heroes and hero not in winners:
                    winners.add(hero)
                    await self.save_state({**state, "destiny_winners": sorted(winners)})
                    logger.info(f"Destiny goal: {hero.title()} counts ({len(winners)}/{required}).")
            self.previous_destiny_wins = wins
            if required == 1 and wins:
                winners = winners or {"any"}
        if len(winners) >= required:
            self.finished_game = True
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            logger.info("Goal complete!")

    # ------------------------------------------------------------------ live items

    async def deliver_live_items(self) -> None:
        g = self.game_process
        if not g.globals_ready(self.save_globals()):
            self.warn_once("globals", "Looking for Sun Pieces, Yalee Tickets and Destiny Fragments in the game's "
                                      "memory... (load your save slot and enter the hub)")
            return
        state = dict(self.state or {})
        names = self.received_names()
        multiplier = int(self.slot_data.get("currency_multiplier", 1))
        changed = False

        # Sun Pieces and Yalee Tickets: exactly once each, tracked by position in the received list.
        index = int(state.get("currency_index", 0))
        totals: dict[str, float] = {}
        for name in names[index:]:
            if name in AMOUNTS:
                global_name, amount = AMOUNTS[name]
                value = g.read_global(global_name) + amount * multiplier
                g.write_global(global_name, value)
                self.last_currency[global_name] = value
                totals[global_name] = totals.get(global_name, 0) + amount * multiplier
        for global_name, total in totals.items():
            logger.info(f"Received {total:g} {'Sun Pieces' if global_name == 'sun_pieces' else 'Yalee Tickets'}"
                        + (f" (currency multiplier x{multiplier} included)." if multiplier > 1 else "."))
        if index != len(names):
            state["currency_index"] = len(names)
            changed = True

        # Currency multiplier for what you pick up in-game.
        if multiplier > 1:
            for global_name in ("sun_pieces", "yalee_tickets"):
                value = g.read_global(global_name)
                last = self.last_currency.get(global_name)
                if last is not None and value > last:
                    value += (value - last) * (multiplier - 1)
                    g.write_global(global_name, value)
                self.last_currency[global_name] = value

        # Destiny Fragments: the game recalculates its total when a slot loads, so re-add ours on top.
        bonus = 3 * names.count(data.DESTINY_FRAGMENTS)
        total = g.read_global("destiny_fragments")
        applied = int(state.get("fragments_applied", 0)) if state.get("fragments_pid") == g.pid else 0
        if self.last_fragments is not None and total < self.last_fragments:
            applied = 0  # the game recalculated: our bonus is gone
        if total > 0 and applied != bonus:
            total += bonus - applied
            g.write_global("destiny_fragments", total)
            state.update(fragments_pid=g.pid, fragments_applied=bonus)
            changed = True
        self.last_fragments = total

        if changed:
            await self.save_state(state)
        await self.deliver_run_items()

    # ------------------------------------------------------------------ boons and traps

    def in_run(self) -> bool:
        """A run is going: the save has the run copy "<slot>_run" (written at every room change)."""
        return f"{self.active_slot}_run" in self.save_json

    def run_stones(self) -> dict[str, int]:
        """Stat stones picked up this run (save run copy, section "stones"): key -> count."""
        section = self.save_json.get(f"{self.active_slot}_run", {}).get("stones", {})
        stones = section.get("data", {}) if isinstance(section, dict) else {}
        return {k: int(v) for k, v in stones.items() if k in STAT_STONES and isinstance(v, (int, float)) and v >= 1}

    def waiting_run_items(self) -> int:
        state = self.state or {}
        run_items = [n for n in self.received_names() if n in data.BOON_ITEMS or n in data.TRAP_ITEMS]
        return len(run_items) - int(state.get("run_items_done", 0)) + int(state.get("stones_waiting", 0))

    async def deliver_run_items(self) -> None:
        """Boons and traps: applied in a run, in the order received; outside a run they wait. Tracked by count
        in the data storage, so each one is applied exactly once. A Stat Stone with no stones this run waits for
        the first stone pickup."""
        state = dict(self.state or {})
        run_items = [n for n in self.received_names() if n in data.BOON_ITEMS or n in data.TRAP_ITEMS]
        done = int(state.get("run_items_done", 0))
        stones_waiting = int(state.get("stones_waiting", 0))
        if done >= len(run_items) and not stones_waiting:
            return
        g = self.game_process
        if not self.in_run() or g.read_global("life_max") <= 0:
            if done < len(run_items):
                self.warn_once(f"runwait{len(run_items)}", f"{len(run_items) - done} boon(s)/trap(s) received: "
                                                            "they take effect in your next run.")
            return
        for name in run_items[done:]:
            if name == data.BOONS["Stat Stone"][0]:
                stones_waiting += 1
            elif name == data.BOONS["Level Up"][0]:  # searches the game's memory: not on the main loop
                self.run_message(await asyncio.to_thread(self.add_level), False)
            else:
                self.run_message(self.apply_run_item(name), name in data.TRAP_ITEMS)
            done += 1
        if stones_waiting:
            stones = self.run_stones()
            if stones:
                applied = await self.add_stat_stones(stones, stones_waiting)
                stones_waiting -= applied
            else:
                self.warn_once(f"stonewait{stones_waiting}", "Stat Stone boon: waiting until you pick up a stat stone "
                                                             "in this run.")
        if (done, stones_waiting) != (int(state.get("run_items_done", 0)), int(state.get("stones_waiting", 0))):
            state.update(run_items_done=done, stones_waiting=stones_waiting)
            await self.save_state(state)

    def run_message(self, text: str, trap: bool) -> None:
        logger.info(text)
        self.overlay.post(text, "hint" if trap else "received")

    def apply_run_item(self, name: str) -> str:
        g = self.game_process
        key = data.BOON_ITEMS.get(name) or data.TRAP_ITEMS.get(name)
        add = lambda glob, amount: g.write_global(glob, max(0.0, g.read_global(glob) + amount))  # noqa: E731
        life, life_max = g.read_global("life"), g.read_global("life_max")
        if key == "Keys":
            add("keys", 2)
            return "Boon: +2 keys."
        if key == "Stars":
            add("stars", 5)
            return "Boon: +5 stars."
        if key == "Quartz":
            add("quartz", 50)
            return "Boon: +50 Quartz."
        if key == "Heal":
            g.write_global("life", min(life_max, life + round(life_max * 0.3)))
            return "Boon: healed."
        if key == "Max HP":
            g.write_global("life_max", life_max + 20)
            g.write_global("life", life + 20)
            return "Boon: +20 max HP for this run."
        if key == "Mana":
            g.write_global("mana", g.read_global("mana_max"))
            return "Boon: mana refilled."
        if key == "Level Up":
            return self.add_level()
        if key == "Thief":
            g.write_global("quartz", float(int(g.read_global("quartz") // 2)))
            add("keys", -1)
            return "Trap: a thief took half your Quartz and a key!"
        if key == "Bruise":
            g.write_global("life", max(1.0, life - round(life * 0.25)))
            return "Trap: bruised, -25% HP!"
        if key == "Drain":
            g.write_global("mana", 0.0)
            return "Trap: your mana was drained!"
        return f"{name}: unknown, skipped."

    def add_level(self) -> str:
        """Level Up boon: add one level's worth of XP to the live p1_xp_current (live dictionary, found by name;
        the game levels up on the next XP gain)."""
        g = self.game_process
        found = g.find_live(["p1_xp_current", "p1_xp_nextLvl"])
        current, next_level = found.get("p1_xp_current", []), found.get("p1_xp_nextLvl", [])
        if not current or not next_level:
            return "Boon: Level Up couldn't find your XP in the game's memory (skipped)."
        need = max(g.read_live(a) for a in next_level)
        for address in current:
            g.write_live(address, g.read_live(address) + need)
        return "Boon: Level Up (you level up on your next XP gain)."

    async def add_stat_stones(self, stones: dict[str, int], count: int) -> int:
        """+1 to random stat stones you have this run (live dictionary; only entries that already exist can be
        raised). Returns how many were applied."""
        g = self.game_process
        found = await asyncio.to_thread(g.find_live, list(stones))
        applied = 0
        for _ in range(count):
            options = [k for k in stones if any(abs(g.read_live(a) - stones[k]) <= 5 for a in found.get(k, []))]
            if not options:
                break
            key = random.choice(options)
            for address in found[key]:
                value = g.read_live(address)
                if abs(value - stones[key]) <= 5:
                    g.write_live(address, value + 1)
            stones[key] += 1
            applied += 1
            self.run_message(f"Boon: +1 {STAT_STONES[key]} stone.", False)
        return applied

    # ------------------------------------------------------------------ which save slot belongs to this seed

    def on_linked_slot(self) -> bool:
        """Only touch the game and send checks for the save slot linked to this seed."""
        linked = (self.state or {}).get("save_slot")
        if linked is None:
            if self.setup_running or not self.setup_done:
                return False
            self.warn_once("noslot", "No save slot is linked to this seed yet: type /play and the client sets "
                                     "one up (or /newslot 1, 2 or 3 to pick it yourself).")
            return False
        if not self.save_json or self.active_slot != str(linked):
            key = f"otherslot{self.active_slot}"
            if self.save_json and key not in self.warned:
                self.warned.discard(f"otherslot{linked}")
                self.warn_once(key, f"You're on save slot {int(self.active_slot) + 1}, but this seed uses slot "
                                    f"{int(linked) + 1}. Nothing is sent or delivered until you load slot "
                                    f"{int(linked) + 1}.")
            return False
        if f"otherslot{linked}" not in self.warned:
            self.warned = {w for w in self.warned if not w.startswith("otherslot")}
            self.warned.add(f"otherslot{linked}")
        return True

    async def link_slot(self, slot: str) -> None:
        value = {"save_slot": slot, "prepared": str(self.slot_data.get("world_version", ""))}
        self.stored_data[self.storage_key] = {**(self.state or {}), **value}
        await self.send_msgs([{"cmd": "Set", "key": self.storage_key, "default": {}, "want_reply": False,
                               "operations": [{"operation": "update", "value": value}]}])

    # ------------------------------------------------------------------ unlocks (live table)

    def sync_unlocks(self) -> None:
        """Keep weapons, passives and heroes in the live table in line with the received items."""
        g = self.game_process
        plan = self.unlock_plan()
        task = self.live_scan_task
        if task is not None and task.done():
            self.live_scan_task = None
            try:
                self.live_addresses = task.result()
            except Exception as e:
                logger.warning(f"Memory search failed: {e}")
                self.live_addresses = {}
            self.live_scan_time = time.monotonic()
        stale = any(not g.live_key_at(a, k) for k, addrs in self.live_addresses.items() for a in addrs[:1])
        save_changed = self.last_save_mtime != self.live_scan_mtime
        since = time.monotonic() - self.live_scan_time
        if self.live_scan_task is None and (self.live_scan_time == 0 or ((stale or save_changed) and since > 10)
                                            or (not self.live_addresses and since > 30)):
            self.live_scan_mtime = self.last_save_mtime
            self.live_scan_time = time.monotonic()
            self.live_scan_task = asyncio.create_task(asyncio.to_thread(g.find_live, list(plan)))
            return
        if stale or not self.live_addresses:
            return
        for key, (item, _section, received) in plan.items():
            for address in self.live_addresses.get(key, []):
                if not g.live_key_at(address, key):
                    continue
                value = g.read_live(address)
                want = save.desired_value(item, received, value)
                if want is not None and value != want:
                    g.write_live(address, want)
                    if received and item not in self.delivered_unlocks:
                        logger.info(f"{item} is now available in the game.")
                        self.delivered_unlocks.add(item)
            if received:
                self.delivered_unlocks.add(item)
                if key not in self.live_addresses:
                    self.warn_once(f"missing{key}", f"{item} can't be delivered: this save slot has no "
                                                    f"'{key}' entry yet. Quit the game and type /play to add it.")

    # ------------------------------------------------------------------ spells and Zim-Zim as items

    def save_globals(self) -> dict[str, float]:
        """Sun Pieces etc. as saved in the linked slot: lets the client find them in memory (Steam build)."""
        progress = self.slot_json.get("gameProgress", {})
        keys = {"sun_pieces": "global_currency_feathers__progress",
                "yalee_tickets": "global_currency_tickets__progress",
                "destiny_fragments": "global_currency_destinyFrag__progress",
                "track_level": "global_val_skillBar_level__progress"}
        values = {}
        for name, key in keys.items():
            try:
                values[name] = float(progress[key])
            except (KeyError, TypeError, ValueError):
                pass
        return values

    def _scan_shop_tables(self, slots: dict[str, dict[str, dict]], active: str) -> dict[str, dict]:
        """(Runs in a thread.) Find the live spellbook_unlocked table and the Zim-Zim array of the ACTIVE save slot. The game keeps every slot's copy in memory, with the same keys, so the copy is chosen
        by its values: the one that matches the active slot's save best, and better than any other slot's."""
        g = self.game_process
        tables: dict[str, dict] = {"spells": {}, "zim": {}}
        if self.slot_data.get("spell_items"):
            anchors = [str(data.TRACK_SPELLS[0][1])]
            walked: list[dict[str, int]] = []
            covered: set[int] = set()
            for headers in g.find_nodes(anchors).values():
                for header in headers:
                    if header in covered:
                        continue
                    table = g.walk_table(header)
                    covered.update(table.values())
                    walked.append(table)

            def best(section: str) -> dict[str, int]:
                wanted = set(slots.get(active, {}).get(section, {}))
                candidates = []
                for table in walked:
                    if len(set(table) & wanted) / max(1, len(set(table) | wanted)) < 0.6:
                        continue
                    live = {key: g.read_text(header) for key, header in table.items()}

                    def score(slot: str) -> int:
                        saved = slots.get(slot, {}).get(section, {})
                        return sum(1 for key, value in live.items() if saved.get(key) == value)

                    mine = score(active)
                    others = max((score(s) for s in slots if s != active), default=-1)
                    if mine > others:
                        candidates.append((mine, table))
                candidates.sort(key=lambda c: c[0], reverse=True)
                if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
                    return {}  # can't tell the copies apart: touch nothing
                return candidates[0][1] if candidates else {}

            tables["spells"] = best("spellbook_unlocked")
        if self.slot_data.get("zimzim_items"):
            saved = slots.get(active, {}).get("botanist_tiers", {})
            scored = []
            for array in g.zimzim_arrays(data.ZIMZIM_TAGS):
                live = {row: g.zimzim_tiers(tag_at) for row, tag_at in array.items()}
                scored.append((sum(1 for row, tiers in live.items() if saved.get(row, 0) == tiers), array))
            scored.sort(key=lambda c: c[0], reverse=True)
            if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                tables["zim"] = scored[0][1]
        return tables

    def _shop_tables_ok(self) -> bool:
        g = self.game_process
        tables = self.shop_tables or {}
        for name in ("spells",):
            table = tables.get(name) or {}
            for key, header in list(table.items())[:3]:
                if g.node_key(header) != key:
                    return False
        for row, tag_at in list((tables.get("zim") or {}).items())[:2]:
            if not g.zimzim_ok(tag_at, data.ZIMZIM_TAGS[row]):
                return False
        return True

    async def sync_shop_items(self) -> None:
        """Spells and Zim-Zim tiers as items: keep the game in line with what you've received, and send the check
        for any Zim-Zim tier bought before its item arrived."""
        sd = self.slot_data
        if not (sd.get("spell_items") or sd.get("zimzim_items")):
            return
        task = self.shop_scan_task
        if task is not None:
            if not task.done():
                return
            self.shop_scan_task = None
            try:
                self.shop_tables = task.result()
            except Exception as e:
                logger.warning(f"Memory search for spells/Zim-Zim failed: {e}")
                self.shop_tables = None
        since = time.monotonic() - self.shop_scan_time
        # The game rebuilds its tables when it saves or loads (room changes, run start): search again after every
        # save change and pause until then, so a stale copy is never written to.
        saved_since_scan = self.last_save_mtime != self.shop_scan_mtime
        ok = self.shop_tables is not None and not saved_since_scan and self._shop_tables_ok()
        complete = ok and all(self.shop_tables.get(n) for n in self._wanted_tables())
        if not complete and (self.shop_scan_time == 0 or saved_since_scan or since > (30 if ok else 10)):
            self.shop_scan_time = time.monotonic()
            self.shop_scan_mtime = self.last_save_mtime
            slots = {slot: save.merged_slot(self.save_json, slot)
                     for slot in ("0", "1", "2") if slot in self.save_json}
            self.shop_scan_task = asyncio.create_task(asyncio.to_thread(self._scan_shop_tables, slots,
                                                                        self.active_slot))
        if not ok:
            return

        state = dict(self.state or {})
        before = json.dumps(state, sort_keys=True)
        steps = [(sd.get("spell_items"), lambda: self._sync_spells(state)),
                 (sd.get("zimzim_items"), lambda: self._sync_zimzim(state))]
        for wanted, step in steps:
            if wanted and self.shop_tables is not None:  # a step drops the tables when something looks wrong
                step()
        if json.dumps(state, sort_keys=True) != before:
            await self.save_state(state)
        await self.send_location_ids(self.counted_checks())

    def _wanted_tables(self) -> list[str]:
        sd = self.slot_data
        return [n for n, on in (("spells", sd.get("spell_items")), ("zim", sd.get("zimzim_items"))) if on]

    def _sync_spells(self, state: dict[str, Any]) -> None:
        """Spell items: spells only come from the multiworld. The Merchant's prices are patched so spells can't be
        bought; as a safety net a spell that turns up owned anyway is taken back, with a refund only when
        Sun Pieces were actually spent. Spells the game hands back again (it did at the start of a run) are
        quietly taken back again."""
        g = self.game_process
        spells = self.shop_tables.get("spells") or {}
        received = self.received_spell_ids()
        new, again = [], []
        for _, spell_id, name, _ in data.TRACK_SPELLS:
            header = spells.get(str(spell_id))
            if header is None:
                continue
            value = g.read_text(header)
            if spell_id in received:
                if value in ("new", "available", "locked"):
                    g.write_text(header, "unlocked")
                    logger.info(f"{name} (spell) is now yours.")
            elif value == "unlocked":
                (again if spell_id in self.spells_taken_back else new).append((header, spell_id, name))
        if len(new) > 3:  # never a real purchase burst: probably the wrong slot's copy
            self.warn_once("spellburst", "The client saw many spell purchases at once and ignored them; searching "
                                         "the game's memory again.")
            self.shop_tables = None
            return
        for header, spell_id, _ in new + again:
            g.write_text(header, "available")
            self.spells_taken_back.add(spell_id)
        now = g.read_global("sun_pieces") if g.globals_address else None
        if new:
            spent = (self.shop_sun - now) if now is not None and self.shop_sun is not None else 0.0
            if spent > 0:
                g.write_global("sun_pieces", now + spent)
                self.last_currency["sun_pieces"] = now + spent  # not a pickup: no currency multiplier
                now += spent
            logger.info(f"Spells only come from the multiworld: took back {', '.join(n for _, _, n in new)}"
                        + (f" and refunded {spent:g} Sun Pieces." if spent > 0 else "."))
        self.shop_sun = now

    def _sync_zimzim(self, state: dict[str, Any]) -> None:
        """Zim-Zim items: the tiers you have are the tiers received. Each tier bought on top sends that upgrade's
        next check and is taken back."""
        g = self.game_process
        rows = self.shop_tables.get("zim") or {}
        tiers_received = self.received_tiers()
        zim_done = {int(k): int(v) for k, v in state.get("zim_done", {}).items()}
        extra = sum(max(0, g.zimzim_tiers(t) - tiers_received.get(r, 0)) for r, t in rows.items())
        if extra > 3:  # never a real purchase burst: probably the wrong slot's copy
            self.warn_once("zimburst", "The client saw many Zim-Zim purchases at once and ignored them; searching "
                                       "the game's memory again.")
            self.shop_tables = None
            return
        for row, tag_at in rows.items():
            name, prices = data.ZIMZIM[row]
            have = tiers_received.get(row, 0)
            if g.zimzim_status(tag_at) == "":
                g.reveal_zimzim(tag_at)
            current = g.zimzim_tiers(tag_at)
            if current > have:
                zim_done[row] = min(len(prices), zim_done.get(row, 0) + current - have)
                logger.info(f"Bought {name}: Zim-Zim check {zim_done[row]}/{len(prices)} sent. It stays at tier "
                            f"{have} until you receive more.")
            if current != have:
                g.set_zimzim_tiers(tag_at, have)
                if current < have:
                    logger.info(f"{name} is now tier {have}.")
        state["zim_done"] = {str(k): v for k, v in zim_done.items()}

    def unlock_plan(self) -> dict[str, tuple[str, str, bool]]:
        received = self.owned_names()
        return {key: (item, section, item in received)
                for item, (section, keys) in save.unlock_keys(self.hero_ids()).items() for key in keys}

    def _backup(self, path: str, rolling: bool = False) -> str:
        """A copy of the save file. rolling=True keeps one copy that is replaced each time."""
        suffix = "archipelago-backup" if rolling else f"before-archipelago-{time.strftime('%Y%m%d-%H%M%S')}"
        backup = f"{path}.{suffix}"
        shutil.copy2(path, backup)
        return backup

    def _save_paths(self) -> tuple[str, str] | None:
        self.save_folder = self.save_folder or save.find_save_folder()
        if not self.save_folder:
            return None
        return os.path.join(self.save_folder, "aa_game.sav"), os.path.join(self.save_folder, "aa_options.sav")

    @staticmethod
    def _write_json(path: str, content: dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f, separators=(",", ":"))

    def _set_active_slot(self, options_path: str, slot: str) -> None:
        """Make it the slot the game's menu (and this client) uses."""
        if os.path.exists(options_path):
            options = save.read_json(options_path)
            options["gameOptions"]["data"]["global_val_dataSlot__option"] = int(slot)
            self._write_json(options_path, options)

    def _setup_slot(self, slot: str, fresh: bool) -> int:
        """With the game closed: (optionally) write the hub start into the slot, add the Archipelago keys,
        make it the active slot and link it to this seed. Returns how many values were set."""
        game_path, options_path = self._save_paths()  # type: ignore[misc]
        save_json = save.read_json(game_path) if os.path.exists(game_path) else {}
        if os.path.exists(game_path):
            self._backup(game_path, rolling=not fresh)
        if fresh:
            save.write_start_slot(save_json, slot)
        changes = save.prepare_slot(save_json, slot, self.hero_ids(), self.owned_names(),
                                    self.slot_data, self.received_tiers(), self.received_spell_ids())
        self._write_json(game_path, save_json)
        self._set_active_slot(options_path, slot)
        asyncio.create_task(self.link_slot(slot))
        self.live_addresses = {}
        self.shop_tables = None
        self.last_save_mtime = 0
        return changes

    def _can_edit_save(self, command: str) -> bool:
        if self.game_process.attach():
            logger.info(f"Close the game first, then type {command} again.")
            return False
        if not self.slot_data or self.state is None:
            logger.info(f"Connect to the Archipelago server first, then type {command} again.")
            return False
        if not self._save_paths():
            logger.info("No save folder found yet. Type /play: the client starts the game so it can create one.")
            return False
        return True

    def new_slot(self, slot_number: str, overwrite: bool) -> None:
        if slot_number not in ("1", "2", "3"):
            logger.info("Usage: /newslot 1, 2 or 3 (the slot number as shown in the game's menu).")
            return
        if not self._can_edit_save("/newslot"):
            return
        slot = str(int(slot_number) - 1)
        game_path, _ = self._save_paths()  # type: ignore[misc]
        in_use = os.path.exists(game_path) and slot in save.read_json(game_path)
        if in_use and not overwrite:
            logger.info(f"Save slot {slot_number} is already in use. To replace it (a backup is made first), "
                        f"type: /newslot {slot_number} overwrite")
            return
        self._setup_slot(slot, fresh=True)
        logger.info(f"Save slot {slot_number} now starts in the hub (tutorial done) and is linked to this seed. "
                    "Type /play to start the game.")

    def prepare_save(self) -> None:
        if not self._can_edit_save("/prepare"):
            return
        game_path, options_path = self._save_paths()  # type: ignore[misc]
        slot = save.active_slot(save.read_json(options_path))
        if slot not in save.read_json(game_path):
            logger.info(f"Save slot {int(slot) + 1} doesn't exist yet: type /newslot {int(slot) + 1}.")
            return
        changes = self._setup_slot(slot, fresh=False)
        logger.info(f"Save slot {int(slot) + 1} prepared ({changes} values set) and linked to this seed.")

    # ------------------------------------------------------------------ one-click start

    async def auto_setup(self, started: bool = False) -> None:
        """Everything a player would otherwise type: find the game, set the game files for this seed, set up and
        link a save slot, and start the game. Runs once after connecting, and again with /play."""
        if self.setup_running and not started:
            return
        self.setup_running = True
        try:
            await self._auto_setup()
        except Exception as e:
            logger.exception(e)
            logger.warning("Automatic setup failed (see above). The manual commands still work: /help.")
        finally:
            self.setup_running = False

    async def _auto_setup(self) -> None:
        g = self.game_process
        found = install_mod.find_install(self.remembered_install())
        if found is None and g.attach():
            folder = g.install_folder()
            found = install_mod.Install(folder, "folder", "") if folder else None
        if found is None:
            logger.warning("Couldn't find Astral Ascent (Epic or Steam). Start the game yourself once: the client "
                           "remembers where it is. Then type /play.")
            return
        self.remember_install(found.folder)
        linked = (self.state or {}).get("save_slot")
        prepared = (self.state or {}).get("prepared") == str(self.slot_data.get("world_version", ""))
        # With Spell Items the Merchant's spells are unbuyable (prices patched); otherwise normal prices. The same
        # for Zim-Zim items and Zim-Zim's prices.
        want_locked = bool(self.slot_data.get("spell_items"))
        prices_ok = (game_mod.spell_price_status(found.folder) == "locked") == want_locked
        want_zim_locked = bool(self.slot_data.get("zimzim_items"))
        prices_ok = prices_ok and game_mod.zimzim_file_locked(found.folder) == want_zim_locked

        if g.attach():
            ready = prepared and prices_ok and self._patched_before_start(found.folder)
            if linked is not None and ready:
                logger.info("Astral Ascent is running and set up. Have fun!")
                return
            logger.info("Astral Ascent is running. Please quit the game (from the main menu): the client will set "
                        "up your save slot and start it again.")
            while g.attach():
                await asyncio.sleep(2)

        if not self._save_paths():
            logger.info("Starting Astral Ascent once so it creates its save folder. When you reach the main menu, "
                        "quit the game: the client takes it from there.")
            install_mod.launch(found)
            seen_running, waited = False, 0
            while not (self._save_paths() and seen_running and not g.attach()):
                await asyncio.sleep(2)
                waited += 2
                seen_running = seen_running or g.attach()
                if not seen_running and waited > 300:
                    logger.warning("The game didn't start. Start it yourself, quit at the main menu, then type /play.")
                    return
                if seen_running and not g.attach() and not self._save_paths():
                    logger.warning("The game closed before it made a save folder. Start a new game until you reach "
                                   "the main menu, quit, then type /play.")
                    return

        if game_mod.set_zimzim_file_prices(found.folder, want_zim_locked):
            logger.info("Zim-Zim prices set for this seed (out of reach when Zim-Zim upgrades are items).")
        if (game_mod.spell_price_status(found.folder) == "locked") != want_locked:
            game_mod.set_spell_prices(found.folder, want_locked)
            logger.info("Spells only come from the multiworld in this seed: the Merchant's spells can't be bought."
                        if want_locked else "The Merchant's spell prices are back to normal for this seed.")

        game_path, _ = self._save_paths()  # type: ignore[misc]
        save_json = save.read_json(game_path) if os.path.exists(game_path) else {}
        if linked is not None and str(linked) in save_json:
            target = str(linked)
            changes = self._setup_slot(target, fresh=False)
            logger.info(f"Using save slot {int(linked) + 1} for this seed ({changes} values updated).")
        elif linked is not None:
            # The linked slot vanished (deleted in the game, or the store restored an older cloud save). Starting
            # it over would throw away progress, so let the player decide.
            logger.warning(f"Save slot {int(linked) + 1}, which belongs to this seed, is missing from your save file. "
                           "If Epic or Steam asked about cloud and local saves, the cloud copy may have replaced it: "
                           "your "
                           f"backups are next to aa_game.sav. To start slot {int(linked) + 1} over, type "
                           f"/newslot {int(linked) + 1}, then /play.")
            return
        else:
            free = [s for s in ("0", "1", "2") if s not in save_json]
            target = free[0] if free else None
            if target is None:
                logger.warning("All three save slots are in use. Pick one to replace (a backup is made first) by "
                               "typing /newslot 1, 2 or 3 overwrite, then /play.")
                return
            self._setup_slot(target, fresh=True)
            logger.info(f"Save slot {int(target) + 1} is new for this seed: it starts in the hub, tutorial done.")

        install_mod.launch(found)
        slot_number = int(target) + 1
        store = {"epic": "Epic", "steam": "Steam"}.get(found.store)
        logger.info(f"Starting Astral Ascent{f' through {store}' if store else ''}. "
                    + (f"If {store} asks which save to keep, choose the LOCAL one. " if store else "")
                    + f"Load save slot {slot_number} and play: keep this window open.")

    def _patched_before_start(self, folder: str) -> bool:
        """Were the game files the client changes (spell prices, Zim-Zim prices) changed before the game
        started? (The game reads them at start-up.)"""
        started = self.game_process.process_start_time()
        paths = [os.path.join(folder, name) for name in (game_mod.XP_TRACK_FILE, game_mod.BOTANIST_FILE)]
        return not started or all(os.path.getmtime(p) <= started for p in paths if os.path.exists(p))

    def files_command(self, action: str) -> None:
        folder = self.game_process.install_folder() if self.game_process.attach() else self.remembered_install()
        if not folder:
            logger.info("Start the game once so the client can find its install folder.")
            return
        self.remember_install(folder)
        if action == "restore":
            if self.game_process.attach():
                logger.info("Close the game first, then type /files restore again.")
                return
            ok = game_mod.restore_track_file(folder)
            game_mod.set_zimzim_file_prices(folder, False)
            logger.info("Game files restored (spell and Zim-Zim prices)." if ok
                        else "Zim-Zim prices restored; no spell-price backup found (verify the game files in Epic "
                             "or Steam if prices still look wrong).")
        logger.info(f"Game files ({folder}): Merchant spell prices {game_mod.spell_price_status(folder)}, "
                    f"Zim-Zim prices {'locked' if game_mod.zimzim_file_locked(folder) else 'original'}.")

    def remembered_install(self) -> str | None:
        from Utils import persistent_load

        return persistent_load().get("astral_ascent", {}).get("install_folder")

    def remember_install(self, folder: str) -> None:
        from Utils import persistent_store

        persistent_store("astral_ascent", "install_folder", folder)

    def print_status(self) -> None:
        attached = self.game_process.attach()
        logger.info(f"Game running: {'yes' if attached else 'no'}")
        if attached and self.game_process.globals_ready(self.save_globals()):
            logger.info(f"Sun Pieces {int(self.game_process.read_global('sun_pieces'))}")
        elif attached:
            logger.info("Sun Pieces etc. not found in the game's memory yet (load your slot and enter the hub).")
        self.last_save_mtime = 0
        if self.read_save():
            logger.info(f"Save folder: {self.save_folder}, active slot {int(self.active_slot) + 1}")
        folder = self.game_process.install_folder() if attached else self.remembered_install()
        if folder:
            logger.info(f"Merchant spell prices: {game_mod.spell_price_status(folder)}")
        received = set(self.received_names())
        pending = [n for n in save.unlock_keys(self.hero_ids()) if n in received]
        linked = (self.state or {}).get("save_slot")
        logger.info(f"Save slot linked to this seed: {int(linked) + 1 if linked is not None else 'none (use /newslot)'}")
        waiting = self.waiting_run_items()
        if waiting:
            logger.info(f"Boons/traps waiting for a run: {waiting}")
        found = sum(1 for k in self.live_addresses if self.live_addresses[k])
        logger.info(f"Unlock items received: {len(pending)}; live game entries found: {found}")
        tables = self.shop_tables or {}
        logger.info("Shop tables found: " + ", ".join(f"{name} {len(tables.get(name) or {})}" for name in ("spells", "zim")))


async def main(args) -> None:
    ctx = AstralAscentContext(args.connect, args.password)
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    from Utils import gui_enabled

    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    await ctx.exit_event.wait()
    ctx.overlay.stop()
    await ctx.shutdown()
