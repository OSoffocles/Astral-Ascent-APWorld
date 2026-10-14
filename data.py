"""
Names, IDs and save-file mappings shared by the world (generation) and the client.

Item and location IDs are frozen from v0.1.0: they must never change, or existing seeds break.
"""
from .game_data import (AURA_CHAINS, BAPY_ACHIEVEMENTS, FINAL_BOSS, HEROES, MINIBOSSES, PASSIVES, WEAPONS,
                        WORLD_BOSSES, XP_TRACK, ZIMZIM,
                        ZIMZIM_TAGS)

TRACK_STEPS = len(XP_TRACK)  # 131
BASE_HERO_IDS = [1, 2, 3, 4]
DLC_HERO_IDS = [5, 6]
STARTING_HERO_IDS = [1, 2]  # Ayla and Kiran are available from the start
MAX_DESTINY_CHECK_LEVEL = 20
MAX_VOID_BOSS_CHECKS = 100
YALEE_SHOP_ITEMS = 144  # Oloon's colours: 36 per base hero

# ------------------------------------------------------------------------------------------- logic
# Sphere 1 = everything up to the World 1 boss. Deeper worlds need a share of the seed's upgrade
# items ("power"); Destiny Level n needs DESTINY_BASE_SHARE + DESTINY_POWER_PER_LEVEL x n, all capped at
# DESTINY_POWER_CAP. Logic Difficulty multiplies the shares (and divides the Sun Piece budgets).
WORLD_POWER_SHARE = {1: 0.0, 2: 0.10, 3: 0.20, 4: 0.30, 5: 0.40}  # world 5 = the final boss
DESTINY_BASE_SHARE = 0.40
DESTINY_POWER_PER_LEVEL = 0.04
DESTINY_POWER_CAP = 0.8
LOGIC_DIFFICULTY_FACTOR = {0: 1.25, 1: 1.0, 2: 0.6}  # easy / normal / hard
# Sun Piece spending in logic per area (a first run dying at the World 1 boss earns ~300, plus 200 from the
# Sire Bapy tiers claimed on load). Cheapest purchases first; what's left goes to the Destiny Levels.
SUN_PIECE_BUDGETS = [(1, 1500), (2, 5000), (3, 15000), (4, 35000), (5, 75000)]


def world_region(w: int) -> str:
    """Region for world 1-4, or 5 = the final boss world."""
    return "Final Boss" if w == 5 else f"World {w}"


def destiny_region(level: int) -> str:
    return f"Destiny {level}"


def power_share_world(w: int, difficulty: int) -> float:
    return min(DESTINY_POWER_CAP, WORLD_POWER_SHARE[w] * LOGIC_DIFFICULTY_FACTOR[difficulty])


def power_share_destiny(level: int, difficulty: int) -> float:
    return min(DESTINY_POWER_CAP, (DESTINY_BASE_SHARE + DESTINY_POWER_PER_LEVEL * level)
               * LOGIC_DIFFICULTY_FACTOR[difficulty])


def milestone_world(n: int, total: int) -> int:
    """Void / Yalee shop milestone n of total: spread evenly over worlds 1-4."""
    return min(4, 1 + (n - 1) * 4 // max(1, total))


def bapy_world(key: str, tier: int) -> int:
    """World (1-4, 5 = final boss) a Sire Bapy tier is expected in. Achievements tied to a world (key ending
    _w1.._w4): that world for tier 1, one world further per tier. Others: tier 1 World 2, tier 2 World 3,
    tier 3 World 4, tier 4+ the final boss."""
    if key in ("obj_boss_ophiuchus", "pathOfDestinies_unlocked"):
        return 5
    if len(key) > 3 and key[-3:-1] == "_w" and key[-1] in "1234":
        return min(5, int(key[-1]) + tier - 1)
    return min(5, tier + 1)


# ----------------------------------------------------------------------------------------------- items

DESTINY_FRAGMENTS = "3 Destiny Fragments"
SUN_PIECES = "250 Sun Pieces"
YALEE_TICKETS = "5 Yalee Tickets"
FILLER_ITEMS = [SUN_PIECES, YALEE_TICKETS]


def weapon_item(hero_id: int, weapon_no: int) -> str:
    return f"{HEROES[hero_id]}'s {WEAPONS[(hero_id, weapon_no)]}"


def passive_item(arsenal_id: int) -> str:
    hero_id, weapon_no = arsenal_id // 100, arsenal_id // 10 % 10
    return f"{HEROES[hero_id]} {WEAPONS[(hero_id, weapon_no)]} Passive: {PASSIVES[arsenal_id]}"


ITEM_NAME_TO_ID: dict[str, int] = {DESTINY_FRAGMENTS: 50, SUN_PIECES: 60, YALEE_TICKETS: 61}
for _hero_id, _hero in HEROES.items():
    ITEM_NAME_TO_ID[_hero] = 10 + _hero_id
for (_hero_id, _weapon_no) in WEAPONS:
    if _weapon_no > 1:  # weapon 1 is every hero's default weapon
        ITEM_NAME_TO_ID[weapon_item(_hero_id, _weapon_no)] = 100 + _hero_id * 10 + _weapon_no
for _arsenal_id in PASSIVES:
    ITEM_NAME_TO_ID[passive_item(_arsenal_id)] = 1000 + _arsenal_id

TRACK_SPELLS = [(step, spell_id, name, tab) for step, kind, spell_id, name, tab, _ in XP_TRACK if kind == "spell"]
TRACK_AURAS = [(step, relic_id, name) for step, kind, relic_id, name, _, _ in XP_TRACK if kind == "relic"]

# Merchant tabs and their XP-track spells (the checks count purchases per tab).
SPELL_TABS = ["Common", "Ayla", "Kiran", "Calie", "Octave"]
TAB_SPELLS = {tab: [spell_id for _, spell_id, _, t in TRACK_SPELLS if t == tab] for tab in SPELL_TABS}
SPELL_TAB = {spell_id: t for t, ids in TAB_SPELLS.items() for spell_id in ids}


def spell_item(name: str) -> str:
    return f"Spell: {name}"


def zimzim_item(row: int) -> str:
    """Progressive: each copy is one more tier of that Zim-Zim upgrade."""
    return f"Progressive {ZIMZIM[row][0]}"


for _step, _spell_id, _name, _tab in TRACK_SPELLS:
    ITEM_NAME_TO_ID[spell_item(_name)] = 2000 + _spell_id
for _row in ZIMZIM:
    ITEM_NAME_TO_ID[zimzim_item(_row)] = 4000 + _row

# Run boons and traps: applied live during a run; received outside a run they wait for the next one.
# key -> (item name, id). The keys are the names used in the Boons / Traps options.
BOONS = {
    "Keys": ("Boon: 2 Keys", 5101),
    "Stars": ("Boon: 5 Stars", 5102),
    "Quartz": ("Boon: 50 Quartz", 5103),
    "Heal": ("Boon: Heal", 5104),             # +30% of max HP, up to max HP
    "Max HP": ("Boon: +20 Max HP", 5105),     # max HP and HP +20 for this run
    "Mana": ("Boon: Mana Refill", 5106),
    "Level Up": ("Boon: Level Up", 5107),     # one level's worth of XP: you level up on your next XP gain
    "Stat Stone": ("Boon: Stat Stone", 5108),  # +1 to a stat stone you already have this run
}
TRAPS = {
    "Thief": ("Trap: Thief", 5201),    # lose half your Quartz and a key
    "Bruise": ("Trap: Bruise", 5202),  # lose 25% of your current HP (never lethal)
    "Drain": ("Trap: Drain", 5203),    # mana to 0
}
BOON_ITEMS = {name: key for key, (name, _) in BOONS.items()}  # item name -> key
TRAP_ITEMS = {name: key for key, (name, _) in TRAPS.items()}
for _name, _id in list(BOONS.values()) + list(TRAPS.values()):
    ITEM_NAME_TO_ID[_name] = _id
FILLER_ITEMS += list(BOON_ITEMS)

ITEM_ID_TO_NAME = {v: k for k, v in ITEM_NAME_TO_ID.items()}

SPELL_ITEM_IDS = {spell_item(name): spell_id for _, spell_id, name, _ in TRACK_SPELLS}  # item name -> spell id
ZIMZIM_ITEM_ROWS = {zimzim_item(row): row for row in ZIMZIM}                             # item name -> row

ITEM_GROUPS = {
    "Spells": set(SPELL_ITEM_IDS),
    "Zim-Zim Upgrades": set(ZIMZIM_ITEM_ROWS),
    "Heroes": set(HEROES.values()),
    "Weapons": {weapon_item(h, w) for (h, w) in WEAPONS if w > 1},
    "Passives": {passive_item(a) for a in PASSIVES},
    "Boons": set(BOON_ITEMS),
    "Traps": set(TRAP_ITEMS),
}


def duplicate_categories() -> dict[str, list[str]]:
    """Duplicates option: category -> the items an extra copy is made of."""
    cats = {f"{tab} Spells": [spell_item(name) for _, _, name, t in TRACK_SPELLS if t == tab] for tab in SPELL_TABS}
    cats["Zim-Zim"] = [zimzim_item(row) for row, (_, prices) in ZIMZIM.items() for _ in prices]
    for hero_id, hero in HEROES.items():
        cats[f"{hero} Weapons"] = [weapon_item(h, w) for (h, w) in WEAPONS if h == hero_id and w > 1]
        cats[f"{hero} Passives"] = [passive_item(a) for a in PASSIVES if a // 100 == hero_id]
    return cats


DUPLICATE_CATEGORIES = duplicate_categories()

# ------------------------------------------------------------------------------------------- locations


def spell_location(tab: str, n: int) -> str:
    """The n-th different spell bought in that Merchant tab (with Spell Items: spells can't be bought)."""
    return f"Merchant: {tab} Spell {n}"


def aura_location(n: int) -> str:
    """The n-th different aura collected at Barbecue."""
    return f"Barbecue: Aura {n}"


def zimzim_location(row: int, tier: int) -> str:
    return f"Zim-Zim: {ZIMZIM[row][0]} {tier}"


def boss_slot_name(world_slot: int) -> str:
    return "Final Boss" if world_slot == 5 else f"World {world_slot} Boss"


def escape_location(world_slot: int) -> str:
    return f"Escape: {boss_slot_name(world_slot)}"


def destiny_location(level: int, world_slot: int) -> str:
    return f"Destiny {level}: {boss_slot_name(world_slot)}"


def yalee_shop_location(milestone: int) -> str:
    """Milestone n = n x (purchases per check) items bought in the Yalee Ticket shop (Oloon), any of them."""
    return f"Yalee Ticket Shop Milestone {milestone}"


def lost_yalee_location(world: int, n: int) -> str:
    """Saving a lost Yalee in a run (hostage or in a pot): save yaleePlace['world_<w>_id_<n - 1>'] = 'saved'."""
    return f"World {world} Lost Yalee {n}"


LOST_YALEES = [(w, n) for w in range(1, 5) for n in range(1, 6)]

# Rooms: 12 rooms per world including the boss room; the final-boss world (5) has 2.
ROOMS_PER_WORLD = {1: 11, 2: 11, 3: 11, 4: 11, 5: 1}  # rooms before the boss room


def room_location(world: int, room: int) -> str:
    """Clearing room n of world w in a run (any Destiny Level)."""
    return f"World {world} Room {room}"


ROOMS = [(w, r) for w, count in ROOMS_PER_WORLD.items() for r in range(1, count + 1)]


def boss_bonus_location(world_slot: int, n: int) -> str:
    """Extra checks for beating a world's boss (Escape), from the Boss Checks option."""
    return f"Escape: {boss_slot_name(world_slot)} Bonus {n}"


def boss_bonus_count(mode: int, world_slot: int) -> int:
    """Boss Checks option: 0 = no bonus, 1 = one extra per boss, 2 = weighted (world n boss gives n extra)."""
    return 0 if mode == 0 else 1 if mode == 1 else world_slot


def bapy_location(title: str, tier: int) -> str:
    """Reaching a Sire Bapy achievement tier (save capybaraUnlocked['<key>*<tier>'] = 'new' or 'unlocked')."""
    return f"Sire Bapy: {title} {tier}"


# Achievements tied to one hero, and ones that can't be done in some seeds.
BAPY_HERO = {"ayla_levelMax": "Ayla", "kiran_levelMax": "Kiran", "octave_levelMax": "Octave", "calie_levelMax": "Calie",
             "yamat_levelMax": "Yamat", "arven_levelMax": "Arven", "unlock_octave": "Octave", "unlock_calie": "Calie",
             "unlock_yamat": "Yamat", "unlock_arven": "Arven"}
BAPY_NEEDS_SPELL_PURCHASES = {"merchant_boughtSpells", "merchantBuyEverything"}
BAPY_DESTINY_LEVELS = "gameCompleted_destinyLevel"  # tier n = beat Destiny Level n


# Sire Bapy achievements by category (options: one "highest tier" per category, or a preset).
BAPY_CATEGORIES = {
    "Combat": ["enemyKills_elites", "enemyKills_bouncingShroom", "enemyKills_firePortal", "highestDamageMade",
               "enemyKills_clam", "enemyKills_redDiamond", "obj_enemy_pinata", "enemyKills_miniboss",
               "uniqueMinibossDefeated", "summonZodiacs", "numberOfUspellUse", "lifeSacrificed_pavoRuins",
               "obj_boss_ophiuchus", "meet_zodiacSign"],
    "Challenges": ["perfectedFightRooms", "enemiesKilledWithoutBeingHit", "fightRoomChallengeSuccess",
                   "challengesSuccess"],
    "World Feats": [f"{key}_w{w}" for key in ("enemyKills", "uniqueZodiacsDefeated", "zodiacPerfected",
                                             "challengesSuccess") for w in range(1, 5)],
    "Builds": ["spellMaxAffinity", "differentSpellsUsed", "gambitEquiped", "legendarySpell", "numberOfStoneEquiped",
               "numberOfAurasEquiped", "astralAuraEquiped", "astralGambitEquiped", "numberOfEchoEquiped"],
    "Exploration": ["numberOfRuns", "crystalsCollected", "chestOpened", "yaleesSaved", "keysUsed",
                    "difficultyStarsUsed", "findNest", "meet_chameleon", "dialogueBench", "visits_cetus",
                    "beSavedBySova"],
    "Shops & NPCs": ["merchantBuys", "merchant_boughtSpells", "merchantBuyEverything", "andromedaBarUse",
                     "botanist_unlockedRows", "botanist_eatFruits", "relicNPC_unlockedRelics", "stylist_unlockedColors",
                     "papaYalee_unlockedMemories"],
    "Heroes": ["ayla_levelMax", "kiran_levelMax", "octave_levelMax", "calie_levelMax", "yamat_levelMax",
               "arven_levelMax", "unlock_octave", "unlock_calie", "unlock_yamat", "unlock_arven"],
    "Destiny": ["pathOfDestinies_unlocked", "gameCompleted_destinyLevel", "numberOfDestinyFragment"],
}
BAPY_CATEGORY = {key: cat for cat, keys in BAPY_CATEGORIES.items() for key in keys}
assert set(BAPY_CATEGORY) == {key for key, _, _ in BAPY_ACHIEVEMENTS}, "every achievement needs one category"
# Presets: highest tier per category (Custom = the per-category options).
BAPY_PRESETS = {
    "off": 0,
    "light": 1,       # tier 1 of everything: ~70 checks
    "standard": 2,    # tiers 1-2: ~125 checks
    "full": 9,        # every tier: ~210 checks (long grinds included)
}


def void_boss_location(milestone: int) -> str:
    """Milestone n = n x (Void bosses per check) Astral Void bosses (minibosses) beaten, any of them."""
    return f"Astral Void Milestone {milestone}"


LOCATION_NAME_TO_ID: dict[str, int] = {}
for _slot in range(1, 6):
    LOCATION_NAME_TO_ID[escape_location(_slot)] = _slot
for _n in range(1, MAX_VOID_BOSS_CHECKS + 1):
    LOCATION_NAME_TO_ID[void_boss_location(_n)] = 200 + _n
for _n in range(1, YALEE_SHOP_ITEMS + 1):
    LOCATION_NAME_TO_ID[yalee_shop_location(_n)] = 400 + _n
for _level in range(1, MAX_DESTINY_CHECK_LEVEL + 1):
    for _slot in range(1, 6):
        LOCATION_NAME_TO_ID[destiny_location(_level, _slot)] = 1000 + _level * 10 + _slot
for _i, _tab in enumerate(SPELL_TABS):
    for _n in range(1, len(TAB_SPELLS[_tab]) + 1):
        LOCATION_NAME_TO_ID[spell_location(_tab, _n)] = 6000 + _i * 20 + _n
for _n in range(1, len(TRACK_AURAS) + 1):
    LOCATION_NAME_TO_ID[aura_location(_n)] = 7000 + _n
for _row, (_name, _prices) in ZIMZIM.items():
    for _tier in range(1, len(_prices) + 1):
        LOCATION_NAME_TO_ID[zimzim_location(_row, _tier)] = 4000 + _row * 20 + _tier

for _w, _r in ROOMS:
    LOCATION_NAME_TO_ID[room_location(_w, _r)] = 9100 + _w * 20 + _r
for _slot in range(1, 6):
    for _n in range(1, 6):
        LOCATION_NAME_TO_ID[boss_bonus_location(_slot, _n)] = 9300 + _slot * 10 + _n
for _w, _n in LOST_YALEES:
    LOCATION_NAME_TO_ID[lost_yalee_location(_w, _n)] = 9000 + _w * 10 + _n
for _i, (_key, _title, _tiers) in enumerate(BAPY_ACHIEVEMENTS):
    for _tier in range(1, len(_tiers) + 1):
        LOCATION_NAME_TO_ID[bapy_location(_title, _tier)] = 8000 + _i * 10 + _tier

LOCATION_ID_TO_NAME = {v: k for k, v in LOCATION_NAME_TO_ID.items()}

__all__ = [
    "AURA_CHAINS", "ZIMZIM_TAGS", "FINAL_BOSS", "HEROES", "MINIBOSSES", "PASSIVES", "WEAPONS", "WORLD_BOSSES",
    "XP_TRACK", "ZIMZIM",
]
