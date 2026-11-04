# DD2 Completionist Tracker

A completionist tracker for **Dragon's Dogma 2** on PC (Steam) that needs **no mods**. It reads your save files,
never writes to them, and shows what you have found and what is left on a map in your browser: on the same PC, or on
your phone next to the game.

![The tracker's map around Vernworth: chests, items, Seeker's Tokens, Golden Trove Beetles, campsites and dungeon entrances, coloured by one player's save (grey = looted, gold ring = passed without looting), with the layer list and counts in the journal on the left](docs/screenshot.jpg)

<sub>Map artwork © Capcom, read from the player's own installation.</sub>

> **Vibe-coded project.** Almost all of this code was written by an AI coding assistant (Claude Code), directed and
> play-tested by a human player. Not every line has been reviewed by a person. The tool only reads your saves and
> never writes to them, but use it at your own risk.

Using it needs no AI service and no account, and your save never leaves your PC. The only thing fetched from the
internet is two web fonts from Google Fonts, when you are online; offline the page uses your system's fonts.

## What it shows

The game's own world map, with every dungeon and cave drawn beside it, and on it:

- **Loot**: every chest, item on the ground and Dark Arisen cache, coloured by what your save says: not visited,
  passed without looting (gold ring), or looted (small and grey). Chests holding weapons, armour or rings stand out.
- **Collectibles**: all Seeker's Tokens, all 78 Golden Trove Beetles and Dark Arisen's 140 Norgan Ducats, with how
  many you have taken. The chests and items of the Lost Rites proving grounds are on their own maps.
- **Campsites and Riftstones**, the campsites you have found, and dungeon entrances.
- **Quests**: where the quests in progress continue and where the ones you haven't started begin. Quests you
  haven't started that close at the end of your current story phase get an orange ring.
- **Farming** (off by default): gathering spots with their yields, monster spawns with their drops, smiths and shops.

And in the journal beside the map:

- **Quests**: a story timeline of the five **points of no return**. Under each one are the quests that close
  there and how you stand on them: done, in progress, can start now, opens later, or missed. Later phases stay
  hidden until you turn on spoilers, and the quest list can be narrowed to quests you can still miss. A banner warns
  while you are on a quest whose end closes others, and while a timed quest is running.
- **Achievements**: all of the game's Steam achievements, which ones your account has unlocked and when, and
  progress bars from your save for the counting ones (Seeker's Tokens, people's affection, dungeons found), with a
  jump to the map layer that helps. Hidden story achievements stay hidden until you unlock or reveal them.
- **Unique gear**: every piece that exists only once or twice in the world, and where.
- **Materials**: everything smiths use, how many you have, who drops it, who sells it, and where to gather it.
- **Party**: you, your main pawn and hired pawns: vocations, ranks, skills, augments, what to learn next.
- **Nearby**: the closest unlooted spots, campsite and Riftstone from where you last saved, filtered by kind
  (chests, unique gear, Seeker's Tokens, beetles, Norgan Ducats, or Wakestones and their shards).
- **Log**: what each game save changed: spots looted, quests started, finished or closed, items, levels and ranks.

The map follows your game: a few seconds after each save it reads the new save by itself.

## Download and start

1. Download `DD2-Completionist-Tracker-<version>.zip` from the
   [Releases](https://github.com/anasurimbor87/dd2-completionist-tracker/releases) page.
2. Unzip it somewhere you can write to, such as your Documents folder (not Program Files).
3. Double-click **DD2 Completionist Tracker.exe**. A console window opens (keep it open while you play; close it
   to stop the tracker) and the map opens in your browser at http://127.0.0.1:8642/.
4. The first start builds the map from your own game files. That takes a few minutes; the page shows the steps.

Windows may warn about an unknown app the first time: see the questions below.

## Questions

**Windows says "Windows protected your PC".** The program is not signed with a paid certificate, so SmartScreen
doesn't know it yet. Click "More info", then "Run anyway". The ZIP is built by GitHub from the public source code
(see `.github/workflows/release.yml`), never on someone's PC. To check that your download is that ZIP, compare its
SHA-256 with the `.sha256` file on the Releases page:
`certutil -hashfile DD2-Completionist-Tracker-<version>.zip SHA256`

**Is my save safe?** The tracker never writes to the Steam save folder or the game. It copies the save folder and
reads the copy. Before reading a new save it keeps a backup of it in `work\backups\` (the last 30).

**Where does it put its files?** Next to the program: `gamedata\`, `map\`, `extracted\` (built from your game) and
`work\` (save copies, backups, the log). To remove the tracker, delete its folder.

**The game was updated.** The page offers "Rebuild map data" when Steam reports a new game version. Until then the
map keeps working with the old data.

**I have several Steam accounts.** The tracker reads the account with the newest save. When more than one account
has saves, the journal shows a picker.

**Steam doesn't know where the game is.** The first start then asks for the game folder (the one with DD2.exe).

**Can I use it on my phone?** Start **DD2 Completionist Tracker (phone).cmd** instead. The journal shows the address
and a QR code for phones and tablets on the same Wi-Fi; anyone on that network can view the map while the window is
open. Windows asks once whether the program may accept connections. If your network is set to "Private", allow it.
If Windows calls it "Public", allow it for public networks, or switch the network to "Private" in the Windows
network settings; otherwise the phone can't connect.

**Steam Deck or Linux?** Not supported yet; it reads Steam's Windows registry entries.

**Do I need mods?** No. If you prefer an overlay inside the game, these REFramework mods cover parts of the same
ground: [Arisen's Ledger](https://github.com/whiteyt223/arisens-ledger) (quests, cutoffs, timers),
[Clairvoyance](https://github.com/polston/dd2-clairvoyance) (quests and world markers) and
[Map Markers and Collectables by Raze](https://www.nexusmods.com/dragonsdogma2/mods/1551) (collectibles on the map
and minimap).

## Run from source

Python 3.14 on Windows. See [CONTRIBUTING.md](CONTRIBUTING.md): set up a virtual environment, run
`python dd2.py fetch-assets`, then start `DD2 Completionist Tracker.cmd`. How the save and the game files are read is
written up in [docs/FORMAT.md](docs/FORMAT.md).

## Licence and credits

GPL-3.0 (see [LICENSE](LICENSE)). The save reading is a port of
[kvasszn/ree-save-editor](https://github.com/kvasszn/ree-save-editor); the game-file reading builds on
[REasy](https://github.com/seifhassine/REasy), [RE-Engine-Lib](https://github.com/kagenocookie/RE-Engine-Lib) and
[REMSG_Converter](https://github.com/dtlnor/REMSG_Converter); the map uses [Leaflet](https://leafletjs.com/). Details
and licence texts: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Vibe-coded fan project, not affiliated with Capcom. Dragon's Dogma is a trademark of Capcom. The tracker ships no
game files: the map, item names and quest texts come from your own installation.
