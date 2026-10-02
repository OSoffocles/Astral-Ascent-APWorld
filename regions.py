"""
Regions (the "map" the generator sees) and all locations.

The regions follow how deep a run goes (sphere 1 = up to the World 1 boss):

Hub              - Barbecue aura checks (all on display from the start).
World 1..4       - that world's rooms, boss, boss bonus and lost Yalees; also the Void / Yalee shop milestones,
                   Sire Bapy tiers and Sun Piece purchases (Merchant, Zim-Zim) expected by then.
Final Boss       - the final boss world.
Destiny 1..N     - runs on the Path of Destinies.
Entering World 2+ needs a share of the seed's upgrade items (see rules.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Location, Region

from . import data

if TYPE_CHECKING:
    from .world import AstralAscentWorld


class AstralAscentLocation(Location):
    game = "Astral Ascent"


destiny_region = data.destiny_region


def bapy_region(world: AstralAscentWorld, key: str, tier: int, destiny_level: int) -> str:
    if destiny_level:
        return destiny_region(destiny_level)
    return data.world_region(data.bapy_world(key, tier))


def purchase_regions(world: AstralAscentWorld) -> dict[str, str]:
    """Merchant (Spells: Checks) and Zim-Zim (Zim-Zim: Checks) purchase checks -> region, by a Sun Piece budget:
    purchases in buying order, cheapest next purchase first; each area's budget (data.SUN_PIECE_BUDGETS, times the
    currency multiplier, divided by the Logic Difficulty factor) covers what's in logic there; the rest is spread
    over the Destiny Levels (or the final boss without Destiny regions)."""
    import heapq

    queues: list[list[tuple[int, str]]] = []
    if world.flags["zimzim_checks"]:
        for row, (_, prices) in data.ZIMZIM.items():
            queues.append([(p, data.zimzim_location(row, t)) for t, p in enumerate(prices, 1)])
    if world.flags["spell_checks"]:
        price = {spell_id: p for _, kind, spell_id, _, _, p in data.XP_TRACK if kind == "spell"}
        for tab, spell_ids in data.TAB_SPELLS.items():
            if tab == "Common" or tab in world.hero_names:
                queues.append([(price.get(i) or 0, data.spell_location(tab, n)) for n, i in enumerate(spell_ids, 1)])
    heap = [(q[0][0], i, 0) for i, q in enumerate(queues) if q]
    heapq.heapify(heap)
    order: list[str] = []
    spent: list[int] = []
    total = 0
    while heap:
        p, i, j = heapq.heappop(heap)
        total += p
        order.append(queues[i][j][1])
        spent.append(total)
        if j + 1 < len(queues[i]):
            heapq.heappush(heap, (queues[i][j + 1][0], i, j + 1))

    scale = world.options.currency_multiplier.value / data.LOGIC_DIFFICULTY_FACTOR[world.options.logic_difficulty.value]
    result: dict[str, str] = {}
    rest: list[str] = []
    for name, cost in zip(order, spent):
        w = next((w for w, budget in data.SUN_PIECE_BUDGETS if cost <= budget * scale), None)
        if w is None:
            rest.append(name)
        else:
            result[name] = data.world_region(w)
    levels = world.destiny_region_count
    for k, name in enumerate(rest):
        result[name] = destiny_region(1 + k * levels // len(rest)) if levels else data.world_region(5)
    return result


def bapy_locations(world: AstralAscentWorld) -> list[tuple[str, str, int, int]]:
    """(location name, achievement key, tier, Destiny Level needed or 0) for the Sire Bapy checks in this seed."""
    o = world.options
    result = []
    for key, title, tiers in data.BAPY_ACHIEVEMENTS:
        hero = data.BAPY_HERO.get(key)
        if hero and hero not in world.hero_names:
            continue
        if key in data.BAPY_NEEDS_SPELL_PURCHASES and world.flags["spell_items"]:
            continue
        for tier in range(o.sire_bapy_min_tier.value, min(o.sire_bapy_max_tier.value, len(tiers)) + 1):
            destiny_level = tiers[tier - 1] if key == data.BAPY_DESTINY_LEVELS else 0
            if destiny_level > world.destiny_region_count:
                continue
            result.append((data.bapy_location(title, tier), key, tier, destiny_level))
    return result


def add_checks_for_items(world: AstralAscentWorld, short: int) -> list[str]:
    """Safeguard: a seed with more items than checks gets extra checks, in this order: Void milestones
    (up to 100), Yalee Ticket shop milestones (up to the shop's size), the next Sire Bapy tier(s). Raises the
    options too, so slot data and rules match. Returns what was added (for the warning)."""
    o, player = world.options, world.player
    added: list[str] = []

    def add(region_name: str, name: str) -> None:
        r = world.get_region(region_name)
        r.locations.append(AstralAscentLocation(player, name, data.LOCATION_NAME_TO_ID[name], r))
        world.location_names_created.add(name)

    void_extra = min(short, data.MAX_VOID_BOSS_CHECKS - o.void_boss_checks.value)
    if void_extra > 0:
        for milestone in range(o.void_boss_checks.value + 1, o.void_boss_checks.value + void_extra + 1):
            add(data.world_region(4), data.void_boss_location(milestone))
        o.void_boss_checks.value += void_extra
        short -= void_extra
        added.append(f"{void_extra} Void Boss Checks (now {o.void_boss_checks.value})")

    shop_cap = data.YALEE_SHOP_ITEMS // o.yalee_shop_purchases_per_check.value
    shop_now = min(o.yalee_shop_checks.value, shop_cap)
    shop_extra = min(short, shop_cap - shop_now)
    if shop_extra > 0:
        for milestone in range(shop_now + 1, shop_now + shop_extra + 1):
            add(data.world_region(4), data.yalee_shop_location(milestone))
        o.yalee_shop_checks.value = shop_now + shop_extra
        short -= shop_extra
        added.append(f"{shop_extra} Yalee Shop Checks (now {o.yalee_shop_checks.value})")

    while short > 0 and o.sire_bapy_max_tier.value < 9:
        o.sire_bapy_max_tier.value = max(o.sire_bapy_max_tier.value + 1, o.sire_bapy_min_tier.value)
        new = [(name, bapy_region(world, key, tier, level)) for name, key, tier, level in bapy_locations(world)
               if name not in world.location_names_created]
        for name, region_name in new:
            add(region_name, name)
        short -= len(new)
        added.append(f"{len(new)} Sire Bapy checks (Sire Bapy Max Tier now {o.sire_bapy_max_tier.value})")
    return added


def create_regions_and_locations(world: AstralAscentWorld) -> None:
    options = world.options
    player = world.player

    def region(name: str) -> Region:
        r = Region(name, player, world.multiworld)
        world.multiworld.regions.append(r)
        return r

    def add(r: Region | str, name: str) -> None:
        r = world.get_region(r) if isinstance(r, str) else r
        r.locations.append(AstralAscentLocation(player, name, data.LOCATION_NAME_TO_ID[name], r))

    hub = region("Hub")
    previous = hub
    for w in range(1, 6):
        r = region(data.world_region(w))
        previous.connect(r, f"{previous.name} -> {r.name}")
        previous = r
    for level in range(1, world.destiny_region_count + 1):
        r = region(destiny_region(level))
        previous.connect(r, f"{previous.name} -> {r.name}")
        previous = r

    # Barbecue: every aura is on display from the start (sphere 1)
    if world.flags["aura_checks"]:
        for n in range(1, len(data.TRACK_AURAS) + 1):
            add(hub, data.aura_location(n))

    # Sun Piece purchases (Merchant, Zim-Zim) by budget
    for name, region_name in purchase_regions(world).items():
        add(region_name, name)

    # Runs: rooms, bosses, bonus checks and lost Yalees in their world
    for slot in range(1, 6):
        add(data.world_region(slot), data.escape_location(slot))
        for n in range(1, data.boss_bonus_count(options.boss_checks.value, slot) + 1):
            add(data.world_region(slot), data.boss_bonus_location(slot, n))
    for w, r in data.ROOMS:
        add(data.world_region(w), data.room_location(w, r))
    if options.lost_yalee_checks:
        for w, n in data.LOST_YALEES:
            add(data.world_region(w), data.lost_yalee_location(w, n))

    # Milestones spread over worlds 1-4 (Void bosses appear in any world; Yalee Tickets are 1-2 per world)
    void_checks = options.void_boss_checks.value
    for milestone in range(1, void_checks + 1):
        add(data.world_region(data.milestone_world(milestone, void_checks)), data.void_boss_location(milestone))
    shop_checks = min(options.yalee_shop_checks.value,
                      data.YALEE_SHOP_ITEMS // options.yalee_shop_purchases_per_check.value)
    for milestone in range(1, shop_checks + 1):
        add(data.world_region(data.milestone_world(milestone, shop_checks)), data.yalee_shop_location(milestone))

    # Destiny Level checks
    for level in range(1, options.destiny_check_levels.value + 1):
        for slot in range(1, 6):
            add(destiny_region(level), data.destiny_location(level, slot))

    # Sire Bapy achievement tiers
    for name, key, tier, destiny_level in bapy_locations(world):
        add(bapy_region(world, key, tier, destiny_level), name)

    # Goal: an event location with a locked "Victory" item.
    goal_region = world.get_region(
        destiny_region(options.goal_destiny_level.value) if options.goal == options.goal.option_destiny_level
        else data.world_region(5)
    )
    victory = AstralAscentLocation(player, "Goal", None, goal_region)
    victory.place_locked_item(world.create_event("Victory"))
    goal_region.locations.append(victory)
