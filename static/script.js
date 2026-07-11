/*
  CalcParser - script.js
  Semua logika sisi klien ada di sini: pindah tab, panggil API Flask, dan
  gambar ulang visualisasi (diagram automata, pohon penurunan, tabel CYK).
  Sengaja ditulis polos pakai vanilla JS, tanpa framework, biar gampang
  ditelusuri satu per satu waktu presentasi atau demo video.
*/

const $ = (id) => document.getElementById(id);
const EPS = "ε";

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Terjadi kesalahan tak terduga.");
  return data;
}

function errorBox(el, message) {
  if (!message) { el.innerHTML = ""; return; }
  el.innerHTML = `<div class="error-box">⚠ ${escapeHtml(message)}</div>`;
}

// --- Navigasi sub-tab (dipakai di halaman Tokenizer & Parser, yang punya
// beberapa alat berbeda dalam satu halaman) ----------------------------------
document.querySelectorAll(".subtab-nav").forEach((nav) => {
  nav.querySelectorAll(".subtab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      nav.querySelectorAll(".subtab-btn").forEach((b) => b.classList.remove("active"));
      const parent = nav.parentElement;
      parent.querySelectorAll(":scope > .subtab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $(btn.dataset.sub).classList.add("active");
    });
  });
});

// Diagram automata (SVG, tata letak berjenjang).
// Kolom tiap state = jarak BFS dari state awal, biar posisi ikut struktur graf.

const AUTOMATON_MAX_NODES = 26; // di atas ini, tampilkan tabel transisi saja

function computeLayeredLayout(automaton) {
  const states = automaton.states;
  const n = Math.max(states.length, 1);
  const nodeR = n <= 8 ? 24 : n <= 14 ? 20 : n <= 20 ? 17 : 15;

  const adj = {};
  states.forEach((s) => { adj[s] = new Set(); });
  (automaton.transitions || []).forEach((t) => {
    (t.to || []).forEach((to) => { if (to !== t.from) adj[t.from].add(to); });
  });

  // BFS dari start buat nentuin ada di kolom (rank) keberapa tiap state
  const rank = {};
  rank[automaton.start] = 0;
  const queue = [automaton.start];
  let qi = 0;
  while (qi < queue.length) {
    const cur = queue[qi++];
    adj[cur].forEach((nb) => { if (!(nb in rank)) { rank[nb] = rank[cur] + 1; queue.push(nb); } });
  }
  let maxRankSoFar = 0;
  Object.values(rank).forEach((r) => { if (r > maxRankSoFar) maxRankSoFar = r; });
  states.forEach((s) => { if (!(s in rank)) rank[s] = maxRankSoFar + 1; }); // jaga-jaga kalau ada state tak terjangkau

  const byRank = {};
  states.forEach((s) => {
    if (!byRank[rank[s]]) byRank[rank[s]] = [];
    byRank[rank[s]].push(s);
  });
  const ranks = Object.keys(byRank).map(Number).sort((a, b) => a - b);
  const maxPerRank = Math.max(1, ...ranks.map((r) => byRank[r].length));

  const rankGap = Math.max(150, nodeR * 6.4);
  const nodeGap = nodeR * 2 + 58; // termasuk jatah ruang buat self-loop di atas node
  const padX = 60, padY = 70;

  const width = padX * 2 + Math.max(0, ranks.length - 1) * rankGap + nodeR * 2;
  const height = padY * 2 + (maxPerRank - 1) * nodeGap + nodeR * 2;

  const pos = {};
  ranks.forEach((r) => {
    const list = byRank[r];
    const k = list.length;
    const colX = padX + nodeR + r * rankGap;
    list.forEach((s, i) => {
      pos[s] = { x: colX, y: height / 2 + (i - (k - 1) / 2) * nodeGap };
    });
  });

  return { nodeR, width, height, pos, rank };
}

// Simbol satu karakter yang berurutan disingkat jadi rentang (mis. "0-9")
// supaya label transisi tidak panjang dan menabrak node lain.
function compressSymbols(symbols) {
  if (symbols.length <= 2 || !symbols.every((s) => s.length === 1)) {
    return symbols.length > 6 ? symbols.slice(0, 6).join(",") + ",.." : symbols.join(",");
  }
  const sorted = [...symbols].sort();
  const ranges = [];
  let start = sorted[0], prev = sorted[0];
  for (let i = 1; i < sorted.length; i++) {
    const cur = sorted[i];
    if (cur.charCodeAt(0) === prev.charCodeAt(0) + 1) { prev = cur; }
    else { ranges.push(start === prev ? start : start + "-" + prev); start = cur; prev = cur; }
  }
  ranges.push(start === prev ? start : start + "-" + prev);
  return ranges.join(",");
}

function buildAutomatonSVG(automaton, idSuffix) {
  const states = automaton.states;
  const { nodeR, width, height, pos, rank } = computeLayeredLayout(automaton);

  // beberapa transisi bisa punya asal-tujuan sama tapi simbol beda (mis. tiap digit
  // 0..9), jadi digabung dulu supaya labelnya jadi satu garis, bukan sepuluh garis tumpang tindih
  const groups = {};
  (automaton.transitions || []).forEach((t) => {
    (t.to || []).forEach((toState) => {
      const key = t.from + "||" + toState;
      if (!groups[key]) groups[key] = { from: t.from, to: toState, symbols: [] };
      groups[key].symbols.push(t.symbol);
    });
  });

  const parts = [];
  parts.push(`<defs><marker id="arrow-${idSuffix}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8fb3d6"/></marker></defs>`);

  function labelBackground(x, y, text) {
    const w = text.length * 7.4 + 8;
    return `<rect x="${x - w / 2}" y="${y - 10}" width="${w}" height="15" rx="3" fill="var(--bg-inset)" opacity="0.92"/>`;
  }

  Object.entries(groups).forEach(([key, g]) => {
    const label = compressSymbols(g.symbols);
    if (g.from === g.to) {
      // self loop: busur kecil melengkung di atas node-nya sendiri
      const p = pos[g.from];
      const d = `M ${p.x - 16} ${p.y - nodeR + 4} C ${p.x - 38} ${p.y - nodeR - 42}, ${p.x + 38} ${p.y - nodeR - 42}, ${p.x + 16} ${p.y - nodeR + 4}`;
      const ly = p.y - nodeR - 46;
      parts.push(`<path class="fa-edge-path" data-key="${key}" d="${d}" marker-end="url(#arrow-${idSuffix})"/>`);
      parts.push(labelBackground(p.x, ly, label));
      parts.push(`<text class="fa-edge-label" data-key="${key}" x="${p.x}" y="${ly}">${escapeHtml(label)}</text>`);
    } else {
      const p1 = pos[g.from], p2 = pos[g.to];
      const hasReverse = !!groups[g.to + "||" + g.from];
      const dx = p2.x - p1.x, dy = p2.y - p1.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const ux = dx / dist, uy = dy / dist;
      const sx = p1.x + ux * nodeR, sy = p1.y + uy * nodeR;
      const ex = p2.x - ux * nodeR, ey = p2.y - uy * nodeR;
      // Makin jauh lompatan kolomnya, makin besar lengkungan garisnya.
      const rankDist = Math.abs((rank[g.from] ?? 0) - (rank[g.to] ?? 0));
      const baseOffset = hasReverse ? 26 : 18;
      const offset = baseOffset + Math.max(0, rankDist - 1) * 22;
      // Arah lengkung diselang-seling berdasarkan rank asal, kecuali
      // pasangan bolak-balik yang arahnya sudah otomatis berlawanan.
      const sign = hasReverse ? 1 : ((rank[g.from] ?? 0) % 2 === 0 ? 1 : -1);
      const nx = (-dy / dist) * sign, ny = (dx / dist) * sign;
      const mx = (sx + ex) / 2 + nx * offset, my = (sy + ey) / 2 + ny * offset;
      const d = `M ${sx} ${sy} Q ${mx} ${my} ${ex} ${ey}`;
      parts.push(`<path class="fa-edge-path" data-key="${key}" d="${d}" marker-end="url(#arrow-${idSuffix})"/>`);
      parts.push(labelBackground(mx, my, label));
      parts.push(`<text class="fa-edge-label" data-key="${key}" x="${mx}" y="${my}">${escapeHtml(label)}</text>`);
    }
  });

  states.forEach((s) => {
    const p = pos[s];
    const isFinal = (automaton.finals || []).includes(s);
    const shortLabel = s.length > 8 ? s.slice(0, 7) + "…" : s;
    parts.push(`<g class="fa-node" data-state="${escapeHtml(s)}">
      <title>${escapeHtml(s)}</title>
      ${isFinal ? `<circle class="fa-node-ring-final" cx="${p.x}" cy="${p.y}" r="${nodeR + 5}" fill="none"/>` : ""}
      <circle class="fa-node-circle" cx="${p.x}" cy="${p.y}" r="${nodeR}"/>
      <text class="fa-node-label" x="${p.x}" y="${p.y + 4}">${escapeHtml(shortLabel)}</text>
    </g>`);
  });

  if (pos[automaton.start]) {
    const p = pos[automaton.start];
    const sx = p.x - nodeR - 34, sy = p.y;
    parts.push(`<path class="fa-start-arrow" d="M ${sx} ${sy} L ${p.x - nodeR - 3} ${sy}" marker-end="url(#arrow-${idSuffix})"/>`);
    parts.push(`<text class="fa-edge-label" x="${sx - 6}" y="${sy - 8}" style="text-anchor:end;">mulai</text>`);
  }

  // width/height eksplisit (bukan cuma viewBox) agar otomata kecil
  // tidak dipaksa melar; CSS hanya boleh menyusutkan lewat max-width.
  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">${parts.join("")}</svg>`;
}

function buildTransitionTableFallback(automaton) {
  const rows = (automaton.transitions || []).map((t) =>
    `<tr><td>${escapeHtml(t.from)}</td><td>${escapeHtml(t.symbol)}</td><td>${escapeHtml(t.to.join(", "))}</td></tr>`
  ).join("");
  return `<div class="p-3">
    <p class="text-dim small mb-2">Mesin ini punya ${automaton.states.length} state, terlalu banyak untuk
      digambar sebagai diagram yang masih terbaca. Berikut tabel transisinya sebagai gantinya.</p>
    <table class="cp-table"><thead><tr><th>Dari</th><th>Simbol</th><th>Ke</th></tr></thead><tbody>${rows}</tbody></table>
  </div>`;
}

function automatonLegendHTML(automaton) {
  return `<div class="fa-legend">
    <span><span class="legend-swatch swatch-normal"></span>state biasa</span>
    <span><span class="legend-swatch swatch-final"></span>state akhir (final)</span>
    <span><span class="legend-swatch swatch-active"></span>state aktif saat simulasi</span>
    <span class="text-dim">mulai dari state <b>${escapeHtml(automaton.start)}</b>${automaton.type ? ` &middot; tipe: ${automaton.type}` : ""}</span>
  </div>`;
}

function renderAutomaton(container, automaton) {
  if (automaton.states.length > AUTOMATON_MAX_NODES) {
    container.innerHTML = buildTransitionTableFallback(automaton);
    return { highlightStates() {} };
  }
  container.innerHTML = buildAutomatonSVG(automaton, container.id) + automatonLegendHTML(automaton);
  return {
    highlightStates(names) {
      container.querySelectorAll(".fa-node").forEach((g) => {
        g.classList.toggle("active", names.includes(g.getAttribute("data-state")));
      });
    },
  };
}

/* =========================================================================
   Stepper generik (prev / next / play) dipakai di beberapa modul
   ========================================================================= */
function attachStepper({ prevBtn, nextBtn, playBtn, statusEl }, total, onIndex, formatStatus) {
  let idx = 0, playing = false, timer = null;
  function stop() { playing = false; clearInterval(timer); playBtn.textContent = "▶"; }
  function update() {
    onIndex(idx);
    statusEl.textContent = formatStatus(idx, total);
    prevBtn.disabled = idx <= 0;
    nextBtn.disabled = idx >= total - 1;
  }
  prevBtn.onclick = () => { stop(); if (idx > 0) { idx--; update(); } };
  nextBtn.onclick = () => { stop(); if (idx < total - 1) { idx++; update(); } };
  playBtn.onclick = () => {
    if (playing) { stop(); return; }
    if (idx >= total - 1) idx = 0;
    playing = true; playBtn.textContent = "⏸";
    timer = setInterval(() => {
      if (idx >= total - 1) { stop(); update(); return; }
      idx++; update();
    }, 750);
  };
  playBtn.disabled = total <= 1;
  update();
  return { goTo(i) { stop(); idx = i; update(); } };
}

// Pohon penurunan digambar sebagai SVG asli (bukan trik CSS ul/li).
// Daun berurutan kiri-ke-kanan; induk di tengah rata-rata posisi anaknya.
function computeTreeLayout(root) {
  const nodeW = 30, leafGap = 26, levelH = 64;
  let leafCounter = 0;
  const pos = new Map();
  let maxDepth = 0;

  function assign(node, depth) {
    maxDepth = Math.max(maxDepth, depth);
    if (!node.children || node.children.length === 0) {
      const x = leafCounter * (nodeW + leafGap);
      leafCounter++;
      pos.set(node, { x, depth });
      return x;
    }
    const childXs = node.children.map((c) => assign(c, depth + 1));
    const x = (childXs[0] + childXs[childXs.length - 1]) / 2;
    pos.set(node, { x, depth });
    return x;
  }
  assign(root, 0);

  const padX = 50, padY = 40;
  const width = leafCounter <= 1 ? nodeW + padX * 2 : leafCounter * (nodeW + leafGap) - leafGap + padX * 2;
  const height = (maxDepth + 1) * 64 + padY * 2 - (64 - 34);
  pos.forEach((p, node) => { p.x += padX; p.y = padY + p.depth * levelH; });
  return { pos, width, height };
}

function buildTreeSVG(root) {
  const { pos, width, height } = computeTreeLayout(root);
  const parts = [];

  // garis dulu, baru kotak, supaya kotaknya tergambar di atas garis (bukan ketutup)
  (function drawEdges(node) {
    if (!node.children) return;
    const p = pos.get(node);
    node.children.forEach((c) => {
      const cp = pos.get(c);
      const midY = (p.y + cp.y) / 2;
      parts.push(`<path class="tree-edge" d="M ${p.x} ${p.y + 12} C ${p.x} ${midY}, ${cp.x} ${midY}, ${cp.x} ${cp.y - 12}"/>`);
      drawEdges(c);
    });
  })(root);

  (function drawNode(node) {
    const p = pos.get(node);
    const isLeaf = !node.children || node.children.length === 0;
    const label = String(node.symbol);
    const boxW = Math.max(30, label.length * 8.4 + 14);
    parts.push(`<g class="tree-node ${isLeaf ? "leaf" : ""}">
      <rect x="${p.x - boxW / 2}" y="${p.y - 12}" width="${boxW}" height="24" rx="6"/>
      <text x="${p.x}" y="${p.y + 4}">${escapeHtml(label)}</text>
    </g>`);
    if (node.children) node.children.forEach(drawNode);
  })(root);

  return `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">${parts.join("")}</svg>`;
}

function renderTree(container, root) {
  if (!root) { container.innerHTML = "<p class='text-dim small p-3'>Belum ada pohon untuk ditampilkan.</p>"; return; }
  container.innerHTML = buildTreeSVG(root);
}

/* =========================================================================
   RENDERER: TABEL CYK
   ========================================================================= */
function renderCykTable(container, rows, terminalSeq) {
  const n = terminalSeq.length;
  if (n === 0) { container.innerHTML = "<p class='text-dim small'>Input kosong.</p>"; return; }
  let html = '<table class="cyk-table"><thead><tr><th class="head">panjang \\ i</th>';
  terminalSeq.forEach((t, i) => { html += `<th class="head">${i}<br>${escapeHtml(t)}</th>`; });
  html += "</tr></thead><tbody>";
  for (let l = n; l >= 1; l--) {
    html += `<tr><td class="head">l=${l}</td>`;
    const rowData = rows[l - 1] || [];
    for (let i = 0; i < n; i++) {
      if (i <= n - l) {
        const syms = rowData[i] || [];
        const isAccept = l === n && i === 0 && syms.length > 0;
        html += `<td class="${syms.length ? "filled" : ""} ${isAccept ? "accept" : ""}">${syms.join(", ")}</td>`;
      } else {
        html += `<td style="border:none;background:transparent;"></td>`;
      }
    }
    html += "</tr>";
  }
  html += "</tbody></table>";
  container.innerHTML = html;
}

function renderDerivations(container, lines) {
  container.innerHTML = lines.map((l, i) =>
    `<div class="derivation-line"><span class="arrow">${i === 0 ? "" : "⇒"}</span>${escapeHtml(l)}</div>`
  ).join("");
}

function renderPdaTable(tbody, steps) {
  tbody.innerHTML = steps.map((s, i) =>
    `<tr><td>${i + 1}</td><td>${escapeHtml(s.stack.join(" ") || "ε")}</td><td>${escapeHtml(s.remaining.join(" ") || "ε")}</td><td>${escapeHtml(s.action)}</td></tr>`
  ).join("");
}

function renderGrammarSteps(container, steps) {
  container.innerHTML = steps.map((s) =>
    `<div class="grammar-step-title">${escapeHtml(s.title)}</div><div class="grammar-block">${escapeHtml(s.grammar.join("\n"))}</div>`
  ).join("");
}

/* =========================================================================
   PRESET DATA
   ========================================================================= */
function digitLines(from, to) {
  return "0123456789".split("").map((d) => `${from} ${d} ${to}`).join("\n");
}

const PRESETS = {
  fsa1: `states: q0, q1
alphabet: 0, 1
start: q0
final: q0
q0 0 q0
q0 1 q1
q1 0 q1
q1 1 q0`,
  fsa2: `states: q0, q1, q2
alphabet: a, b
start: q0
final: q2
q0 a q0
q0 b q0
q0 a q1
q1 b q2`,
  fsa3: `states: q0, q1, q2, q3, qf
alphabet: 0,1,2,3,4,5,6,7,8,9,.
start: q0
final: qf
${digitLines("q0", "q1")}
${digitLines("q1", "q1")}
q1 eps qf
q1 . q2
${digitLines("q2", "q3")}
${digitLines("q3", "q3")}
q3 eps qf`,
  nfa1: `states: q0, q1, q2, q3, q4
alphabet: a, b
start: q0
final: q2, q4
q0 a q0
q0 b q0
q0 a q1
q1 a q2
q2 a q2
q2 b q2
q0 b q3
q3 b q4
q4 a q4
q4 b q4`,
  nfa2: `states: q0, q1, q2, q3, qf
alphabet: 0,1,2,3,4,5,6,7,8,9,.
start: q0
final: qf
${digitLines("q0", "q1")}
${digitLines("q1", "q1")}
q1 eps qf
q1 . q2
${digitLines("q2", "q3")}
${digitLines("q3", "q3")}
q3 eps qf`,
  moore: `states: q0, q1
alphabet: 0, 1
start: q0
outputs: q0=GENAP, q1=GANJIL
q0 0 q0
q0 1 q1
q1 0 q1
q1 1 q0`,
  mealy: `states: q0, q1
alphabet: 0, 1
start: q0
q0 0 q0 GENAP
q0 1 q1 GANJIL
q1 0 q1 GANJIL
q1 1 q0 GENAP`,
  re1: "[0-9]+(\\.[0-9]+)?",
  re2: "(a|b)*abb",
  re3: "\\d\\d?:\\d\\d",
  cfgb1: "S -> a S b | a b",
  cfgb2: "S -> a S a | b S b | a | b",
  cfgb3: "S -> ( S ) S | eps",
  cfgb4: "E -> E + T | E - T | T\nT -> T * F | T / F | F\nF -> ( E ) | id",
  cnf1: "E -> E + T | E - T | T\nT -> T * F | T / F | F\nF -> ( E ) | id",
  cnf2: "S -> a S b | a b",
  cnf3: "S -> A B\nA -> a A | eps\nB -> b B | eps",
};

document.querySelectorAll(".preset-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const key = chip.dataset.preset;
    const text = PRESETS[key];
    if (!text) return;
    const targetMap = {
      fsa1: "fsaDef", fsa2: "fsaDef", fsa3: "fsaDef",
      nfa1: "nfaDef", nfa2: "nfaDef",
      re1: "reInput", re2: "reInput", re3: "reInput",
      cfgb1: "cfgbDef", cfgb2: "cfgbDef", cfgb3: "cfgbDef", cfgb4: "cfgbDef",
      cnf1: "cnfDef", cnf2: "cnfDef", cnf3: "cnfDef",
    };
    const targetId = targetMap[key];
    if (targetId) $(targetId).value = text;
    if (key.startsWith("cfgb")) {
      $("cfgbInput").value = key === "cfgb1" ? "a a b b"
        : key === "cfgb2" ? "a b a"
        : key === "cfgb3" ? "( ) ( )"
        : "id + id * id";
    }
  });
});

/* =========================================================================
   MODULE 1A - TOKENIZER
   ========================================================================= */
let tokStepperState = null;
async function runTokenizer() {
  errorBox($("tokError"), "");
  const expr = $("tokInput").value;
  try {
    const data = await postJSON("/api/tokenize", { expression: expr });
    $("tokResultWrap").style.display = "block";
    const view = renderAutomaton($("tokAutomatonView"), data.automaton);
    $("tokStream").innerHTML = data.tokens.map((t) =>
      `<span class="token-chip ${t.type === "ERROR" ? "err" : ""}">${escapeHtml(t.lexeme)}<small>${t.type}</small></span>`
    ).join("") || "<span class='text-dim small'>Tidak ada token.</span>";

    const traces = data.traces.filter((t) => t.type !== "WHITESPACE");
    if (traces.length) {
      attachStepper(
        { prevBtn: $("tokPrev"), nextBtn: $("tokNext"), playBtn: $("tokPlay"), statusEl: $("tokStepStatus") },
        traces.length,
        (i) => { view.highlightStates([traces[i].path[traces[i].path.length - 1]]); },
        (i, total) => `Token ${i + 1}/${total}: "${traces[i].lexeme}" → lintasan ${traces[i].path.join(" → ")}`
      );
    } else {
      $("tokStepStatus").textContent = "-";
    }
  } catch (e) {
    errorBox($("tokError"), e.message);
    $("tokResultWrap").style.display = "none";
  }
}

/* =========================================================================
   MODULE 1B - CUSTOM FSA SIMULATOR
   ========================================================================= */
async function runCustomFSA() {
  errorBox($("fsaError"), "");
  $("fsaBanner").innerHTML = "";
  try {
    const data = await postJSON("/api/fsa/simulate", {
      definition: $("fsaDef").value, input: $("fsaInput").value,
    });
    $("fsaResultWrap").style.display = "block";
    const view = renderAutomaton($("fsaAutomatonView"), data.automaton);
    $("fsaBanner").innerHTML = `<div class="result-banner ${data.accepted ? "ok" : "bad"}">
      ${data.accepted ? "✓ DITERIMA" : "✕ DITOLAK"} oleh mesin (${data.automaton.type})
      <span class="value">state akhir: ${data.final_states.join(", ") || "∅"}</span></div>`;
    attachStepper(
      { prevBtn: $("fsaPrev"), nextBtn: $("fsaNext"), playBtn: $("fsaPlay"), statusEl: $("fsaStepStatus") },
      data.trace.length,
      (i) => { view.highlightStates(data.trace[i].states); },
      (i, total) => {
        const step = data.trace[i];
        return `Langkah ${i}/${total - 1}${step.symbol !== null ? ` - baca '${step.symbol}'` : " - mulai"} → {${step.states.join(",") || "∅"}}`;
      }
    );
  } catch (e) {
    errorBox($("fsaError"), e.message);
    $("fsaResultWrap").style.display = "none";
  }
}

/* =========================================================================
   MODULE 1C - NFA -> DFA
   ========================================================================= */
async function runNfaToDfa() {
  errorBox($("nfaError"), "");
  try {
    const data = await postJSON("/api/fsa/nfa2dfa", { definition: $("nfaDef").value });
    $("nfaResultWrap").style.display = "block";
    renderAutomaton($("nfaOrigView"), data.nfa);
    renderAutomaton($("nfaDfaView"), data.dfa);
    const rows = data.steps.map((s) =>
      `<tr><td>${escapeHtml(s.from)}</td><td>${escapeHtml(s.symbol)}</td><td>${escapeHtml(s.to)}</td></tr>`
    ).join("");
    $("nfaStepsTable").innerHTML =
      `<thead><tr><th>State DFA Asal</th><th>Simbol</th><th>State DFA Tujuan</th></tr></thead><tbody>${rows}</tbody>`;
  } catch (e) {
    errorBox($("nfaError"), e.message);
    $("nfaResultWrap").style.display = "none";
  }
}

/* =========================================================================
   MODULE 1D - MOORE / MEALY
   ========================================================================= */
async function runMoore() {
  errorBox($("moorError"), "");
  try {
    const data = await postJSON("/api/fsa/moore", { definition: $("moorDef").value, input: $("moorInput").value });
    const rows = data.trace.map((t, i) =>
      `<tr><td>${i}</td><td>${escapeHtml(t.state)}</td><td>${t.symbol === null ? "-" : escapeHtml(t.symbol)}</td><td>${escapeHtml(t.output)}</td></tr>`
    ).join("");
    $("moorResult").innerHTML = `<div class="result-banner ok" style="background:var(--accent-soft);border-color:var(--accent);color:var(--accent);">
        Output: <span class="value mono" style="color:var(--text-primary)">${escapeHtml(data.output_string)}</span></div>
      <table class="cp-table"><thead><tr><th>#</th><th>State</th><th>Baca</th><th>Output</th></tr></thead><tbody>${rows}</tbody></table>`;
  } catch (e) { errorBox($("moorError"), e.message); $("moorResult").innerHTML = ""; }
}
async function runMealy() {
  errorBox($("mealError"), "");
  try {
    const data = await postJSON("/api/fsa/mealy", { definition: $("mealDef").value, input: $("mealInput").value });
    const rows = data.trace.map((t, i) =>
      `<tr><td>${i}</td><td>${escapeHtml(t.state)}</td><td>${escapeHtml(t.symbol)}</td><td>${escapeHtml(t.next)}</td><td>${escapeHtml(t.output)}</td></tr>`
    ).join("");
    $("mealResult").innerHTML = `<div class="result-banner ok" style="background:var(--accent-soft);border-color:var(--accent);color:var(--accent);">
        Output: <span class="value mono" style="color:var(--text-primary)">${escapeHtml(data.output_string)}</span></div>
      <table class="cp-table"><thead><tr><th>#</th><th>State</th><th>Baca</th><th>Tujuan</th><th>Output</th></tr></thead><tbody>${rows}</tbody></table>`;
  } catch (e) { errorBox($("mealError"), e.message); $("mealResult").innerHTML = ""; }
}
/* =========================================================================
   MODULE 2 - REGULAR EXPRESSION
   ========================================================================= */
let lastRegexPattern = "";
async function compileRegexHandler() {
  errorBox($("reError"), "");
  try {
    const pattern = $("reInput").value;
    const data = await postJSON("/api/regex/compile", { pattern });
    lastRegexPattern = pattern;
    $("reResultWrap").style.display = "block";
    renderAutomaton($("reNfaView"), data.nfa);
    renderAutomaton($("reDfaView"), data.dfa);
    $("reGrammarBlock").textContent = data.grammar.join("\n");
  } catch (e) {
    errorBox($("reError"), e.message);
    $("reResultWrap").style.display = "none";
  }
}
async function testRegexHandler() {
  try {
    const pattern = lastRegexPattern || $("reInput").value;
    const data = await postJSON("/api/regex/test", { pattern, input: $("reTestInput").value });
    $("reTestBanner").innerHTML = `<div class="result-banner ${data.accepted ? "ok" : "bad"}">
      ${data.accepted ? "✓ COCOK dengan pola" : "✕ TIDAK COCOK"}
      <span class="value">state akhir: ${data.final_states.join(", ") || "∅"}</span></div>`;
    $("reTestStepWrap").style.display = "block";
    const view = renderAutomaton($("reTestDfaView"), data.dfa);
    attachStepper(
      { prevBtn: $("rePrev"), nextBtn: $("reNext"), playBtn: $("rePlay"), statusEl: $("reStepStatus") },
      data.trace.length,
      (i) => { view.highlightStates(data.trace[i].states); },
      (i, total) => {
        const s = data.trace[i];
        return `Langkah ${i}/${total - 1}${s.symbol !== null ? ` - baca '${s.symbol}'` : " - mulai"} → {${s.states.join(",") || "∅"}}`;
      }
    );
  } catch (e) {
    $("reTestBanner").innerHTML = `<div class="error-box">⚠ ${escapeHtml(e.message)}</div>`;
    $("reTestStepWrap").style.display = "none";
  }
}
/* =========================================================================
   MODULE 3A - ARITHMETIC PARSER (PDA)
   ========================================================================= */
let arData = null, arShowRight = true;
async function runArithmeticParse() {
  errorBox($("arError"), "");
  try {
    const data = await postJSON("/api/cfg/arithmetic/parse", { expression: $("arInput").value });
    arData = data;
    $("arResultWrap").style.display = "block";
    $("arValue").textContent = data.value !== null && data.value !== undefined ? `= ${data.value}` : "";
    renderTree($("arTreeView"), data.tree);
    renderDerivations($("arDerivWrap"), arShowRight ? data.rightmost : data.leftmost);
    $("arDerivToggle").textContent = "tampilkan: " + (arShowRight ? "kiri" : "kanan");
    renderPdaTable($("arPdaTable").querySelector("tbody"), data.pda_trace);
  } catch (e) {
    errorBox($("arError"), e.message);
    $("arResultWrap").style.display = "none";
  }
}
function toggleArDerivation() {
  if (!arData) return;
  arShowRight = !arShowRight;
  renderDerivations($("arDerivWrap"), arShowRight ? arData.rightmost : arData.leftmost);
  $("arDerivToggle").textContent = "tampilkan: " + (arShowRight ? "kiri" : "kanan");
}

/* =========================================================================
   MODULE 3B - GENERIC CFG / PDA via CYK
   ========================================================================= */
async function runGenericCFG() {
  errorBox($("cfgbError"), "");
  $("cfgbBanner").innerHTML = "";
  try {
    const data = await postJSON("/api/cfg/generic/parse", {
      grammar: $("cfgbDef").value, input: $("cfgbInput").value,
    });
    $("cfgbResultWrap").style.display = "block";
    $("cfgbCnfBlock").textContent = data.cnf_grammar.join("\n");
    renderCykTable($("cfgbCykTable"), data.cyk_table, data.terminal_seq);
    $("cfgbBanner").innerHTML = `<div class="result-banner ${data.accepted ? "ok" : "bad"}">
      ${data.accepted ? "✓ STRING DITERIMA" : "✕ STRING DITOLAK"} oleh grammar</div>`;
    if (data.accepted) {
      $("cfgbTreeDerivWrap").style.display = "flex";
      $("cfgbPdaWrap").style.display = "block";
      renderTree($("cfgbTreeView"), data.tree);
      renderDerivations($("cfgbDerivWrap"), data.leftmost);
      renderPdaTable($("cfgbPdaTable").querySelector("tbody"), data.pda_trace);
    } else {
      $("cfgbTreeDerivWrap").style.display = "none";
      $("cfgbPdaWrap").style.display = "none";
    }
  } catch (e) {
    errorBox($("cfgbError"), e.message);
    $("cfgbResultWrap").style.display = "none";
  }
}
/* =========================================================================
   MODULE 4 - CHOMSKY NORMAL FORM & GNF
   ========================================================================= */
async function runCnfConversion() {
  errorBox($("cnfError"), "");
  try {
    const data = await postJSON("/api/cfg/cnf", { grammar: $("cnfDef").value });
    $("cnfResultWrap").style.display = "block";
    renderGrammarSteps($("cnfStepsWrap"), data.steps);
    $("cnfFinalBlock").textContent = data.cnf_grammar.join("\n");
    if (data.gnf.success) {
      $("gnfWrap").innerHTML = `<div class="result-banner ok">✓ Konversi GNF berhasil</div>
        <div class="grammar-block">${escapeHtml(data.gnf.grammar.join("\n"))}</div>`;
    } else {
      $("gnfWrap").innerHTML = `<div class="result-banner bad">✕ ${escapeHtml(data.gnf.message)}</div>`;
    }
  } catch (e) {
    errorBox($("cnfError"), e.message);
    $("cnfResultWrap").style.display = "none";
  }
}
/* =========================================================================
   HERO - DEMO PIPELINE END-TO-END
   ========================================================================= */
async function runHeroPipeline() {
  const expr = $("heroInput").value;
  $("pl-input").textContent = expr.length > 10 ? expr.slice(0, 10) + "…" : expr || "-";
  document.querySelectorAll(".pipeline-schematic .stage, .pipeline-arrow").forEach((el) => el.classList.remove("active", "fail"));
  $("heroMessage").textContent = "Memproses…";
  $("heroTokenStream").innerHTML = "";
  await sleep(150);
  document.querySelector('.stage[data-stage="input"]').classList.add("active");
  document.querySelectorAll(".pipeline-arrow")[0].classList.add("active");
  try {
    const data = await postJSON("/api/pipeline/run", { expression: expr });
    await sleep(300);
    document.querySelector('.stage[data-stage="lexer"]').classList.add(data.lexer_ok ? "active" : "fail");
    $("heroTokenStream").innerHTML = data.tokens.map((t) =>
      `<span class="token-chip ${t.type === "ERROR" ? "err" : ""}">${escapeHtml(t.lexeme)}<small>${t.type}</small></span>`
    ).join("");
    if (!data.lexer_ok) {
      $("heroMessage").textContent = "✕ " + (data.message || "Token tidak dikenali.");
      $("pl-result").textContent = "gagal";
      return;
    }
    document.querySelectorAll(".pipeline-arrow")[1].classList.add("active");
    await sleep(300);
    document.querySelector('.stage[data-stage="parser"]').classList.add(data.parser_ok ? "active" : "fail");
    if (!data.parser_ok) {
      $("heroMessage").textContent = "✕ " + (data.message || "Struktur ekspresi tidak valid.");
      $("pl-result").textContent = "gagal";
      return;
    }
    document.querySelectorAll(".pipeline-arrow")[2].classList.add("active");
    await sleep(250);
    document.querySelector('.stage[data-stage="result"]').classList.add("active");
    $("pl-result").textContent = data.value;
    $("heroMessage").textContent = `Diproses melalui ${data.token_count} token → hasil = ${data.value}`;
  } catch (e) {
    $("heroMessage").textContent = "⚠ " + e.message;
  }
}
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

// INISIALISASI PER HALAMAN: tiap modul punya wiring sendiri, dipanggil
// sesuai atribut data-page di <body> agar tidak menyentuh elemen yang tak ada.

function initHomePage() {
  $("heroRunBtn").addEventListener("click", runHeroPipeline);
  runHeroPipeline(); // langsung tampilkan contoh biar beranda tidak kosong
}

function initTokenizerPage() {
  $("fsaDef").value = PRESETS.fsa1;
  $("nfaDef").value = PRESETS.nfa1;
  $("moorDef").value = PRESETS.moore;
  $("mealDef").value = PRESETS.mealy;
  $("tokRunBtn").addEventListener("click", runTokenizer);
  $("fsaRunBtn").addEventListener("click", runCustomFSA);
  $("nfaRunBtn").addEventListener("click", runNfaToDfa);
  $("moorRunBtn").addEventListener("click", runMoore);
  $("mealRunBtn").addEventListener("click", runMealy);
  runTokenizer(); // langsung tokenisasi contoh bawaan biar kelihatan hasilnya
}

function initRegexPage() {
  $("reCompileBtn").addEventListener("click", compileRegexHandler);
  $("reTestBtn").addEventListener("click", testRegexHandler);
  compileRegexHandler();
}

function initParserPage() {
  $("cfgbDef").value = PRESETS.cfgb1;
  $("arRunBtn").addEventListener("click", runArithmeticParse);
  $("arDerivToggle").addEventListener("click", toggleArDerivation);
  $("cfgbRunBtn").addEventListener("click", runGenericCFG);
  runArithmeticParse();
}

function initCnfPage() {
  $("cnfDef").value = PRESETS.cnf1;
  $("cnfRunBtn").addEventListener("click", runCnfConversion);
}

const PAGE_INIT = {
  home: initHomePage,
  tokenizer: initTokenizerPage,
  regex: initRegexPage,
  parser: initParserPage,
  cnf: initCnfPage,
};
const currentPage = document.body.dataset.page;
if (PAGE_INIT[currentPage]) PAGE_INIT[currentPage]();
