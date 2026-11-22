# torment-converter

Convert save games from the original **Planescape: Torment** (1999, the classic GOG/CD
release) so they load in **Planescape: Torment: Enhanced Edition** (Beamdog, 2017).

The official answer is that original saves "are not compatible" with the Enhanced
Edition. That is true for copying the files across: the EE changed the format of the
save game, of every creature, and of how inventory, proficiencies and kill counters are
stored, so a plain copy crashes the load screen. This tool rewrites a save into the EE
formats instead.

> **Status: experimental.** A converted save has been loaded in PST:EE 3.2.2 (macOS),
> played and saved again by the game. That is one playthrough, not broad testing. Keep
> your original saves; the tool never modifies them.

## Requirements

- Python 3.8 or newer. No third-party packages.
- An installed copy of Planescape: Torment: Enhanced Edition. The tool reads the EE's
  own game data (maps, creatures, world map) from the install to build the new save.
- Save folders from the original game (each holds `TORMENT.GAM` and `TORMENT.SAV`).

## Install

```sh
git clone <this repository> torment-converter
cd torment-converter
python3 -m pip install .        # installs the `torment-convert` command
```

Or run it without installing:

```sh
PYTHONPATH=src python3 -m torment_converter --help
```

## Usage

Convert every save in the original game's `save` directory:

```sh
torment-convert convert "/path/to/Planescape Torment/save"
```

Convert a single save folder:

```sh
torment-convert convert "/path/to/Planescape Torment/save/000000023-My Save"
```

Each folder is written to the EE save directory under the same name. Existing folders are
skipped unless you pass `--force`.

| Option | Meaning |
| --- | --- |
| `--ee PATH` | Enhanced Edition install folder. Auto-detected for common Steam, GOG, Beamdog and macOS locations. |
| `--out PATH` | Where to write the converted saves. Default: the EE save directory (see below). |
| `--suffix TEXT` | Append text to each folder name, e.g. `--suffix " (converted)"`. |
| `--force` | Overwrite existing save folders of the same name. |
| `-v` | List what was carried over for each save. |

### Where the files are

| | Location |
| --- | --- |
| Original saves (GOG / CD, Windows) | `<game folder>\save\` |
| Original saves (GOG classic for Mac) | `~/Library/Application Support/GOG.com/Planescape Torment/save/` |
| EE saves, Windows and macOS | `Documents/Planescape Torment - Enhanced Edition/save/` |
| EE saves, Linux | `~/.local/share/Planescape Torment - Enhanced Edition/save/` |
| EE install, Steam | `steamapps/common/Project P` |

### Undo

Delete the converted folders from the EE save directory. If the EE's *Load Game* screen
crashes, quit the game and remove the converted folders; your own EE saves are untouched
unless you used `--force` on a folder with the same name.

## What carries over

- **Party:** stats, level, XP, HP, inventory and equipped items, spells, weapon
  proficiencies, quick-bar assignments.
- **Game state:** gold, game time, all global variables (quest and dialogue state), kill
  counters, journal, bestiary, world map discovery, store stock.
- **Areas you visited:** who is alive or dead and where they stand, container and
  ground items, door and trap states, area variables, explored map (fog of war).

## What does not, or might not

- **Map notes you wrote yourself** are dropped (the EE stores notes differently).
- **Areas:** the EE's own version of each map is used as the base and your saved state is
  merged into it. Creatures Beamdog added to an area you already visited will be missing;
  creatures Beamdog removed may reappear.
- **Items in the original's sixth quiver slot** (not reachable in the original GUI)
  stay in the inventory list but unequipped.
- **The Modron Maze** layout is not converted. Saves made before you enter the maze are
  unaffected; saves made inside it are untested.
- **Mods:** saves from a modded original game may reference files the EE does not have.

## Checking the converter

If you also have the original game installed, you can compare the creature converter
with Beamdog's own conversion of the game's ~1,070 creatures:

```sh
torment-convert validate --original "/path/to/Planescape Torment"
```

It reports the fields that still differ. Remaining differences are content changes Beamdog
made in the EE (fixed scripts, sounds, item placement), not format errors.

Unit tests use synthetic data and need no game files:

```sh
python3 -m unittest discover -s tests
```

## How it works

See [docs/how-it-works.md](docs/how-it-works.md) for the format differences and how each
mapping was established.

## Reporting problems

Please include the output of `torment-convert convert -v ...` for the save, the EE version
and platform, and what happened (load screen crash, crash on load, wrong state in game).
Do not attach game data files; save files are fine.

## Legal

Licensed under the Apache License 2.0 (see [LICENSE](LICENSE)).

Not affiliated with or endorsed by Beamdog, Black Isle Studios or Wizards of the Coast.
Planescape and Planescape: Torment are trademarks of their respective owners. This
repository contains no game data; the tool reads your own installed copy.

## Credits

File format knowledge from the [IESDP](https://gibberlings3.github.io/iesdp/) and the
[Near Infinity](https://github.com/NearInfinityBrowser/NearInfinity) project.
