// Clicks through teach/index.html without a browser: node tests/page_harness.mjs http://127.0.0.1:PORT
//
// A small, strict stand-in for the DOM (enough for this page, and it throws on anything it
// does not know), the page's own script run against a live teach/server.py, and a click path
// through the tutor, the practice card and the exam. It fails on a script error, an unhandled
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
  check(calls.filter(c => c === "api/practice").length === 3, "and asks the server for one problem");
  for (const b of letters()) { if (b.disabled) continue; await click(b); if (b.classList.contains("right")) break; }
  check(letters().every(b => b.disabled), "the Cangur problem is locked once solved");
  check($("#feed").querySelectorAll(".msg.practice .letters button").every(b => !b.disabled), "the practice card still takes answers");
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

if (doc.querySelector("#exambtn")) await step("exam: the result, the review with the tutor and the way back", async () => {
  const pane = $("#exampane");
  check(/\d/.test(pane.querySelector(".score").textContent), "a score: " + pane.querySelector(".score").textContent);
  const rows = pane.querySelectorAll(".review li");
  check(rows.length === 3, "three questions in the review");
  check(rows.filter(r => /En blanc/.test(r.textContent)).length === 1, "one blank");
  check(timers.size === 0, "the clock is stopped");
  const ticks = calls.filter(c => c.includes("examtick")).length;
  await new Promise(r => setTimeout(r, 200));
  check(calls.filter(c => c.includes("examtick")).length === ticks, "no more clock requests after handing in");
  await click(rows[1].querySelector("button"));
  check(!$("#tutorpane").hidden && $("#exampane").hidden, "the tutor is back");
  check($("#img").src === pane.querySelectorAll(".review li")[1].getAttribute("data-img"), "with the question picked");
  check(letters().length === 5 && letters().every(b => !b.disabled), "ready to answer");
  check(!$("#exambtn").hidden && /Resultats/.test($("#exambtn").textContent), "the header leads back to the result");
  await click(letters()[0]);
  await click($("#exambtn"));
  check(pane.querySelectorAll(".review li").length === 3, "the result again");
  await click(pane.querySelector(".eagain"));
  check(pane.querySelectorAll(".paperpick button").length >= 1, "another paper can be chosen");
  await click(pane.querySelector(".eleave"));
  check(!$("#tutorpane").hidden && /Mode examen/.test($("#exambtn").textContent), "back to the tutor");
});

for (const t of timers) clearInterval(t);
console.log(`OK: ${done.length} steps: ${done.join("; ")}`);
process.exit(0);
