"""Story phases and quest cutoffs (the game's quest tree): when a quest opens and which quest's end closes it.

The quest tree (appsystem/quest/userdata/questtree*.user.3) lists per quest the quests it waits for (_PrevTransitions)
and the ones whose end closes it (_EndConditionParam). Most side quests close with a hidden phase quest (11010 .. 11050);
each phase quest ends together with one main quest, named by its scene (appdata/quest/qu01/qu0110n0/resident.scn.21:
the processor before NotifyEndQuest waits for a CheckScenario of that main quest).

A condition leaf [quest, result] holds once the save's QuestContext ResultNo of that quest equals result (-1 = not
ended); {"and": [...]} and {"or": [...]} combine them. gamedata/quest_tree.json, per quest with a title:
  "opens": condition or None (no prerequisite in the tree)
  "ends":  [[quest, result, shown], ...], any one closes it; shown = the quest the player sees end (the main quest for
           a phase quest, the titled quest for an untitled helper such as 20391 next to 20390)
  "o":     story order (prerequisite depth), for listing cutoffs in the order they come
plus "phases": [[phase quest, main quest it ends with], ...] in story order.
"""
import ree_rsz

TREES = ("natives/stm/appsystem/quest/userdata/questtree.user.3",
         "natives/stm/appsystem/quest/userdata/questtree_contents0014.user.3")
PHASE_SCENE = "natives/stm/appdata/quest/qu01/qu{:06d}/resident.scn.21"
PHASE_IDS = range(11000, 12000)  # the hidden phase quests of the base game's tree
OPERATORS = {0: "and", 1: "or"}  # app.QuestTreeData.TransitionData.LogicalOperator, app.quest.condition.LogicalOperator
EQUAL = 0  # app.quest.condition.LogicalOperatorBool
CLOSED_STATUSES = ("Complete", "Impossible")  # app.QuestLogManager.QuestStatus: finished either way


def _combine(op, parts):
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else {OPERATORS[op]: parts}


def _element(e):
    leaves = [[p["_QuestID"], p["_ResultNo"]] for p in e["_ParamArray"]]
    return _combine(e["_Operator"], leaves + [_element(x) for x in e["_ElementArray"]])


def _opens(node):
    trans = node["_PrevTransitions"]
    if len(trans) > 1 or any(len(t["_ElementArray"]) > 1 for t in trans):  # never the case in the game's data
        raise ValueError(f"quest {node['_QuestID']}: several prerequisite lists, not understood")
    return _element(trans[0]["_ElementArray"][0]) if trans and trans[0]["_ElementArray"] else None


def _end_leaves(node):
    end = node["_EndConditionParam"]
    conds = end["_ConditionArray"]
    if any(c["_Logic"] != EQUAL or not c["$type"].endswith("CheckScenario") for c in conds):
        raise ValueError(f"quest {node['_QuestID']}: an end condition other than 'quest ended with result'")
    if len(conds) > 1 and OPERATORS[end["_Operator"]] != "or":
        raise ValueError(f"quest {node['_QuestID']}: end conditions that must all hold, not understood")
    return [[c["_QuestID"], c["_ResultNo"]] for c in conds]


def _phase_end(insts):
    """[quest, result] that a phase quest's scene waits for before it ends the phase"""
    def at(ref):
        return insts[ref[1]]

    procs = {x["ProcID"]: x for x in insts if x and x["$type"] == "app.QuestProcessor"}

    def action(p):
        return at(at(p["Process"])["QuestAction"])

    def prev(p):
        return [at(q)["_ProcID"] for e in at(p["PrevProcCondition"])["_ElementArray"] for q in at(e)["_ParamArray"]]

    def scenarios(x, seen):
        if isinstance(x, tuple) and x and x[0] == "$ref":
            if x[1] in seen or not 0 < x[1] < len(insts):
                return []
            seen.add(x[1])
            x = insts[x[1]]
        if isinstance(x, dict):
            found = [[x["_QuestID"], x["_ResultNo"]]] if x["$type"] == "app.quest.condition.CheckScenarioParam" else []
            if found and x["_Logic"] != EQUAL:
                raise ValueError("phase quest waits for a quest not to have ended, not understood")
            return found + [s for k, v in x.items() if k != "$type" for s in scenarios(v, seen)]
        if isinstance(x, list):
            return [s for v in x for s in scenarios(v, seen)]
        return []

    found, seen, todo = [], set(), [pid for p in procs.values()
                                    if action(p)["$type"] == "app.quest.action.NotifyEndQuest" for pid in prev(p)]
    while todo:
        pid = todo.pop()
        if pid in seen or pid not in procs:
            continue
        seen.add(pid)
        found += scenarios(at(procs[pid]["Process"]), set())
        todo += prev(procs[pid])
    if len(found) != 1:
        raise ValueError(f"phase quest scene: expected one quest to wait for, found {found}")
    return found[0]


def _story_order(opens):
    """quest id -> depth of its prerequisites (0 = none): an AND waits for its latest part, an OR for its earliest"""
    memo, busy = {}, set()

    def depth(cond):
        if cond is None:
            return 0
        if isinstance(cond, list):
            return quest(cond[0]) + 1
        (op, parts), = cond.items()
        return (max if op == "and" else min)(depth(p) for p in parts)

    def quest(q):
        if q not in memo:
            if q in busy:  # a loop would be a data error; count it as no prerequisite
                return 0
            busy.add(q)
            memo[q] = depth(opens.get(q))
            busy.discard(q)
        return memo[q]

    return {q: quest(q) for q in opens}


def build_tree(gf, reg, titled):
    """gamedata/quest_tree.json (see the module docstring); titled: ids of the quests that have a quest log title"""
    nodes = [n for path in TREES for n in ree_rsz.parse_user(gf.read(path), reg)[0]["NodeDataArray"]]
    phases = []
    for q in sorted(n["_QuestID"] for n in nodes if n["_QuestID"] in PHASE_IDS):
        main, result = _phase_end(ree_rsz.parse_scn_instances(gf.read(PHASE_SCENE.format(q)), reg))
        if result != 0:
            raise ValueError(f"phase quest {q} waits for result {result} of {main}, not understood")
        phases.append([q, main])
    by_phase = dict(phases)

    def shown(q, r):
        if q in by_phase and r == 0:
            return by_phase[q]
        base = q - q % 10
        return base if q not in titled and base in titled else q

    opens = {n["_QuestID"]: _opens(n) for n in nodes}
    order = _story_order(opens)
    quests = {}
    for n in nodes:
        q = n["_QuestID"]
        if q in titled:
            quests[str(q)] = {"opens": opens[q], "ends": [[e, r, shown(e, r)] for e, r in _end_leaves(n)],
                              "o": order[q]}
    return {"quests": quests, "phases": phases}


def holds(cond, results):
    """results: quest id (int) -> ResultNo from the save's quest contexts"""
    if isinstance(cond, list):
        return results.get(cond[0], -1) == cond[1]
    (op, parts), = cond.items()
    return (all if op == "and" else any)(holds(p, results) for p in parts)


def closed(tree, results, statuses):
    """quest id -> [quest, result, shown] of the end that closed it, for the quests the tree has closed while the quest
    log has them neither completed nor failed (statuses: quest id (str) -> quest log status). A quest that was already
    started may still play out its own way (Oxcart Courier's own script checks for Readvent of Calamity)."""
    out = {}
    for qid, node in tree["quests"].items():
        if statuses.get(qid) in CLOSED_STATUSES:
            continue
        hit = next((e for e in node["ends"] if holds(e[:2], results)), None)
        if hit:
            out[qid] = hit
    return out
