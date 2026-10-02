"""
The generator's rules (rules.py), mirrored for the client: which locations are in logic with the items
received so far. Used for the "checks in logic" counter in the overlay.

The slot data lists the upgrade items each location needs ("location_power"); on top of that, spells from a
hero's Merchant tab and hero achievements need that hero.
"""
from __future__ import annotations

from typing import Any

from .. import data

_STARTING_TABS = {"Common"} | {data.HEROES[h] for h in data.STARTING_HERO_IDS}
_BAPY_HERO = {}
for _i, (_key, _title, _tiers) in enumerate(data.BAPY_ACHIEVEMENTS):
    for _tier in range(1, len(_tiers) + 1):
        if _key in data.BAPY_HERO:
            _BAPY_HERO[8000 + _i * 10 + _tier] = data.BAPY_HERO[_key]
_POWER_GROUPS = {"spell_items": "Spells", "zimzim_items": "Zim-Zim Upgrades",
                 "weapon_items": "Weapons", "passive_items": "Passives"}


def _hero_needed(location_id: int) -> str | None:
    if location_id in _BAPY_HERO:
        hero = _BAPY_HERO[location_id]
        return None if hero in _STARTING_TABS else hero
    if 6000 < location_id < 6100:  # Merchant checks per tab
        tab = data.SPELL_TABS[(location_id - 6000) // 20]
        return None if tab in _STARTING_TABS else tab
    return None


def power_items(slot_data: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for option, group in _POWER_GROUPS.items():
        if slot_data.get(option):
            names |= data.ITEM_GROUPS[group]
    return names


def power_count(received: list[str], slot_data: dict[str, Any]) -> int:
    """Upgrade items received, without duplicates (Duplicates option): each spell, weapon and passive counts once,
    a Zim-Zim upgrade up to its number of tiers."""
    names = power_items(slot_data)
    counts: dict[str, int] = {}
    for name in received:
        if name in names:
            counts[name] = counts.get(name, 0) + 1
    return sum(min(n, len(data.ZIMZIM[data.ZIMZIM_ITEM_ROWS[name]][1])) if name in data.ZIMZIM_ITEM_ROWS else 1
               for name, n in counts.items())


def count_in_logic(missing: set[int], received: list[str], slot_data: dict[str, Any]) -> int:
    heroes = set(received)
    power = power_count(received, slot_data)
    location_power = {int(k): int(v) for k, v in slot_data.get("location_power", {}).items()}

    def ok(location_id: int) -> bool:
        if power < location_power.get(location_id, 0):
            return False
        hero = _hero_needed(location_id)
        return hero is None or hero in heroes

    return sum(1 for location_id in missing if ok(location_id))
