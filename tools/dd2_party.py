"""You and your pawns from the save: vocation ranks, skills, augments, what to learn next, pawn quest knowledge.

The characters are context records in app.ContextDBMSSaveData: app.JobContext (CurrentJob, CulmativeExp per vocation
= running total of vocation points, ConsumableExp = Discipline), app.HumanSkillContext / app.AbilityContext (per
vocation equipped skills / augments, learned skills with level, unlocked augments), app.HumanStatusContext (level),
app.PawnDataContext (name, personality, specialization), app.PawnKnowledgeContext (quest knowledge bit fields).
Names, costs and unlock ranks come from gamedata/vocations.json (dd2_gamedata.build_vocations).
"""
PLAYER_CTX, MAIN_PAWN_CTX, HIRED_CTX = "app.PlayerPersonalDataContext", "app.MainPawnDataContext", "app.SubPawnDataContext"
NOT_FOR_SALE = 99999  # skills this expensive are not bought with Discipline (the game teaches them some other way)


def rank_of(exp, steps):
    """steps: points needed for each next rank, from rank 1 on. -> (rank, points into it, points for the next rank or None)"""
    rank, base = 1, 0
    for need in steps:
        if exp < base + need:
            return rank, exp - base, need
        base += need
        rank += 1
    return rank, exp - base, None


def _members(records):
    db = records.get("app.ContextDBMSSaveData", {}).get("DBSaveData", {}).get("Records", [])
    for r in db:
        ctx = {c["$type"]: c for c in r.get("Contexts", []) if c}
        if "app.JobContext" not in ctx or "app.HumanStatusContext" not in ctx:
            continue
        who = "you" if PLAYER_CTX in ctx else "main pawn" if MAIN_PAWN_CTX in ctx else "hired pawn" if HIRED_CTX in ctx else None
        if who:
            yield who, ctx


def _skill_level(voc, sid, lv):
    s = voc["skills"].get(str(sid))
    if not s:
        return {"id": sid, "lv": lv, "n": f"Skill {sid}", "t": ""}
    level = next((x for x in s["levels"] if x["lv"] == lv), s["levels"][0])
    return {"id": sid, "lv": level["lv"], "n": level["n"], "t": level["t"]}


def _augment(voc, aid):
    a = voc["augments"].get(str(aid), {})
    return {"id": aid, "n": a.get("n", f"Augment {aid}"), "t": a.get("t", "")}


def _next(voc, job, rank, dp, learned, augments_known):
    """skills and augments of the current vocation still to learn: affordable now / short of Discipline / next rank / other"""
    out = {"now": [], "dp": [], "rank": [], "other": []}
    options = []
    for sid, s in voc["skills"].items():
        if job not in s["jobs"]:
            continue
        nxt = next((x for x in s["levels"] if x["lv"] == learned.get(int(sid), 0) + 1), None)
        if nxt:
            options.append({"kind": "skill", "id": int(sid), "lv": nxt["lv"], "n": nxt["n"], "t": nxt["t"],
                            "cost": nxt["cost"], "rank": nxt["rank"]})
    for aid, a in voc["augments"].items():
        if a["job"] == job and int(aid) not in augments_known:
            options.append({"kind": "augment", "id": int(aid), "n": a["n"], "t": a["t"], "cost": a["cost"], "rank": a["rank"]})
    for o in sorted(options, key=lambda o: (o["rank"], o["cost"], o["n"])):
        if o["cost"] >= NOT_FOR_SALE or o["rank"] >= NOT_FOR_SALE:
            out["other"].append(dict(o, cost=None, rank=None))
        elif o["rank"] <= rank:
            out["now" if o["cost"] <= dp else "dp"].append(o)
        elif o["rank"] == rank + 1:
            out["rank"].append(o)
    return out


def _knowledge(voc, k):
    known = []
    for cat in ("1", "2", "3"):
        bits = k.get(f"_QuestKnowledge0{cat}", 0) or 0
        for bit, quest in voc["knowledge"][cat].items():
            if bits >> int(bit) & 1:
                known.append(quest)
    return known


def party(records, voc):
    out = []
    for who, ctx in _members(records):
        job_ctx, status = ctx["app.JobContext"], ctx["app.HumanStatusContext"]
        job, dp = job_ctx["CurrentJob"], job_ctx["ConsumableExp"]
        exps = job_ctx["CulmativeExp"]  # index = vocation - 1
        steps = lambda j: voc["jobs"].get(str(j), {}).get("ranks", [])
        if 1 <= job <= len(exps):
            rank, into, need = rank_of(exps[job - 1], steps(job))
        else:  # no current vocation (not seen in real saves): don't read another vocation's points
            rank, into, need = 1, 0, None
        vocations = [[j, rank_of(e, steps(j))[0]] for j, e in enumerate(exps, start=1) if e or j == job]
        qualified = job_ctx["QualifiedJobBits"] | job_ctx["ChangedJobBits"]  # bit vocation-1
        used = {j for j, _ in vocations}
        skills_ctx, ab_ctx = ctx.get("app.HumanSkillContext", {}), ctx.get("app.AbilityContext", {})
        learned = {s["CustomSkillID"]: s["Level"] for s in skills_ctx.get("EnabledCustomSkills", []) if s["Level"]}
        known_aug = sorted(a["AbilityID"] for a in ab_ctx.get("EnableAbilities", []) if a["IsEnable"] and a["AbilityID"])
        equipped = (skills_ctx.get("EquipedSkills") or [])[job]["Skills"] if job < len(skills_ctx.get("EquipedSkills") or []) else []
        equipped_aug = (ab_ctx.get("EquipedAbilities") or [])[job]["Abilities"] if job < len(ab_ctx.get("EquipedAbilities") or []) else []
        m = {
            "who": who, "level": status["_Level"], "job": job, "rank": rank, "into": into, "step": need,
            "points_to_next": need - into if need else None,
            "dp": dp, "vocations": vocations,
            "unlocked": [j for j in range(1, 11) if qualified >> (j - 1) & 1 and j not in used],
            "skills": [_skill_level(voc, s, learned.get(s, 1)) for s in equipped if s],
            "augments": [_augment(voc, a) for a in equipped_aug if a],
            "augments_known": known_aug, "learned": learned,
        }
        if who == "you":
            p = ctx[PLAYER_CTX]
            m.update(name=p["Name"], nick=p["NickName"])
        else:
            p = ctx.get("app.PawnDataContext", {})
            spec = p.get("_SubSkill", 0)
            m.update(name=p.get("_Name", ""), nick=p.get("_Nickname", ""),
                     personality=voc["personalities"].get(str(p.get("_Personality"))),
                     specialization=voc["specializations"].get(str(spec)) if spec else None,
                     knows=_knowledge(voc, ctx.get("app.PawnKnowledgeContext", {})))
            if who == "hired pawn":
                m["owner"] = ctx.get("app.PawnOwnerContext", {}).get("_Name", "")
        if who != "hired pawn":  # only your own party members' Discipline can be spent
            m["next"] = _next(voc, job, rank, dp, learned, known_aug)
        out.append(m)
    order = {"you": 0, "main pawn": 1, "hired pawn": 2}
    return sorted(out, key=lambda m: order[m["who"]])
