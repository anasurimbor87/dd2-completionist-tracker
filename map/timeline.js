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
//
// The result: {current: phase index or null, phases: [{index, phase, main, quests}], side: [...], always: [...]},
// each quest as {id, status: done|active|passed|open|later|missed, o, t}

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

// main story quests (Vermund's and Dark Arisen's): the story can't go on without them, so finishing one is sure to happen
function timelineIsMain(id) { const k = Math.floor(+id / 10000); return k === 1 || k === 4; }

// index of the phase whose stretch of the story holds a main quest: the first phase whose own main quest comes no
// earlier in the story (untitled steps, like the last phase's end, count as the very end)
function timelineMainPhase(quests, phases, main) {
  const order = quests[String(main)]?.o ?? 99;
  const i = phases.findIndex(([, m]) => (quests[String(m)]?.o ?? 99) >= order);
  return i < 0 ? null : i;
}

// a quest that closed or failed before you finished it can't close anything any more
function timelineGone(id, statuses, closed) {
  const s = statuses[String(id)];
  return s === "Impossible" || (!s && !!closed[String(id)]);
}

// index of the phase a quest closes in for sure: its earliest end that is a point of no return or the finishing of a
// main quest. Ends of side quests are no sure thing: you may never do them. Its own other outcomes don't close it.
function timelineSurePhase(quests, phases, id, q) {
  let best = null;
  for (const [quest, result, shown] of q.ends || []) {
    if (shown === +id) continue;
    let i = phases.findIndex(([p, main]) => p === quest || main === shown);
    if (i < 0 && result === 0 && quest === shown && Math.floor(shown / 10000) === 1) i = timelineMainPhase(quests, phases, shown);
    if (i != null && i >= 0 && (best == null || i < best)) best = i;
  }
  return best;
}

// where a quest goes in the timeline: {phase: index} under the earliest point of no return before which it can close,
// {side: true} when only side quests that never close can close it, or null when nothing closes it. A side quest that
// can close it counts while that side quest can still be done, in the phase that side quest itself closes in.
function timelinePlace(quests, phases, id, q, statuses, closed) {
  let best = timelineSurePhase(quests, phases, id, q), side = false;
  for (const [quest, , shown] of q.ends || []) {
    if (shown === +id || phases.some(([p, main]) => p === quest || main === shown) || Math.floor(shown / 10000) === 1) continue;
    if (timelineGone(shown, statuses, closed)) continue;
    const i = timelineSurePhase(quests, phases, shown, quests[String(shown)] || {});
    if (i == null) side = true;
    else if (best == null || i < best) best = i;
  }
  return best != null ? { phase: best } : side ? { side: true } : null;
}

// a main quest of a phase after the one you're in (current: index, null before the story's first result): the spoiler
// switch hides its name
function timelineLaterMain(quests, phases, current, id) {
  if (Math.floor(+id / 10000) !== 1 || quests[String(id)]?.o == null) return false;  // unknown place: not hidden
  const i = timelineMainPhase(quests, phases, id);
  return i != null && i > (current ?? 0);
}

function timelineStatus(id, q, results, statuses, closed) {
  const s = statuses[id];
  if (s === "Complete") return "done";
  if (s === "Impossible") return "missed";
  if (s) return closed[id] ? "passed" : "active";  // started, but the story moved past it: it may play out differently
  if (closed[id]) return "missed";
  return timelineHolds(results, q.opens) ? "open" : "later";
}

function phaseTimeline(quests, phases, results, statuses, closed) {
  const phaseQuests = new Set(phases.map(([p]) => String(p)));
  const out = phases.map(([phase, main], index) => ({ index, phase, main, quests: [] }));
  const side = [], always = [];
  for (const [id, q] of Object.entries(quests)) {
    if (!q.t || phaseQuests.has(id)) continue;  // hidden story steps
    const entry = { id, status: timelineStatus(id, q, results, statuses, closed), o: q.o ?? 99, t: q.t };
    const at = timelinePlace(quests, phases, id, q, statuses, closed);
    if (at?.phase != null) out[at.phase].quests.push(entry);
    else if (at?.side) side.push(entry);
    else if (!timelineIsMain(id)) always.push(entry);  // main quests can't be missed
  }
  const order = (a, b) => a.o - b.o || a.t.localeCompare(b.t);
  for (const p of out) p.quests.sort(order);
  side.sort(order);
  always.sort(order);
  let current = null;
  if (Object.keys(results).length) {
    current = phases.findIndex(([p]) => timelineResult(results, p) < 0);
    if (current < 0) current = phases.length;
  }
  return { current, phases: out, side, always };
}
