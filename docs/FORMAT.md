# How the tracker reads Dragon's Dogma 2

Notes on the save format and the game files, as far as the tracker uses them. Everything here was worked out by
reading the files; nothing is official.

## Save files

- Location: `Steam\userdata\<account id>\2054970\remote\win64_save\`, slots `data00NSlot.bin`. The tracker copies the
  folder (hash-checked) and reads the copy; it never writes to the Steam folder.
- Container `DSSS` version 2. Flags `0x10` = Mandarin encryption (saves from before Dark Arisen), `0x18` = Mandarin
  plus raw Deflate.
- The Mandarin key is the lower 32 bits of the SteamID64, which is the account id (the `userdata\<id>` folder name).
- The last 4 bytes are murmur3(rest of the file, seed 0xffffffff). A mismatch means a half-written or damaged file and
  is an error, as are a payload length larger than the file and an inflated size different from the header's.
- The payload is a list of manager records (`app.GimmickManager.GameSaveData`, `app.ItemManager.GameSaveData`, ...),
  each a self-describing tree of (field hash, type, value). Field hash = murmur3(field name, 0xffffffff).

### Parser rules (`tools/dd2_parse.py`)

- Names come from two type dumps (`assets.lock.json`): `rszdd2.json` (before Dark Arisen, from ree-save-editor) for
  field alignment, `rszdd2_dlc.json` (current, from REasy) for class and field names.
- Struct values whose size is not a power of two start at their alignment, pushed into the upper half of a 32-byte
  window (`s % 32 < 16 -> s += 16`, measured on thousands of samples).
- Structs added with Dark Arisen have no known alignment. The parser tries starts and takes the earliest whose end
  meets a plausible field header (type and size checked, up to 256 bytes ahead). A start whose end meets a field the
  class is known to have wins over one that meets only an unknown hash: a dismissed pawn's 112-byte struct
  (`NPCSaveStrayPawnPast.?a1bad783`) sits behind 4 to 100 bytes of padding and once ended early on a chance header.
- After a parse failure the parser resyncs after the next `HashValue` field (the last field of every record).
- `app.NPCManager` holds per NPC: state bits and revive count (`_NPCHolders`), morgue coffins with the time of death
  (`_NPCCoffins`), affinity (`_NPCSentiments`), crime and jail, oxcarts, history. The tracker doesn't use it yet.

## Loot

- A placement's `_ManualSetGuid` (in the game's `appdata/generate/manualset/` files) equals the save's
  `UniqueID._RowID` (as `uuid.UUID(guid).bytes_le.hex()`).
- Looted: `GmItemContext._IsPick` in `app.ContextDBMSSaveData`, or the id is in
  `GenerateManager.GenerateSaveData2._NeverGenerateIDs`. Seen (passed, not looted): a context record without either.
- **Golden Trove Beetles** (gimmick 161 = Gm82_080, item 398, +0.15 kg carry weight each): 78 placements in gather and
  item folders alike. Taken = `app.GatherContext._Num` (beetles left) is 0, read for beetle spots only since herbs
  and ore grow back. They are one-time pickups.
- **Seeker's Tokens**: gimmick 167 (Gm82_036).
- Dark Arisen proving-ground loot (`content\rdl_0nn`) is drawn only in its own proving ground (UI area 6000+nn).

## Quests

- The quest log and `app.QuestContext.SaveData` give per quest its status, current task and `ResultNo` (-1 = not
  ended).
- `appsystem/quest/userdata/questtree.user.3` (and `_contents0014` for Dark Arisen) lists per quest
  `_PrevTransitions` (the quests it waits for) and `_EndConditionParam` (CheckScenario: quest X ended with result N;
  `LogicalOperator` 0 = And, 1 = Or).
- **Story phases.** Most side quests close with one of five hidden phase quests, 11010 to 11050. Each ends together
  with a main quest: Gaoled Awakening, Seat of the Sovran, Feast of Deception, Legacy and the last story step (10220).
  That pairing is read from the processor before `NotifyEndQuest` in `appdata\quest\qu01\qu0110n0\resident.scn.21`
  (the scene's RSZ block sits at the last offset of its `<4s5I5Q` header).
- A quest counts as **closed** when its end condition holds while the quest log has it neither completed nor failed.
  Started quests whose cutoff passes stay in progress with "may play out differently": the tree closes them, but their
  own scripts may handle it (Oxcart Courier's script checks for Readvent of Calamity). Dark Arisen quests never close.
  Deaths, timers and choices can still fail a quest; "Opens when" is the earliest point, the NPC may want more.
- **Timed quests**: the quest log marks a task as timed (10 quests have one). There is no countdown: the save's 453
  quest timers (`TimeManager.DetectionSaveData.QuestDatas`, 2880 units = 1 in-game day) also run for quests that
  haven't started, so they are not deadlines. The start day comes from the save log.

## Achievements

- The save has one record per achievement in `app.GlobalUserDataManager.SaveData.SaveGameRecordDataList`
  (`_RecordID` = Steam's achievement id 1 to 60, `_IsUnlock`, `_Count` for the counting ones, `_ProgressBitFlag`).
  `appsystem/gamerecord/userdata/gamerecordsettinguserdata.user.3` maps record ids to each platform's ids (on Steam
  the same numbers). The game's own `message/ui/trophy.msg.24` is empty on PC.
- Names, texts and the hidden flag come from Steam's local schema, `Steam/appcache/stats/UserGameStatsSchema_2054970.bin`
  (binary KeyValues: stats blocks of 32 bits, each bit with `name` = the achievement id and `display`). The account's
  unlocks are `UserGameStats_<account id>_2054970.bin`: `cache/<block>/AchievementTimes/<bit>` = unix time.
- Goals of the counting achievements are the number in their text (80 Seeker's Tokens, 50 people, 50 dungeons).

## You and your pawns

- Character records sit in `app.ContextDBMSSaveData`; `PlayerPersonalDataContext`, `MainPawnDataContext` and
  `SubPawnDataContext` mark who is who.
- `app.JobContext.CulmativeExp[vocation-1]` is the running total of vocation points, `ConsumableExp` the Discipline,
  `QualifiedJobBits` bit vocation-1 the unlocked vocations. Equipped skills and augments are indexed by vocation id.
- `app.PawnKnowledgeContext._QuestKnowledge01..03` are bit fields named by the enums
  `app.PawnKnowledge.QuestKnowledge.Category01..03` (bit i = one quest id).
- Vocation tables: `gui\jobmenu\jobinformationdata`, `customskillinformationdata` (cost 999999 = not bought with
  Discipline), `abilityinformationdata`, `jobrankparameter`; texts in `message\ui\job*.msg`, `subskill.msg`,
  `personality.msg`.

## Campsites and Riftstones

- Icons from `gui\userdata\mapicondata.user.3`, `autocollectmapicondata.user.3` (icons that appear once found) and
  their `contents0014` Dark Arisen versions: map icon type 23 = campsite, 8 = Riftstone, 32 = dungeon entrance
  (`_MapArea` = the dungeon's UI area).
- Found campsites: `app.CampSaveData.DiscoverBits` (64-bit words, bit n = campsite n) and `LastSleepIndex`. The
  numbering is not documented; `dd2_mapdata._camp_order` uses the order that fits the saves seen so far: the campfire
  placements under the 84 base-game icons (gimmicks 198, 199, 475, 476; `_ParamId` = fire type) sorted by the area
  number in their path, then path, then row. Numbers above 54 are not confirmed by a save yet; Norgan's 25 campsites
  have no number.

## Drops, gathering, smithing

- Drop chances are per kill: the table's chance per roll (an item listed several times counts with all its entries;
  item 0 = nothing) combined with the number of rolls from `_LotList`. Tables with `_RegionNo` > 0 drop when that body
  part breaks. Only species default tables with `_Type` 0 are used (other types are pickpocketing and special drops).
  Dark Arisen monsters' drops come from `contents0014enemyextendeditemdropdata` (`DefaultRate` used as the weight:
  approximate).
- Gathering chances are per visit, from the gimmick drop tables.
- Smithing costs: `itemdata\*enhancedata.user.3`. In the save the field `?84705117` of `ItemStorageBackup` (unnamed
  in both type dumps) = level | style << 16, style = `app.EnhanceType` (0 Vermundian, 1 Battahli, 2 Elven, 3 Dwarven,
  4 Wyrmfire). The Materials tab lists every item those costs use.

## The map

- Menu map `app.MapTexListData`, UI area 0: an 8x8 grid of 4096 px tiles, 1024 world units each, origin
  (-4096, -4096); grid rows grow with world z, so north is -z. The Dark Arisen list (`contents0014…`) adds the Norgan
  tiles.
- Dungeon and cave maps (120, with all their floors) are drawn in the margin around the world map. Loot is placed on
  a floor when the floor map is opaque at its position and it comes from a dungeon placement file; overlapping floors
  are split by height.

## Game files and the build

- `tools/ree_pak.py` reads the PAK archives (v4.x with the 0x40 remap table), following REasy and RE-Engine-Lib. File
  names come from REasy's `DD2_STM.list`; the commit pinned in `assets.lock.json` is the first with the Dark Arisen
  paths. One entry of the game is resource-encrypted (the shop table `itemshopadditionaldata.user.3`).
- `.user.3` and scene files are RSZ trees (`tools/ree_rsz.py`), texts `.msg.24` (`tools/ree_msg.py`), textures
  `.tex.251211553` (`tools/ree_tex.py`).
- `tools/dd2_build.py` builds in five steps into the data folder: reading game files, the game tables (`gamedata\`),
  the map tiles, the dungeon maps, the map data (`map\data\static.json`). `gamedata\meta.json` is written last with
  Steam's build id of the game; without it the next start builds again, and a different build id offers a rebuild.
- **Bumping a pinned file** in `assets.lock.json` (after a game update changes the types, say): change commit and
  SHA-256 together, run `dd2.py build` into an empty folder (`DD2_DATA_DIR`), and compare the result with the
  previous build before committing.
