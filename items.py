"""
Items: what gets shuffled into the multiworld.

- Heroes (progression): Calie and Octave (plus Yamat and Arven with the DLC). Ayla and Kiran start unlocked.
- Upgrades, each type optional: spells, progressive Zim-Zim tiers, weapons and weapon passives.
  The logic counts them to open deeper areas (see rules.py), so they're progression too.
- Destiny Fragments (useful), Sun Pieces, Yalee Tickets and run boons (filler) and traps, in the shares set by the
  filler options; extra copies from the Duplicates option (only the first copy of an item counts for logic; a
  Zim-Zim copy is a real tier).
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification
from Options import OptionError

from . import data
from .data import HEROES, PASSIVES, WEAPONS

if TYPE_CHECKING:
    from .world import AstralAscentWorld


class AstralAscentItem(Item):
    game = "Astral Ascent"


POWER_GROUPS = ("Spells", "Zim-Zim Upgrades", "Weapons", "Passives")
POWER_ITEMS = set().union(*(data.ITEM_GROUPS[g] for g in POWER_GROUPS))
POWER = "Upgrades"  # the counter the Destiny rules use (see AstralAscentWorld.collect)


def copies_that_count(name: str) -> int:
    """How many copies of an upgrade count toward POWER: Zim-Zim upgrades one per tier, everything else one."""
    row = data.ZIMZIM_ITEM_ROWS.get(name)
    return len(data.ZIMZIM[row][1]) if row is not None else 1


def classification_for(name: str) -> ItemClassification:
    if name in HEROES.values():
        return ItemClassification.progression
    if name in POWER_ITEMS:
        return ItemClassification.progression_skip_balancing
    if name in data.TRAP_ITEMS:
        return ItemClassification.trap
    if name in data.FILLER_ITEMS:
        return ItemClassification.filler
    return ItemClassification.useful


def create_item(world: AstralAscentWorld, name: str) -> AstralAscentItem:
    return AstralAscentItem(name, classification_for(name), data.ITEM_NAME_TO_ID[name], world.player)


def sun_pieces_useful(world: AstralAscentWorld) -> bool:
    """Sun Pieces only matter with a shop to spend them in (the Merchant or Zim-Zim not on Items)."""
    f = getattr(world, "flags", None)  # (item link groups have no options of their own)
    return not f or not (f["spell_items"] and f["zimzim_items"])


def filler_weights(world: AstralAscentWorld) -> dict[str, int]:
    """Filler kind -> share (the five filler options). Kinds that can't be used get 0."""
    o = getattr(world, "options", None)
    if o is None or not hasattr(o, "boons_filler"):
        return {"tickets": 1}
    weights = {
        "sun": o.sun_pieces_filler.value if sun_pieces_useful(world) else 0,
        "tickets": o.yalee_tickets_filler.value,
        "destiny": o.destiny_fragments_filler.value,
        "boons": o.boons_filler.value if o.boons.value else 0,
        "traps": o.traps_filler.value if o.traps.value else 0,
    }
    return weights if any(weights.values()) else {"tickets": 1}


def _filler_of_kind(world: AstralAscentWorld, kind: str) -> str:
    if kind == "sun":
        return data.SUN_PIECES
    if kind == "destiny":
        return data.DESTINY_FRAGMENTS
    if kind == "boons":
        return data.BOONS[world.random.choice(sorted(world.options.boons.value))][0]
    if kind == "traps":
        return data.TRAPS[world.random.choice(sorted(world.options.traps.value))][0]
    return data.YALEE_TICKETS


def get_random_filler_item_name(world: AstralAscentWorld) -> str:
    weights = filler_weights(world)
    kinds = [k for k, w in weights.items() if w > 0]
    return _filler_of_kind(world, world.random.choices(kinds, [weights[k] for k in kinds])[0])


def filler_mix(world: AstralAscentWorld, count: int) -> list[str]:
    """count filler items split by the filler shares (largest remainder), each kind's items picked at random."""
    weights = filler_weights(world)
    total = sum(weights.values())
    exact = {k: count * w / total for k, w in weights.items()}
    amounts = {k: int(v) for k, v in exact.items()}
    for k in sorted(exact, key=lambda k: exact[k] - amounts[k], reverse=True)[:count - sum(amounts.values())]:
        amounts[k] += 1
    return [_filler_of_kind(world, k) for k, n in amounts.items() for _ in range(n)]


def duplicate_items(world: AstralAscentWorld) -> list[str]:
    """Extra copies from the Duplicates option, for categories that are items in this seed."""
    in_pool = set(upgrade_items(world))
    result: list[str] = []
    for category, copies in sorted(world.options.duplicates.value.items()):
        names = [n for n in data.DUPLICATE_CATEGORIES.get(category, []) if n in in_pool]
        result += names * copies
    return result


def upgrade_items(world: AstralAscentWorld) -> list[str]:
    """Every upgrade item this world puts in the pool (decided by the item options)."""
    o, f = world.options, world.flags
    pool: list[str] = []
    if f["spell_items"]:
        pool += list(data.SPELL_ITEM_IDS)
    if f["zimzim_items"]:
        for row, (_, prices) in data.ZIMZIM.items():
            pool += [data.zimzim_item(row)] * len(prices)
    for hero_id in world.hero_ids:
        if o.weapon_items:
            pool += [data.weapon_item(hero_id, w) for (h, w) in WEAPONS if h == hero_id and w > 1]
        if o.passive_items:
            pool += [data.passive_item(a) for a in PASSIVES if a // 100 == hero_id]
    return pool


def create_all_items(world: AstralAscentWorld) -> None:
    from .regions import add_checks_for_items, bapy_locations

    options = world.options
    heroes = [HEROES[h] for h in world.hero_ids if h not in data.STARTING_HERO_IDS]
    upgrades = upgrade_items(world)
    pool = heroes + upgrades

    required = len(pool)
    location_count = len(world.multiworld.get_unfilled_locations(world.player))
    if required > location_count:
        added = add_checks_for_items(world, required - location_count)
        new_count = len(world.multiworld.get_unfilled_locations(world.player))
        logging.warning(
            "\n" + "!" * 100 + f"\nAstral Ascent ({world.player_name}): {required} items but only {location_count} "
            f"checks. Added {new_count - location_count} checks to make room: {'; '.join(added) or 'none possible'}."
            f"\nTo choose yourself: add checks or set Spells/Zim-Zim to Checks or Vanilla.\n" + "!" * 100)
        location_count = new_count
    if required > location_count:
        raise OptionError(
            f"Astral Ascent ({world.player_name}): {required} items but only {location_count} checks, "
            f"{required - location_count} short, even after adding every Void, Yalee shop and Sire Bapy check. "
            f"Set Spells/Zim-Zim to Checks or Vanilla, or turn off Weapon/Passive Items. "
            f"(Items: {len(heroes)} heroes, {len(upgrades)} upgrades.)"
        )

    room = location_count - required
    no_progression = sum(1 for _, _, tier, _ in bapy_locations(world)
                         if tier > options.sire_bapy_progression_max_tier.value)
    if no_progression > room:
        raise OptionError(
            f"Astral Ascent ({world.player_name}): {no_progression} Sire Bapy checks may not hold progression items, "
            f"but there are only {room} other items for them. Lower Sire Bapy Max Tier, raise Sire Bapy Progression "
            f"Max Tier, or add other checks."
        )

    # Free slots: guaranteed Destiny Fragment bundles, then duplicates (cut at random if needed), then filler.
    bundles = [data.DESTINY_FRAGMENTS] * min(options.destiny_fragment_bundles.value, room)
    duplicates = duplicate_items(world)
    world.random.shuffle(duplicates)
    # (duplicates are progression-class like the items they copy, so they can't go in the no-progression slots)
    cut = max(0, len(duplicates) - min(room - len(bundles), room - no_progression))
    duplicates = duplicates[:len(duplicates) - cut]
    filler = filler_mix(world, room - len(bundles) - len(duplicates))
    pool += bundles + duplicates + filler

    # Duplicates keep the classification of the item they copy: trackers (Universal Tracker) rebuild items by
    # name, and the Upgrades counter only counts the first copy of each item (Zim-Zim: up to its tiers, and a
    # duplicate Zim-Zim tier IS a real tier in game), so generator and trackers agree.
    world.multiworld.itempool += [create_item(world, name) for name in pool]

    for hero_id in data.STARTING_HERO_IDS:
        world.push_precollected(create_item(world, HEROES[hero_id]))

    log_summary(world, heroes, upgrades, bundles, duplicates, cut, filler)


def log_summary(world: AstralAscentWorld, heroes, upgrades, bundles, duplicates, cut, filler) -> None:
    """Per-player budget in the generation log: checks by source, items by kind, how the free slots were filled."""
    sources = Counter()
    for loc in world.multiworld.get_locations(world.player):
        if loc.address is None:
            continue
        name = loc.name
        kind = ("Rooms" if " Room " in name else "Boss bonus" if " Bonus " in name else
                "Escape bosses" if name.startswith("Escape:") else "Destiny Levels" if name.startswith("Destiny ") else
                "Lost Yalees" if "Lost Yalee" in name else "Void milestones" if name.startswith("Astral Void") else
                "Yalee shop" if name.startswith("Yalee Ticket Shop") else "Sire Bapy" if name.startswith("Sire Bapy") else
                "Merchant" if name.startswith("Merchant") else "Barbecue" if name.startswith("Barbecue") else
                "Zim-Zim" if name.startswith("Zim-Zim") else "Other")
        sources[kind] += 1
    kinds = Counter("Sun Pieces" if n == data.SUN_PIECES else "Yalee Tickets" if n == data.YALEE_TICKETS else
                    "Destiny Fragments" if n == data.DESTINY_FRAGMENTS else "Boons" if n in data.BOON_ITEMS else
                    "Traps" for n in filler)
    logging.info(
        f"Astral Ascent ({world.player_name}): {sum(sources.values())} checks "
        f"({', '.join(f'{k} {v}' for k, v in sources.most_common())}); items: {len(heroes)} heroes, "
        f"{len(upgrades)} upgrades, {len(bundles)} Destiny Fragment bundles, {len(duplicates)} duplicates"
        + (f" ({cut} duplicates didn't fit)" if cut else "")
        + f", {len(filler)} filler ({', '.join(f'{k} {v}' for k, v in kinds.most_common()) or 'none'})."
    )
