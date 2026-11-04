# Changelog

What changed in each version of DD2 Completionist Tracker. Download a version from the
[Releases](https://github.com/anasurimbor87/dd2-completionist-tracker/releases) page.

## [1.1.0] - 2026-11-04

Story timeline, achievements and Norgan Ducats. Ready for Dragon's Dogma 2 Title Update 4.2 (the Delicious in Dungeon
collaboration).

### Highlights

- **See the points of no return.** The Quests tab now opens with a story timeline: the five moments where finishing
  a main quest closes side quests for good, and under each one the quests that close there, with how you stand on them.
- **Achievements.** A new tab lists all 60 achievements: which ones you have unlocked and when, and how far along you
  are with the ones that count up.
- **Norgan Ducats on the map.** All 140 Ducats of Dark Arisen now have their own map layer and count.

### Added

- Quests: each quest in the timeline says whether you have done it, are on it, can start it now, can start it later,
  or missed it. If something closes it before the point of no return, its line says what.
- Quests: a group for the quests that close when you finish a certain other quest rather than at a point of no
  return.
- Quests: later story phases stay hidden until you turn on "Show later phases", so the timeline doesn't spoil the
  story.
- Quests: the quest list can show only the quests you can still miss.
- Map: quests you haven't started that can close in your current story phase have an orange ring.
- Achievements: progress bars for the three that count up (Seeker's Tokens, people's affection and dungeons found),
  counted from your save.
- Achievements: hidden story achievements stay hidden until you unlock them or choose to show them.
- Achievements: a click takes you to what helps, for example the Seeker's Tokens nearest to you.
- Achievements: newly unlocked achievements show up in the Log.
- Nearby: filters for Norgan Ducats and for Wakestones, with how many Wakestones, Wakestone Shards and Eternal
  Wakestones are still out in the world.

### Changed

- The story timeline replaces the box of story phases at the top of the Quests tab.
- While "Show later phases" is off, main quests of later story phases are also left out of the quest list and the
  map, and quest notes don't name them. Turn it on to see everything.
- Ready for Title Update 4.2. The new collaboration outfits are given to you by the game rather than found in the
  world, so there is nothing new to put on the map; they show up in your Log once you have them.

### Fixed

- Quest notes no longer warn that a quest can be lost through another quest you can no longer do.

### Good to know

- **The first start after updating rebuilds the map** from your game files, once, because both the game and the
  tracker's map data changed. It takes a few minutes; the page shows the steps.
- **To update**, close the tracker's window, then unzip the new version into the folder that holds your old
  **DD2 Completionist Tracker** folder and let Windows replace the files. Your Log, save backups and settings stay.
- **Norgan Ducats you pick up should show as taken.** This could not be tried on a real save yet. If a Ducat you
  collected still shows as not taken, please open an issue.

## [1.0.0] - 2026-11-04

The first public version.

- A live map of the whole world and every dungeon, with all chests, items, Dark Arisen caches, Seeker's Tokens and
  Golden Trove Beetles, coloured by what your newest save says: not visited, passed, or looted.
- Campsites and Riftstones, dungeon entrances, quest positions, and optional layers for gathering spots, monster
  spawns, smiths and shops.
- Tabs for quests (with the quests the story closes), unique gear, materials, your party, the nearest unlooted spots,
  and a log of what each game save changed.
- A view for phones and tablets on your home Wi-Fi.
- Reads your save only; never changes it. Needs no mods.

[1.1.0]: https://github.com/anasurimbor87/dd2-completionist-tracker/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/anasurimbor87/dd2-completionist-tracker/releases/tag/v1.0.0
