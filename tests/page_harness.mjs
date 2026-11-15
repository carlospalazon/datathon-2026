// Clicks through teach/index.html without a browser: node tests/page_harness.mjs http://127.0.0.1:PORT
//
// A small, strict stand-in for the DOM (enough for this page, and it throws on anything it
// does not know), the page's own script run against a live teach/server.py, and a click path
// through the tutor, the practice card, the exam and the skill map. It fails on a script error, an unhandled
// rejection, or "undefined", "NaN" or "null" on screen. It cannot see CSS, layout, images or focus.
// Run by tests/test_page.py on a made-up catalogue.

const base = process.argv[2].replace(/\/$/, "") + "/";
const VOID = new Set(["img", "input", "meta", "br", "link", "hr"]);
const FLAGS = ["hidden", "disabled", "checked"];

class Node {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.parent = null; this.attrs = {}; this.text = "";
    this.style = {}; this.value = ""; this.hidden = false; this.disabled = false; this.checked = false;
    const self = this;
    this.classList = {
      list: () => (self.className || "").split(/\s+/).filter(Boolean),
      contains: c => self.classList.list().includes(c),
      add: (...cs) => { self.className = [...new Set([...self.classList.list(), ...cs])].join(" "); },
      remove: (...cs) => { self.className = self.classList.list().filter(c => !cs.includes(c)).join(" "); },
      toggle: (c, on) => { (on === undefined ? !self.classList.contains(c) : on) ? self.classList.add(c) : self.classList.remove(c); },
    };
    this.className = "";
  }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === "class") this.className = String(v); if (k === "id") this.id = String(v); if (FLAGS.includes(k)) this[k] = true; }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; if (FLAGS.includes(k)) this[k] = false; }
  _adopt(n) { if (typeof n === "string") { const t = new Node("#text"); t.text = n; n = t; } if (n.parent) n.remove(); n.parent = this; return n; }
  append(...ns) { for (const n of ns) this.children.push(this._adopt(n)); }
  prepend(...ns) { this.children.unshift(...ns.map(n => this._adopt(n))); }
  remove() { if (this.parent) { this.parent.children = this.parent.children.filter(c => c !== this); this.parent = null; } }
  get elements() { return this.children.filter(c => c.tagName !== "#text"); }
  get firstElementChild() { return this.elements[0] || null; }
  get textContent() { return this.tagName === "#text" ? this.text : this.children.map(c => c.textContent).join(""); }
  set textContent(v) { this.children = []; this.append(String(v)); }
  get innerHTML() { return this.children.map(c => c.tagName === "#text" ? c.text : `<${c.tagName}>${c.innerHTML}</${c.tagName}>`).join(""); }
  set innerHTML(html) { this.children = []; parseInto(this, String(html)); }
  insertAdjacentHTML(where, html) { if (where !== "beforeend") throw new Error("insertAdjacentHTML " + where); parseInto(this, String(html)); }
  scrollIntoView() {}
  focus() {}
  get visible() { for (let n = this; n; n = n.parent) if (n.hidden) return false; return true; }
  *walk() { for (const c of this.elements) { yield c; yield* c.walk(); } }
  querySelectorAll(sel) { const m = compile(sel); const out = [...this.walk()].filter(n => m(n, this)); out.forEach = Array.prototype.forEach.bind(out); return out; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  click() { if (this.disabled) throw new Error(`click on a disabled <${this.tagName}> "${this.textContent.trim()}"`);
    if (!this.visible) throw new Error(`click on a hidden <${this.tagName}> "${this.textContent.trim()}"`);
    if (typeof this.onclick !== "function") throw new Error(`no click handler on <${this.tagName}> "${this.textContent.trim()}"`);
    return this.onclick({ target: this, preventDefault() {} }); }
}

function simple(part) {  // tag, #id and .class in any mix: "button", "#feed", ".msg.practice"
  if (!/^([a-z0-9]+)?([#.][\w-]+)*$/i.test(part) || !part) throw new Error("selector not supported by the harness: " + part);
  const tag = (part.match(/^[a-z0-9]+/i) || [null])[0];
  const id = (part.match(/#([\w-]+)/) || [])[1];
  const classes = [...part.matchAll(/\.([\w-]+)/g)].map(m => m[1]);
  return n => (!tag || n.tagName === tag.toLowerCase()) && (!id || n.id === id) && classes.every(c => n.classList.contains(c));
}
function compile(sel) {
  const alts = sel.split(",").map(s => s.trim().split(/\s+/).map(simple));
  return (n, root) => alts.some(chain => {
    if (!chain[chain.length - 1](n)) return false;
    let i = chain.length - 2;
    for (let a = n.parent; a && a !== root.parent && i >= 0; a = a.parent) if (chain[i](a)) i--;
    return i < 0;
  });
}
const unescape = s => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&amp;/g, "&");
function parseInto(root, html) {
  let at = root;
  const re = /<!--[\s\S]*?-->|<\/([a-z0-9]+)\s*>|<([a-z0-9]+)((?:\s+[\w-]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*\/?>|([^<]+)/gi;
  let m, last = 0;
  while ((m = re.exec(html))) {
    if (m.index !== last) throw new Error("the harness cannot parse this HTML: " + html.slice(last, last + 60));
    last = re.lastIndex;
    if (m[1]) { const tag = m[1].toLowerCase(); let n = at; while (n !== root && n.tagName !== tag) n = n.parent;
      if (n === root) throw new Error(`</${tag}> closes nothing in: ${html.slice(0, 80)}`); at = n.parent; }
    else if (m[2]) { const n = new Node(m[2].toLowerCase());
      for (const a of m[3].matchAll(/([\w-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) n.setAttribute(a[1], unescape(a[2] ?? a[3] ?? a[4] ?? ""));
      at.append(n); if (!VOID.has(n.tagName)) at = n; }
    else if (m[4]) at.append(unescape(m[4]));
  }
  if (last !== html.length) throw new Error("the harness cannot parse the end of this HTML");
  if (at !== root) throw new Error(`<${at.tagName}> is never closed in: ${html.slice(0, 80)}`);
}

// --- Load the page the way a browser would: the HTML, then its script ---
const errors = [];
process.on("unhandledRejection", e => errors.push("unhandled rejection: " + (e && e.stack || e)));
process.on("uncaughtException", e => errors.push("uncaught: " + (e && e.stack || e)));
const page = await (await fetch(base)).text();
const body = page.match(/<body>([\s\S]*)<\/body>/)[1];
const scripts = [...body.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (/<script[^>]+src=|<link[^>]+href=|@import|url\(\s*["']?https?:/.test(page)) errors.push("the page loads something from outside");
const doc = new Node("html"); doc.body = new Node("body"); doc.append(doc.body);
parseInto(doc.body, body.replace(/<script>[\s\S]*?<\/script>/g, ""));
const document = { body: doc.body, createElement: t => new Node(t), querySelector: s => doc.querySelector(s), querySelectorAll: s => doc.querySelectorAll(s) };
let inflight = 0; const calls = [];
const fakeFetch = async path => { inflight++; calls.push(path); try { const r = await fetch(new URL(path, base)); const t = await r.text(); return { ok: r.ok, status: r.status, json: async () => JSON.parse(t) }; } finally { inflight--; } };
const timers = new Set();
const fakeInterval = (fn, ms) => { const t = setInterval(fn, Math.min(ms, 30)); timers.add(t); return t; };  // page time runs fast
const fakeClear = t => { clearInterval(t); timers.delete(t); };
const fakeTimeout = (fn, ms) => setTimeout(fn, Math.min(ms, 30));
for (const s of scripts) new Function("document", "fetch", "setInterval", "clearInterval", "setTimeout", "window", s)(document, fakeFetch, fakeInterval, fakeClear, fakeTimeout, {});

async function settle() {  // until no request is in flight and what they started has run
  for (let quiet = 0; quiet < 3;) { await new Promise(r => setTimeout(r, 5)); quiet = inflight ? 0 : quiet + 1; }
  if (errors.length) throw new Error(errors.join("\n"));
  const seen = [...doc.walk()].filter(n => n.visible && n.tagName !== "pre").flatMap(n => n.children.filter(c => c.tagName === "#text").map(c => c.text)
    .concat(Object.values(n.attrs))).join(" | ");
  const bad = seen.match(/.{0,40}\b(undefined|NaN|null)\b.{0,40}/);
  if (bad) throw new Error("on screen: " + bad[0]);
}
const $ = s => { const n = doc.querySelector(s); if (!n) throw new Error("not on the page: " + s); return n; };
const check = (ok, what) => { if (!ok) throw new Error("expected: " + what); };
const click = async n => { await n.click(); await settle(); };
const done = [];
const step = async (name, fn) => { try { await fn(); done.push(name); } catch (e) { console.error(`FAILED at "${name}": ${e.message}`); console.error("  requests so far: " + calls.slice(-6).join(", ")); process.exit(1); } };
const letters = () => $("#letters").querySelectorAll("button");
const lit = () => $("#matrix").querySelectorAll("span.on").length;

await step("the page loads and shows a problem", async () => {
  await settle();
  check($("#img").src && $("#img").src.startsWith("img/"), "an image for the problem");
  check(letters().length === 5, "five letter buttons");
  check($("#matrix").elements.length === 104, "104 LEDs");
  check(lit() > 0, "the level on the matrix");
});

if (doc.querySelector("#warmpane")) await step("warm-up: three short problems in the tutor's place, a slip named, then the Cangur problem", async () => {
  const warm = $("#warmpane");
  check(!warm.hidden && $("#tutorpane").hidden, "the warm-up is offered before the first Cangur problem");
  check(!calls.includes("api/think"), "and the think-first time has not started behind it");
  check($("#mapbtn").hidden && $("#exambtn").hidden, "nothing else in the way");
  check(warm.querySelector(".wskip") && /Avui/.test(warm.textContent), "it says its topics and can be skipped");
  warm.querySelector(".wgo").click(); warm.querySelector(".wgo").click();  // a double click
  await settle();
  check(calls.filter(c => c === "api/warmupnext").length === 1, "a double click starts one problem");
  let slips = 0, figures = 0;
  for (let n = 1; n <= 3; n++) {
    check(new RegExp(`problema ${n} de 3`).test(warm.textContent), "problem " + n + " of 3: " + warm.textContent.slice(0, 60));
    check(warm.querySelector(".ptext").textContent.length > 20 && warm.querySelectorAll(".letters button").length === 5, "a problem as text with five options");
    check(warm.querySelector(".wnext").hidden, "no way on before it is solved, only the skip");
    if (/Raonament visual/.test(warm.textContent)) {  // a picture topic: the figure is drawn by the page
      const fig = warm.querySelector(".pfig svg");
      check(fig && fig.querySelectorAll("rect, path, polygon").length >= 1, "a figure drawn as SVG");
      check(/^0 0 [\d.]+ [\d.]+$/.test(fig.getAttribute("viewBox")), "with a sound size: " + fig.getAttribute("viewBox"));
      figures++;
    }
    for (const b of warm.querySelectorAll(".letters button")) {
      await click(b);
      if (b.classList.contains("right")) break;
      check(b.classList.contains("wrong") && warm.querySelector(".preply").textContent.length > 30, "a sentence about the wrong option");
      slips++;
    }
    check(warm.querySelectorAll(".letters button").every(b => b.disabled) && !warm.querySelector(".wnext").hidden, "solved: the way on appears");
    await click(warm.querySelector(".wnext"));
  }
  check(figures === 1, "one of the three was a picture problem");
  check(warm.hidden && !$("#tutorpane").hidden && !$("#mapbtn").hidden, "after the third, the Cangur problem");
  check(/Escalfament fet/.test($("#feed").firstElementChild.textContent), "with a line saying the warm-up is done");
  check(calls.filter(c => c === "api/warmupnext").length === 4 && !calls.includes("api/practice"), "three problems asked for, none through the practice card");
});

if (doc.querySelector("#think")) await step("think first: a ring in the hint button's place, skipped after typing, and over by itself", async () => {
  const ringOn = () => !$("#think").hidden && $("#help").hidden;
  check(ringOn(), "a new problem starts with the ring, not the hint button");
  check($("#thinkskip").hidden, "no way round it before an attempt");
  check(lit() > 20, "the ring on the matrix: " + lit());
  $("#chattext").value = "crec que";
  $("#chattext").oninput({ target: $("#chattext") });
  await click($("#thinkskip"));
  $("#chattext").value = "";
  check(!ringOn() && !$("#help").hidden && $("#think").hidden, "after typing something the student can have the button back");
  check(calls.includes("api/thinkskip") && lit() < 20, "and the ring leaves the matrix");
  await click($("#next"));
  check(ringOn(), "the next problem starts with the ring again");
  await new Promise(r => setTimeout(r, 1600));  // real time: the server owns the think-first seconds (1 in this test)
  await settle();
  check(!ringOn() && !$("#help").hidden, "the hint button comes back by itself");
  const asked = calls.filter(c => c === "api/think").length;
  await new Promise(r => setTimeout(r, 200));
  check(calls.filter(c => c === "api/think").length === asked && timers.size === 0, "and the page stops asking");
  await click($("#next"));
  check(ringOn(), "a third problem, the ring again");
  await click(letters()[0]);
  check(!ringOn(), "an answer ends it");
  check($("#matrix").querySelectorAll("span.on").length < 20, "and the tick or cross stays on the matrix");
  await click($("#next"));
});

if (doc.querySelector("#readbar")) await step("reading modes: one idea per line, key data, numbers only, more room; kept for the next problem", async () => {
  const picked = () => $("#readbar").querySelectorAll("button.picked").length;
  check($("#reader").hidden && picked() === 0, "the plain page to start with: the image and nothing else");
  await click($("#rm-lines"));
  check(!$("#reader").hidden && $("#reader").querySelectorAll(".rtext p").length === 3, "one idea per line: " + $("#reader").textContent);
  check($("#rm-lines").classList.contains("picked") && $("#rm-lines").getAttribute("aria-pressed") === "true", "the switch shows it is on");
  check(!$("#reader").querySelector("mark") && !$("#reader").querySelector(".numstrip"), "and nothing else yet");
  await click($("#rm-key"));
  check($("#reader").querySelectorAll("mark.kd").length === 2, "the key data marked in the statement");
  check($("#reader").querySelectorAll(".keybox li").length === 2 && /Condició clau/.test($("#reader").textContent), "the key data and the key condition under it");
  check(!/SECRET/.test($("#reader").textContent), "never the first step");
  await click($("#rm-numbers"));
  const strip = $("#reader").querySelectorAll(".numstrip span");
  check(strip.length === 3 && /12/.test(strip[0].textContent) && /boxes/.test(strip[0].textContent), "a strip with only the numbers and what they count");
  await click($("#rm-space"));
  check(doc.body.classList.contains("airy") && picked() === 4, "more room, and the four switches mix");
  await click($("#rm-lines"));
  check($("#reader").querySelectorAll(".rtext p").length === 1 && picked() === 3, "a switch turns off again");
  await click($("#next"));
  check(calls.filter(c => c === "api/reading").length >= 2 && picked() === 3 && !$("#reader").hidden, "the next problem keeps the choice");
  await click($("#rm-key")); await click($("#rm-numbers")); await click($("#rm-space"));
  check($("#reader").hidden && picked() === 0 && !doc.body.classList.contains("airy"), "all off: the plain page again");
  await click($("#rm-lines")); await click($("#rm-numbers"));
  check(calls.filter(c => c.startsWith("api/readingmode/")).length === 10, "every change is told to the server");
});

let pictureCards = 0;  // practice problems asked for by the picture step, for the count further down
if (doc.querySelector("#warmpane")) await step("picture practice: cubes, a folded strip and a staircase drawn by the page, with the slip named", async () => {
  const open = async name => {  // a problem of this topic, through the map's "what to try next"
    await click($("#mapbtn"));
    const row = $("#mappane").querySelectorAll(".nexts .msg").find(m => m.textContent.includes(name));
    check(row, `«${name}» among what to try next`);
    await click(row.querySelector("button"));
    check(!$("#tutorpane").hidden && $("#topic").textContent === name, "a problem of " + name);
  };
  const sound = (nodes, attr, re) => nodes.every(n => re.test(n.getAttribute(attr)));
  const solve = async card => {
    let named = 0;
    for (const b of card.querySelectorAll(".letters button")) {
      await click(b);
      if (b.classList.contains("right")) break;
      check(card.querySelector(".preply").textContent.length > 30, "a sentence about the wrong option");
      named++;
    }
    check(card.querySelectorAll(".letters button.right").length === 1, "the right option is found by clicking");
  };
  await open("Geometria de l'espai");
  check(!$("#practice").hidden, "a practice problem can be made for space geometry");
  await click($("#practice")); pictureCards++;
  let card = $("#feed").querySelector(".msg.practice");
  const faces = card.querySelectorAll(".pfig polygon");
  check(faces.length >= 9 && card.querySelectorAll(".pfig polygon.ftop").length >= 3, "piles of cubes drawn face by face: " + faces.length);
  check(sound(faces, "points", /^(-?\d+(\.\d)?,-?\d+(\.\d)?( |$)){4}$/), "every face with four sound corners: " + faces[0].getAttribute("points"));
  check(card.querySelector(".ptext").textContent.length > 20, "and its question as text");
  await solve(card);
  check(card.querySelectorAll(".xopt").length === 3, "and it asks how it was solved");
  await open("Raonament visual");
  await click($("#practice")); pictureCards++;
  card = $("#feed").querySelector(".msg.practice");
  const strip = card.querySelectorAll(".pfig path.strip"), cuts = card.querySelectorAll(".pfig line.cut");
  check(strip.length === 1 && /^M [\d. ]+H [\d.]+( A [\d. ]+ H [\d.]+){2,5}$/.test(strip[0].getAttribute("d")), "a strip folded in layers: " + (strip[0] && strip[0].getAttribute("d")));
  check(cuts.length >= 1 && cuts.length <= 2 && sound(cuts, "x1", /^\d+(\.\d)?$/), "and its dotted lines");
  await solve(card);
  await click(card.querySelector(".pmore")); pictureCards++;
  card = $("#feed").querySelector(".msg.practice");
  const squares = card.querySelectorAll(".pfig rect.sq");
  check(squares.length >= 5 && sound(squares, "y", /^\d+$/), "a staircase drawn square by square: " + squares.length);
  check(card.querySelectorAll(".letters button").some(b => b.textContent.replace(/^[A-E]/, "") === String(squares.length)), "whose squares can be counted on the drawing");
  await solve(card);
  await open("Càlcul amb dades");
});

await step("a wrong letter, then the practice card from the red message", async () => {
  // The page never learns the right letter; try letters until one is wrong
  let wrong = null;
  for (let tries = 0; tries < 4 && !wrong; tries++) {
    const b = letters()[0];
    await click(b);
    if (b.classList.contains("wrong")) wrong = b;
    else { check(b.classList.contains("right"), "a clicked letter turns right or wrong"); await click($("#next")); }
  }
  check(wrong && wrong.disabled, "the wrong letter is switched off");
  check($("#feed").querySelector(".msg.bad"), "a red message");
  check(!$("#practice").hidden, "the practice button for this topic");
  await click($("#feed").querySelector(".msg.bad .inline"));
  const card = $("#feed").querySelector(".msg.practice");
  check(card && card.querySelector(".ptext").textContent.length > 20, "a practice problem as text");
  if (doc.querySelector("#readbar")) check(card.querySelector(".ptext .numstrip") && card.querySelectorAll(".ptext .rtext p").length >= 2, "laid out with the reading switches that are on");
  check(card.querySelector(".psol").disabled, "no solution before a try");
  const options = card.querySelectorAll(".letters button");
  check(options.length === 5, "five options on the practice card");
  let right = 0, named = 0;
  for (const b of options) {
    if (b.disabled) continue;
    await click(b);
    if (b.classList.contains("right")) { right++; check(options.every(o => o.disabled), "options locked after the right one"); break; }
    check(b.classList.contains("wrong") && card.querySelector(".preply").textContent.length > 30, "a sentence about the wrong option");
    named++;
  }
  check(right === 1, "the right option is found by clicking");
});

await step("another practice problem, its solution on request, and back", async () => {
  await click($("#feed").querySelector(".msg.practice .pmore"));
  check($("#feed").querySelectorAll(".msg.practice").length === 1, "one practice card at a time");
  let card = $("#feed").querySelector(".msg.practice");
  // "Com es resol" opens after one try: make one, wrong or right
  const first = card.querySelectorAll(".letters button")[0];
  await click(first);
  if (first.classList.contains("wrong")) {
    await click(card.querySelector(".psol"));
    check(card.querySelectorAll(".letters button.right").length === 1, "the solution marks one option");
    check(card.querySelectorAll(".letters button").every(o => o.disabled), "options locked after the solution");
  }
  await click(card.querySelector(".pback"));
  check(!$("#feed").querySelector(".msg.practice"), "the card is gone");
  $("#practice").click(); $("#practice").click();  // a double click
  await settle();
  check($("#feed").querySelectorAll(".msg.practice").length === 1, "a double click makes one card");
  check(calls.filter(c => c === "api/practice").length === 3 + pictureCards, "and asks the server for one problem");
  for (const b of letters()) { if (b.disabled) continue; await click(b); if (b.classList.contains("right")) break; }
  check(letters().every(b => b.disabled), "the Cangur problem is locked once solved");
  check($("#feed").querySelectorAll(".msg.practice .letters button").every(b => !b.disabled), "the practice card still takes answers");
});

if (doc.querySelector("#warmpane")) await step("explain it back: after a right answer, one tap on the way it was solved; then the worked solution", async () => {
  let asked = null;
  for (let tries = 0; tries < 6 && !asked; tries++) {  // the kinds rotate: one that can be asked about comes within a few cards
    await click($("#feed").querySelector(".msg.practice .pmore"));
    const card = $("#feed").querySelector(".msg.practice");
    for (const b of card.querySelectorAll(".letters button")) { await click(b); if (b.classList.contains("right")) break; }
    if (card.querySelector(".xopt")) asked = card;
    else check(/tenen en comú/.test(card.querySelector(".preply").textContent), "where it cannot be asked, the worked solution comes at once");
  }
  check(asked, "a practice problem that asks how it was solved");
  const ways = asked.querySelectorAll(".xopt");
  check(ways.length === 3 && ways.every(w => w.textContent.length > 15 && !/\d/.test(w.textContent)), "three ways of solving, in words");
  check(!/tenen en comú/.test(asked.querySelector(".preply").textContent), "the worked solution waits for the tap");
  ways[0].click(); ways[1].click();  // a double tap
  await settle();
  check(calls.filter(c => c.startsWith("api/practiceexplain/")).length === 1, "one tap counts");
  check(ways.every(w => w.disabled) && asked.querySelectorAll(".xopt.match").length === 1, "the way that leads to the answer is marked");
  check(asked.querySelector(".xreply").textContent.length > 20, "a line about the way picked: " + asked.querySelector(".xreply").textContent);
  check(!asked.querySelector(".letters button.wrong.xopt") && /tenen en comú/.test(asked.querySelector(".preply").textContent), "and then the worked solution");
  await click($("#mapbtn"));
  check(/camí ben explicat en [01] de 1/.test($("#mappane").textContent), "the map counts it: " + ($("#mappane").textContent.match(/camí[^·<]{0,40}/) || [""])[0]);
  await click($("#mappane").querySelector(".mleave"));
});

await step("the help ladder, the solution, the chat and the next problem", async () => {
  for (let i = 0; i < 8; i++) await click($("#help"));
  check($("#feed").querySelectorAll(".msg.help").length >= 2, "help messages");
  for (const b of $("#feed").querySelectorAll(".msg.help .actions button")) if (!b.disabled && b.parent.parent) await click(b);
  await click($("#solution"));
  check(/correcta és la [A-E]/.test($("#feed").firstElementChild.textContent), "the solution names a letter");
  $("#chattext").value = "una pista";
  await $("#chat").onsubmit({ preventDefault() {} }); await settle();
  const before = $("#img").src;
  await click($("#next"));
  check($("#img").src !== before, "another problem");
  check($("#feed").elements.length === 0, "an empty feed for the new problem");
});

if (doc.querySelector("#exambtn")) await step("exam: the rules and a paper to choose", async () => {
  await click($("#exambtn"));
  check($("#tutorpane").hidden && !$("#exampane").hidden, "the exam takes the place of the tutor");
  check($("#exampane").querySelectorAll(".rules li").length >= 3, "the scoring rules");
  check($("#exampane").querySelectorAll(".levelpick button").length >= 1, "a level to pick");
  const taster = $("#exampane").querySelectorAll(".paperpick button")[0];
  await click(taster);
  check(taster.classList.contains("picked"), "the paper picked is marked");
  await click($("#exampane .estart"));
});

if (doc.querySelector("#exambtn")) await step("exam: answer, change, blank, hand in; the clock runs on the matrix", async () => {
  const pane = $("#exampane");
  const chips = pane.querySelectorAll(".chips button");
  check(chips.length === 3, "three questions in the taster");
  check(/^\d+:\d\d$/.test(pane.querySelector(".timer").textContent.trim()), "a clock: " + pane.querySelector(".timer").textContent);
  check($("#exambtn").hidden, "no way to the tutor from the header while the paper runs");
  const shot = [...$("#matrix").elements].map(s => s.classList.contains("on")).join("");
  check(lit() > 0, "the countdown on the matrix");
  let opts = pane.querySelectorAll(".letters button");
  check(opts.length === 5 && pane.querySelector(".eimg").src.startsWith("img/"), "question 1 with its image and letters");
  await click(opts[0]);
  check(pane.querySelectorAll(".letters button.picked").length === 1, "the letter is marked");
  check(!pane.querySelector(".letters button.right") && !pane.querySelector(".letters button.wrong"), "no right or wrong during the paper");
  await click(pane.querySelectorAll(".letters button")[1]);
  check(pane.querySelectorAll(".letters button.picked").length === 1, "changing the answer keeps one mark");
  check(pane.querySelectorAll(".chips button.answered").length === 1, "question 1 shows as answered");
  await click(pane.querySelector(".enext"));
  await click(pane.querySelectorAll(".letters button")[2]);
  await click(pane.querySelector(".eblank"));
  check(pane.querySelectorAll(".letters button.picked").length === 0, "blank again");
  await click(pane.querySelector(".enext"));
  await click(pane.querySelectorAll(".letters button")[4]);
  await click(pane.querySelector(".eprev"));
  await click(pane.querySelectorAll(".chips button")[0]);
  check(pane.querySelectorAll(".letters button.picked").length === 1, "question 1 remembers its letter");
  await new Promise(r => setTimeout(r, 1200));  // real time: the server's clock moves
  await settle();
  check(calls.some(c => c.includes("examtick")), "the page asks the server for the time");
  await click(pane.querySelector(".ehand"));
  check(/2 de 3/.test(pane.querySelector(".confirm").textContent), "the count of answered questions before handing in");
  await click(pane.querySelector(".confirm .no"));
  await click(pane.querySelector(".ehand"));
  await click(pane.querySelector(".confirm .yes"));
});

if (doc.querySelector("#exambtn")) await step("exam: the result, the misses as one review queue and the way back", async () => {
  const pane = $("#exampane");
  check(/\d/.test(pane.querySelector(".score").textContent), "a score: " + pane.querySelector(".score").textContent);
  const rows = pane.querySelectorAll(".review li");
  check(rows.length === 3, "three questions in the review");
  check(rows.filter(r => /En blanc/.test(r.textContent)).length === 1, "one blank");
  check(timers.size === 0, "the clock is stopped");
  const ticks = calls.filter(c => c.includes("examtick")).length;
  await new Promise(r => setTimeout(r, 200));
  check(calls.filter(c => c.includes("examtick")).length === ticks, "no more clock requests after handing in");
  check(pane.querySelectorAll(".review li button").length === 0, "no button per question");
  const missed = rows.filter(r => !r.classList.contains("right"));
  check(missed.length >= 1, "something to go over");
  check(/fallat/.test(pane.querySelector(".ereview").textContent), "one button for the whole review");
  check($("#reviewbar").hidden, "no review bar yet");
  pane.querySelector(".ereview").click(); pane.querySelector(".ereview").click();  // a double click
  await settle();
  check(calls.filter(c => c === "api/examreview").length === 1, "a double click opens one question");
  for (let i = 0; i < missed.length; i++) {
    check(!$("#tutorpane").hidden && $("#exampane").hidden, "the tutor is back");
    check($("#img").src === missed[i].getAttribute("data-img"), "with the next question missed, in paper order");
    check(letters().length === 5 && letters().every(b => !b.disabled), "ready to answer");
    check(new RegExp(`${i + 1} de ${missed.length}`).test($("#reviewbar").textContent) && !$("#reviewbar").hidden, "the bar counts the review: " + $("#reviewbar").textContent);
    check(/de l'examen/.test($("#feed").firstElementChild.textContent), "a line about what was marked");
    if (i === 0) {  // the header leads back to the result, which now offers to go on
      check(!$("#exambtn").hidden && /Resultats/.test($("#exambtn").textContent), "the header leads back to the result");
      await click($("#exambtn"));
      check(missed.length === 1 ? /totes/.test(pane.textContent) : /Continua/.test(pane.querySelector(".ereview").textContent), "the result knows how far the review got");
      await click(pane.querySelector(".eleave"));
    }
    await click(letters()[0]);
    await click($("#next"));
  }
  check(!pane.hidden && $("#reviewbar").hidden, "after the last one, back to the result");
  check(/Ja les has repassat totes/.test(pane.textContent), "which says the review is done");
  check(pane.querySelectorAll(".review li").length === 3, "the result again");
  await click(pane.querySelector(".eagain"));
  check(pane.querySelectorAll(".paperpick button").length >= 1, "another paper can be chosen");
  await click(pane.querySelector(".eleave"));
  check(!$("#tutorpane").hidden && /Mode examen/.test($("#exambtn").textContent), "back to the tutor");
});

if (doc.querySelector("#mapbtn")) await step("the skill map: what was done, what to try next, and the class", async () => {
  await click($("#mapbtn"));
  const map = $("#mappane");
  check($("#tutorpane").hidden && !map.hidden && $("#exambtn").hidden && $("#mapbtn").hidden, "the map takes the place of the tutor");
  check(map.querySelectorAll(".tile").length >= 1, "a tile per topic");
  check(map.querySelectorAll(".tile").some(t => !t.classList.contains("new")), "the tutor's answers reached the map");
  check(/a la primera/.test(map.textContent), "a count of first-time answers");
  check(/de pràctica/.test(map.textContent), "the practice card reached the map");
  check(lit() > 0, "the map on the matrix");
  check(map.querySelectorAll(".nexts button").length >= 1, "something to try next");
  await click(map.querySelector(".mclass"));
  check(map.querySelectorAll(".heat tbody tr").length === 1, "one student in the class so far");
  check(map.querySelectorAll(".heat thead th").length >= 2, "a column per topic");
  await click(map.querySelector(".mother"));
  check(map.querySelector(".csample") && map.querySelectorAll(".heat tbody tr").length > 3, "a sample class, marked as made up");
  await click(map.querySelector(".mother"));
  check(!map.querySelector(".csample") && map.querySelectorAll(".heat tbody tr").length === 1, "and back to the real class");
  await click(map.querySelector(".mback"));
  check(map.querySelectorAll(".tile").length >= 1, "back to the map");
});

if (doc.querySelector("#mapbtn")) await step("the map: a new student, back to the first one, and a problem picked from the map", async () => {
  const map = $("#mappane");
  const me = map.querySelector(".mname").textContent, mine = $("#img").src;
  map.querySelector(".seatnew").click(); map.querySelector(".seatnew").click();  // a double click
  await settle();
  check(map.querySelector(".mname").textContent !== me, "another pseudonym");
  check(map.querySelectorAll(".seats button").length === 3, "a double click seats one new student");
  check(map.querySelectorAll(".tile").every(t => t.classList.contains("new")), "an empty map for the new student");
  if (doc.querySelector("#readbar")) check($("#readbar").querySelectorAll("button.picked").length === 0, "and the plain page: the reading switches are each student's own");
  check(!map.hidden && $("#tutorpane").hidden, "still on the map");
  await click(map.querySelector(".mclass"));
  check(map.querySelectorAll(".heat tbody tr").length === 2, "two students in the class");
  check(map.querySelectorAll(".heat tr.me").length === 1, "the one at the board is marked");
  await click(map.querySelector(".mback"));
  if (doc.querySelector("#warmpane")) {  // the new student is offered a warm-up of their own, and skips it
    await click(map.querySelector(".mleave"));
    check(!$("#warmpane").hidden && $("#tutorpane").hidden, "the new student gets the warm-up offer");
    await click($("#warmpane").querySelector(".wskip"));
    check($("#warmpane").hidden && !$("#tutorpane").hidden && $("#feed").elements.length === 0, "skipped: straight to the problem, no fuss");
    await click($("#mapbtn"));
  }
  await click(map.querySelectorAll(".seats button")[0]);
  check(map.querySelector(".mname").textContent === me, "the first student is back");
  check(map.querySelectorAll(".tile").some(t => !t.classList.contains("new")), "with their map");
  check($("#img").src === mine, "and their problem");
  if (doc.querySelector("#readbar")) check($("#readbar").querySelectorAll("button.picked").length === 2, "and their reading switches");
  await click(map.querySelector(".nexts button"));
  check(map.hidden && (!$("#tutorpane").hidden || !$("#exampane").hidden), "the suggestion leaves the map");
  if (!$("#tutorpane").hidden) {
    check(!$("#mapbtn").hidden && letters().length === 5 && letters().every(b => !b.disabled), "a problem ready to answer");
    check(/mapa/.test($("#feed").firstElementChild.textContent), "and a line saying where it came from");
  }
});

if (doc.querySelector("#sessionbtn")) await step("today's session: the plan, its problems one after the other, and the end", async () => {
  const map = $("#mappane");
  check($("#sessionbar").hidden, "no session bar before a session");
  await click($("#sessionbtn"));
  check(!map.hidden && $("#tutorpane").hidden, "the plan takes the place of the tutor");
  const total = map.querySelectorAll(".plan li").length;
  check(total >= 1 && total <= 3, "a plan of up to three problems");
  map.querySelector(".sgo").click(); map.querySelector(".sgo").click();  // a double click
  await settle();
  check(calls.filter(c => c === "api/sessionnext").length === 1, "a double click starts one problem");
  check(map.hidden && !$("#tutorpane").hidden && !$("#sessionbar").hidden, "the first problem, with the session bar");
  check(new RegExp(`problema 1 de ${total}`).test($("#sessionbar").textContent), "the bar says where we are: " + $("#sessionbar").textContent);
  check(/Sessió d'avui, problema 1/.test($("#feed").firstElementChild.textContent), "and a line about the problem");
  await click($("#sessionbtn"));
  check(map.querySelectorAll(".plan li.now").length === 1 && /Continua/.test(map.querySelector(".sgo").textContent), "the plan marks the problem under way");
  await click(map.querySelector(".sgo"));
  for (let n = 2; n <= total; n++) {
    const before = $("#img").src;
    await click(letters()[0]);
    await click($("#next"));
    check($("#img").src !== before, "the session moves to another problem");
    check(new RegExp(`problema ${n} de ${total}`).test($("#sessionbar").textContent), "the bar moves on");
  }
  await click($("#next"));
  check($("#sessionbar").hidden && /acabada/.test($("#feed").firstElementChild.textContent), "the session ends with a line and no bar");
  await click($("#feed").firstElementChild.querySelector(".inline"));
  check(!map.hidden && map.querySelectorAll(".tile").length >= 1, "and leads to the map");
  await click(map.querySelector(".msession"));
  check(/Comença/.test(map.querySelector(".sgo").textContent), "a finished session makes room for a new plan");
  await click(map.querySelector(".sgo"));
  await click($("#sessionbar").querySelector(".pquit"));
  check($("#sessionbar").hidden, "the session can be left");
  const before = $("#img").src;
  await click($("#next"));
  check($("#img").src !== before && $("#sessionbar").hidden, "and the tutor picks the next problem again");
});

for (const t of timers) clearInterval(t);
console.log(`OK: ${done.length} steps: ${done.join("; ")}`);
process.exit(0);
