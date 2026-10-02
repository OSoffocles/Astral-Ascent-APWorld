# Astral Ascent for Archipelago

An [Archipelago](https://archipelago.gg) multiworld randomizer for **Astral Ascent** (game version 2.6.4, Windows,
Epic or Steam), with its own client.

Your heroes, spells, Zim-Zim upgrades, weapons and weapon passives come from the multiworld. What you do in your
runs and in the Garden sends items to the other players: clearing rooms, beating bosses, saving lost Yalees,
collecting auras, buying at the shops, claiming Sire Bapy achievements, Astral Void and Destiny Level progress.

**Status:** beta (v0.1.0). Item and location IDs are fixed from this version on.

## Features
- **One-click setup:** the client finds the game, sets up a fresh save slot for your seed (tutorial done, every
  shop open), backs up your save first and starts the game. Your other save slots are never touched.
- **Items delivered live** while you play: heroes, weapons, passives, spells, Zim-Zim tiers and currencies.
- **Checks** from rooms (each room as you clear it, or a world's rooms when you beat its boss), bosses (with
  optional bonus checks), lost Yalees, Barbecue auras, Merchant spells and Zim-Zim tiers, Astral Void and
  Yalee Ticket shop milestones, Sire Bapy achievement tiers and Destiny Levels.
- **Logic by depth:** everything up to the World 1 boss is open from the start; deeper worlds and Destiny Levels
  expect a share of your upgrades (Logic Difficulty: easy / normal / hard).
- **Filler you choose:** percentage shares for Sun Pieces, Yalee Tickets, Destiny Fragments, run boons (keys,
  stars, Quartz, healing, max HP, mana, a level up, stat stones) and traps (Thief, Bruise, Drain), plus optional
  duplicates per hero and category.
- **Budget help:** every option says how many checks or items it adds, generation prints a summary per player,
  and a seed with more items than checks gets extra checks automatically (with a warning).
- **In-game overlay** with your most recent sends, receives and hints, and how many checks are in logic.
- Goals: beat the final boss, or a Destiny Level, optionally with several different heroes.

## Install and play
1. Install [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or newer.
2. Download `astral_ascent.apworld` from the [Releases](../../releases) page and double-click it.
3. Make your player options with the Options Creator in the Archipelago Launcher (or start from the template it
   generates), and generate or join a multiworld.
4. On your room's page, click **Connect** next to your slot and choose **Astral Ascent Client**.

The full guide, with every option and client command, is in [docs/setup_en.md](docs/setup_en.md).

## Building the .apworld
An `.apworld` is a zip of this folder named `astral_ascent`:

```
astral_ascent.apworld
└── astral_ascent/
    ├── __init__.py
    ├── archipelago.json
    ├── client/
    └── ...
```

Zip the folder (renamed to `astral_ascent`, without `__pycache__`) and change the extension to `.apworld`.

## License
MIT, see [LICENSE](LICENSE). Astral Ascent is made by Hibernian Workshop; this project is not affiliated with
them.
