"use strict";
// The story timeline of the Quests tab: the story's points of no return (the ends of its five phases) and, under
// each, the quests that close there. Pure functions without the page: index.html loads this before app.js, and
// tests/unit/test_timeline.py runs it in node with made-up quests.
//
// quests:   {id: {t: title ("" for hidden steps), o: story order, opens: condition or null, ends: [[quest, result, shown], ...]}}
// phases:   [[phase quest, main quest whose end ends it], ...] in story order
// results:  {quest id: ResultNo} of the quests that ended
// statuses: {quest id: quest log status} of the quests the log has
// closed:   {quest id: [quest, result, shown]} the quests the story has closed (dd2_phases.closed)

function timelineResult(results, q) {
  const r = results[String(q)];
  return r == null ? -1 : r;
}

function timelineHolds(results, c) {
  if (c == null) return true;
  if (Array.isArray(c)) return timelineResult(results, c[0]) === c[1];
  const [op, parts] = Object.entries(c)[0];
  return op === "and" ? parts.every((p) => timelineHolds(results, p)) : parts.some((p) => timelineHolds(results, p));
}

// index of the phase a quest closes in: the earliest phase whose end is among the quest's ends; a quest closed by
// another quest's end counts in the first phase whose main quest comes no earlier in the story than that quest
function timelinePhaseOf(quests, phases, q) {
  let best = null;
  for (const [quest, , shown] of q.ends || []) {
    let i = phases.findIndex(([p, main]) => p === quest || main === shown);
    if (i < 0) {
      const order = quests[String(shown)]?.o ?? 0;
      i = phases.findIndex(([, main]) => (quests[String(main)]?.o ?? 0) >= order);
    }
    if (i >= 0 && (best == null || i < best)) best = i;
  }
  return best;
}

function timelineStatus(id, q, results, statuses, closed) {
  const s = statuses[id];
  if (s === "Complete") return "done";
  if (s === "Impossible") return "missed";
  if (s) return "active";
  if (closed[id]) return "missed";
  return timelineHolds(results, q.opens) ? "open" : "later";
}

function phaseTimeline(quests, phases, results, statuses, closed) {
  const phaseQuests = new Set(phases.map(([p]) => String(p)));
  const out = phases.map(([phase, main], index) => ({ index, phase, main, quests: [] }));
  const always = [];
  for (const [id, q] of Object.entries(quests)) {
    if (!q.t || phaseQuests.has(id)) continue;  // hidden story steps
    const entry = { id, status: timelineStatus(id, q, results, statuses, closed), o: q.o ?? 99, t: q.t };
    const i = timelinePhaseOf(quests, phases, q);
    (i == null ? always : out[i].quests).push(entry);
  }
  const order = (a, b) => a.o - b.o || a.t.localeCompare(b.t);
  for (const p of out) p.quests.sort(order);
  always.sort(order);
  let current = null;
  if (Object.keys(results).length) {
    current = phases.findIndex(([p]) => timelineResult(results, p) < 0);
    if (current < 0) current = phases.length;
  }
  return { current, phases: out, always };
}
