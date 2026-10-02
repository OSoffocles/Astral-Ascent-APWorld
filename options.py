from dataclasses import dataclass

from Options import (Choice, DefaultOnToggle, OptionCounter, OptionGroup, OptionSet, PerGameCommonOptions, Range,
                     Toggle)

from . import data


class Goal(Choice):
    """
    What you need to do to finish your game.
    Final Boss: beat the final boss of a run.
    Destiny Level: beat the final boss on the Path of Destinies at (at least) the Destiny Level set below.
    Combine either with "Unique Heroes Required" to demand wins with several different heroes.
    """

    display_name = "Goal"
    option_final_boss = 0
    option_destiny_level = 1
    default = 0


class GoalDestinyLevel(Range):
    """The Destiny Level you must beat when the goal is "Destiny Level"."""

    display_name = "Goal Destiny Level"
    range_start = 1
    range_end = 20
    default = 3


class UniqueHeroesRequired(Range):
    """
    How many different heroes must achieve the goal.
    Ayla and Kiran are available from the start; more than 2 requires finding Calie and/or Octave
    (and Yamat/Arven if the DLC heroes are included).
    """

    display_name = "Unique Heroes Required"
    range_start = 1
    range_end = 6
    default = 1


class SpellMode(Choice):
    """
    The 72 Merchant of Magic spells.
    Items: 72 items. Spells only come from the multiworld, one item per spell, in random order. The Merchant's spells can't
    be bought (the client sets their price out of reach).
    Checks: 72 checks. Buy spells as normal and keep them; every spell bought is a check ("Merchant: Ayla Spell 3").
    Calie's and Octave's tabs need that hero.
    Vanilla: the Merchant as in the normal game, not part of the multiworld.
    """

    display_name = "Spells"
    option_items = 0
    option_checks = 1
    option_vanilla = 2
    default = 0


class AuraMode(Choice):
    """
    The 44 Barbecue auras. Every aura is on display at Barbecue from the start.
    Checks: 44 checks. Collect auras as normal and keep them; every collection is a check. They're all
    available right away (free early checks; more room for filler).
    Vanilla: Barbecue as in the normal game, not part of the multiworld.
    """

    display_name = "Auras"
    option_checks = 1
    option_vanilla = 2
    default = 1


class ZimZimMode(Choice):
    """
    The Zim-Zim upgrades (98 tiers).
    Items: 98 items. Progressive items, every copy is one more tier of that upgrade. Zim-Zim's upgrades can't be bought
    (the client sets their prices out of reach).
    Checks: 98 checks. Buy upgrades as normal and keep them; every tier bought is a check.
    Vanilla: Zim-Zim as in the normal game, not part of the multiworld.
    """

    display_name = "Zim-Zim Upgrades"
    option_items = 0
    option_checks = 1
    option_vanilla = 2
    default = 1


class WeaponItems(DefaultOnToggle):
    """
    The heroes' extra Arsenal weapons become items: 12 items (+4 with the DLC heroes).
    Off: they're all unlocked from the start.
    """

    display_name = "Weapon Items"


class PassiveItems(DefaultOnToggle):
    """
    The Arsenal weapon passives become items: 48 items (+18 with the DLC heroes).
    Off: they're all claimable from the start.
    """

    display_name = "Passive Items"


class LogicDifficulty(Choice):
    """
    How many of your upgrade items (spells, Zim-Zim tiers, weapons, passives) the logic expects before deeper
    areas. Everything up to the World 1 boss is always in logic.
    Normal: World 2 10%, World 3 20%, World 4 30%, final boss 40%, Destiny Level n 40% + 4% per level (max 80%).
    Easy: 25% more than Normal. Hard: 40% less than Normal.
    Sun Piece purchases (Merchant, Zim-Zim) are expected by budget per area (about 1,500 Sun Pieces up to the
    World 1 boss, 5,000 World 2, 15,000 World 3, 35,000 World 4, 75,000 the final boss, the rest over the
    Destiny Levels; times the currency multiplier); Easy expects less spending per area, Hard more.
    """

    display_name = "Logic Difficulty"
    option_easy = 0
    option_normal = 1
    option_hard = 2
    default = 1


class DestinyCheckLevels(Range):
    """
    Destiny Levels 1 up to this number each get 5 checks: beating a World 1, 2, 3 and 4 boss (any of the
    three bosses of that world counts) and the final boss at that Destiny Level: 5 checks per level. 0 disables them.
    Higher Destiny Levels expect more of your upgrade items (spells, Zim-Zim tiers, weapons, passives).
    """

    display_name = "Destiny Check Levels"
    range_start = 0
    range_end = 20
    default = 7


class VoidBossesPerCheck(Range):
    """
    How many Astral Void bosses (the optional minibosses) you must beat for each Void check. Any Void boss
    counts, and beating the same one again counts too: it's about how many, not which.
    """

    display_name = "Void Bosses per Check"
    range_start = 1
    range_end = 10
    default = 1


class VoidBossChecks(Range):
    """
    How many Void checks there are in total. With "Void Bosses per Check" at 2 and this at 5, your 2nd, 4th,
    6th, 8th and 10th Void boss each send a check. 0 = no Void checks.
    If a seed has more items than checks, generation adds Void checks (up to 100) to make room, with a warning.
    """

    display_name = "Void Boss Checks"
    range_start = 0
    range_end = 100
    default = 15


class RoomChecks(Choice):
    """
    Clearing each room of a run is a check: 11 rooms in each of worlds 1-4 and 1 in the final world (45, the boss
    rooms are boss checks): 45 checks, always on.
    Drip: each room sends its check as you clear it.
    Bulk: a world's room checks are all sent when you beat that world's boss.
    """

    display_name = "Room Checks"
    option_drip = 0
    option_bulk = 1
    default = 0


class BossChecks(Choice):
    """
    How many checks the bosses of a normal escape are worth.
    Room: one check per boss, like any room (5 checks).
    Bonus: one extra check per boss (10 checks).
    Weighted: the further the boss, the more extra checks: World 1 boss +1, World 2 boss +2, ... final boss +5
    (20 checks).
    """

    display_name = "Boss Checks"
    option_room = 0
    option_bonus = 1
    option_weighted = 2
    default = 1


class LostYaleeChecks(DefaultOnToggle):
    """Saving each of the 20 lost Yalees in runs (5 per world, held hostage or hidden in pots) is a check: 20 checks."""

    display_name = "Lost Yalee Checks"


class SireBapyMinTier(Range):
    """
    Sire Bapy achievements: claiming an achievement tier is a check, for tiers from this number up to
    Sire Bapy Max Tier. Achievements with fewer tiers count up to their last one.
    """

    display_name = "Sire Bapy Min Tier"
    range_start = 1
    range_end = 9
    default = 1


class SireBapyMaxTier(Range):
    """
    Highest Sire Bapy achievement tier that is a check. 0 = no Sire Bapy checks. Tier 1 alone is about 70 checks,
    tier 2 about 50 more, tier 3 about 50 more, tier 4 about 20 more; late tiers are long grinds (e.g. 5000 kills in a world, 100,000
    Quartz). As a last resort, generation raises this to make room when a seed has more items than checks.
    """

    display_name = "Sire Bapy Max Tier"
    range_start = 0
    range_end = 9
    default = 1


class SireBapyProgressionMaxTier(Range):
    """
    Sire Bapy tiers above this number never hold progression items (heroes and upgrades), only useful items
    and filler, so long grinds never block you. 9 = no limit.
    """

    display_name = "Sire Bapy Progression Max Tier"
    range_start = 0
    range_end = 9
    default = 2


class DestinyFragmentBundles(Range):
    """
    How many "3 Destiny Fragments" items are always added to the item pool (for the Void Catalyst), as long as
    there is room. More can come from the Destiny Fragments filler share.
    """

    display_name = "Destiny Fragment Bundles"
    range_start = 0
    range_end = 30
    default = 10


class CurrencyMultiplier(Range):
    """
    Multiplies every Sun Piece and Yalee Ticket you pick up in-game or receive from the multiworld,
    to make the game less grindy. 1 = normal.
    """

    display_name = "Currency Multiplier"
    range_start = 1
    range_end = 10
    default = 1


class IncludeDLCHeroes(Toggle):
    """
    Adds the DLC heroes (Yamat and Arven) as items, with their weapons and weapon passives.
    Only turn this on if you own the DLC. When off, the DLC heroes stay locked for this seed.
    """

    display_name = "Include DLC Heroes"


class YaleeShopPurchasesPerCheck(Range):
    """How many items (colours) you must buy in the Yalee Ticket shop (Oloon) for each shop check. Any item counts."""

    display_name = "Yalee Shop Purchases per Check"
    range_start = 1
    range_end = 10
    default = 3


class YaleeShopChecks(Range):
    """
    How many Yalee Ticket shop checks there are. With "Purchases per Check" at 3 and this at 5, your 3rd, 6th,
    9th, 12th and 15th purchase each send a check. Total purchases needed can't exceed the 144 items in the
    shop. 0 = no shop checks.
    If a seed has more items than checks (and Void checks are maxed), generation adds shop checks, with a warning.
    """

    display_name = "Yalee Shop Checks"
    range_start = 0
    range_end = 144
    default = 10


class FillerShare(Range):
    range_start = 0
    range_end = 100


class SunPiecesFiller(FillerShare):
    """
    Filler: share of the free item slots (after heroes, upgrades, Destiny Fragment Bundles and duplicates) that
    become 250 Sun Pieces. Make the five filler shares add up to 100 (other totals are scaled to 100). 0 = none.
    Sun Pieces are only useful with a shop to spend them in (Spells or Zim-Zim not on Items); otherwise their
    share goes to the other kinds.
    """

    display_name = "Filler: Sun Pieces %"
    default = 10


class YaleeTicketsFiller(FillerShare):
    """Filler: share of the free item slots that become 5 Yalee Tickets. 0 = none. (If every share is 0, all
    filler is Yalee Tickets.)"""

    display_name = "Filler: Yalee Tickets %"
    default = 30


class DestinyFragmentsFiller(FillerShare):
    """Filler: share of the free item slots that become 3 Destiny Fragments. 0 = none."""

    display_name = "Filler: Destiny Fragments %"
    default = 20


class BoonsFiller(FillerShare):
    """
    Filler: share of the free item slots that become run boons (choose which in "Boons"). A boon takes effect
    in your current run; received outside a run, it waits for the next one. 0 = none.
    """

    display_name = "Filler: Boons %"
    default = 30


class TrapsFiller(FillerShare):
    """
    Filler: share of the free item slots that become traps (choose which in "Traps"). Like boons, a trap hits
    your current run, or waits for the next one. 0 = none.
    """

    display_name = "Filler: Traps %"
    default = 10


class Boons(OptionSet):
    """
    Which boons can be in the pool.
    Keys: +2 keys. Stars: +5 stars. Quartz: +50 Quartz. Heal: +30% of your max HP. Max HP: +20 max HP (and HP)
    for the run. Mana: refills your mana. Level Up: one level's worth of XP (you level up on your next XP gain).
    Stat Stone: +1 to a stat stone (strength, armor, critical, speed) you already have this run; if you have none
    yet, it waits for your first one.
    """

    display_name = "Boons"
    valid_keys = list(data.BOONS)
    default = frozenset(data.BOONS)


class Traps(OptionSet):
    """
    Which traps can be in the pool.
    Thief: lose half your Quartz and a key. Bruise: lose 25% of your current HP (never lethal). Drain: your mana
    drops to 0.
    """

    display_name = "Traps"
    valid_keys = list(data.TRAPS)
    default = frozenset(data.TRAPS)


class Duplicates(OptionCounter):
    """
    Extra copies of items, per category. The number is how many EXTRA copies: 0 or no entry = none, 1 = every item
    in that category twice, 2 = three times. Only categories that are items in your seed count (e.g. "Ayla Spells"
    needs Spells: Items, "Yamat Weapons" needs the DLC heroes and Weapon Items). For logic only the first copy of
    an item counts (a Zim-Zim copy is one more tier, as in game).
    Duplicates take the free item slots BEFORE the filler shares: with many duplicates there may be few or no
    boons, traps or other filler left (the generation log shows the split). Copies that don't fit are left out
    at random.
    Items per copy: Common Spells 12, each hero's Spells 15, Zim-Zim 98, Weapons 3 per hero (Arven 1),
    Passives 12 per hero (Arven 6).
    """

    display_name = "Duplicates"
    valid_keys = list(data.DUPLICATE_CATEGORIES)
    default = {key: 0 for key in data.DUPLICATE_CATEGORIES}
    min = 0
    max = 3


@dataclass
class AstralAscentOptions(PerGameCommonOptions):
    goal: Goal
    logic_difficulty: LogicDifficulty
    goal_destiny_level: GoalDestinyLevel
    unique_heroes_required: UniqueHeroesRequired
    spells: SpellMode
    auras: AuraMode
    zimzim: ZimZimMode
    destiny_check_levels: DestinyCheckLevels
    void_bosses_per_check: VoidBossesPerCheck
    void_boss_checks: VoidBossChecks
    yalee_shop_checks: YaleeShopChecks
    yalee_shop_purchases_per_check: YaleeShopPurchasesPerCheck
    weapon_items: WeaponItems
    passive_items: PassiveItems
    room_checks: RoomChecks
    boss_checks: BossChecks
    lost_yalee_checks: LostYaleeChecks
    sire_bapy_min_tier: SireBapyMinTier
    sire_bapy_max_tier: SireBapyMaxTier
    sire_bapy_progression_max_tier: SireBapyProgressionMaxTier
    destiny_fragment_bundles: DestinyFragmentBundles
    currency_multiplier: CurrencyMultiplier
    include_dlc_heroes: IncludeDLCHeroes
    sun_pieces_filler: SunPiecesFiller
    yalee_tickets_filler: YaleeTicketsFiller
    destiny_fragments_filler: DestinyFragmentsFiller
    boons_filler: BoonsFiller
    traps_filler: TrapsFiller
    boons: Boons
    traps: Traps
    duplicates: Duplicates


option_groups = [
    OptionGroup("Goal", [Goal, GoalDestinyLevel, UniqueHeroesRequired, LogicDifficulty]),
    OptionGroup("Spells, Auras & Zim-Zim", [SpellMode, AuraMode, ZimZimMode]),
    OptionGroup("Checks", [RoomChecks, BossChecks, DestinyCheckLevels, VoidBossChecks,
                            VoidBossesPerCheck,
                            YaleeShopChecks, YaleeShopPurchasesPerCheck, LostYaleeChecks, SireBapyMinTier,
                            SireBapyMaxTier, SireBapyProgressionMaxTier]),
    OptionGroup("Items", [WeaponItems, PassiveItems, DestinyFragmentBundles,
                          CurrencyMultiplier, IncludeDLCHeroes]),
    OptionGroup("Filler", [SunPiecesFiller, YaleeTicketsFiller, DestinyFragmentsFiller, BoonsFiller, TrapsFiller,
                           Boons, Traps, Duplicates]),
]
