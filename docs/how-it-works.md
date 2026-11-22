# How the conversion works

Both games run on the Infinity Engine, but Beamdog moved Planescape: Torment onto the
engine branch used by the other Enhanced Editions. Its data was converted to that
branch's formats; the original's formats are no longer read.

| File in a save | Original | Enhanced Edition |
| --- | --- | --- |
| Game state | `TORMENT.GAM`, `GAMEV1.1` | `BALDUR.gam`, `GAMEV2.0` |
| Area / store archive | `TORMENT.SAV`, `SAV V1.0` | `BALDUR.sav`, `SAV V1.0` |
| Creatures (party, embedded in areas) | `CRE V1.2`, effects `EFF v1` | `CRE V1.0`, effects `EFF v2` |
| Areas | `AREAV1.0` (PST variant) | `AREAV1.0` (EE variant) |
| World map | `WMAPV1.0` | `WMAPV1.0` |
| Stores | `STORV1.1` | `STORV1.1` |

## Method

Mappings come from three sources, in order of weight:

1. **Paired files.** The EE ships Beamdog's conversions of the original game's resources
   under the same names. Converting every original creature and diffing against the EE
   copy (`torment-convert validate`) shows where each field went. The same was done for
   areas, stores and the world map, and for the new-game template (`TORMENT.GAM` in the
   original vs `BALDUR.GAM` in the EE).
2. **Saves written by the EE.** After a converted save was loaded and saved again by the
   game, the EE-written file was compared with the converter's output. This settled the
   details no reference documents (slot count byte, quick-bar slot numbers, selected
   weapon).
3. **Format references:** the IESDP and Near Infinity's readers, plus the EE's own tables
   (`ITMSLOTS.2DA`) and scripts.

## Game file (GAM)

- Header: game time, formation, gold, weather, main/current area and reputation are
  copied to their V2.0 positions (reputation moves from 0x58 to 0x54, current area from
  0x5C to 0x58). The EE fields are filled as the EE writes them: world map `WORLDMAP`, an
  empty 400-byte familiar block, empty stored-location and pocket-plane lists.
- NPC records shrink from 0x168 to 0x160 bytes. The original has five quick items; the
  V2.0 record has three. The EE keeps quick items 4 and 5 (and their abilities) in the
  otherwise unused block at 0x84.
- Quick-bar entries are internal slot numbers, which differ between the games:

  | Slot | Original | EE |
  | --- | --- | --- |
  | Equipment, fist, quiver 1-4 | 0-14 | 0-14 |
  | Quiver 5 | 15 | 39 |
  | Quiver 6 | 16 | (none) |
  | Quick items 1-3 / 4-5 | 17-19 / 20-21 | 15-17 / 41-42 |
  | Inventory 1-16 / 17-20 | 22-37 / 38-41 | 18-33 / 44-47 |
  | Magic weapon | 42 | 34 |
  | Weapons 1-4 | 43-46 | 35-38 |

- Global variables are copied. Start-of-game variables that the EE's `BALDUR.GAM` template
  defines and the save lacks are added.
- **Kill variables.** The original keeps a separate `KAPUTZ` variable scope. The EE has no
  such scope; its scripts read `GLOBAL` variables named `<name>_KAPUTZ`
  (e.g. `KAPUTZMaeth_DEAD` became `GLOBALMaeth_DEAD_KAPUTZ`). Each kill variable becomes
  such a global.
- **Bestiary.** The original stores 260 flag bytes; the EE uses globals named
  `BESTIARY_KNOWN_<index>`.
- **Modron maze** state is not converted.
- Journal entries keep their format. String references stay valid: the EE `dialog.tlk`
  keeps the original numbering.

## Creatures (CRE V1.2 to V1.0)

The header shrinks from 0x378 to 0x2D4 bytes. Most fields keep their offsets; the
PST-only block is relocated:

| Field | V1.2 | V1.0 (PST:EE) |
| --- | --- | --- |
| Colour indices (first four) | words at 0x2E4 | bytes at 0x2C |
| Reputation | word 0x44 | byte 0x44 |
| Hide in shadows | (stealth 0x68) | 0x45 |
| Unspent proficiencies | 0x64 | 0x7B |
| Item slot count | n/a | 0x7C (party: 56, others: 0 = default 40) |
| MURDER increment | 0x2BB | 0x7F |
| Thief / mage XP | 0x29C / 0x2A0 | 0x84 / 0x88 |
| GOOD / LAW / LADY increments | 0x2B8-0x2BA | 0x8C-0x8E |
| Faction / team / species | 0x313 / 0x312 / 0x311 | 0x8F / 0x90 / 0x91 |
| Dialog range, selection circle | 0x2DC-0x2DD | 0x92-0x93 |
| Field of vision | 0x30E | 0x95 |
| Attribute flags | 0x2E0 | 0x96 |
| EA, general, race, class, specific, gender | 0x314-0x319 | 0x270-0x275 |
| Object IDs, alignment | 0x31A-0x31F | 0x276-0x27B |
| Actor enumeration, death variable | 0x320-0x343 | 0x27C-0x29F |
| Section offsets/counts | 0x344 | 0x2A0 |
| Dialog | 0x370 | 0x2CC |

Further EE changes applied to every converted creature:

- **Animation IDs** in the 0x6xxx and 0xExxx ranges move to 0xFxxx.
- **Flags:** bit 0 and bit 20 set, bits 12-13 cleared (the EE does this for all PST
  creatures).
- **Weapon proficiencies** are no longer header bytes. Each becomes an opcode 233 effect
  (timing 9, param1 = stars, param2 = stat): fist 89, edged 96, hammer 97, axe 92,
  club 115, bow 103.
- **Effects** are widened from EFF v1 (48 bytes) to the CRE-embedded EFF v2 (264 bytes).
- **Static fields** where Beamdog fixed content (colours, attribute flags, alignment
  increments) are taken from the EE's copy of the same creature when the animation matches.
- Script references to files the EE no longer ships are cleared, as Beamdog did.

### Inventory slots

The original stores 48 words (46 slots, selected weapon, ability). The EE stores 40 words
for ordinary creatures and 57 for party members (`ITMSLOTS.2DA`, column `SAVE_INDEX`):

| Original index | Content | Party (57) | Other (40) |
| --- | --- | --- | --- |
| 0-16 | equipment, weapons 1-4, quiver 1-4 | same | same |
| 17 | quiver 5 | 38 | - |
| 18 | quiver 6 | - | - |
| 19 | upper right tattoo | 17 | 17 |
| 20-22 | quick items 1-3 | 18-20 | 18-20 |
| 23-24 | quick items 4-5 | 40-41 | - |
| 25-40 | inventory 1-16 | 21-36 | 21-36 |
| 41-44 | inventory 17-20 | 42-45 | - |
| 45 | magic weapon | 37 | 37 |

Items with no target slot remain in the creature's item list, unequipped. The EE resets
the party's selected weapon on load, so it is written as "none".

## Areas

Beamdog edited many maps (doors, regions, creatures, automap notes), so a converted
original area would not match the EE's scripts. Instead, for each area in the save:

1. Start from the EE's own `.ARE` for that map.
2. Replace the creature list with the saved one, each embedded creature converted as
   above (so dead creatures stay dead and moved ones stay moved).
3. Match containers by name: take the saved lock/trap state and contents. Saved
   containers the EE map lacks (piles of dropped items) are added with their outline.
4. Match doors and trigger regions by name; take their saved flags and trap state.
5. Merge area variables (saved values win).
6. Convert the explored map (fog of war), see below.

### Explored map

Both games keep one bit per 32x32-pixel cell, least significant bit first, rows packed
without padding. For a map of W x H 64-pixel tiles (from the area's WED file) the original
grid is 2W x 2H cells; the EE grid is (2W+1) x (2H+1). The converter re-packs the bits
row by row and fills the extra column and row from their neighbours. Checked against an
area the EE saved again after loading a converted save: same size, and 99.8% of the cells
the EE marked explored were already set by the converter.

The EE's own area files ship with no explored data, so without this step every visited
map shows full fog of war.

Rewritten sections are appended to the file and the header is repointed; the original
EE sections stay in place but unreferenced.

Areas the EE does not have are dropped from the save and reported.

## World map and stores

The EE's `WORLDMAP.WMP` is used, with each area's status flags (visible, reachable,
visited) copied from the save. Store files are unchanged in format and copied as they are.

## Open questions

- Whether the EE reads `BESTIARY_KNOWN_<n>` with the same index numbering as the original
  bestiary (the variable prefix is in the EE engine; the index format is assumed).
- Saves made inside the Modron Maze.
- Saves with party members beyond the Nameless One, Morte and Dak'kon have only been
  checked structurally.
