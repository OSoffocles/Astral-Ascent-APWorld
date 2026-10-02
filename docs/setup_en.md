# Astral Ascent – Archipelago setup (v0.1.0, game version 2.6.4)

## What you need
- Astral Ascent (Epic or Steam), Windows.
- Archipelago 0.6.7 or newer.

## Playing a seed
1. Install `astral_ascent.apworld` (double-click it).
2. On your room's page, click **Connect** next to your slot and choose **Astral Ascent Client**
   (or open the Archipelago Launcher → Astral Ascent Client and type `/connect <address>` and your slot name).
3. That's it. The client then:
   - finds the game (Epic or Steam),
   - picks a free save slot for this seed, starting in the Garden with the tutorial done, every shop and NPC
     open (Arsenal, Barbecue, Poetic Peddler, Zim-Zim, Sire Bapy, Papa Yalee, Oloon) and the whole XP track
     revealed: every spell, aura and Zim-Zim upgrade is in the shops from the start. Your other slots are
     never touched and your save file is backed up first.
   - and starts the game. If Epic or Steam asks which save to keep, choose the **local** one. Load the slot
     the client names, talk to Sova and play. Keep the client window open.

Coming back later: connect again and the client starts the game with the same slot. If the game is
already running when you connect, the client asks you to quit it once so it can check the save.
All three slots in use? The client asks you to pick one with `/newslot 1|2|3 overwrite`.

## In-game overlay
While you play, the top-right corner of the game keeps the 8 most recent messages: what you receive and
send, hints about your items, other players finishing their goal; plus a line with how many checks are in
logic right now. It only shows
while the game is the active window (it needs the game's default borderless fullscreen or windowed mode).
Turn it off or on with `/overlay off` / `/overlay on`.

## Spells, Auras and Zim-Zim
Spells and Zim-Zim have three choices each, Auras two (`random` works too):

| | Items | Checks | Vanilla |
|---|---|---|---|
| **Spells** (default: items) | One item per spell, received in random order. The Merchant's spells can't be bought (price out of reach). | Buy spells as normal and keep them; every spell bought is a check ("Merchant: Ayla Spell 3"). | Normal game, not in the multiworld. |
| **Auras** (default: checks) | – | Collect as normal and keep them; every collection is a check. All auras are on display from the start: free early checks. | Normal game, not in the multiworld. |
| **Zim-Zim** (default: checks) | Progressive items, one tier per copy. Zim-Zim's upgrades can't be bought (prices out of reach). | Buy as normal and keep them; every tier bought is a check. | Normal game, not in the multiworld. |

Prices out of reach are
set by the client in the game's files and your seed's save slot; `/files restore` restores the files.

Weapons and passives have their own on/off options (on: items; off: all unlocked from the start).
Heroes always come from the multiworld (Ayla and Kiran start unlocked).

## Filler, boons and traps
Every check needs an item. After heroes, upgrades and the *Destiny Fragment Bundles*, the free slots are filled
in this order:
1. **Duplicates** (*Duplicates* option): the number is how many EXTRA copies per category, e.g.
   `Ayla Spells: 1` = each of Ayla's 15 spells twice; 0 or no entry = none. Only categories that are items in
   your seed count; for logic only the first copy of an item counts (a Zim-Zim copy is one more tier,
   as in game), and copies are cut at random if there isn't room. **Duplicates go
   first: with many of them, little or no room is left for boons, traps and other filler.**
2. **Filler shares**: *Filler: Sun Pieces / Yalee Tickets / Destiny Fragments / Boons / Traps %*. **Make the
   five add up to 100.** 0 turns a kind off. Sun Pieces only count when there's a shop to spend them in
   (Spells or Zim-Zim not on Items).

Sun Pieces, Yalee Tickets and Destiny Fragments arrive immediately. **Boons** and **traps** work on your current
run; received outside a run, they wait for the next one (`/status` shows how many are waiting). Choose which ones
can appear with the *Boons* and *Traps* options:

| Boons | | Traps | |
|---|---|---|---|
| Keys | +2 keys | Thief | lose half your Quartz and a key |
| Stars | +5 stars | Bruise | lose 25% of your current HP (never lethal) |
| Quartz | +50 Quartz | Drain | mana to 0 |
| Heal | +30% of max HP | | |
| Max HP | +20 max HP for the run | | |
| Mana | mana refilled | | |
| Level Up | one level's worth of XP (you level up on your next XP gain) | | |
| Stat Stone | +1 to a stat stone (strength, armor, critical, speed) you already have this run; with none yet, it waits for your first | | |

Receiving an item never sends a check: checks come from what you do. When you own everything at Barbecue or
in a Zim-Zim upgrade, the checks left there are sent for you.

## Checks
**Rooms**: clearing each room of a run (11 per world, 1 in the final world; *Room Checks*: drip = each room as
you clear it, bulk = a world's rooms when you beat its boss). **Bosses**: *Boss Checks* = room (one check per
boss), bonus (one extra per boss) or weighted (World 1 boss +1 extra … final boss +5). Barbecue auras, Zim-Zim
tiers and Merchant spells (each when its mode is Checks), each world's boss and the final
boss (in a normal escape and on Destiny Levels; any of a world's three bosses counts), Astral Void milestones
(every *Void Bosses per Check* Void bosses, repeats count, up to *Void Boss Checks*), Yalee Ticket shop
milestones (every *Yalee Shop Purchases per Check* items bought at Oloon, up to *Yalee Shop Checks*), the 20
**lost Yalees** you save in runs (5 per world, held hostage or hidden in pots), and **Sire Bapy
achievements**: claiming a tier's reward
is a check, for tiers *Sire Bapy Min Tier* to *Sire Bapy Max Tier* (default: tier 1 only, about 70 checks).
Tiers above *Sire Bapy Progression Max Tier* (default 2) never hold heroes or upgrades, so long grinds never
block you.

## Logic
Everything up to and including the World 1 boss is in logic from the start, as are the Barbecue aura checks.
Deeper areas expect a share of your upgrade items (spells, Zim-Zim tiers, weapons, passives), set by *Logic
Difficulty* (Normal shown; Easy expects 25% more, Hard 40% less):

| Area | Upgrade items expected |
|---|---|
| World 1 | none |
| World 2 / 3 / 4 | 10% / 20% / 30% |
| Final boss | 40% |
| Destiny Level n | 40% + 4% per level, up to 80% |

Checks belong to an area: rooms, bosses and lost Yalees to their world; Void and Yalee shop milestones are spread
evenly over Worlds 1-4; Sire Bapy tier 1 is expected around World 2, tier 2 World 3, tier 3 World 4, higher tiers
at the final boss (achievements for one world start in that world); Merchant spells and Zim-Zim tiers (Checks
mode) by Sun Piece budget, cheapest first: about 1,500 Sun Pieces up to World 1, 5,000 World 2, 15,000 World 3,
35,000 World 4, 75,000 the final boss, the rest spread over the Destiny Levels (times the currency multiplier).

Every option's description says how many checks or items it adds, and generation prints a summary per player
(checks by source, items by kind, how the free slots were filled). Too many items for your checks? Generation adds
checks for you, in this order: Void Boss Checks (up to 100), Yalee Shop Checks, then the next Sire Bapy tier, and
prints a big warning saying what it added. Only if that still isn't enough does it stop with an error. To choose
yourself, add checks or set Spells/Zim-Zim to Checks or Vanilla. (The DLC heroes add 32 items.)

## Steam
Steam works the same as Epic. The Steam version may be a slightly different build: the client then
looks up where the game keeps Sun Pieces and Yalee Tickets when you enter the hub, and says so once.

## Commands
`/play` (set up and start the game again) · `/overlay on|off` · `/status` · `/deliver` (search the game's memory
again, if an unlock doesn't show up) · `/newslot 1|2|3 [overwrite]` and `/prepare` (game closed; manual slot
setup) · `/files status|restore` (the game files the client changes: spell and Zim-Zim prices; `restore` puts the originals back, with the game closed)

## Known limitations (v0.1.0)
- Currency items received while you're at the main menu may be lost: stay in the Garden or a run.
- A boon or trap that arrives on the death screen still counts for that (finished) run.
- Boons and traps are for player 1 (no co-op support).
- Heroes you haven't received yet can still unlock through the game's own events if you reach
  World 3/4; the client locks them again.
- Locking a weapon you have equipped leaves it equipped (only matters for slots with earlier progress).
- To play Astral Ascent normally again after a seed: `/files restore` (or verify the game files in Epic / Steam).
