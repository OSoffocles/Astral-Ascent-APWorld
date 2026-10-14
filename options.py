"""
Player options. Each description: what the option does, then how many checks or items it adds.
The groups at the bottom are the sections of the Options Creator and the YAML template.
"""
from dataclasses import dataclass

from Options import (Choice, DefaultOnToggle, OptionCounter, OptionGroup, OptionSet, PerGameCommonOptions, Range,
                     Toggle)

from . import data

# ----------------------------------------------------------------------------------------------------- goal


class Goal(Choice):
    """
    What finishes your game.
    Final Boss: beat the final boss of a normal run.
    Destiny Level: beat the final boss at (at least) Goal Destiny Level on the Path of Destinies.
    """

    display_name = "Goal"
    option_final_boss = 0
    option_destiny_level = 1
    default = 0


class GoalDestinyLevel(Range):
    """The Destiny Level to beat when the goal is Destiny Level."""

    display_name = "Goal Destiny Level"
    range_start = 1
    range_end = 20
    default = 3


class UniqueHeroesRequired(Range):
    """
    How many different heroes must reach the goal.
    Ayla and Kiran start unlocked; more needs Calie and/or Octave (and Yamat/Arven with the DLC heroes).
    """

    display_name = "Unique Heroes Required"
    range_start = 1
    range_end = 6
    default = 1


# ---------------------------------------------------------------------------------------------------- logic


class LogicDifficulty(Choice):
    """
    How many of your upgrades (spells, Zim-Zim tiers, weapons, passives) the logic expects before deeper areas.
    Everything up to the World 1 boss is always in logic.
    Normal: World 2 10%, World 3 20%, World 4 30%, final boss 40%, Destiny Level n 40% + 4% per level (max 80%).
    Easy expects 25% more upgrades and less Sun Piece spending per area; Hard 40% fewer upgrades and more spending.
    """

    display_name = "Logic Difficulty"
    option_easy = 0
    option_normal = 1
    option_hard = 2
    default = 1


# ---------------------------------------------------------------------------------------------------- items


class SpellMode(Choice):
    """
    The 72 Merchant of Magic spells.
    Items: one item per spell (72 items); the Merchant's spells can't be bought.
    Checks: buying spells is a check, per Merchant tab (72 checks).
    Vanilla: normal game, not in the multiworld.
    """

    display_name = "Spells"
    option_items = 0
    option_checks = 1
    option_vanilla = 2
    default = 0


class ZimZimMode(Choice):
    """
    The 15 Zim-Zim upgrades (98 tiers).
    Items: one progressive item per tier (98 items); Zim-Zim's upgrades can't be bought.
    Checks: buying a tier is a check (98 checks).
    Vanilla: normal game, not in the multiworld.
    """

    display_name = "Zim-Zim Upgrades"
    option_items = 0
    option_checks = 1
    option_vanilla = 2
    default = 1


class WeaponItems(DefaultOnToggle):
    """
    The heroes' extra Arsenal weapons are items (12 items, +4 with the DLC heroes).
    Off: all unlocked from the start.
    """

    display_name = "Weapon Items"


class PassiveItems(DefaultOnToggle):
    """
    The Arsenal weapon passives are items (48 items, +18 with the DLC heroes).
    Off: all claimable from the start.
    """

    display_name = "Passive Items"


class IncludeDLCHeroes(Toggle):
    """
    Adds the DLC heroes Yamat and Arven as items, with their weapons and passives. Only if you own the DLC.
    Off: the DLC heroes stay locked in this seed.
    """

    display_name = "Include DLC Heroes"


# ----------------------------------------------------------------------------------------------- run checks


class RoomChecks(Choice):
    """
    Clearing a room of a run is a check: 11 rooms in each of worlds 1-4, 1 in the final world (45 checks).
    Drip: each room as you clear it. Bulk: a world's rooms all at once when you beat its boss.
    """

    display_name = "Room Checks"
    option_drip = 0
    option_bulk = 1
    default = 0


class BossChecks(Choice):
    """
    What the bosses of a normal escape are worth (any of a world's three bosses counts).
    Room: one check per boss (5 checks). Bonus: one extra per boss (10 checks).
    Weighted: World 1 boss +1 extra, World 2 boss +2, ... final boss +5 (20 checks).
    """

    display_name = "Boss Checks"
    option_room = 0
    option_bonus = 1
    option_weighted = 2
    default = 1


class LostYaleeChecks(DefaultOnToggle):
    """Saving a lost Yalee in a run (held hostage or hidden in a pot) is a check (20 checks, 5 per world)."""

    display_name = "Lost Yalee Checks"


class VoidBossChecks(Range):
    """
    Astral Void boss milestones: how many checks (0-100). Any Void boss counts, repeats too.
    Also added automatically when a seed has more items than checks (with a warning).
    """

    display_name = "Void Boss Checks"
    range_start = 0
    range_end = 100
    default = 15


class VoidBossesPerCheck(Range):
    """Void bosses to beat for each Void milestone check (2 = your 2nd, 4th, 6th ... Void boss)."""

    display_name = "Void Bosses per Check"
    range_start = 1
    range_end = 10
    default = 1


# ----------------------------------------------------------------------------------------------- hub checks


class AuraMode(Choice):
    """
    The 44 Barbecue auras, all on display from the start.
    Checks: collecting an aura is a check (44 checks, free early checks).
    Vanilla: normal game, not in the multiworld.
    """

    display_name = "Aura Checks"
    option_checks = 1
    option_vanilla = 2
    default = 1


class YaleeShopChecks(Range):
    """
    Yalee Ticket shop (Oloon) milestones: how many checks (0-144, at most 144 / Purchases per Check).
    Also added automatically when a seed has more items than checks (with a warning).
    """

    display_name = "Yalee Shop Checks"
    range_start = 0
    range_end = 144
    default = 10


class YaleeShopPurchasesPerCheck(Range):
    """Colours to buy at Oloon for each Yalee shop check (3 = your 3rd, 6th, 9th ... purchase). Any colour counts."""

    display_name = "Yalee Shop Purchases per Check"
    range_start = 1
    range_end = 10
    default = 3


# ------------------------------------------------------------------------------------------- destiny checks


class DestinyCheckLevels(Range):
    """
    Destiny Levels 1 up to this one each have 5 checks: a World 1, 2, 3 and 4 boss and the final boss at that
    level (5 checks per level). 0 = none.
    """

    display_name = "Destiny Check Levels"
    range_start = 0
    range_end = 20
    default = 7


# ------------------------------------------------------------------------------------------------ Sire Bapy


class SireBapyChecks(Choice):
    """
    Sire Bapy achievements: reaching an achievement tier is a check (sent as soon as you reach it, no need to
    claim the reward first). Choose a preset, or Custom to pick the highest tier per category below.
    Off: none. Light: tier 1 of everything (about 70 checks). Standard: tiers 1-2 (about 125 checks).
    Full: every tier (about 210 checks, with long grinds such as 5000 kills in a world).
    """

    display_name = "Sire Bapy Checks"
    option_off = 0
    option_light = 1
    option_standard = 2
    option_full = 3
    option_custom = 4
    default = 1


class SireBapyMinTier(Range):
    """Skip the tiers below this one, in every category (1 = start at tier 1)."""

    display_name = "Sire Bapy Min Tier"
    range_start = 1
    range_end = 9
    default = 1


class SireBapyProgressionMaxTier(Range):
    """Tiers above this one never hold heroes or upgrades, so long grinds never block you. 9 = no limit."""

    display_name = "Sire Bapy Progression Max Tier"
    range_start = 0
    range_end = 9
    default = 2


class BapyCategory(Range):
    """(Custom only.) Highest tier that is a check in this category; 0 = none."""

    range_start = 0
    default = 1
    category = ""


class BapyCombat(BapyCategory):
    """
    (Custom only.) Highest tier in Combat: elites, minibosses, damage, special enemies, zodiac summons (14
    achievements; tier 1: 14 checks, up to 2: 23, up to 3: 32).
    """

    display_name = "Sire Bapy: Combat"
    range_end = 9
    category = "Combat"


class BapyChallenges(BapyCategory):
    """
    (Custom only.) Highest tier in Challenges: perfect rooms, kills without being hit, room and star challenges
    (4 achievements; tier 1: 4 checks, up to 2: 8, up to 3: 12).
    """

    display_name = "Sire Bapy: Challenges"
    range_end = 4
    category = "Challenges"


class BapyWorldFeats(BapyCategory):
    """
    (Custom only.) Highest tier in World Feats: kills, zodiacs beaten and perfected, and challenges per world
    (16 achievements; tier 1: 16 checks, up to 2: 32, up to 3: 48).
    """

    display_name = "Sire Bapy: World Feats"
    range_end = 4
    category = "World Feats"


class BapyBuilds(BapyCategory):
    """
    (Custom only.) Highest tier in Builds: spell affinity, spells used, gambits, legendary spells, stones, auras
    and echoes (9 achievements; tier 1: 9 checks, up to 2: 18, up to 3: 26).
    """

    display_name = "Sire Bapy: Builds"
    range_end = 4
    category = "Builds"


class BapyExploration(BapyCategory):
    """
    (Custom only.) Highest tier in Exploration: runs, Quartz, chests, Yalees, keys, stars, secrets and visits
    (11 achievements; tier 1: 11 checks, up to 2: 19, up to 3: 27).
    """

    display_name = "Sire Bapy: Exploration"
    range_end = 5
    category = "Exploration"


class BapyShopsNPCs(BapyCategory):
    """
    (Custom only.) Highest tier in Shops & NPCs: Merchant, Andromeda, Zim-Zim, Barbecue, Oloon and Papa Yalee
    (9 achievements; tier 1: 9 checks, up to 2: 16, up to 3: 22). Merchant spell achievements are left out
    with Spells: Items.
    """

    display_name = "Sire Bapy: Shops & NPCs"
    range_end = 7
    category = "Shops & NPCs"


class BapyHeroes(BapyCategory):
    """
    (Custom only.) Heroes: max level and unlocking Calie and Octave (and the DLC heroes) (10 achievements, one
    tier each; DLC heroes only with Include DLC Heroes).
    """

    display_name = "Sire Bapy: Heroes"
    range_end = 1
    category = "Heroes"


class BapyDestiny(BapyCategory):
    """
    (Custom only.) Highest tier in Destiny: the Path of Destinies, Destiny Levels beaten, Destiny Fragments (3
    achievements; tier 1: 3 checks, up to 2: 5, up to 3: 7). Destiny Level tiers need that level's region.
    """

    display_name = "Sire Bapy: Destiny"
    range_end = 6
    category = "Destiny"


BAPY_CATEGORY_OPTIONS = [BapyCombat, BapyChallenges, BapyWorldFeats, BapyBuilds, BapyExploration, BapyShopsNPCs,
                         BapyHeroes, BapyDestiny]

# ----------------------------------------------------------------------------------------------------- filler


class FillerShare(Range):
    range_start = 0
    range_end = 100


class SunPiecesFiller(FillerShare):
    """
    Share of the free item slots that become 250 Sun Pieces. Make the five filler shares add up to 100 (other
    totals are scaled). Only used when a shop takes Sun Pieces (Spells or Zim-Zim not on Items).
    """

    display_name = "Filler: Sun Pieces %"
    default = 10


class YaleeTicketsFiller(FillerShare):
    """Share of the free item slots that become 5 Yalee Tickets. (All shares 0: all filler is Yalee Tickets.)"""

    display_name = "Filler: Yalee Tickets %"
    default = 30


class DestinyFragmentsFiller(FillerShare):
    """Share of the free item slots that become 3 Destiny Fragments."""

    display_name = "Filler: Destiny Fragments %"
    default = 20


class BoonsFiller(FillerShare):
    """Share of the free item slots that become run boons (see Boons). They work in your current or next run."""

    display_name = "Filler: Boons %"
    default = 30


class TrapsFiller(FillerShare):
    """Share of the free item slots that become traps (see Traps). They hit your current or next run."""

    display_name = "Filler: Traps %"
    default = 10


class Boons(OptionSet):
    """
    Boons that can be in the pool. Keys: +2 keys. Stars: +5 stars. Quartz: +50 Quartz. Heal: +30% of max HP.
    Max HP: +20 max HP for the run. Mana: mana refilled. Level Up: one level of XP (you level up on your next XP
    gain). Stat Stone: +1 to a stat stone you already have this run (waits for your first one).
    """

    display_name = "Boons"
    valid_keys = list(data.BOONS)
    default = frozenset(data.BOONS)


class Traps(OptionSet):
    """
    Traps that can be in the pool. Thief: lose half your Quartz and a key. Bruise: lose 25% of your current HP
    (never lethal). Drain: mana to 0.
    """

    display_name = "Traps"
    valid_keys = list(data.TRAPS)
    default = frozenset(data.TRAPS)


class DestinyFragmentBundles(Range):
    """"3 Destiny Fragments" items always in the pool (for the Void Catalyst), as far as there is room."""

    display_name = "Destiny Fragment Bundles"
    range_start = 0
    range_end = 30
    default = 10


class CurrencyMultiplier(Range):
    """Multiplies the Sun Pieces and Yalee Tickets you pick up or receive. 1 = normal."""

    display_name = "Currency Multiplier"
    range_start = 1
    range_end = 10
    default = 1


# ------------------------------------------------------------------------------------------------- duplicates


class Duplicates(OptionCounter):
    """
    EXTRA copies of every item in a category: 0 or no entry = none, 1 = each item twice, 2 = three times.
    Only categories that are items in your seed count; for logic only the first copy counts (a Zim-Zim copy is one
    more tier, as in game). Duplicates take free slots BEFORE the filler shares, so many duplicates leave little or
    no filler (copies that don't fit are left out at random).
    Items per copy: Common Spells 12, each hero's Spells 15, Zim-Zim 98, Weapons 3 per hero (Arven 1), Passives
    12 per hero (Arven 6).
    """

    display_name = "Duplicates"
    valid_keys = list(data.DUPLICATE_CATEGORIES)
    default = {key: 0 for key in data.DUPLICATE_CATEGORIES}
    min = 0
    max = 3


@dataclass
class AstralAscentOptions(PerGameCommonOptions):
    goal: Goal
    goal_destiny_level: GoalDestinyLevel
    unique_heroes_required: UniqueHeroesRequired
    logic_difficulty: LogicDifficulty
    spells: SpellMode
    zimzim: ZimZimMode
    weapon_items: WeaponItems
    passive_items: PassiveItems
    include_dlc_heroes: IncludeDLCHeroes
    room_checks: RoomChecks
    boss_checks: BossChecks
    lost_yalee_checks: LostYaleeChecks
    void_boss_checks: VoidBossChecks
    void_bosses_per_check: VoidBossesPerCheck
    auras: AuraMode
    yalee_shop_checks: YaleeShopChecks
    yalee_shop_purchases_per_check: YaleeShopPurchasesPerCheck
    destiny_check_levels: DestinyCheckLevels
    sire_bapy_checks: SireBapyChecks
    sire_bapy_min_tier: SireBapyMinTier
    sire_bapy_progression_max_tier: SireBapyProgressionMaxTier
    bapy_combat: BapyCombat
    bapy_challenges: BapyChallenges
    bapy_world_feats: BapyWorldFeats
    bapy_builds: BapyBuilds
    bapy_exploration: BapyExploration
    bapy_shops_npcs: BapyShopsNPCs
    bapy_heroes: BapyHeroes
    bapy_destiny: BapyDestiny
    sun_pieces_filler: SunPiecesFiller
    yalee_tickets_filler: YaleeTicketsFiller
    destiny_fragments_filler: DestinyFragmentsFiller
    boons_filler: BoonsFiller
    traps_filler: TrapsFiller
    boons: Boons
    traps: Traps
    destiny_fragment_bundles: DestinyFragmentBundles
    currency_multiplier: CurrencyMultiplier
    duplicates: Duplicates


BAPY_CATEGORY_FIELDS = {"bapy_combat": "Combat", "bapy_challenges": "Challenges", "bapy_world_feats": "World Feats",
                        "bapy_builds": "Builds", "bapy_exploration": "Exploration", "bapy_shops_npcs": "Shops & NPCs",
                        "bapy_heroes": "Heroes", "bapy_destiny": "Destiny"}

option_groups = [
    OptionGroup("Goal", [Goal, GoalDestinyLevel, UniqueHeroesRequired]),
    OptionGroup("Logic", [LogicDifficulty]),
    OptionGroup("Items", [SpellMode, ZimZimMode, WeaponItems, PassiveItems, IncludeDLCHeroes]),
    OptionGroup("Run Checks", [RoomChecks, BossChecks, LostYaleeChecks, VoidBossChecks, VoidBossesPerCheck]),
    OptionGroup("Hub Checks", [AuraMode, YaleeShopChecks, YaleeShopPurchasesPerCheck]),
    OptionGroup("Destiny Checks", [DestinyCheckLevels]),
    OptionGroup("Sire Bapy", [SireBapyChecks, SireBapyMinTier, SireBapyProgressionMaxTier, *BAPY_CATEGORY_OPTIONS]),
    OptionGroup("Filler", [SunPiecesFiller, YaleeTicketsFiller, DestinyFragmentsFiller, BoonsFiller, TrapsFiller, Boons,
                           Traps, DestinyFragmentBundles, CurrencyMultiplier]),
    OptionGroup("Duplicates", [Duplicates]),
]
