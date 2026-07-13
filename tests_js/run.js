// Test regresi logika murni di static/script.js lewat vm dengan stub DOM minimal.
// Jalankan: node tests_js/run.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function fakeElement() {
  return { querySelectorAll: () => [], addEventListener: () => {}, classList: { add() {}, remove() {}, toggle() {} } };
}
const fakeDocument = {
  querySelectorAll: () => [],
  getElementById: () => null,
  body: { dataset: {} },
};
const sandbox = { document: fakeDocument, window: {}, console };
vm.createContext(sandbox);
const code = fs.readFileSync(path.join(__dirname, "..", "static", "script.js"), "utf8");
vm.runInContext(code, sandbox, { filename: "script.js" });

let pass = 0, fail = 0;
function check(name, cond) {
  if (cond) { pass++; console.log(`  ok  - ${name}`); }
  else { fail++; console.log(`FAIL  - ${name}`); }
}

// 1) formatStateSet: satu state tidak boleh dibungkus kurung kurawal ganda.
check("formatStateSet satu state apa adanya", sandbox.formatStateSet(["{n3,n4,n5}"]) === "{n3,n4,n5}");
check("formatStateSet banyak state dibungkus {}", sandbox.formatStateSet(["q0", "q1"]) === "{q0, q1}");
check("formatStateSet kosong jadi ∅", sandbox.formatStateSet([]) === "∅");

// 2) compressSymbols: rentang digit disingkat, simbol campuran tidak.
check("compressSymbols digit 0-9 disingkat", sandbox.compressSymbols(["0","1","2","3","4","5","6","7","8","9"]) === "0-9");
check("compressSymbols non-digit tidak disingkat", sandbox.compressSymbols(["a","b"]) === "a,b");

// 3) humanizeRegex: pola dasar harus menghasilkan teks, bukan kosong/error.
check("humanizeRegex ab* menghasilkan teks", sandbox.humanizeRegex("ab*").length > 0);
check("humanizeRegex grup dikenali", sandbox.humanizeRegex("(a|b)*abb").includes("ATAU"));

// 4) Regresi bug nyata: label "mulai" sempat digambar di luar kanvas (x negatif)
//    karena text-anchor:end dekat tepi kiri. Pastikan geometrinya tidak berulang.
const automaton = {
  states: ["q0", "q1"], alphabet: ["0", "1"], start: "q0", finals: ["q0"],
  type: "DFA",
  transitions: [{ from: "q0", symbol: "0", to: ["q0"] }, { from: "q0", symbol: "1", to: ["q1"] }],
};
const svg = sandbox.buildAutomatonSVG(automaton, "test");
const labelMatch = svg.match(/<text class="fa-edge-label" x="(-?[\d.]+)"/);
check("SVG punya label 'mulai'", !!labelMatch);
if (labelMatch) {
  const anchorX = parseFloat(labelMatch[1]);
  const approxTextWidth = 32; // ~5 karakter monospace @10.5px
  check("label 'mulai' tidak keluar dari tepi kiri kanvas (x - lebar >= 0)", anchorX - approxTextWidth >= 0);
}

console.log(`\n${pass} lulus, ${fail} gagal`);
process.exit(fail > 0 ? 1 : 0);
