"""
Rules (logic): what you need before a check is expected of you.

Sphere 1 is everything up to the World 1 boss (plus the Barbecue aura checks).
Each deeper area needs a share of the seed's upgrade items (spells, Zim-Zim tiers, weapons, passives):
World 2 10%, World 3 20%, World 4 30%, final boss 40%, Destiny Level n 40% + 4% x n, capped at 80%, all
multiplied by the Logic Difficulty. Checks are placed in the area where they're expected (regions.py): Sun Piece
purchases by budget, milestones spread over the worlds, Sire Bapy tiers by world.
Spells from a hero's Merchant tab and hero achievements need that hero. The goal needs the required number of
different heroes.
"""
from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING

from . import data
from .items import POWER
from .regions import bapy_locations, destiny_region

if TYPE_CHECKING:
    from .world import AstralAscentWorld


def area_power_needed(world: AstralAscentWorld) -> dict[str, int]:
    """Region name -> upgrade items needed to enter it. Capped at half the checks before that area that can hold
    progression, so seeds with few early checks (and little filler) still fill."""
    difficulty = world.options.logic_difficulty.value
    order = area_order(world)
    no_progression = {name for name, _, tier, _ in bapy_locations(world)
                      if tier > world.options.sire_bapy_progression_max_tier.value}
    needed: dict[str, int] = {}
    before = 0
    for name in order:
        if name == "Hub" or name == data.world_region(1):
            share = 0.0
        elif name.startswith("Destiny "):
            share = data.power_share_destiny(int(name.split()[1]), difficulty)
        else:
            share = data.power_share_world(5 if name == data.world_region(5) else int(name.split()[1]), difficulty)
        needed[name] = min(ceil(world.power_total * share), before // 2)
        before += sum(1 for loc in world.get_region(name).locations
                      if loc.address is not None and loc.name not in no_progression)
    return needed


def area_order(world: AstralAscentWorld) -> list[str]:
    return ["Hub"] + [data.world_region(w) for w in range(1, 6)] + [
        destiny_region(level) for level in range(1, world.destiny_region_count + 1)]


def set_all_rules(world: AstralAscentWorld) -> None:
    player = world.player

    def location_rule(name: str, rule) -> None:
        if name in world.location_names_created:
            world.get_location(name).access_rule = rule

    needed = area_power_needed(world)
    order = area_order(world)
    for before, after in zip(order, order[1:]):
        if needed[after]:
            world.get_entrance(f"{before} -> {after}").access_rule = \
                lambda state, n=needed[after]: state.has(POWER, player, n)

    starting_tabs = {"Common"} | {data.HEROES[h] for h in data.STARTING_HERO_IDS}
    for tab, spell_ids in data.TAB_SPELLS.items():
        if tab not in starting_tabs:
            for n in range(1, len(spell_ids) + 1):
                location_rule(data.spell_location(tab, n), lambda state, h=tab: state.has(h, player))

    progression_max = world.options.sire_bapy_progression_max_tier.value
    for name, key, tier, _ in bapy_locations(world):
        hero = data.BAPY_HERO.get(key)
        if hero and hero not in (data.HEROES[h] for h in data.STARTING_HERO_IDS):
            location_rule(name, lambda state, h=hero: state.has(h, player))
        if tier > progression_max:
            world.get_location(name).item_rule = lambda item: not item.advancement

    hero_names = world.hero_names
    required = world.options.unique_heroes_required.value
    world.get_location("Goal").access_rule = lambda state: sum(state.has(h, player) for h in hero_names) >= required

    world.multiworld.completion_condition[player] = lambda state: state.has("Victory", player)


def location_power_needed(world: AstralAscentWorld) -> dict[int, int]:
    """Location id -> upgrade items needed (for the client's "checks in logic" counter). Zeros left out."""
    needed = area_power_needed(world)
    return {loc.address: needed[loc.parent_region.name] for loc in world.multiworld.get_locations(world.player)
            if loc.address is not None and needed.get(loc.parent_region.name)}
