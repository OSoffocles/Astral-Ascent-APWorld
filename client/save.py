"""
Reading Astral Ascent's save files. Pure Python (no game or network access), so it can be tested anywhere.

aa_game.sav  : JSON. Top-level keys "0", "1", "2" are the three save slots ("<n>_run" = a run in progress).
aa_options.sav: JSON. gameOptions.data.global_val_dataSlot__option = the slot currently in use.
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any

from .. import data

SAVE_ROOT = os.path.join(os.path.expandvars("%USERPROFILE%"), "Saved Games", "Astral Ascent")


def find_save_folder() -> str | None:
    """The folder holding aa_game.sav (the most recently written one if there are several)."""
    candidates = glob.glob(os.path.join(SAVE_ROOT, "*", "aa_game.sav"))
    if not candidates:
        return None
    return os.path.dirname(max(candidates, key=os.path.getmtime))


def read_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def active_slot(options_json: dict[str, Any]) -> str:
    return str(options_json["gameOptions"]["data"].get("global_val_dataSlot__option", "0"))


def _section(slot_data: dict[str, Any], name: str) -> dict[str, Any]:
    section = slot_data.get(name, {})
    return section.get("data", section) if isinstance(section, dict) else {}


def merged_slot(save_json: dict[str, Any], slot: str) -> dict[str, dict[str, Any]]:
    """The slot's persistent data, with the in-run copy ("<slot>_run") layered on top where present."""
    result: dict[str, dict[str, Any]] = {}
    for key in (slot, f"{slot}_run"):
        slot_data = save_json.get(key)
        if not isinstance(slot_data, dict):
            continue
        for name in ("gameProgress", "spellbook_unlocked", "relics_unlocked", "arsenal", "ngpData",
                     "achievements", "yaleePlace", "capybaraUnlocked"):
            result.setdefault(name, {}).update(_section(slot_data, name))
        botanist = slot_data.get("botanist", {}).get("data")
        if botanist:
            result["botanist_tiers"] = {row: int(botanist[2][row][0] or 0) for row in range(1, len(botanist[2]))}
    return result


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def void_bosses_beaten(slot: dict[str, dict[str, Any]]) -> int:
    """Astral Void bosses beaten in this slot, repeats included (achievements counters)."""
    achievements = slot.get("achievements", {})
    per_boss = sum(_num(achievements.get(f"miniboss_defeat_{b}")) for b in data.MINIBOSSES)
    return int(max(per_boss, _num(achievements.get("enemyKills_miniboss"))))


def yalee_shop_purchases(slot: dict[str, dict[str, Any]]) -> int:
    """Items bought in the Yalee Ticket shop (Oloon's colours) in this slot."""
    return int(_num(slot.get("achievements", {}).get("stylist_unlockedColors")))


def checked_locations(slot: dict[str, dict[str, Any]], destiny_levels: int,
                      void_checks: int = 0, void_per_check: int = 1,
                      shop_checks: int = 0, shop_per_check: int = 1, zimzim_from_save: bool = True,
                      spells_from_save: bool = True, auras_from_save: bool = True,
                      room_mode: int = 0, boss_mode: int = 0) -> set[int]:
    """All location ids this save slot has completed. *_from_save=False: those checks are counted by the client
    instead (with spell/aura/Zim-Zim items the save shows what was received, not what was bought)."""
    ids = data.LOCATION_NAME_TO_ID
    done: set[str] = set()
    progress = slot.get("gameProgress", {})
    spells = slot.get("spellbook_unlocked", {})
    relics = slot.get("relics_unlocked", {})
    ngp = slot.get("ngpData", {})
    tiers = slot.get("botanist_tiers", {})

    if spells_from_save:  # Merchant checks count the spells bought per tab
        for tab, spell_ids in data.TAB_SPELLS.items():
            bought = sum(1 for spell_id in spell_ids if spells.get(str(spell_id)) == "unlocked")
            done.update(data.spell_location(tab, n) for n in range(1, bought + 1))
    if auras_from_save:  # Barbecue checks count the auras collected
        collected = sum(1 for _, relic_id, _ in data.TRACK_AURAS if relics.get(str(relic_id)) == "unlocked")
        done.update(data.aura_location(n) for n in range(1, collected + 1))
    for row, (_, prices) in data.ZIMZIM.items():
        for tier in range(1, (min(tiers.get(row, 0), len(prices)) if zimzim_from_save else 0) + 1):
            done.add(data.zimzim_location(row, tier))

    for world_slot in range(1, 6):
        bosses = [data.FINAL_BOSS] if world_slot == 5 else data.WORLD_BOSSES[world_slot]
        if any(_num(progress.get(f"d_val_defeatedZodiac_{b}")) >= 1 for b in bosses):
            done.add(data.escape_location(world_slot))
        for level in range(1, destiny_levels + 1):
            if any(_num(ngp.get(f"{level}_{b}")) >= 1 for b in bosses):
                done.add(data.destiny_location(level, world_slot))

    # Rooms: drip = cleared rooms of the run in progress (json_roomProgress_v2 in the run copy, rewritten at every
    # room change: currentWorld, currentRoom = 0-based index of the room you're in); a beaten world boss also
    # means its rooms were cleared (and is the only source in bulk mode).
    reached_world, reached_room = run_position(progress) if room_mode == 0 else (0, 0)
    for w, r in data.ROOMS:
        boss_done = data.escape_location(w) in done
        if boss_done or reached_world > w or (reached_world == w and reached_room >= r):
            done.add(data.room_location(w, r))
    for world_slot in range(1, 6):
        if data.escape_location(world_slot) in done:
            done.update(data.boss_bonus_location(world_slot, n)
                        for n in range(1, data.boss_bonus_count(boss_mode, world_slot) + 1))

    for w, n in data.LOST_YALEES:  # lost Yalees saved in runs (hostage or in pots)
        if slot.get("yaleePlace", {}).get(f"world_{w}_id_{n - 1}") == "saved":
            done.add(data.lost_yalee_location(w, n))
    capybara = slot.get("capybaraUnlocked", {})
    for key, title, tiers in data.BAPY_ACHIEVEMENTS:  # Sire Bapy tiers whose reward was claimed
        for tier in range(1, len(tiers) + 1):
            if capybara.get(f"{key}*{tier}") == "unlocked":
                done.add(data.bapy_location(title, tier))

    milestones = min(void_checks, void_bosses_beaten(slot) // max(1, void_per_check))
    for milestone in range(1, milestones + 1):
        done.add(data.void_boss_location(milestone))
    shop_checks = min(shop_checks, data.YALEE_SHOP_ITEMS // max(1, shop_per_check))
    for milestone in range(1, min(shop_checks, yalee_shop_purchases(slot) // max(1, shop_per_check)) + 1):
        done.add(data.yalee_shop_location(milestone))

    return {ids[name] for name in done}


def run_position(progress: dict[str, Any]) -> tuple[int, int]:
    """(world, 0-based room index) of the run in progress, from gameProgress json_roomProgress_v2; (0, 0) if none."""
    raw = progress.get("json_roomProgress_v2")
    if not isinstance(raw, str) or not raw:
        return 0, 0
    try:
        position = json.loads(raw).get("progress", {})
        return int(float(position.get("currentWorld", 0))), int(float(position.get("currentRoom", 0)))
    except (ValueError, TypeError, AttributeError):
        return 0, 0


def final_boss_winners(slot: dict[str, dict[str, Any]]) -> set[str]:
    """Heroes (lower-case names) that have beaten the final boss at least once."""
    progress = slot.get("gameProgress", {})
    return {hero.lower() for hero in data.HEROES.values()
            if _num(progress.get(f"d_val_defeatedZodiac_{data.FINAL_BOSS}_{hero.lower()}")) >= 1}


def destiny_final_wins(slot: dict[str, dict[str, Any]]) -> set[int]:
    """Destiny Levels at which the final boss has been beaten."""
    wins = set()
    for key, value in slot.get("ngpData", {}).items():
        level, _, boss = key.partition("_")
        if boss == data.FINAL_BOSS and level.isdigit() and _num(value) >= 1:
            wins.add(int(level))
    return wins


def current_hero(slot: dict[str, dict[str, Any]]) -> str:
    return str(slot.get("gameProgress", {}).get("d_str_player", "")).lower()


# ---------------------------------------------------------------------------------- unlock bookkeeping

def unlock_keys(hero_ids: list[int]) -> dict[str, tuple[str, list[str]]]:
    """
    Save keys the client controls, per item name: (section, [keys]).
    Weapons: arsenal weapon_<hero>_<weapon>; passives: arsenal <id>_unlock; heroes: gameProgress unlock_<hero>.
    """
    result: dict[str, tuple[str, list[str]]] = {}
    for hero_id in hero_ids:
        hero = data.HEROES[hero_id]
        if hero_id not in data.STARTING_HERO_IDS:
            # unlock_<hero> alone left the game's "meet the new hero" event repeating after every run and kept the
            # hero's Merchant tab closed: the bar meeting (d_bool_<hero>_bar_meet) is set with it.
            result[hero] = ("gameProgress", [f"unlock_{hero.lower()}", f"d_bool_{hero.lower()}_bar_meet"])
        for (h, w) in data.WEAPONS:
            if h == hero_id and w > 1:
                result[data.weapon_item(h, w)] = ("arsenal", [f"weapon_{h}_{w}"])
        for arsenal_id in data.PASSIVES:
            if arsenal_id // 100 == hero_id:
                result[data.passive_item(arsenal_id)] = ("arsenal", [f"{arsenal_id}_unlock"])
    # DLC heroes that aren't part of this seed stay locked. They are never received, so
    # their key is always held at 0. (Untested: whether the game honours unlock_<dlc hero> for owned DLC.)
    for hero_id in data.DLC_HERO_IDS:
        if hero_id not in hero_ids:
            result[data.HEROES[hero_id]] = ("gameProgress", [f"unlock_{data.HEROES[hero_id].lower()}"])
    return result


def desired_value(item_name: str, received: bool, current: float) -> int | None:
    """What the client wants a controlled key to be. None = leave it alone."""
    if item_name in data.HEROES.values():
        return 1 if received else 0
    if "Passive:" in item_name:
        if received:
            return None if current >= 1 else 1  # make it claimable; never undo a claim
        return 0 if current == 1 else None      # hide a passive the game made claimable on its own
    return 2 if received else 0                 # weapons


# Hub NPCs, shops and systems opened from the start, and their first-visit tutorials marked as seen, so items
# from the multiworld can be used right away. Values copied from a fully progressed slot.
HUB_OPEN = {
    "d_bool_merchant_unlocked": 1,     # Poetic Peddler (spells)
    "d_bool_botanist_unlocked": 1,     # Zim-Zim
    "d_bool_relicNPC_unlocked": 1,     # Barbecue (auras)
    "d_bool_capybara_unlocked": 1,     # Sire Bapy
    "d_bool_papaYalee_unlocked": 1,
    "d_bool_stylist_unlocked": 1,      # Oloon
    "unlock_arsenal": 1,
    "imprintSystemUnlocked": 1, "imprintAltar_unlockEvent": 1, "imprintAltar_intro": 1,
    "event_telescope": 1,
    "tutorialEvent": 1, "global_oneTimetutorial_level__progress": 1,
    "merchant_tutorial": 1, "botanist_tutorial": 1, "barbecue_tutorial": 1, "capybara_tutorial": 1,
    "papaYalee_tutorial": 1, "arsenal_tutorial_v3": 1, "arsenal_tutorial_secondWeapon_v2": 1,
    "yaleeBuilder_tutorial": 1, "telescope_tutorial": 1, "cursedTelescope_tutorial": 1, "cinema_tutorial": 1,
    "inventoryUse_tutorial": 1, "previewSpell_tutorial": 1, "perkTree_tutorial_rework": 1, "seedUI_tutorial": 1,
    "uiTutorial_gambit": 1, "uiTutorial_imprint": 1, "uiTutorial_midRunSave": 1, "uiTutorial_stylist": 1,
    "uiTutorial_summonBar": 1, "bonusSunPieces_hint": 1,
}


def open_hub(slot_data: dict[str, Any]) -> int:
    """Set the HUB_OPEN flags (only ones that are missing or 0). Returns how many were set."""
    progress = slot_data["gameProgress"]["data"]
    changes = 0
    for key, value in HUB_OPEN.items():
        if _num(progress.get(key, 0)) == 0:
            progress[key] = value
            changes += 1
    return changes


# ---------------------------------------------------------------------- revealed track, shop items

TRACK_DONE_LEVEL = data.TRACK_STEPS + 1  # global_val_skillBar_level__progress of a fully levelled track


def _dict_section(slot_data: dict[str, Any], name: str) -> dict[str, Any]:
    section = slot_data.setdefault(name, {"c2dictionary": True, "data": {}})
    return section.setdefault("data", {})


def reveal_track(slot_data: dict[str, Any]) -> int:
    """Reveal the whole XP track: every track spell becomes "new" (buyable), every aura is on display at Barbecue
    and every Zim-Zim upgrade available. Nothing is bought or collected. Returns how many values changed."""
    changes = 0
    progress = slot_data["gameProgress"]["data"]
    if _num(progress.get("global_val_skillBar_level__progress")) < TRACK_DONE_LEVEL:
        progress["global_val_skillBar_level__progress"] = TRACK_DONE_LEVEL
        progress["global_val_XP__progress"] = 0
        changes += 1
    spells = _dict_section(slot_data, "spellbook_unlocked")
    for _, spell_id, _, _ in data.TRACK_SPELLS:
        if spells.get(str(spell_id)) in (None, "locked"):
            spells[str(spell_id)] = "new"
            changes += 1
    relics = _dict_section(slot_data, "relics_unlocked")
    for _, relic_id, _ in data.TRACK_AURAS:
        for tier_id in data.AURA_CHAINS[relic_id]:
            current = relics.get(str(tier_id))
            if current not in (None, "locked", "new"):
                continue  # collected: leave it
            want = "new"
            if current != want:
                relics[str(tier_id)] = want
                changes += 1
    botanist = slot_data.get("botanist", {}).get("data")
    if botanist:
        for row in data.ZIMZIM:
            if botanist[3][row][0] != "unlocked":
                botanist[3][row][0] = "unlocked"
                changes += 1
    return changes


def set_spells_received(slot_data: dict[str, Any], received_ids: set[int]) -> int:
    """Spell items: received spells are owned ("unlocked"), others bought earlier go back to "available"."""
    spells = _dict_section(slot_data, "spellbook_unlocked")
    changes = 0
    for _, spell_id, _, _ in data.TRACK_SPELLS:
        key, current = str(spell_id), spells.get(str(spell_id))
        want = "unlocked" if spell_id in received_ids else ("available" if current == "unlocked" else current)
        if current != want:
            spells[key] = want
            changes += 1
    return changes


LOCKED_ZIMZIM_PRICE = 999999


def set_zimzim_prices(slot_data: dict[str, Any], locked: bool) -> int:
    """Zim-Zim items: every tier's price out of reach, so upgrades only come from the multiworld.
    Otherwise the normal prices. The save keeps the whole Zim-Zim table, prices included (column 1)."""
    botanist = slot_data.get("botanist", {}).get("data")
    changes = 0
    if botanist:
        for row, (_, prices) in data.ZIMZIM.items():
            want = "*".join(str(LOCKED_ZIMZIM_PRICE if locked else p) for p in prices)
            if botanist[1][row][0] != want:
                botanist[1][row][0] = want
                changes += 1
    return changes


def set_zimzim_tiers(slot_data: dict[str, Any], received_tiers: dict[int, int]) -> int:
    """With Zim-Zim items: the tiers you have are the tiers you've received."""
    botanist = slot_data.get("botanist", {}).get("data")
    changes = 0
    if botanist:
        for row, (_, prices) in data.ZIMZIM.items():
            want = min(received_tiers.get(row, 0), len(prices))
            # Exact comparison: an untouched row holds "" (a text cell); the client needs a number there.
            if botanist[2][row][0] != want or isinstance(botanist[2][row][0], (str, bool)):
                botanist[2][row][0] = want
                changes += 1
    return changes


def prepare_slot(save_json: dict[str, Any], slot: str, hero_ids: list[int], received: set[str],
                 options: dict[str, Any] | None = None, received_tiers: dict[int, int] | None = None,
                 spell_ids: set[int] | None = None) -> int:
    """
    Offline setup (game closed): make sure every controlled key exists in the slot, set to what the
    received items say. Keys must exist before the game starts, because the client can change values
    in memory but cannot add new entries. Returns how many keys were added or changed.
    options = the seed's slot data (reveals the track and sets the shop items).
    """
    slot_data = save_json[slot]
    changes = open_hub(slot_data)
    options = options or {}
    changes += reveal_track(slot_data)
    if options.get("spell_items"):
        changes += set_spells_received(slot_data, spell_ids or set())
    if options.get("zimzim_items"):
        changes += set_zimzim_tiers(slot_data, received_tiers or {})
    changes += set_zimzim_prices(slot_data, bool(options.get("zimzim_items")))
    for item_name, (section, keys) in unlock_keys(hero_ids).items():
        target = slot_data[section]["data"]
        for key in keys:
            current = _num(target.get(key, 0))
            want = desired_value(item_name, item_name in received, current)
            if key not in target:
                target[key] = want if want is not None else 0
                changes += 1
            elif want is not None and current != want:
                target[key] = want
                changes += 1
    return changes


def start_slot_template() -> dict[str, Any]:
    """A slot saved right after the tutorial, on first arrival in the hub (captured in game version 2.6.4)."""
    import pkgutil  # works inside the zipped .apworld too

    raw = pkgutil.get_data(__name__, "start_slot.json")
    return json.loads(raw.decode("utf-8"))


def write_start_slot(save_json: dict[str, Any], slot: str) -> None:
    """Replace a save slot with the post-tutorial start (and drop any run in progress in that slot)."""
    save_json[slot] = start_slot_template()
    save_json.pop(f"{slot}_run", None)
