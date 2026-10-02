from collections.abc import Mapping
from typing import Any

from BaseClasses import ItemClassification
from Options import OptionError
from worlds.AutoWorld import WebWorld, World

from . import data, items, regions, rules
from . import options as aa_options
from .data import HEROES


class AstralAscentWeb(WebWorld):
    theme = "stone"
    option_groups = aa_options.option_groups


class AstralAscentWorld(World):
    """
    Astral Ascent is a 2D roguelite platformer. Escape the Garden, beat the Zodiacs, and climb the
    Path of Destinies. In this randomizer your heroes, spells, Zim-Zim upgrades, weapons and
    passives come from the multiworld, and your purchases and boss kills send items to others.
    """

    game = "Astral Ascent"
    web = AstralAscentWeb()

    options_dataclass = aa_options.AstralAscentOptions
    options: aa_options.AstralAscentOptions

    item_name_to_id = data.ITEM_NAME_TO_ID
    item_name_groups = data.ITEM_GROUPS
    location_name_to_id = data.LOCATION_NAME_TO_ID
    origin_region_name = "Hub"

    hero_ids: list[int]
    hero_names: list[str]
    power_total: int
    flags: dict[str, bool]
    destiny_region_count: int
    location_names_created: set[str]

    def generate_early(self) -> None:
        o = self.options
        self.hero_ids = list(data.BASE_HERO_IDS) + (list(data.DLC_HERO_IDS) if o.include_dlc_heroes else [])
        self.hero_names = [HEROES[h] for h in self.hero_ids]
        if o.unique_heroes_required > len(self.hero_ids):
            raise OptionError(
                f"Astral Ascent ({self.player_name}): Unique Heroes Required is {o.unique_heroes_required.value}, "
                f"but only {len(self.hero_ids)} heroes are available (turn on Include DLC Heroes for 6)."
            )
        # Spells / Auras / Zim-Zim mode → what is an item and what is a check (also sent to the client as flags).
        items_, checks_ = 0, 1
        self.flags = {
            "spell_items": o.spells == items_, "spell_checks": o.spells == checks_,
            "aura_checks": o.auras == checks_,
            "zimzim_items": o.zimzim == items_, "zimzim_checks": o.zimzim == checks_,
            "weapon_items": bool(o.weapon_items), "passive_items": bool(o.passive_items),
        }
        self.power_total = len(items.upgrade_items(self))
        goal_level = o.goal_destiny_level.value if o.goal == o.goal.option_destiny_level else 0
        self.destiny_region_count = max(o.destiny_check_levels.value, goal_level)

    def create_regions(self) -> None:
        regions.create_regions_and_locations(self)
        self.location_names_created = {loc.name for loc in self.multiworld.get_locations(self.player)}

    def set_rules(self) -> None:
        rules.set_all_rules(self)

    def create_items(self) -> None:
        items.create_all_items(self)

    def create_item(self, name: str) -> items.AstralAscentItem:
        return items.create_item(self, name)

    def create_event(self, name: str) -> items.AstralAscentItem:
        return items.AstralAscentItem(name, ItemClassification.progression, None, self.player)

    def collect(self, state, item) -> bool:
        # Upgrades counter: each upgrade counts once, a Zim-Zim upgrade up to its number of tiers. Extra copies
        # (Duplicates option) never count, also when a tracker rebuilds them by name as progression items.
        changed = super().collect(state, item)
        if changed and item.name in items.POWER_ITEMS and state.count(item.name, self.player) <= items.copies_that_count(item.name):
            state.prog_items[self.player][items.POWER] += 1
        return changed

    def remove(self, state, item) -> bool:
        changed = super().remove(state, item)
        if changed and item.name in items.POWER_ITEMS and state.count(item.name, self.player) < items.copies_that_count(item.name):
            state.prog_items[self.player][items.POWER] -= 1
            if state.prog_items[self.player][items.POWER] < 1:
                del state.prog_items[self.player][items.POWER]
        return changed

    def get_filler_item_name(self) -> str:
        return items.get_random_filler_item_name(self)

    def fill_slot_data(self) -> Mapping[str, Any]:
        return {
            "hero_ids": self.hero_ids,
            "starting_hero_ids": data.STARTING_HERO_IDS,
            "world_version": "0.1.0",
            "location_power": rules.location_power_needed(self),  # location id -> upgrade items needed
            **self.options.as_dict(
                "goal", "goal_destiny_level", "unique_heroes_required",
                "destiny_check_levels", "currency_multiplier", "include_dlc_heroes",
                "void_boss_checks", "void_bosses_per_check",
                "yalee_shop_checks", "yalee_shop_purchases_per_check",
                "lost_yalee_checks", "room_checks", "boss_checks", "logic_difficulty",
            ),
            **{flag: int(on) for flag, on in self.flags.items()},
        }
