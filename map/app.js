"use strict";

const COLORS = { chest: "#d8a93b", gear: "#9d5fd0", item: "#3fa79a", dlc: "#b03a48", other: "#c98b5a", token: "#e9eef7",
                 beetle: "#f4d43c", ducat: "#e06aa8", gather: "#8fb35a", spawn: "#8c2f3c" };
const BEETLE_ITEM = 398, BEETLE_KG = 0.15;  // the item's own text: eating one adds 0.15 kg of carry weight
const FARM = new Set(["gather", "spawn"]); // regrowing / respawning: no looted state
const SERVICE_LABEL = { smith: "Smith", dragonforge: "The Dragonforged", inn: "Inn", oxcart: "Oxcart", shop: "Shop" };
const SERVICE_BADGE = { smith: "S", dragonforge: "D", inn: "I", oxcart: "O", shop: "M" };
const LAYERS = [
  { key: "chest", label: "Chests" },
  { key: "item", label: "Items on the ground" },
  { key: "dlc", label: "Dark Arisen caches" },
  { key: "other", label: "Other containers" },
  { key: "token", label: "Seeker's Tokens" },
  { key: "beetle", label: "Golden Trove Beetles" },
  { key: "ducat", label: "Norgan Ducats" },
  { key: "quest", label: "Quests in progress" },
  { key: "start", label: "Quests not started" },
  { key: "entrance", label: "Dungeon and cave entrances" },
  { key: "rest", label: "Campsites and Riftstones" },
  { key: "service", label: "Smiths and services" },
  { key: "gather", label: "Gathering spots" },
  { key: "spawn", label: "Monster spawns" },
];
const SLOT_NAMES = { 0: "Weapons", 1: "Off-hand", 2: "Head", 3: "Body", 4: "Legs", 5: "Cloaks", 6: "Rings", 7: "Neck" };
const STATE_TEXT = {
  looted: "Looted",
  seen: "You passed this without looting it",
  undefined: "Not visited yet",
};
const POLL_MS = 4000;
const REPO_URL = "https://github.com/anasurimbor87/dd2-completionist-tracker";  // the public repository; empty hides the link in the footer

let STATIC = null;
let STATE = { loot: {}, quests: {}, version: 0 };
let F = null; // field map transform
const markers = []; // loot + token circle markers
const restMarkers = []; // campsites and Riftstones
const byItem = new Map(); // item id -> markers
const groups = {};
let questMarkers = [];
let youMarker = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ---------- map ----------
const map = L.map("map", {
  crs: L.CRS.Simple, minZoom: 1, maxZoom: 9, zoomSnap: 0.5, zoomDelta: 0.5,
  attributionControl: false, preferCanvas: true, zoomControl: false,
});
L.control.zoom({ position: "bottomright" }).addTo(map);
const renderer = L.canvas({ padding: 0.5 });

// ---------- map icons: stylized badges drawn by the page itself; dots when zoomed far out ----------
// Stylized map icons: a coloured badge with a white symbol, a dark rim and a light edge, drawn once per icon into a
// sprite (an offscreen canvas) and then stamped onto the map. Symbols are drawn in a 24-unit box.
const BADGE = {
  chest: { fill: "#b8862a", draw: chest },
  item: { fill: "#25897d", draw: bag },
  gear: { fill: "#8b3fb8", draw: chest },  // chests holding weapons, armour or rings
  dlc: { fill: "#7c1d2c", draw: chest },
  other: { fill: "#9a6438", draw: barrel },
  token: { fill: "#eef1f6", ink: "#25304a", draw: medal },
  beetle: { fill: "#f0cf3a", ink: "#3a2a08", draw: beetle },  // brighter than the chests' gold, with a dark symbol
  ducat: { fill: "#d6488f", ink: "#ffffff", draw: ducat },  // raspberry: no other badge is pink; a coin with a crown
  herb: { fill: "#5d8a2e", draw: leaf },
  ore: { fill: "#5f7d8c", draw: gem },
  remains: { fill: "#8a7a5c", draw: bone },
  spawn: { fill: "#9b2f3a", draw: claws },
  camp: { fill: "#d0702a", draw: campfire },
  rift: { fill: "#2f86a6", draw: shard },
  entrance: { fill: "#3b4256", draw: arch },
  inn: { fill: "#efe6d2", ink: "#2a2117", draw: bed },
  smith: { fill: "#efe6d2", ink: "#2a2117", draw: anvil },
  dragonforge: { fill: "#efe6d2", ink: "#9b2f3a", draw: flame },
  oxcart: { fill: "#efe6d2", ink: "#2a2117", draw: wheel },
  shop: { fill: "#efe6d2", ink: "#2a2117", draw: coins },
};
const GREY = { fill: "#8f897b", ink: "#ece6d8" };

// ---------- symbols: ink = the symbol's colour, bg = the badge's (for details cut into the symbol) ----------
function chest(c, ink, bg) {
  c.fillStyle = ink;
  c.beginPath(); c.moveTo(4, 10.5); c.quadraticCurveTo(4, 5.5, 12, 5.5); c.quadraticCurveTo(20, 5.5, 20, 10.5); c.closePath(); c.fill();
  c.fillRect(4, 11.8, 16, 7.2);
  c.fillStyle = bg; c.fillRect(10.6, 10.2, 2.8, 4.2);
}
function bag(c, ink, bg) {
  c.fillStyle = ink;
  c.beginPath(); c.moveTo(9, 4.5); c.lineTo(15, 4.5); c.lineTo(13.6, 8);
  c.bezierCurveTo(19.5, 9.5, 20, 19.5, 12, 19.5); c.bezierCurveTo(4, 19.5, 4.5, 9.5, 10.4, 8); c.closePath(); c.fill();
  c.fillStyle = bg; c.fillRect(9.4, 7.6, 5.2, 1.4);
}
function barrel(c, ink, bg) {
  c.fillStyle = ink;
  c.beginPath(); c.moveTo(7.5, 4.5); c.lineTo(16.5, 4.5); c.quadraticCurveTo(19.8, 12, 16.5, 19.5); c.lineTo(7.5, 19.5);
  c.quadraticCurveTo(4.2, 12, 7.5, 4.5); c.closePath(); c.fill();
  c.fillStyle = bg; c.fillRect(5, 8.2, 14, 1.3); c.fillRect(5, 14.5, 14, 1.3);
}
function star(c, cx, cy, ro, ri) {
  c.beginPath();
  for (let i = 0; i < 10; i++) {
    const r = i % 2 ? ri : ro, a = -Math.PI / 2 + i * Math.PI / 5;
    c[i ? "lineTo" : "moveTo"](cx + r * Math.cos(a), cy + r * Math.sin(a));
  }
  c.closePath();
}
function medal(c, ink, bg) {
  c.fillStyle = ink; c.beginPath(); c.arc(12, 12, 7.5, 0, 2 * Math.PI); c.fill();
  c.fillStyle = bg; star(c, 12, 12.4, 5, 2.1); c.fill();
}
function ducat(c, ink, bg) {
  c.fillStyle = ink; c.beginPath(); c.arc(12, 12.5, 7.5, 0, 2 * Math.PI); c.fill();  // the coin
  c.fillStyle = bg;
  c.beginPath(); c.moveTo(7.5, 15.5); c.lineTo(7.5, 9.5); c.lineTo(9.8, 12); c.lineTo(12, 8.5); c.lineTo(14.2, 12);
  c.lineTo(16.5, 9.5); c.lineTo(16.5, 15.5); c.closePath(); c.fill();  // a crown on it
}
function beetle(c, ink, bg) {
  c.strokeStyle = ink; c.lineWidth = 1.5; c.lineCap = "round";
  for (const [x0, y0, x1, y1] of [[9, 10.5, 5, 7.5], [8, 14, 4, 14], [9, 17.5, 5, 20.5]]) {  // legs, mirrored
    c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke();
    c.beginPath(); c.moveTo(24 - x0, y0); c.lineTo(24 - x1, y1); c.stroke();
  }
  c.lineWidth = 1.2;
  c.beginPath(); c.moveTo(10.8, 6); c.quadraticCurveTo(9.6, 3.6, 7.6, 3.2); c.stroke();  // feelers
  c.beginPath(); c.moveTo(13.2, 6); c.quadraticCurveTo(14.4, 3.6, 16.4, 3.2); c.stroke();
  c.fillStyle = ink;
  c.beginPath(); c.ellipse(12, 7.2, 2.7, 2.1, 0, 0, 2 * Math.PI); c.fill();  // head
  c.beginPath(); c.ellipse(12, 14.2, 5.2, 6.4, 0, 0, 2 * Math.PI); c.fill();  // shell
  c.strokeStyle = bg; c.lineWidth = 1.1;
  c.beginPath(); c.moveTo(12, 9.2); c.lineTo(12, 20); c.stroke();  // where the wing cases meet
}
function leaf(c, ink, bg) {
  c.fillStyle = ink;
  c.beginPath(); c.moveTo(5, 19); c.bezierCurveTo(4, 9, 11, 4, 19.5, 4.5); c.bezierCurveTo(20, 13, 15, 20, 5, 19); c.closePath(); c.fill();
  c.strokeStyle = bg; c.lineWidth = 1.4; c.lineCap = "round";
  c.beginPath(); c.moveTo(6.5, 17.5); c.quadraticCurveTo(12, 12, 17, 7); c.stroke();
}
function gem(c, ink, bg) {
  c.fillStyle = ink;
  c.beginPath(); c.moveTo(12, 4); c.lineTo(18.5, 9); c.lineTo(16, 19); c.lineTo(8, 19); c.lineTo(5.5, 9); c.closePath(); c.fill();
  c.strokeStyle = bg; c.lineWidth = 1.2; c.lineJoin = "round";
  c.beginPath(); c.moveTo(5.8, 9.2); c.lineTo(18.2, 9.2); c.moveTo(12, 4.5); c.lineTo(9.5, 9.2); c.lineTo(12, 18.6); c.lineTo(14.5, 9.2); c.closePath(); c.stroke();
}
function bone(c, ink) {
  c.save(); c.translate(12, 12); c.rotate(-Math.PI / 4); c.fillStyle = ink;
  c.fillRect(-6, -1.7, 12, 3.4);
  for (const x of [-6.5, 6.5]) for (const y of [-2.2, 2.2]) { c.beginPath(); c.arc(x, y, 2.6, 0, 2 * Math.PI); c.fill(); }
  c.restore();
}
function claws(c, ink) {
  c.strokeStyle = ink; c.lineWidth = 2.6; c.lineCap = "round";
  for (const dx of [-5, 0, 5]) { c.beginPath(); c.moveTo(9 + dx, 4.5); c.quadraticCurveTo(14 + dx, 11, 9.5 + dx, 19.5); c.stroke(); }
}
function campfire(c, ink, bg) {
  c.fillStyle = ink;
  c.beginPath(); c.moveTo(12, 3.5); c.bezierCurveTo(17.5, 8, 17.5, 15, 12, 16.5); c.bezierCurveTo(6.5, 15, 6.5, 9.5, 10, 7);
  c.bezierCurveTo(10, 9.5, 11.5, 10.5, 12, 10.5); c.bezierCurveTo(11.5, 8, 11.5, 5.5, 12, 3.5); c.closePath(); c.fill();
  c.lineWidth = 2.2; c.strokeStyle = ink; c.lineCap = "round";
  c.beginPath(); c.moveTo(5, 20); c.lineTo(19, 16.5); c.moveTo(5, 16.5); c.lineTo(19, 20); c.stroke();
}
function shard(c, ink, bg) {
  c.fillStyle = ink;
  c.beginPath(); c.moveTo(12, 3); c.lineTo(16.5, 8); c.lineTo(15, 20.5); c.lineTo(9, 20.5); c.lineTo(7.5, 8); c.closePath(); c.fill();
  c.strokeStyle = bg; c.lineWidth = 1.2; c.beginPath(); c.moveTo(12, 4); c.lineTo(12, 20); c.stroke();
}
function arch(c, ink, bg) {
  c.fillStyle = ink;
  c.beginPath(); c.moveTo(4.5, 20); c.lineTo(4.5, 11); c.arc(12, 11, 7.5, Math.PI, 0); c.lineTo(19.5, 20); c.closePath(); c.fill();
  c.fillStyle = bg;
  c.beginPath(); c.moveTo(8, 20); c.lineTo(8, 11.5); c.arc(12, 11.5, 4, Math.PI, 0); c.lineTo(16, 20); c.closePath(); c.fill();
}
function bed(c, ink) {
  c.fillStyle = ink;
  c.fillRect(4, 7, 2.2, 12); c.fillRect(4, 13.5, 16, 3); c.fillRect(17.8, 13.5, 2.2, 5.5);
  c.beginPath(); c.ellipse(9.2, 11.6, 2.6, 1.7, 0, 0, 2 * Math.PI); c.fill();
  c.fillRect(12, 10.6, 8, 3);
}
function anvil(c, ink) {
  c.fillStyle = ink;
  c.beginPath(); c.moveTo(3.5, 8); c.lineTo(20.5, 8); c.lineTo(20.5, 10); c.quadraticCurveTo(16, 11, 15, 13.5); c.lineTo(15, 15);
  c.lineTo(18, 18.5); c.lineTo(6, 18.5); c.lineTo(9, 15); c.lineTo(9, 13.5); c.quadraticCurveTo(7, 11, 3.5, 10.5); c.closePath(); c.fill();
}
function flame(c, ink, bg) {
  c.fillStyle = ink;
  c.beginPath(); c.moveTo(12, 3); c.bezierCurveTo(19, 8, 19, 18, 12, 20.5); c.bezierCurveTo(5, 18, 5, 11, 9.5, 7.5);
  c.bezierCurveTo(9.5, 10.5, 11, 12, 12, 12); c.bezierCurveTo(11, 9, 11, 6, 12, 3); c.closePath(); c.fill();
  c.fillStyle = bg; c.beginPath(); c.ellipse(12.4, 16.5, 2.2, 2.6, 0, 0, 2 * Math.PI); c.fill();
}
function wheel(c, ink) {
  c.strokeStyle = ink; c.lineWidth = 2; c.beginPath(); c.arc(12, 12, 7, 0, 2 * Math.PI); c.stroke();
  c.lineWidth = 1.5;
  for (let i = 0; i < 4; i++) { const a = i * Math.PI / 4; c.beginPath(); c.moveTo(12 + 7 * Math.cos(a), 12 + 7 * Math.sin(a)); c.lineTo(12 - 7 * Math.cos(a), 12 - 7 * Math.sin(a)); c.stroke(); }
  c.fillStyle = ink; c.beginPath(); c.arc(12, 12, 2, 0, 2 * Math.PI); c.fill();
}
function coins(c, ink, bg) {
  for (const [x, y] of [[9, 14], [15, 10]]) {
    c.fillStyle = ink; c.beginPath(); c.arc(x, y, 5.2, 0, 2 * Math.PI); c.fill();
    c.strokeStyle = bg; c.lineWidth = 1.1; c.beginPath(); c.arc(x, y, 3.4, 0, 2 * Math.PI); c.stroke();
  }
}

// ---------- sprites ----------
const SPRITE_PX = 64;  // drawn large once, stamped smaller: sharp on high-density screens too
function badgeSprite(name, grey = false) {
  const b = BADGE[name];
  const cv = document.createElement("canvas");
  cv.width = cv.height = SPRITE_PX;
  const c = cv.getContext("2d");
  const k = SPRITE_PX / 32;  // badge in a 32-unit box: radius 13, rim 2, light edge 1
  c.scale(k, k);
  c.beginPath(); c.arc(16, 16, 15, 0, 2 * Math.PI); c.fillStyle = "rgba(255, 250, 240, 0.9)"; c.fill();  // light edge
  c.beginPath(); c.arc(16, 16, 14, 0, 2 * Math.PI); c.fillStyle = "#1b1712"; c.fill();                 // dark rim
  const fill = grey ? GREY.fill : b.fill, ink = grey ? GREY.ink : b.ink || "#ffffff";
  c.beginPath(); c.arc(16, 16, 12.4, 0, 2 * Math.PI); c.fillStyle = fill; c.fill();
  const S = 0.92;  // the 24-unit symbol inside, as large as the badge allows
  c.save(); c.translate(16 - 12 * S, 16 - 12 * S); c.scale(S, S);
  b.draw(c, ink, fill);
  c.restore();
  return cv;
}
function starSprite() {
  const cv = document.createElement("canvas");
  cv.width = cv.height = SPRITE_PX;
  const c = cv.getContext("2d");
  c.scale(SPRITE_PX / 24, SPRITE_PX / 24);
  star(c, 12, 12.8, 10.5, 4.4); c.fillStyle = "#ffd45a"; c.fill();
  c.lineWidth = 1.8; c.strokeStyle = "#1b1712"; c.lineJoin = "round"; c.stroke();
  return cv;
}

const SPRITES = { canvas: {}, url: {}, ready: false };
const ICON_ZOOM = 4;  // below this the world is a carpet of thousands of spots: dots read better
function buildSprites() {
  try {
    for (const name of Object.keys(BADGE)) {
      SPRITES.canvas[name] = badgeSprite(name);
      SPRITES.canvas[name + "-grey"] = badgeSprite(name, true);
    }
    SPRITES.canvas.star = starSprite();
    SPRITES.ready = true;
  } catch (e) {
    console.warn("map icons could not be drawn: dots instead", e);
  }
}
function spriteUrl(key) { return SPRITES.url[key] ||= SPRITES.canvas[key].toDataURL(); }
function iconMode() { return SPRITES.ready && map.getZoom() >= ICON_ZOOM; }
function iconSize() { const z = map.getZoom(); return z >= 7 ? 32 : z >= 6 ? 28 : 24; }
const LOOT_ICON = { chest: "chest", item: "item", dlc: "dlc", other: "other", token: "token", beetle: "beetle", ducat: "ducat", spawn: "spawn" };
function iconName(entry) {
  if (entry.c === "gather") return entry.k || "herb";
  return entry.c === "chest" && hasGear(entry) ? "gear" : LOOT_ICON[entry.c] || "other";
}

// a badge in a DOM element (services, campsites, entrances, the layer list), or null without badges
function spriteHtml(name, size, cls = "") {
  if (!SPRITES.ready || !SPRITES.canvas[name]) return null;
  return `<img class="sprite ${cls}" src="${spriteUrl(name)}" width="${size}" height="${size}" alt="" draggable="false">`;
}

// spots are circle markers on one canvas (thousands of them); with a sprite in their options they are drawn as
// badges. The radius leaves room around the badge for the rings and the star, so Leaflet's hit test and redraw
// areas stay right.
const drawCircle = renderer._updateCircle;
renderer._updateCircle = function (layer) {
  const o = layer.options;
  const sprite = o.sprite && SPRITES.canvas[o.sprite];
  if (!sprite) return drawCircle.call(this, layer);
  if (!this._drawing || layer._empty()) return;
  const ctx = this._ctx, p = layer._point, s = o.badge;
  if (o.glow) {  // highlighted
    ctx.beginPath(); ctx.arc(p.x, p.y, s / 2 + 2, 0, 2 * Math.PI);
    ctx.lineWidth = 3; ctx.strokeStyle = "#fffaf0"; ctx.stroke();
  }
  ctx.globalAlpha = o.faded ? 0.85 : 1;
  ctx.drawImage(sprite, p.x - s / 2, p.y - s / 2, s, s);
  ctx.globalAlpha = 1;
  if (o.ring) {  // passed without looting
    ctx.beginPath(); ctx.arc(p.x, p.y, s / 2 + 1.5, 0, 2 * Math.PI);
    ctx.lineWidth = 2; ctx.strokeStyle = "#ffd45a"; ctx.stroke();
  }
  if (o.unique) {
    const t = s * 0.5;
    ctx.drawImage(SPRITES.canvas.star, p.x + s / 2 - t * 0.7, p.y - s / 2 - t * 0.3, t, t);
  }
};
L.tileLayer("tiles/{z}/{x}/{y}.jpg", {
  maxNativeZoom: 6, maxZoom: 9, noWrap: true, bounds: [[-256, 0], [0, 256]],
}).addTo(map);

function ll(x, z) {
  return [-(z - F.BasePosZ) * 256 / F.DispRangeZ, (x - F.BasePosX) * 256 / F.DispRangeX];
}
function world(latlng) {
  return [latlng.lng * F.DispRangeX / 256 + F.BasePosX, -latlng.lat * F.DispRangeZ / 256 + F.BasePosZ];
}

map.on("mousemove", (e) => {
  if (!F) return;
  const [x, z] = world(e.latlng);
  $("coords").textContent = `x ${x.toFixed(0)}, z ${z.toFixed(0)}`;
});
let iconKey = null;  // icons or dots, and their size: restyle the spots only when that changes
map.on("zoomend", () => {
  map.getContainer().classList.toggle("map-zoom-low", map.getZoom() < 4);
  const key = iconMode() ? iconSize() : 0;
  if (key !== iconKey && markers.length) { iconKey = key; applyFilters(); }
});

// ---------- loot markers ----------
function itemInfo(id) { return STATIC.items[id] || { n: `Item #${id}` }; }
function hasUnique(entry) { return (entry.it || []).some(([i]) => itemInfo(i).unique); }
// weapons, armour or rings inside (chests with gear get a purple badge); the contents never change, so ask once
function hasGear(entry) { return entry.gear ??= (entry.it || []).some(([i]) => itemInfo(i).gear); }
function dotColor(entry) { return (entry.c === "chest" && hasGear(entry) ? COLORS.gear : COLORS[entry.c]) || COLORS.other; }

const highlighted = new Set(); // markers matching the current item search

const NO_SPRITE = { sprite: null, badge: 0, ring: false, glow: false, unique: false, faded: false };

function styleFor(entry, m) {
  return Object.assign({}, NO_SPRITE, iconMode() ? iconStyle(entry, m) : dotStyle(entry, m));
}

function iconStyle(entry, m) {
  const st = FARM.has(entry.c) ? undefined : STATE.loot[entry.id];
  const hl = !!(m && highlighted.has(m));
  const looted = st === "looted";
  const size = iconSize() * (hl ? 1.45 : looted ? 0.7 : 1);
  return { radius: size / 2 + Math.max(3.5, size * 0.16), badge: size, sprite: iconName(entry) + (looted ? "-grey" : ""),
           faded: looted && !hl, ring: st === "seen" && !hl, glow: hl, unique: !looted && hasUnique(entry), stroke: false, fill: false };
}

function dotStyle(entry, m) {
  const st = STATE.loot[entry.id];
  if (m && highlighted.has(m)) {
    return { radius: 9, color: "#fffaf0", weight: 3, fillColor: st === "looted" ? "#a39c8c" : dotColor(entry),
             fillOpacity: 1, opacity: 1, stroke: true, fill: true };
  }
  if (entry.c === "gather") return { radius: 3.5, color: "#2f3a1c", weight: 1, fillColor: COLORS.gather, fillOpacity: 0.9, opacity: 1, stroke: true, fill: true };
  if (entry.c === "spawn") {
    return { radius: 3 + Math.min(entry.count, 12) * 0.35, color: "#f3e7cf", weight: 1, fillColor: COLORS.spawn, fillOpacity: 0.9, opacity: 1, stroke: true, fill: true };
  }
  if (st === "looted") {
    return { radius: 3, color: "#5f5a50", weight: 1, fillColor: "#a39c8c", fillOpacity: 0.55, opacity: 0.9, stroke: true, fill: true };
  }
  return {
    radius: hasUnique(entry) ? 7.5 : 5,
    color: st === "seen" ? "#ffd45a" : "#2a2117",
    weight: st === "seen" ? 2.5 : 1,
    fillColor: dotColor(entry),
    fillOpacity: 0.95,
    opacity: 1,
    stroke: true,
    fill: true,
  };
}

function itemLine(id, num) {
  const it = itemInfo(id);
  if (it.gold) return `<li>${num.toLocaleString()} gold</li>`;
  const tags = (it.unique ? '<span class="tag unique">Unique</span>' : "") + (it.dlc ? '<span class="tag dlc">DLC</span>' : "");
  let sub = "";
  if (it.gear) {
    const stat = it.slot === 0 || it.slot === 1 ? `attack ${it.atk}` : `defence ${it.def}`;
    sub = `Lv ${it.lv}, ${stat}, weight ${(it.wt / 100).toFixed(2)}`;
  }
  return `<li>${esc(it.n)}${num > 1 ? ` ×${num}` : ""}${tags}${sub ? `<span class="sub">${sub}</span>` : ""}</li>`;
}

function chanceList(pairs, max = 8) {
  return pairs.slice(0, max).map(([i, c]) => `<li>${esc(itemInfo(i).gold ? "Gold" : itemInfo(i).n)} <span class="sub" style="display:inline">${c}%</span></li>`).join("");
}

// drops of a spawn spot: its monsters' character ids (variants of one monster drop different things)
function spawnDrops(entry) {
  const kill = new Map(), parts = new Map();
  for (const ch of entry.ch || []) {
    const d = STATIC.enemy_drops[ch];
    if (!d) continue;
    for (const [i, c] of d.kill) kill.set(i, Math.max(kill.get(i) || 0, c));
    for (const [i, c] of d.parts) parts.set(i, Math.max(parts.get(i) || 0, c));
  }
  const sorted = (m) => [...m].sort((a, b) => b[1] - a[1]);
  return { kill: sorted(kill), parts: sorted(parts) };
}

function farmPopup(entry) {
  const where = `<p class="pop-coords">x ${entry.x.toFixed(0)}, z ${entry.z.toFixed(0)}</p>`;
  if (entry.c === "gather") {
    return `<p class="pop-title">${esc(entry.p || "Gathering spot")}</p><p class="pop-state">Gathering spot, regrows after a while</p>
      <p class="sub">Chance per visit</p><ul class="pop-items">${chanceList(entry.yields)}</ul>${where}`;
  }
  const drops = spawnDrops(entry);
  return `<p class="pop-title">${esc(entry.n)}${entry.count > 1 ? ` ×${entry.count}` : ""}</p>
    <p class="pop-state">${esc(entry.p || "Out in the field")}. Spawns can depend on time of day and story progress.</p>
    ${drops.kill.length ? `<p class="sub">Chance per kill</p><ul class="pop-items">${chanceList(drops.kill)}</ul>` : ""}
    ${drops.parts.length ? `<p class="sub">When a body part breaks</p><ul class="pop-items">${chanceList(drops.parts)}</ul>` : ""}${where}`;
}

function popupFor(entry) {
  if (FARM.has(entry.c)) return farmPopup(entry);
  const st = STATE.loot[entry.id];
  const title = entry.p || (entry.c === "token" ? "Seeker's Token" : "Out in the field");
  const items = entry.c === "token" ? "<li>Seeker's Token</li>" : (entry.it || []).map(([i, n]) => itemLine(i, n)).join("");
  return `<p class="pop-title">${esc(title)}</p>
    <p class="pop-state ${st ? "state-" + st : ""}">${STATE_TEXT[st]}</p>
    <ul class="pop-items">${items}</ul>
    <p class="pop-coords">x ${entry.x.toFixed(0)}, z ${entry.z.toFixed(0)}</p>`;
}

// ---------- dungeon insets ----------
const dungeonByUi = new Map();
let linkLine = null;

function insetLL(entry) {
  const [ui, idx] = entry.d;
  const f = dungeonByUi.get(ui).floors[idx];
  const [[latB, lngL], [latT, lngR]] = f.bounds;
  return [latT - (entry.z - f.z0) / (f.z1 - f.z0) * (latT - latB), lngL + (entry.x - f.x0) / (f.x1 - f.x0) * (lngR - lngL)];
}
function pos(entry) { return entry.d ? insetLL(entry) : ll(entry.x, entry.z); }

function insetCenter(d) {
  const b = L.latLngBounds(d.floors.flatMap((f) => f.bounds));
  return b.getCenter();
}

function showLink(d, from, only) {
  // a dungeon can have several entrances: one line each, or just the one that was clicked
  if (linkLine) linkLine.remove();
  const to = from || insetCenter(d);
  const ends = only ? [only] : d.entrances;
  // share the markers' renderer: a path on the default renderer adds a second canvas on top of the marker canvas,
  // and markers under it stop receiving clicks
  linkLine = L.polyline(ends.map((e) => [ll(e[0], e[1]), to]), { renderer, color: "#fffaf0", weight: 1.5, opacity: 0.9, dashArray: "4 4", interactive: false }).addTo(map);
}

function dungeonSummary(d) {
  const inside = markers.filter((m) => m.entry.d && m.entry.d[0] === d.ui && m.entry.c !== "token" && !FARM.has(m.entry.c));
  const open = inside.filter((m) => STATE.loot[m.entry.id] !== "looted").length;
  const tokens = markers.filter((m) => m.entry.d && m.entry.d[0] === d.ui && m.entry.c === "token");
  const tokOpen = tokens.filter((m) => STATE.loot[m.entry.id] !== "looted").length;
  return `${open} of ${inside.length} spots not looted` + (tokens.length ? `, ${tokOpen} of ${tokens.length} Seeker's Tokens left` : "");
}

function dungeonPopup(d, target) {
  return `<p class="pop-title">${esc(d.name)}</p><p class="pop-state">${dungeonSummary(d)}</p>
    ${d.entrance_known ? "" : '<p class="pop-coords">The game does not mark this entrance: the arch sits in the middle of the cave.</p>'}
    <button class="refresh" data-go="${target}" data-ui="${d.ui}">${target === "inset" ? "Show the dungeon map" : "Show the entrance"}</button>`;
}

function buildDungeons() {
  // frames go in their own pane under the overlay pane: Leaflet stacks canvases (z 100) above image overlays (z 1)
  map.createPane("insetFrames").style.zIndex = 350;
  const frames = L.layerGroup().addTo(map);
  for (const d of STATIC.dungeons) {
    dungeonByUi.set(d.ui, d);
    for (const f of d.floors) {
      // the floor maps are brown line work with soft alpha, made for a parchment background like the world map
      L.rectangle(f.bounds, { pane: "insetFrames", color: "#8c7445", weight: 1.5, fillColor: "#e4d6b4", fillOpacity: 1, interactive: false }).addTo(frames);
      // clicks on the image are handled by the map click handler below: the marker canvas covers the images
      L.imageOverlay(f.img, f.bounds).addTo(frames);
      L.tooltip({ permanent: true, direction: "top", className: "inset-label", interactive: false })
        .setLatLng([f.bounds[1][0], (f.bounds[0][1] + f.bounds[1][1]) / 2])
        .setContent(d.floors.length > 1 ? `${esc(d.name)} ${f.label}` : esc(d.name)).addTo(frames);
    }
    const sprite = spriteHtml("entrance", 24, "cave-sprite");
    const icon = sprite ? L.divIcon({ className: "", html: sprite, iconSize: [24, 24], iconAnchor: [12, 12] })
      : L.divIcon({ className: "", html: '<div class="cave"></div>', iconSize: [12, 12], iconAnchor: [6, 6] });
    for (const ent of d.entrances) {
      const open = () => {
        showLink(d, null, ent);
        L.popup({ maxWidth: 300 }).setLatLng(ll(ent[0], ent[1])).setContent(dungeonPopup(d, "inset")).openOn(map);
      };
      L.marker(ll(ent[0], ent[1]), { icon, title: d.name, keyboard: true, bubblingMouseEvents: false }).addTo(groups.entrance)
        .on("click", open)
        .on("keypress", (e) => { if (e.originalEvent.key === "Enter") open(); });  // Leaflet only opens bound popups on Enter
    }
  }
  const floorBounds = STATIC.dungeons.flatMap((d) => d.floors.map((f) => [d, L.latLngBounds(f.bounds)]));
  map.on("click", (e) => {
    const hit = floorBounds.find(([, b]) => b.contains(e.latlng));
    if (hit) {
      showLink(hit[0], e.latlng);
      L.popup({ maxWidth: 300 }).setLatLng(e.latlng).setContent(dungeonPopup(hit[0], "entrance")).openOn(map);
    } else if (linkLine) {
      linkLine.remove();
      linkLine = null;
    }
  });
  map.on("popupopen", (e) => {
    const b = e.popup.getElement().querySelector("[data-go]");
    if (!b) return;
    b.addEventListener("click", () => {
      const d = dungeonByUi.get(+b.dataset.ui);
      if (b.dataset.go === "inset") map.flyToBounds(L.latLngBounds(d.floors.flatMap((f) => f.bounds)).pad(0.4), { maxZoom: 6 });
      else map.flyTo(ll(d.entrance[0], d.entrance[1]), Math.max(map.getZoom(), 5));
      showLink(d);
    });
  });
}

function buildMarkers() {
  for (const l of LAYERS) groups[l.key] = L.layerGroup().addTo(map);
  buildDungeons();
  const add = (entry) => {
    const m = L.circleMarker(pos(entry), Object.assign({ renderer, bubblingMouseEvents: false }, styleFor(entry)));
    m.entry = entry;
    m.bindPopup(() => popupFor(entry), { maxWidth: 320 });
    if (entry.d) m.on("click", () => showLink(dungeonByUi.get(entry.d[0]), m.getLatLng()));
    markers.push(m);
    for (const [i] of entry.it || []) {
      if (!byItem.has(i)) byItem.set(i, []);
      byItem.get(i).push(m);
    }
  };
  STATIC.loot.forEach(add);
  STATIC.medals.forEach((t) => add(Object.assign({ c: "token", it: [] }, t)));
  STATIC.gather.forEach((g) => add(Object.assign({ c: "gather" }, g)));
  STATIC.spawns.forEach((s) => add(Object.assign({ c: "spawn" }, s)));
  for (const s of STATIC.services) {
    const sprite = spriteHtml(s.kind, 24, "svc-sprite");
    const icon = sprite ? L.divIcon({ className: "", html: sprite, iconSize: [24, 24], iconAnchor: [12, 12] })
      : L.divIcon({ className: "", html: `<div class="svc svc-${s.kind}">${SERVICE_BADGE[s.kind]}</div>`, iconSize: [16, 16], iconAnchor: [8, 8] });
    const label = s.kind === "smith" ? `Smith, ${STATIC.styles[String(s.style)]} style` : SERVICE_LABEL[s.kind];
    L.marker(ll(s.x, s.z), { icon, title: `${s.name}: ${label}`, keyboard: true, bubblingMouseEvents: false })
      .bindPopup(`<p class="pop-title">${esc(s.name)}</p><p class="pop-state">${esc(label)}${s.place ? `, ${esc(s.place)}` : ""}</p>
        <p class="pop-coords">Usual spot: x ${s.x.toFixed(0)}, z ${s.z.toFixed(0)}. NPCs on schedules can be elsewhere.</p>`, { maxWidth: 300 })
      .addTo(groups.service);
  }
  for (const r of STATIC.rest) {
    const m = L.marker(ll(r.x, r.z), { icon: restIcon(r), title: r.p ? `${r.n}, ${r.p}` : r.n, keyboard: true, bubblingMouseEvents: false })
      .bindPopup(() => restPopup(r), { maxWidth: 300 })
      .addTo(groups.rest);
    m.rest = r;
    restMarkers.push(m);
  }
}

// campsites the save has found (app.CampSaveData; numbers from the campfire under each icon, see dd2_mapdata._camp_order)
function campFound(r) { return r.i != null && (STATE.camps_found || []).includes(r.i); }
function restIcon(r) {
  const muted = r.k === "camp" && STATE.camps_found && !campFound(r);
  const sprite = spriteHtml(r.k + (muted ? "-grey" : ""), 26, "rest-sprite" + (muted ? " rest-unfound" : ""));
  if (sprite) return L.divIcon({ className: "", html: sprite, iconSize: [26, 26], iconAnchor: [13, 13] });
  return L.divIcon({ className: "", html: `<div class="rest${muted ? " rest-unfound" : ""}"><i class="rest-${r.k}"></i></div>`, iconSize: [14, 16], iconAnchor: [7, 8] });
}
function campState(r) {
  if (!STATE.camps_found) return "";
  if (r.i == null) return "Whether you've found it isn't known: the save's campsite numbering doesn't cover it.";
  if (!campFound(r)) return "You haven't found this campsite yet.";
  return STATE.camp_last === r.i ? "You've found it, and it's where you last slept." : "You've found it.";
}
function restPopup(r) {
  const what = r.k === "camp" ? `Campsite: rest here with a camping kit. ${campState(r)}` : "Riftstone: hire and dismiss pawns here.";
  return `<p class="pop-title">${esc(r.n)}</p><p class="pop-state">${esc(r.p || "Out in the field")}</p><p>${what}</p>
    <p class="pop-coords">x ${r.x.toFixed(0)}, z ${r.z.toFixed(0)}</p>`;
}
function restyleCamps() {
  for (const m of restMarkers) if (m.rest.k === "camp") m.setIcon(restIcon(m.rest));
}

function farmMarkers(kind, test) {
  return markers.filter((m) => m.entry.c === kind && test(m.entry));
}

function applyFilters() {
  const hideLooted = $("hide-looted").checked;
  const onlyUnique = $("only-unique").checked;
  for (const m of markers) {
    const e = m.entry;
    const group = groups[e.c] || groups.other;
    const show = highlighted.has(m) ||
      (layerOn(e.c) && !(hideLooted && STATE.loot[e.id] === "looted") && !(onlyUnique && !hasUnique(e)));
    m.setStyle(styleFor(e, m));
    if (show && !group.hasLayer(m)) group.addLayer(m);
    if (!show && group.hasLayer(m)) group.removeLayer(m);
  }
  highlighted.forEach((m) => m.bringToFront());
  for (const key of ["entrance", "service", "rest"]) {
    if (layerOn(key)) map.addLayer(groups[key]); else map.removeLayer(groups[key]);
  }
  updateCounts();
}

const layerState = { gather: false, spawn: false }; // thousands of markers: off until asked for
function layerOn(key) { return layerState[key] !== false; }

const LEGEND_ICON = { chest: "chest", item: "item", dlc: "dlc", other: "other", token: "token", beetle: "beetle", ducat: "ducat", entrance: "entrance",
                      rest: "camp", service: "smith", gather: "herb", spawn: "spawn" };

function renderLayers() {
  $("layers").innerHTML = LAYERS.map((l) => `
    <li><label><input type="checkbox" data-layer="${l.key}" ${layerOn(l.key) ? "checked" : ""}>
      ${spriteHtml(LEGEND_ICON[l.key], 22, "legend-sprite") || `<span class="swatch" style="background:${{ quest: "var(--seal)", start: "#f3e7cf", entrance: "#c9a95c", service: "#f3e7cf", rest: "var(--camp)" }[l.key] || COLORS[l.key]}"></span>`}
      <span>${l.label} <span class="counts" id="count-${l.key}"></span></span></label></li>`).join("");
  $("layers").querySelectorAll("input").forEach((cb) => cb.addEventListener("change", () => {
    layerState[cb.dataset.layer] = cb.checked;
    applyFilters();
    renderQuestMarkers();
  }));
}

function updateCounts() {
  const tally = {};
  for (const m of markers) {
    const t = (tally[m.entry.c] ||= { looted: 0, seen: 0, total: 0 });
    t.total++;
    const st = STATE.loot[m.entry.id];
    if (st) t[st]++;
  }
  for (const [k, t] of Object.entries(tally)) {
    const el = $("count-" + k);
    if (!el) continue;
    el.innerHTML = FARM.has(k) ? `${t.total} spots` : `<b>${t.looted}</b> of ${t.total} looted${t.seen ? `, ${t.seen} passed` : ""}`;
  }
  const gear = markers.filter((m) => m.entry.c === "chest" && hasGear(m.entry));
  if ($("count-chest") && gear.length) {
    const open = gear.filter((m) => STATE.loot[m.entry.id] !== "looted").length;
    $("count-chest").insertAdjacentHTML("beforeend", `<span class="count-gear">${spriteHtml("gear", 13, "inline-sprite") || ""}${gear.length} hold gear, ${open} not looted</span>`);
  }
  const bt = tally.beetle;
  if ($("count-beetle") && bt) {  // beetles you carry (or keep in storage) still wait to be eaten
    const held = (STATE.inventory || {})[BEETLE_ITEM] || {};
    const uneaten = (held.you || 0) + (held["main pawn"] || 0) + (held.storage || 0);
    $("count-beetle").innerHTML = `<b>${bt.looted}</b> of ${bt.total} taken${bt.seen ? `, ${bt.seen} passed` : ""}`
      + (uneaten ? `<span class="count-note">${uneaten} not eaten yet: +${+(uneaten * BEETLE_KG).toFixed(2)} kg carry weight</span>` : "");
  }
  const du = tally.ducat;
  if ($("count-ducat") && du) $("count-ducat").innerHTML = `<b>${du.looted}</b> of ${du.total} taken${du.seen ? `, ${du.seen} passed` : ""}`;
  if ($("count-service")) $("count-service").textContent = `${STATIC.services.length} places`;
  const camps = STATIC.rest.filter((r) => r.k === "camp").length;
  const found = STATIC.rest.filter((r) => r.k === "camp" && campFound(r)).length;
  if ($("count-rest")) $("count-rest").innerHTML = `${camps} campsites${STATE.camps_found ? ` (<b>${found}</b> found)` : ""}, ${STATIC.rest.length - camps} Riftstones`;
  const inProgress = Object.keys(STATE.quests).filter(questActive).length;
  if ($("count-quest")) $("count-quest").innerHTML = `<b>${inProgress}</b>`;
  const notStarted = Object.entries(STATIC.quests).filter(([id, q]) => q.t && !STATE.quests[id] && !questClosed(id)).length;
  if ($("count-start")) $("count-start").textContent = `${notStarted} quests`;
  if ($("count-entrance")) $("count-entrance").textContent = `${STATIC.dungeons.length} dungeons and caves`;
}

// ---------- quests ----------
function questKind(id) {
  const n = Math.floor(id / 10000);
  return { 1: "Main quests", 2: "Side quests", 3: "World quests", 4: "Dark Arisen main", 5: "Dark Arisen side" }[n] || "Other";
}

// app.QuestLogManager.QuestStatus: Wait, Progressing, Complete, Impossible (failed or no longer possible)
const ACTIVE = new Set(["Progressing", "Wait"]);
function questActive(id) { const s = STATE.quests[id]; return !!s && ACTIVE.has(s.status); }

function questTask(id) {
  // an active quest: its current step only (an earlier step's spot would send you to the wrong place);
  // not started: the first step with a known position
  const q = STATIC.quests[id];
  const s = STATE.quests[id];
  if (!q) return null;
  if (s && ACTIVE.has(s.status)) return q.tasks[s.task] && q.tasks[s.task].d.length ? q.tasks[s.task] : null;
  return q.tasks.find((x) => x.d.length) || null;
}
function timedNow(id) { const q = STATIC.quests[id], s = STATE.quests[id]; return !!(q && s && ACTIVE.has(s.status) && q.tasks[s.task]?.timed); }

function questDestinations(id) {
  // several destinations of one task often share a spot: merge them and keep their hint texts
  const t = questTask(id);
  const spots = new Map();
  for (const [x, z, text] of t ? t.d : []) {
    const key = `${Math.round(x / 5)},${Math.round(z / 5)}`;
    const s = spots.get(key) || spots.set(key, [x, z, new Set()]).get(key);
    if (text) s[2].add(text);
  }
  return [...spots.values()].map(([x, z, texts]) => [x, z, [...texts].join(", ")]);
}

function renderQuestMarkers() {
  questMarkers.forEach((m) => m.remove());
  questMarkers = [];
  const t = STATIC.phases?.length ? storyTimeline() : null;
  const closesIn = t ? missablePhase(t) : {};
  for (const [id, q] of Object.entries(STATIC.quests)) {
    const s = STATE.quests[id];
    const progressing = questActive(id);
    const notStarted = !s && !questClosed(id);
    if (!q.t) continue;  // untitled entries are hidden story steps
    if ((progressing && !layerOn("quest")) || (notStarted && !layerOn("start")) || (!progressing && !notStarted)) continue;
    for (const [x, z, text] of questDestinations(id)) {
      const size = progressing ? 22 : 14;
      const icon = L.divIcon({
        className: "", iconSize: [size, size], iconAnchor: [size / 2, size / 2],
        html: `<div class="seal ${progressing ? "" : "start"}${notStarted && t && closesIn[id] === t.current ? " missable" : ""}">${timedNow(id) ? "⌛" : ""}</div>`,
      });
      const m = L.marker(ll(x, z), { icon, keyboard: true, title: q.t }).addTo(map);
      const task = questTask(id);
      const note = questNote(id);
      m.bindPopup(`<p class="pop-title">${esc(q.t)}</p>
        <p class="pop-state">${progressing ? "In progress" : "Not started yet, first objective"}${timedNow(id) ? ". Timed: this step can run out" : !progressing && q.timed ? ". Has a timed step" : ""}</p>
        ${task && task.t ? `<p>${esc(task.t)}</p>` : ""}
        ${text ? `<p class="pop-state">${esc(text)}</p>` : ""}
        ${note ? `<p class="pop-state">${note}</p>` : ""}
        <p class="pop-coords">x ${x.toFixed(0)}, z ${z.toFixed(0)}</p>`, { maxWidth: 320 });
      m.questId = id;
      questMarkers.push(m);
    }
  }
}

function renderQuestList() {
  // with the timeline's filter on: only quests a later story step can still close
  const entries = Object.entries(STATIC.quests)
    .filter(([id, q]) => q.t && (!missableOnly || (unfinished(id) && pendingCutoffs(id).length > 0)));
  const sections = [
    ["In progress", entries.filter(([id]) => questActive(id))],
    ["Not started yet", entries.filter(([id]) => !STATE.quests[id] && !questClosed(id))],
    ["Completed", entries.filter(([id]) => STATE.quests[id]?.status === "Complete")],
    ["Failed or no longer possible", entries.filter(([id]) => STATE.quests[id]?.status === "Impossible" || (!STATE.quests[id] && questClosed(id)))],
  ];
  const knowers = questKnowers();
  let html = "";
  for (const [title, list] of sections) {
    if (!list.length) continue;
    html += `<p class="group">${title} (${list.length})</p>`;
    const byKind = {};
    for (const e of list) (byKind[questKind(+e[0])] ||= []).push(e);
    for (const [kind, qs] of Object.entries(byKind)) {
      if (title !== "In progress") html += `<p class="sub" style="margin:.4rem 0 .1rem;color:var(--vellum-dim)">${kind}</p>`;
      for (const [id, q] of qs) {
        const located = questDestinations(id).length > 0;
        html += `<button class="entry" data-quest="${id}" ${located ? "" : 'aria-disabled="true"'}>${esc(q.t)}
          <span class="sub">${q.timed ? '<span class="timed">Timed quest. </span>' : ""}${(title === "In progress" || title === "Not started yet") && knowers[id]
            ? `<span class="knows">${esc(nameList(knowers[id]))} ${knowers[id].length === 1 ? "knows" : "know"} this quest. </span>` : ""}${questNote(id)}${located ? "" : questActive(id) ? "No map position known for the current step" : "No map position known"}</span></button>`;
      }
    }
  }
  $("pane-quests").innerHTML = timelineCard() + (html || `<p>${missableOnly ? "No quest you can still miss." : "No quests found in this save."}</p>`);
  $("pane-quests").querySelectorAll("[data-quest]").forEach((b) => b.addEventListener("click", () => goToQuest(b.dataset.quest)));
  $("tl-spoilers")?.addEventListener("change", (ev) => {
    try { localStorage.setItem(SPOILER_KEY, ev.target.checked ? "1" : "0"); } catch (e) { /* private window: not remembered */ }
    renderQuestList();
  });
  $("q-missable")?.addEventListener("change", (ev) => { missableOnly = ev.target.checked; renderQuestList(); });
}

function goToQuest(id) {
  const d = questDestinations(id);
  if (!d.length) return;
  flyTo(d.map(([x, z]) => ll(x, z)));
  const m = questMarkers.find((qm) => qm.questId === id);
  if (m) m.openPopup();
}

// timed quests in progress: what to do and since when (the save log knows the day a quest first showed up)
function renderTimed() {
  const rows = [];
  for (const [id, s] of Object.entries(STATE.quests)) {
    const q = STATIC.quests[id];
    if (!q || !timedNow(id)) continue;  // only while the timed step is the current one
    const task = q.tasks[s.task];
    const day = (STATE.quest_days || {})[id];
    const since = day == null ? "Started before your save log began." : `In your log since day ${day}, today is day ${STATE.day}.`;
    rows.push(`<li><button class="link" data-timed="${id}">${esc(q.t)}</button>${task && task.t ? `: ${esc(task.t)}` : ""}
      <span class="sub">${since}</span></li>`);
  }
  $("timed").hidden = !rows.length;
  $("timed").innerHTML = rows.length ? `<p class="timed-head">⌛ ${rows.length === 1 ? "A timed quest is running" : `${rows.length} timed quests are running`}</p>
    <ul>${rows.join("")}</ul>
    <p class="sub">Waiting too long can fail these quests or change how they end. Sleeping at an inn or a camp moves time forward too.</p>` : "";
  $("timed").querySelectorAll("[data-timed]").forEach((b) => b.addEventListener("click", () => goToQuest(b.dataset.timed)));
}

// ---------- story phases and cutoffs (dd2_phases): when quests open, and the quests whose end closes them ----------
function questResult(q) { const r = (STATE.results || {})[q]; return r == null ? -1 : r; }
function condHolds(c) {
  if (Array.isArray(c)) return questResult(c[0]) === c[1];
  const [op, parts] = Object.entries(c)[0];
  return op === "and" ? parts.every(condHolds) : parts.some(condHolds);
}
function questOpen(id) { const o = STATIC.quests[id]?.opens; return !o || condHolds(o); }
function questClosed(id) { return !!(STATE.closed || {})[id]; }
function storyOrder(q) { return STATIC.quests[q]?.o ?? 99; }
function storyName(q) { return STATIC.quests[q]?.t || "a later story step"; }
function isPhase(q) { return (STATIC.phases || []).some(([p]) => p === q); }
function orList(names) { return names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} or ${names[names.length - 1]}`; }
// closed by finishing that quest (a phase quest ends with its main quest), not by one of its other outcomes
function byFinishing([q, r, shown]) { return r === 0 && (shown === q || isPhase(q)); }

// the ends of a quest that haven't happened yet, one per quest you see end, in story order
function pendingCutoffs(id) {
  const by = new Map();
  for (const e of STATIC.quests[id]?.ends || []) {
    const [q, r, shown] = e;
    if (questResult(q) === r || shown === +id) continue;  // happened already, or one of the quest's own outcomes
    by.set(shown, { q: shown, finish: byFinishing(e) && (by.get(shown)?.finish ?? true) });
  }
  return [...by.values()].sort((a, b) => storyOrder(a.q) - storyOrder(b.q));
}
function cutoffPhrase(events) {
  const finish = events.filter((e) => e.finish).map((e) => esc(storyName(e.q)));
  const ends = events.filter((e) => !e.finish).map((e) => esc(storyName(e.q)));
  return [finish.length && `you finish ${orList(finish)}`, ends.length && `${orList(ends)} ${ends.length === 1 ? "ends" : "end"}`]
    .filter(Boolean).join(", or when ");
}
// what a quest still waits for: "Monster Culling and An Unsettling Encounter" (finished parts of an AND are left out)
function opensPhrase(c) {
  if (Array.isArray(c)) return esc(storyName(c[0]));
  const [op, parts] = Object.entries(c)[0];
  const names = (op === "and" ? parts.filter((p) => !condHolds(p)) : parts)
    .map((p) => (Array.isArray(p) ? opensPhrase(p) : `(${opensPhrase(p)})`));
  return op === "and" ? nameList(names) : orList(names);
}

// index into STATIC.phases of the phase you're in (phases.length once the story is over); null without the data
function currentPhase() {
  if (!STATIC.phases?.length || !STATE.results || !Object.keys(STATE.results).length) return null;
  const i = STATIC.phases.findIndex(([p]) => questResult(p) < 0);
  return i < 0 ? STATIC.phases.length : i;
}
function phaseMain() { const i = currentPhase(); return i == null || i >= STATIC.phases.length ? null : STATIC.phases[i][1]; }
// near: its quest is running, or it comes no later in the story than the end of the phase you're in
function cutoffNear(q) { const main = phaseMain(); return questActive(q) || (main != null && storyOrder(q) <= storyOrder(main)); }

// [[quest whose end closes others, [unfinished quests it closes]], ...] in story order
function upcomingCutoffs() {
  const by = new Map();
  for (const [id, q] of Object.entries(STATIC.quests)) {
    if (!q.t || !unfinished(id)) continue;
    for (const e of pendingCutoffs(id)) (by.get(e.q) || by.set(e.q, []).get(e.q)).push(id);
  }
  return [...by.entries()].sort((a, b) => storyOrder(a[0]) - storyOrder(b[0]) || a[0] - b[0]);
}

function questLink(id, attr = "data-quest") {
  const t = esc(STATIC.quests[id].t);
  return questDestinations(id).length ? `<button class="link" ${attr}="${id}">${t}</button>` : t;
}

// one line for a quest in the list and in its map popup: when it opens, what closes it
function questNote(id) {
  const s = STATE.quests[id];
  if (s && !ACTIVE.has(s.status)) return "";  // completed or failed
  const closedBy = (STATE.closed || {})[id];
  if (closedBy) {
    const name = esc(storyName(closedBy[2])), own = closedBy[2] === +id, finished = byFinishing(closedBy);
    if (s) return `<span class="cutoff near">${own ? "The story has moved past it" : finished ? `${name} is finished` : `${name} has ended`}: this quest may play out differently. </span>`;
    return `<span class="cutoff">${own ? "No longer possible" : finished ? `Closed when you finished ${name}` : `Closed when ${name} ended`}. </span>`;
  }
  let out = "";
  if (!s && !questOpen(id)) out += `<span class="opens">Opens when you finish ${opensPhrase(STATIC.quests[id].opens)}. </span>`;
  const pending = pendingCutoffs(id);
  if (pending.length) {
    out += `<span class="cutoff${cutoffNear(pending[0].q) ? " near" : ""}">${s ? "May change or end" : "Lost"} when ${cutoffPhrase(pending)}. </span>`;
  }
  return out;
}

// top of the Quests tab: the story's points of no return and the quests that close at each (map/timeline.js)
const SPOILER_KEY = "dd2.showLaterPhases";
function laterPhasesShown() { try { return localStorage.getItem(SPOILER_KEY) === "1"; } catch (e) { return false; } }
function storyTimeline() {
  const statuses = Object.fromEntries(Object.entries(STATE.quests || {}).map(([id, s]) => [id, s.status]));
  return phaseTimeline(STATIC.quests, STATIC.phases || [], STATE.results || {}, statuses, STATE.closed || {});
}
// the phase each quest closes in, for the map's missable rings and the list filter
function missablePhase(t) {
  const at = {};
  t.phases.forEach((p) => p.quests.forEach((q) => { at[q.id] = p.index; }));
  return at;
}
const TL_STATE = {
  done: ["✓", "done"], active: ["●", "in progress: finish it before this point"], open: ["○", "can start now"],
  later: ["○", ""], missed: ["✕", "missed"],
};
function timelineRow(q) {
  const [mark, label] = TL_STATE[q.status];
  const text = q.status === "later" ? `opens when you finish ${opensPhrase(STATIC.quests[q.id].opens)}` : label;
  return `<li class="tl-${q.status}"><span class="tl-mark" aria-hidden="true">${mark}</span>${questLink(q.id)} <span class="sub">${text}</span></li>`;
}
function timelineCard() {
  if (!STATIC.phases?.length) return "";
  const t = storyTimeline();
  const cur = t.current == null ? 0 : t.current;
  const showLater = laterPhasesShown();
  let html = `<div class="timeline"><p class="phase-head">Story timeline</p>
    <p class="sub">${t.current == null ? "Your save doesn't say how far the story is yet." : cur >= t.phases.length
      ? "The story is complete: nothing closes any more." : `You are in phase ${cur + 1} of ${t.phases.length}.`}
      Each phase ends at a point of no return: finishing that story quest closes the quests listed under it.</p>
    <ol class="tl-phases">`;
  for (const p of t.phases) {
    const past = p.index < cur, now = p.index === cur, hide = p.index > cur && !showLater;
    const count = (st) => p.quests.filter((q) => st.includes(q.status)).length;
    const open = count(["open", "later", "active"]), done = count(["done"]), missed = count(["missed"]);
    const tally = [open && `${open} still open`, done && `${done} done`, missed && `${missed} missed`].filter(Boolean).join(", ") || "nothing closes here";
    const end = hide ? "a later story quest" : esc(storyName(p.main));
    html += `<li class="tl-phase${now ? " now" : past ? " past" : ""}"><details${now ? " open" : ""}>
      <summary><b>Phase ${p.index + 1}</b>${now ? ' <span class="tl-here">you are here</span>' : ""}
        <span class="tl-end">Point of no return: finishing ${end}</span><span class="tl-tally">${tally}</span></summary>
      ${hide ? `<p class="sub">${p.quests.length} ${p.quests.length === 1 ? "quest closes" : "quests close"} here. Turn on "Show later phases" to see them.</p>`
        : p.quests.length ? `<ul class="tl-quests">${p.quests.map(timelineRow).join("")}</ul>` : ""}
    </details></li>`;
  }
  html += `</ol>
    <details class="tl-always"><summary>Never closes (${t.always.length})</summary><ul class="tl-quests">${t.always.map(timelineRow).join("")}</ul></details>
    <label class="check"><input type="checkbox" id="tl-spoilers"${showLater ? " checked" : ""}> Show later phases (story spoilers)</label>
    <label class="check"><input type="checkbox" id="q-missable"${missableOnly ? " checked" : ""}> In the list below, only quests that can still be missed</label></div>`;
  return html;
}
let missableOnly = false;

// a banner while you're on a quest whose end closes quests you haven't finished
function renderCutoffs() {
  let count = 0;
  const rows = upcomingCutoffs().filter(([q]) => questActive(q)).map(([q, ids]) => {
    count += ids.length;
    const fresh = ids.filter((id) => !STATE.quests[id]), started = ids.filter((id) => STATE.quests[id]);
    const names = (list) => list.map((id) => questLink(id, "data-cutoff")).join(", ");
    const parts = [fresh.length && `closes ${fresh.length === 1 ? "a quest" : `${fresh.length} quests`} you haven't started: ${names(fresh)}`,
      started.length && `may change ${names(started)}, which you started`].filter(Boolean);
    return `<li>Finishing <b>${esc(storyName(q))}</b> ${parts.join("; it ")}.</li>`;
  });
  $("cutoff").hidden = !rows.length;
  $("cutoff").innerHTML = rows.length ? `<p class="timed-head">⚠ ${rows.length === 1 ? "The quest you're on closes others" : "Quests you're on close others"}</p>
    <ul>${rows.join("")}</ul>
    <p class="sub">${count === 1 ? "Finish it first if you want it" : "Finish them first if you want them"}: the game won't offer quests you haven't started again in this playthrough.</p>` : "";
  $("cutoff").querySelectorAll("[data-cutoff]").forEach((b) => b.addEventListener("click", () => goToQuest(b.dataset.cutoff)));
}

// ---------- achievements (dd2_achievements: Steam's schema and stats, progress counts from the save) ----------
const ACH_KEY = "dd2.showHiddenAchievements";
function hiddenAchievementsShown() { try { return localStorage.getItem(ACH_KEY) === "1"; } catch (e) { return false; } }
// where an achievement is worked on: a map layer (with a Nearby filter for Seeker's Tokens) or the Party tab
const ACH_LINKS = {
  28: { layer: "token", near: "token", label: "Show Seeker's Tokens" },
  46: { layer: "entrance", label: "Show dungeon entrances" },
  14: { layer: "rest", label: "Show campsites" },
};
for (const id of [9, 10, 11, 12, 13, 23, 24, 25]) ACH_LINKS[id] = { tab: "tab-party", label: "Open the Party tab" };

function achievementRow(a, showHidden) {
  const secret = a.hidden && !a.unlocked && !showHidden;
  const name = secret ? "Hidden achievement" : esc(a.n);
  const text = secret ? "A story achievement: its name stays hidden until you unlock it." : esc(a.d);
  const bar = a.goal ? `<span class="ach-bar"><progress max="${a.goal}" value="${a.unlocked ? a.goal : Math.min(a.count, a.goal)}"></progress>
    ${a.unlocked ? a.goal : a.count} / ${a.goal}${a.unlocked ? "" : " in this save"}</span>` : "";
  const when = a.unlocked && a.at ? `<span class="sub">Unlocked ${new Date(a.at * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</span>` : "";
  const link = !secret && !a.unlocked && ACH_LINKS[a.id] ? `<button class="link" data-ach="${a.id}">${ACH_LINKS[a.id].label}</button>` : "";
  return `<li class="ach${a.unlocked ? " ach-done" : ""}"><span class="ach-name">${a.unlocked ? '<span aria-hidden="true">✓ </span>' : ""}${name}</span>
    <span class="sub">${text}</span>${bar}${when}${link}</li>`;
}

function renderAchievements() {
  const list = STATE.achievements || [];
  if (!list.length) {
    $("pane-ach").innerHTML = '<p class="sub">No achievement data yet: the tracker reads it from your newest save and from Steam.</p>';
    return;
  }
  const showHidden = hiddenAchievementsShown();
  const unlocked = list.filter((a) => a.unlocked).sort((a, b) => (b.at || 0) - (a.at || 0));
  const counting = list.filter((a) => !a.unlocked && a.goal).sort((a, b) => b.count / b.goal - a.count / a.goal);
  const rest = list.filter((a) => !a.unlocked && !a.goal);
  const fromSave = STATE.achievements_from !== "steam";
  const section = (title, rows) => rows.length ? `<p class="group">${title} (${rows.length})</p><ul class="ach-list">${rows.map((a) => achievementRow(a, showHidden)).join("")}</ul>` : "";
  $("pane-ach").innerHTML = `<p class="phase-head">${fromSave ? `${unlocked.length} unlocked in this save` : `${unlocked.length} of ${list.length} unlocked`}</p>
    <p class="sub">${fromSave ? "Unlocks as recorded in this save (Steam's achievement files were not found)." : "Unlocks for your Steam account; counts from your newest save."}</p>
    <label class="check"><input type="checkbox" id="ach-hidden"${showHidden ? " checked" : ""}> Show hidden achievements (story spoilers)</label>
    ${section("Counting up", counting)}${section("Not unlocked yet", rest)}${section("Unlocked", unlocked)}`;
  $("ach-hidden").addEventListener("change", (ev) => {
    try { localStorage.setItem(ACH_KEY, ev.target.checked ? "1" : "0"); } catch (e) { /* private window: not remembered */ }
    renderAchievements();
  });
  $("pane-ach").querySelectorAll("[data-ach]").forEach((b) => b.addEventListener("click", () => {
    const go = ACH_LINKS[+b.dataset.ach];
    if (go.tab) { $(go.tab).click(); return; }
    if (!layerOn(go.layer)) { layerState[go.layer] = true; renderLayers(); applyFilters(); }
    if (go.near) {
      const radio = document.querySelector(`input[name="near"][value="${go.near}"]`);
      if (radio) { radio.checked = true; renderNearby(); }
      $("tab-near").click();
    }
    showMap();
  }));
}

// ---------- unique gear ----------
function renderGear() {
  const openOnly = $("gear-open").checked;
  const rows = [];
  for (const [id, ms] of byItem) {
    const it = itemInfo(id);
    if (!it.unique) continue;
    for (const m of ms) {
      const st = STATE.loot[m.entry.id];
      if (openOnly && st === "looted") continue;
      rows.push({ it, m, st });
    }
  }
  const bySlot = {};
  for (const r of rows) (bySlot[r.it.slot] ||= []).push(r);
  let html = "";
  for (const slot of Object.keys(bySlot).sort((a, b) => a - b)) {
    const list = bySlot[slot].sort((a, b) => (b.it.atk + b.it.def) - (a.it.atk + a.it.def));
    html += `<p class="group">${SLOT_NAMES[slot] || "Other"}</p>`;
    for (const { it, m, st } of list) {
      const stat = it.slot === 0 || it.slot === 1 ? `attack ${it.atk}` : `defence ${it.def}`;
      html += `<button class="entry" data-marker="${markers.indexOf(m)}">${esc(it.n)}${it.dlc ? '<span class="tag dlc">DLC</span>' : ""}
        <span class="sub">Lv ${it.lv}, ${stat}. ${esc(m.entry.p || "Out in the field")}.
        <span class="${st ? "state-" + st : ""}">${STATE_TEXT[st]}</span></span></button>`;
    }
  }
  $("gear-list").innerHTML = html || "<p>Nothing left to find with these filters.</p>";
  $("gear-list").querySelectorAll("[data-marker]").forEach((b) => b.addEventListener("click", () => focusMarker(markers[+b.dataset.marker])));
}

// ---------- materials ----------
function have(itemId) {
  const b = (STATE.inventory || {})[String(itemId)] || {};
  return { bag: b.you || 0, storage: b.storage || 0, pawn: b["main pawn"] || 0 };
}

function renderMaterials() {
  const q = $("mat-find").value.trim().toLowerCase();
  const rows = (STATIC.materials || []).map((id) => ({ id, it: itemInfo(id), h: have(id) }))
    .filter((r) => !q || r.it.n.toLowerCase().includes(q))
    .sort((a, b) => a.it.n.localeCompare(b.it.n));
  const counts = (h) => [h.bag && `carried ${h.bag}`, h.storage && `stored ${h.storage}`, h.pawn && `pawn ${h.pawn}`]
    .filter(Boolean).join(", ") || "none";
  $("mat-list").innerHTML = rows.map((r) => `<button class="entry mat" data-mat="${r.id}">${esc(r.it.n)}
    <span class="sub">${counts(r.h)}</span></button>`).join("") || "<p>No material matches.</p>";
  $("mat-list").querySelectorAll("[data-mat]").forEach((b) => b.addEventListener("click", () => showMaterial(+b.dataset.mat, b)));
}

function showSpots(ms) {
  highlight(ms);
  if (ms.length === 1) focusMarker(ms[0]);
  else if (ms.length) flyTo(ms.map((m) => m.getLatLng()));
}

function showMaterial(id, anchor) {
  const it = itemInfo(id);
  const drops = (STATIC.drops[String(id)] || []).slice(0, 6);
  const spots = (byItem.get(id) || []).filter((m) => STATE.loot[m.entry.id] !== "looted");
  const gathering = farmMarkers("gather", (e) => e.yields.some(([i]) => i === id));
  const dropper = new Set(drops.flatMap((d) => d[2]));
  const spawns = farmMarkers("spawn", (e) => (e.ch || []).some((c) => dropper.has(c)));
  const dropText = ([who, best, , part, low]) => {
    const kill = best ? `${low != null && low !== best ? `${low}–${best}` : best}% per kill` : "";
    return `${esc(who)} (${[kill, part ? `${part}% when a part breaks` : ""].filter(Boolean).join(", ")})`;
  };
  let box = document.getElementById("mat-pop");
  if (!box) { box = document.createElement("div"); box.id = "mat-pop"; box.className = "mat-info"; }
  anchor.after(box);
  const button = (cls, n, what) => `<button class="refresh ${cls}">Show ${n} ${what}</button>`;
  // gathering yields are often a few percent per spot (remains piles), so show the best chance with the count
  const bestGather = Math.max(0, ...gathering.flatMap((m) => m.entry.yields.filter(([i]) => i === id).map(([, c]) => c)));
  box.innerHTML = `<p><b>${esc(it.n)}</b></p>
    ${drops.length ? `<p class="sub">Dropped by ${drops.map(dropText).join(", ")}</p>` : ""}
    ${it.sold ? '<p class="sub">Sold by some shops.</p>' : ""}
    <p class="mat-buttons">
    ${spawns.length ? button("mat-spawn", spawns.length, "spawn spots") : ""}
    ${gathering.length ? button("mat-gather", gathering.length, `${gathering.length > 1 ? "gathering spots" : "gathering spot"} (up to ${bestGather}% per visit)`) : ""}
    ${spots.length ? button("mat-show", spots.length, spots.length > 1 ? "unlooted spots" : "unlooted spot") : ""}
    </p>
    ${!spawns.length && !gathering.length && !spots.length ? '<p class="sub">No map spot gives it.</p>' : ""}`;
  for (const [cls, ms] of [["mat-show", spots], ["mat-gather", gathering], ["mat-spawn", spawns]]) {
    const btn = box.querySelector("." + cls);
    if (btn) btn.addEventListener("click", () => showSpots(ms));
  }
}

// ---------- party ----------
function jobName(j) { return (STATIC.vocations.jobs[j] || {}).n || `Vocation ${j}`; }
function skillName(id, lv) {
  const s = STATIC.vocations.skills[id];
  return s ? (s.levels.find((x) => x.lv === lv) || s.levels[0]).n : `Skill ${id}`;
}
function augmentName(id) { return (STATIC.vocations.augments[id] || {}).n || `Augment ${id}`; }
function nameList(names) { return names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`; }
function unfinished(q) { const s = STATE.quests[q]; return s ? ACTIVE.has(s.status) : !questClosed(q); }

// quest id -> names of the pawns in your party who know it
function questKnowers() {
  const out = {};
  for (const m of STATE.party || []) for (const q of m.knows || []) (out[q] ||= []).push(m.name);
  return out;
}

function nextGroup(title, items) {
  if (!items.length) return "";
  return `<p class="up-style">${title}</p><ul class="party-next">${items.map((x) => `<li title="${esc(x.t)}">${esc(x.n)}
    <span class="sub">${x.kind === "augment" ? "augment" : "skill"}${x.cost != null ? `, ${x.cost.toLocaleString()} Discipline` : ""}</span></li>`).join("")}</ul>`;
}

function memberCard(m) {
  const progress = m.step ? Math.round(100 * m.into / m.step) : 100;
  const toNext = m.points_to_next == null ? "the highest rank" : `${m.points_to_next.toLocaleString()} points to rank ${m.rank + 1}`;
  const role = m.who === "you" ? "You" : m.who === "main pawn" ? "Your main pawn" : `Hired pawn from ${esc(m.owner || "another Arisen")}`;
  const traits = [m.personality, m.specialization].filter(Boolean).map(esc).join(", ");
  const others = m.vocations.filter(([j]) => j !== m.job).map(([j, r]) => `${jobName(j)} rank ${r}`)
    .concat(m.unlocked.map((j) => `${jobName(j)} (unlocked, not used yet)`));
  let html = `<div class="party-card">
    <p class="up-head">${esc(m.name)}${m.nick && m.nick !== m.name ? ` <span class="sub">“${esc(m.nick)}”</span>` : ""}</p>
    <p class="sub">${role}, level ${m.level}${traits ? `. ${traits}` : ""}</p>
    <p class="party-voc">${esc(jobName(m.job))}, rank ${m.rank}${m.who === "hired pawn" ? "" : ` <span class="sub">${toNext}</span>`}</p>
    ${m.who === "hired pawn" ? "" : `<div class="rank-bar" role="img" aria-label="${progress}% of the way to the next rank"><span style="width:${progress}%"></span></div>`}`;
  if (m.who !== "hired pawn") html += `<p class="sub">${m.dp.toLocaleString()} Discipline to spend</p>`;
  if (m.skills.length) html += `<p class="party-gear"><span class="sub">Skills</span> ${m.skills.map((s) => `<span title="${esc(s.t)}">${esc(s.n)}</span>`).join(", ")}</p>`;
  if (m.augments.length) html += `<p class="party-gear"><span class="sub">Augments</span> ${m.augments.map((a) => `<span title="${esc(a.t)}">${esc(a.n)}</span>`).join(", ")}</p>`;
  if (others.length) html += `<p class="sub">Also: ${others.map(esc).join(", ")}</p>`;
  if (m.next) {
    const n = m.next;
    html += nextGroup("Affordable now (each on its own)", n.now) + nextGroup("Rank reached, needs more Discipline", n.dp)
      + nextGroup(`At ${esc(jobName(m.job))} rank ${m.rank + 1}`, n.rank) + nextGroup("Not bought with Discipline", n.other);
  }
  const qs = (m.knows || []).filter((q) => STATIC.quests[q]?.t && unfinished(q));
  if (qs.length) {
    html += `<p class="up-style">Knows ${qs.length === 1 ? "a quest" : `${qs.length} quests`} you haven't finished</p>
      <p class="party-knows">${qs.map((q) => `<button class="link" data-party-quest="${q}">${esc(STATIC.quests[q].t)}</button>`).join(", ")}</p>`;
  }
  return html + "</div>";
}

function renderParty() {
  const party = STATE.party || [];
  $("pane-party").innerHTML = party.length ? party.map(memberCard).join("")
    : '<p class="sub">No party data yet: run <b>dd2.py gamedata</b> once, then restart the map.</p>';
  $("pane-party").querySelectorAll("[data-party-quest]").forEach((b) => b.addEventListener("click", () => goToQuest(b.dataset.partyQuest)));
}

// ---------- nearby ----------
function compass(dx, dz) {
  // map up is world -z
  const deg = (Math.atan2(dx, -dz) * 180 / Math.PI + 360) % 360;
  return ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][Math.round(deg / 45) % 8];
}

function distText(d) { return d < 1000 ? `${Math.round(d / 10) * 10} m` : `${(d / 1000).toFixed(1)} km`; }

function renderNearRest(px, pz) {
  const closest = (k) => restMarkers.filter((m) => m.rest.k === k)
    .map((m) => ({ m, d: Math.hypot(m.rest.x - px, m.rest.z - pz) })).sort((a, b) => a.d - b.d)[0];
  const parts = [["camp", "campsite"], ["rift", "Riftstone"]].map(([k, label]) => {
    const c = closest(k);
    if (!c) return "";
    const name = k === "rift" ? ` (${esc(c.m.rest.n)})` : "";
    const found = k === "camp" && c.m.rest.i != null && STATE.camps_found ? (campFound(c.m.rest) ? ", found" : ", not found yet") : "";
    return `Closest ${label}: <button class="link" data-near-rest="${k}">${distText(c.d)} ${compass(c.m.rest.x - px, c.m.rest.z - pz)}</button>${name}${found}.`;
  });
  $("near-rest").innerHTML = parts.filter(Boolean).join(" ");
  $("near-rest").querySelectorAll("[data-near-rest]").forEach((b) => b.addEventListener("click", () => {
    const m = closest(b.dataset.nearRest).m;
    if (!layerOn("rest")) { layerState.rest = true; renderLayers(); applyFilters(); }
    showMap();
    map.flyTo(m.getLatLng(), Math.max(map.getZoom(), 6));
    openAfterFlight(m.getLatLng(), () => m.openPopup());
  }));
}

function lootSummary(entry) {
  if (entry.c === "token") return "Seeker's Token";
  const its = (entry.it || []).map(([i, n]) => ({ it: itemInfo(i), n }));
  its.sort((a, b) => (b.it.unique ? 1 : 0) - (a.it.unique ? 1 : 0));
  return its.map(({ it, n }) => (it.gold ? `${n.toLocaleString()} gold` : it.n + (n > 1 ? ` ×${n}` : ""))).join(", ");
}

// Wakestones bring the dead back; three shards make one. Where the ones still out in the world lie
const WAKESTONES = new Set([76, 77, 78]);  // Eternal Wakestone, Wakestone, Wakestone Shard
function wakestoneSummary() {
  const spots = markers.filter((m) => (m.entry.it || []).some(([i]) => WAKESTONES.has(i)));
  const open = spots.filter((m) => STATE.loot[m.entry.id] !== "looted");
  const left = {};
  for (const m of open) for (const [i, n] of m.entry.it) if (WAKESTONES.has(i)) left[i] = (left[i] || 0) + n;
  const parts = [[77, "Wakestone"], [78, "Wakestone Shard"], [76, "Eternal Wakestone"]]
    .filter(([i]) => left[i]).map(([i, name]) => `${left[i]} ${name}${left[i] > 1 ? "s" : ""}`);
  return `${spots.length - open.length} of ${spots.length} Wakestone spots looted${parts.length ? `. Still out there: ${parts.join(", ")}` : ""}.`;
}

function renderNearby() {
  const list = $("near-list");
  if (!STATE.player) {
    list.innerHTML = '<li class="sub">The save has no position yet.</li>';
    $("near-rest").innerHTML = "";
    return;
  }
  const [px, , pz] = STATE.player;
  renderNearRest(px, pz);
  $("near-wake").innerHTML = document.querySelector('input[name="near"]:checked').value === "wakestone" ? wakestoneSummary() : "";
  const mode = document.querySelector('input[name="near"]:checked').value;
  const pick = (m) => {
    const e = m.entry;
    if (mode === "chest") return e.c === "chest";
    if (mode === "unique") return hasUnique(e);
    if (mode === "token") return e.c === "token";
    if (mode === "beetle") return e.c === "beetle";
    if (mode === "ducat") return e.c === "ducat";
    if (mode === "wakestone") return (e.it || []).some(([i]) => WAKESTONES.has(i));
    return e.c !== "token";
  };
  const open = markers.filter((m) => !FARM.has(m.entry.c) && STATE.loot[m.entry.id] !== "looted");
  const dist = (m) => Math.hypot(m.entry.x - px, m.entry.z - pz);
  const near = open.filter(pick).map((m) => ({ m, d: dist(m) }))
    .sort((a, b) => a.d - b.d).slice(0, 15);
  list.innerHTML = near.map(({ m, d }, i) => `<li><button data-near="${i}">${esc(lootSummary(m.entry))}
    <span class="sub">${Math.round(d)} m ${compass(m.entry.x - px, m.entry.z - pz)}${m.entry.p ? `, ${esc(m.entry.p)}` : ""}${STATE.loot[m.entry.id] === "seen" ? ', <span class="state-seen">passed before</span>' : ""}</span></button></li>`).join("")
    || '<li class="sub">Nothing left of this kind.</li>';
  list.querySelectorAll("[data-near]").forEach((b) => b.addEventListener("click", () => {
    const m = near[+b.dataset.near].m;
    highlight([m]);
    focusMarker(m);
  }));
}
document.querySelectorAll('input[name="near"]').forEach((r) => r.addEventListener("change", renderNearby));

// ---------- save log ----------
let LOG = [];

function questName(id) { return STATIC.quests[id].t; }

function logEntryHtml(e, i) {
  const when = e.saved ? new Date(e.saved.replace(" ", "T")).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "Unknown time";
  if (e.new_run) return `<div class="log-entry"><p class="up-head">${when}</p><p class="sub">A different playthrough starts here.</p></div>`;
  if (e.reloaded) return `<div class="log-entry"><p class="up-head">${when}</p><p class="sub">An earlier save of this playthrough was loaded (back to day ${esc(e.day)}). The entries below happened in the save you left.</p></div>`;
  e = Object.assign({ looted: [], quests: [], items: {}, growth: [], closed: [], achievements: [] }, e);
  const lines = [];
  if (e.looted.length) {
    const lootMarkers = markers.filter((m) => e.looted.includes(m.entry.id));
    lines.push(`<button class="link" data-log-loot="${i}">${e.looted.length} ${e.looted.length === 1 ? "spot" : "spots"} looted</button>`
      + (lootMarkers.length < e.looted.length ? ` <span class="sub" style="display:inline">(${lootMarkers.length} on the map)</span>` : ""));
  }
  for (const [q, before, after] of e.quests.filter(([id]) => STATIC.quests[id]?.t)) { // unnamed ones are hidden story steps
    const verb = { Complete: "Completed", Impossible: "Failed" }[after] || (!before ? "Started" : after === "Wait" ? "On hold" : "Resumed");
    lines.push(`${verb}: ${esc(questName(q))}`);
  }
  for (const [ev, fresh, started] of e.closed) {  // dd2_session._closed
    const names = (ids) => ids.filter((q) => q !== ev && STATIC.quests[q]?.t).map((q) => esc(questName(q))).join(", ");
    if (fresh.includes(ev) && STATIC.quests[ev]?.t) lines.push(`No longer possible: ${esc(questName(ev))}`);
    if (names(fresh)) lines.push(`Closed by the end of ${esc(storyName(ev))}: ${names(fresh)}`);
    if (names(started)) lines.push(`${esc(storyName(ev))} is over, these may play out differently now: ${names(started)}`);
  }
  const pawnName = esc((STATE.party || []).find((m) => m.who === "main pawn")?.name || "Your pawn");
  for (const [, name] of e.achievements) lines.push(`Achievement unlocked: ${esc(name)}`);
  for (const g of e.growth || []) {
    const say = (verb, rest) => (g[0] === "you" ? verb[0].toUpperCase() + verb.slice(1) : `${pawnName} ${verb}`) + " " + rest;
    if (g[1] === "level") lines.push(say("reached", `level ${g[3]}`));
    if (g[1] === "rank") lines.push(say("reached", `${esc(jobName(g[2]))} rank ${g[4]}`));
    if (g[1] === "skill") lines.push(say("learned", esc(skillName(g[2], g[3]))));
    if (g[1] === "augment") lines.push(say("learned", `the augment ${esc(augmentName(g[2]))}`));
  }
  const gained = Object.entries(e.items).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);
  const lost = Object.entries(e.items).filter(([, n]) => n < 0).sort((a, b) => a[1] - b[1]);
  const fmt = (pairs) => pairs.slice(0, 8).map(([i, n]) => `${esc(itemInfo(+i).n)} ${n > 0 ? "+" : ""}${n}`).join(", ") + (pairs.length > 8 ? `, and ${pairs.length - 8} more` : "");
  if (gained.length) lines.push(`Gained: ${fmt(gained)}`);
  if (lost.length) lines.push(`Used or sold: ${fmt(lost)}`);
  const money = [e.gold && `${e.gold > 0 ? "+" : ""}${e.gold.toLocaleString()} gold`, e.rift && `${e.rift > 0 ? "+" : ""}${e.rift.toLocaleString()} Rift Crystals`].filter(Boolean);
  if (money.length) lines.push(money.join(", "));
  const days = e.days ? `, ${e.days} in-game ${Math.abs(e.days) === 1 ? "day" : "days"} later` : "";
  return `<div class="log-entry"><p class="up-head">${when} <span class="sub" style="display:inline">day ${e.day}${days}</span></p>
    ${lines.length ? `<ul class="log-lines">${lines.map((l) => `<li>${l}</li>`).join("")}</ul>` : '<p class="sub">Nothing changed.</p>'}</div>`;
}

function renderLog() {
  $("pane-log").innerHTML = LOG.length ? LOG.map(logEntryHtml).join("")
    : '<p class="sub">The log starts with your next save: each save adds what changed since the previous one.</p>';
  $("pane-log").querySelectorAll("[data-log-loot]").forEach((b) => b.addEventListener("click", () => {
    const ids = new Set(LOG[+b.dataset.logLoot].looted);
    showSpots(markers.filter((m) => ids.has(m.entry.id)));
  }));
}

async function loadLog() {
  try {
    LOG = await (await fetch("/api/log", { cache: "no-store" })).json();
  } catch (e) {
    LOG = [];
  }
  renderLog();
}

// ---------- phone ----------
async function renderPhone() {
  let info = { lan: false, urls: [] };
  try { info = await (await fetch("/api/info", { cache: "no-store" })).json(); } catch (e) { /* server not running */ }
  if (!info.lan || !info.urls.length) {
    $("phone-body").innerHTML = '<p class="sub">Start <b>DD2 Completionist Tracker (phone).cmd</b> instead to open this map on a phone or tablet on the same Wi-Fi.</p>';
    return;
  }
  const url = info.urls[0];
  let qr = "";
  if (window.qrcode) {
    const code = qrcode(0, "M");
    code.addData(url);
    code.make();
    qr = code.createSvgTag({ cellSize: 4, margin: 2, scalable: true });
  }
  $("phone-body").innerHTML = `<p class="sub">Scan this or open <b>${esc(url)}</b> on a device on the same Wi-Fi.</p>
    <div class="qr">${qr}</div>${info.urls.length > 1 ? `<p class="sub">Other addresses: ${info.urls.slice(1).map(esc).join(", ")}</p>` : ""}`;
}

// ---------- find ----------
function highlight(ms) {
  highlighted.clear();
  ms.forEach((m) => highlighted.add(m));
  $("hl-chip").hidden = !highlighted.size;
  $("hl-text").textContent = `Showing ${highlighted.size} ${highlighted.size === 1 ? "spot" : "spots"}`;
  applyFilters();
}
$("hl-clear").addEventListener("click", () => highlight([]));

function renderFind(typed = false) {
  const q = $("find").value.trim().toLowerCase();
  if (q.length < 2) {
    $("find-results").innerHTML = "";
    if (typed && highlighted.size) highlight([]);  // clearing the search clears its spots; a new save doesn't
    return;
  }
  const hits = [];
  for (const [id, ms] of byItem) {
    const it = itemInfo(id);
    if (!it.n.toLowerCase().includes(q)) continue;
    const open = ms.filter((m) => STATE.loot[m.entry.id] !== "looted").length;
    hits.push({ id, it, ms, open });
  }
  hits.sort((a, b) => b.open - a.open || a.it.n.localeCompare(b.it.n));
  // monsters by name, and items that can be gathered
  const monsters = [...new Set(STATIC.spawns.map((s) => s.n))].filter((n) => n.toLowerCase().includes(q));
  const gatherable = new Map();
  for (const m of markers) {
    if (m.entry.c !== "gather") continue;
    for (const [i] of m.entry.yields) {
      if (itemInfo(i).n.toLowerCase().includes(q)) (gatherable.get(i) || gatherable.set(i, []).get(i)).push(m);
    }
  }
  const results = [];
  const groupsFound = [];
  for (const h of hits.slice(0, 30)) {
    groupsFound.push(h.ms);
    results.push(`${esc(h.it.n)}<span class="sub">${h.ms.length} ${h.ms.length === 1 ? "place" : "places"}, ${h.open} not looted</span>`);
  }
  for (const [i, ms] of [...gatherable].slice(0, 10)) {
    groupsFound.push(ms);
    results.push(`${esc(itemInfo(i).n)}<span class="sub">${ms.length} gathering ${ms.length === 1 ? "spot" : "spots"}</span>`);
  }
  for (const n of monsters.slice(0, 10)) {
    const ms = farmMarkers("spawn", (e) => e.n === n);
    groupsFound.push(ms);
    const total = ms.reduce((a, m) => a + m.entry.count, 0);
    results.push(`${esc(n)}<span class="sub">monster, ${ms.length} spawn ${ms.length === 1 ? "spot" : "spots"} (${total} placed)</span>`);
  }
  $("find-results").innerHTML = results.map((r, i) => `<li><button data-found="${i}">${r}</button></li>`).join("")
    || "<li class=\"sub\">Nothing with that name lies, grows or spawns anywhere in the world.</li>";
  $("find-results").querySelectorAll("[data-found]").forEach((b) => b.addEventListener("click", () => showSpots(groupsFound[+b.dataset.found])));
}

// on a phone the journal is a sheet over the lower part of the map: fold it away before jumping to a spot
const PHONE = matchMedia("(max-width: 760px)");  // the same breakpoint as the style sheet

function showMap() {
  if (!PHONE.matches || document.body.classList.contains("panel-closed")) return;
  document.body.classList.add("panel-closed");
  $("panel-toggle").setAttribute("aria-expanded", "false");
}

function flyTo(latlngs) {
  showMap();
  if (latlngs.length === 1) map.flyTo(latlngs[0], Math.max(map.getZoom(), 6));
  else map.flyToBounds(L.latLngBounds(latlngs).pad(0.3), { maxZoom: 6 });
}
// open a popup when the flight to it ends; if the user dragged the map meanwhile, leave the map where they put it
function openAfterFlight(target, open) {
  map.once("moveend", () => {
    if (map.latLngToContainerPoint(target).distanceTo(map.getSize().divideBy(2)) < 80) open();
  });
}

function focusMarker(m) {
  const g = groups[m.entry.c] || groups.other;
  if (!g.hasLayer(m)) g.addLayer(m);
  showMap();
  map.flyTo(m.getLatLng(), Math.max(map.getZoom(), 6));
  openAfterFlight(m.getLatLng(), () => m.openPopup());
}

// ---------- live state ----------
function describeSave() {
  if (!STATE.saved) return;
  const d = new Date(STATE.saved.replace(" ", "T"));
  const when = d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const money = STATE.gold != null ? ` ${STATE.gold.toLocaleString()} gold, ${STATE.rift.toLocaleString()} Rift Crystals.` : "";
  $("save-line").textContent = `Saved ${when}, in-game day ${STATE.day}.${money}`;
}

function stampNewlyLooted(prev) {
  for (const m of markers) {
    const id = m.entry.id;
    if (STATE.loot[id] === "looted" && prev[id] !== "looted") {
      const s = L.marker(m.getLatLng(), { icon: L.divIcon({ className: "", html: '<div class="stamp"></div>', iconSize: [34, 34], iconAnchor: [17, 17] }), interactive: false }).addTo(map);
      setTimeout(() => s.remove(), 1600);
    }
  }
}

let centered = false;

// returns the names of the parts that failed to draw (each part is drawn on its own, so one bug can't blank the rest)
function applyState(next, animate) {
  const prev = STATE.loot || {};
  STATE = next;
  if (!centered && STATE.player) { map.setView(ll(STATE.player[0], STATE.player[2]), 5); centered = true; }
  const failed = [];
  for (const [name, fn] of [["save line", describeSave], ["map", applyFilters], ["quest seals", renderQuestMarkers],
    ["campsites", restyleCamps], ["quests", renderQuestList], ["timed quests", renderTimed], ["cutoffs", renderCutoffs], ["unique gear", renderGear],
    ["materials", renderMaterials], ["achievements", renderAchievements], ["party", renderParty], ["nearby", renderNearby], ["search", () => renderFind(false)],
    ["log", loadLog]]) {
    try { fn(); } catch (e) { console.error(name, e); failed.push(name); }
  }
  if (youMarker) youMarker.remove();
  if (STATE.player) {
    youMarker = L.marker(ll(STATE.player[0], STATE.player[2]), {
      icon: L.divIcon({ className: "", html: '<div class="you"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }),
      title: "Where you last saved",
    }).addTo(map).bindTooltip("Where you last saved");
  }
  if (animate) stampNewlyLooted(prev);
  return failed;
}

let polling = false;
async function poll() {
  if (polling) return;  // one request at a time: answers can't arrive out of order
  polling = true;
  try {
    let s;
    try {
      s = await (await fetch(`/api/state?since=${STATE.version || ""}`, { cache: "no-store" })).json();
    } catch (e) {
      setLive("The map server isn't running. Start DD2 Completionist Tracker again.", "error");
      return;
    }
    if (s.setup && s.setup.needed) { location.reload(); return; }  // a rebuild started: show its progress
    if (s.setup) renderUpdateBanner(s.setup);
    if (s.accounts) renderAccounts(s.accounts);
    let failed = [];
    if (!s.unchanged && s.version && s.version !== STATE.version) failed = applyState(s, STATE.version > 0);
    if (failed.length) setLive(`Part of the page couldn't be drawn (${failed.join(", ")}). Reload the page; if that doesn't help, rebuild with dd2.py map.`, "error");
    else if (s.status === "error") setLive(`Couldn't read the newest save: ${s.error || "unknown error"}. The map shows the last save it could read and tries again by itself.`, "error");
    else if (s.status === "starting") setLive("Reading your save…");
    else setLive("Watching your save. The map updates whenever the game saves.", "ok");
  } finally {
    polling = false;
  }
}
function setLive(text, cls = "") { const el = $("live-line"); el.textContent = text; el.className = "live-line " + cls; }

$("refresh").addEventListener("click", async () => {
  $("refresh").disabled = true;
  try {
    await fetch("/api/refresh", { method: "POST" }).catch(() => null);
    await poll();  // shows the result, error included
  } finally { $("refresh").disabled = false; }
});

// ---------- panel & controls ----------
$("panel-toggle").addEventListener("click", () => {
  const closed = document.body.classList.toggle("panel-closed");
  $("panel-toggle").setAttribute("aria-expanded", String(!closed));
  setTimeout(() => map.invalidateSize(), 50);
});
for (const id of ["hide-looted", "only-unique"]) $(id).addEventListener("change", applyFilters);
$("gear-open").addEventListener("change", renderGear);
$("mat-find").addEventListener("input", renderMaterials);
if (REPO_URL) $("repo-link").innerHTML = ` <a href="${esc(REPO_URL)}" target="_blank" rel="noopener">Source code</a>`;
$("find").addEventListener("input", () => renderFind(true));
const TABS = [["tab-quests", "pane-quests"], ["tab-ach", "pane-ach"], ["tab-gear", "pane-gear"], ["tab-mat", "pane-mat"], ["tab-party", "pane-party"], ["tab-near", "pane-near"], ["tab-log", "pane-log"]];
for (const [tab, pane] of TABS) {
  $(tab).addEventListener("click", () => {
    for (const [t, p] of TABS) {
      $(t).setAttribute("aria-selected", String(t === tab));
      $(p).hidden = p !== pane;
    }
  });
}

function placeLabels() {
  const seen = new Set();
  for (const p of STATIC.places) {
    if (seen.has(p.name)) continue;
    seen.add(p.name);
    L.tooltip({ permanent: true, direction: "center", className: "place-label", interactive: false })
      .setLatLng(ll(p.x + p.w / 2, p.z + p.h / 2)).setContent(esc(p.name)).addTo(map);
  }
}

// ---------- first start, game updates, Steam accounts ----------
async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  let data = {};
  try { data = await r.json(); } catch (e) { /* no JSON body */ }
  return { ok: r.ok, data };
}

function renderSetup(setup) {
  const step = setup.running ? setup.step : -1;
  const steps = setup.steps.map((name, i) => {
    const cls = i < step ? "done" : i === step ? "current" : "";
    return `<li class="${cls}"${i === step ? ' aria-current="step"' : ""}>${esc(name)}${i === step ? "…" : ""}</li>`;
  }).join("");
  let html = `<h2>Building the map from your game files</h2>
    <p class="sub">This happens once, and again after a game update. It takes a few minutes; the game can stay open.</p>
    <ol class="setup-steps">${steps}</ol>`;
  if (setup.error) {
    html += `<p class="setup-error">The build stopped: ${esc(setup.error)}</p><button class="refresh" id="setup-retry">Try again</button>`;
  }
  if (setup.game_dir_missing) {
    html += `<form id="setup-game" class="setup-game">
      <label for="game-dir">Steam didn't say where Dragon's Dogma 2 is installed. Paste the game folder (the one with DD2.exe):</label>
      <input id="game-dir" type="text" placeholder="D:\\SteamLibrary\\steamapps\\common\\Dragons Dogma 2" autocomplete="off">
      <button class="refresh" type="submit">Use this folder</button>
      <p id="game-dir-error" class="setup-error" role="alert"></p>
    </form>`;
  }
  const box = $("setup");
  // redraw only when something changed, and never under the player's typing (a redraw would eat a click or the text)
  const typing = document.activeElement && document.activeElement.id === "game-dir";
  if (typing || box.dataset.html === html) return;
  box.dataset.html = html;
  box.innerHTML = html;
  const retry = $("setup-retry");
  if (retry) retry.addEventListener("click", () => post("/api/setup/build"));
  const form = $("setup-game");
  if (form) form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const res = await post("/api/setup/game-dir", { path: $("game-dir").value });
    $("game-dir-error").textContent = res.ok ? "" : res.data.error || "That folder didn't work.";
    if (res.ok) $("game-dir").blur();  // let the setup box redraw: the build's steps show from now on
  });
}

async function runSetup(first) {
  document.body.classList.add("setup-mode");
  $("setup").hidden = false;
  $("save-line").textContent = "Setting up";
  renderSetup(first.setup);
  setInterval(async () => {
    let s;
    try { s = await (await fetch("/api/state?since=0", { cache: "no-store" })).json(); } catch (e) { return; }
    if (!s.setup || !s.setup.needed) location.reload();
    else renderSetup(s.setup);
  }, 1500);
}

function renderUpdateBanner(setup) {
  const show = setup.outdated && !setup.running;
  $("update-banner").hidden = !show;
  if (!show || $("update-banner").dataset.shown) return;
  $("update-banner").dataset.shown = "1";
  $("update-banner").innerHTML = `<p><b>The game was updated.</b> Rebuild the map data so the map matches it (a few minutes).</p>
    <button class="refresh" id="rebuild">Rebuild map data</button>`;
  $("rebuild").addEventListener("click", async () => { await post("/api/setup/build"); location.reload(); });
}

function renderAccounts(accounts) {
  const line = $("account-line");
  line.hidden = accounts.length < 2;
  if (line.hidden) return;
  const sel = $("account");
  const html = accounts.map((a) => `<option value="${a.id}"${a.current ? " selected" : ""}>${a.id} (saved ${esc(a.saved)})</option>`).join("");
  if (sel.dataset.html !== html) { sel.innerHTML = html; sel.dataset.html = html; }
}
$("account").addEventListener("change", async () => {
  await post("/api/account", { id: +$("account").value });
  setLive("Reading the other account's newest save…");
});

// small screens (a phone next to the game): start with the map full screen, the journal one tap away
if (PHONE.matches) {
  document.body.classList.add("panel-closed");
  $("panel-toggle").setAttribute("aria-expanded", "false");
}

(async function start() {
  let first = null;
  try { first = await (await fetch("/api/state", { cache: "no-store" })).json(); } catch (e) { /* the server isn't running */ }
  if (first && first.setup && first.setup.needed) { runSetup(first); return; }
  try {
    STATIC = await (await fetch("data/static.json")).json();
  } catch (e) {
    $("save-line").textContent = "The map data is missing or damaged. Restart the tracker to build it again.";
    return;
  }
  F = STATIC.field;
  buildSprites();
  map.setView(ll(520, -1000), 4);
  map.getContainer().classList.toggle("map-zoom-low", map.getZoom() < 4);
  iconKey = iconMode() ? iconSize() : 0;
  renderLayers();
  buildMarkers();
  placeLabels();
  applyFilters();
  renderQuestList();
  renderPhone();
  await poll();
  setInterval(poll, POLL_MS);
})();
