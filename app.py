# -*- coding: utf-8 -*-
"""CalcParser: simulasi Tokenizer/FSA, Regex, Parser CFG/PDA, dan konversi CNF.
Seluruh logika otomata ditulis manual (tanpa modul `re`) untuk demo konsep kuliah."""

import itertools
import os
from collections import OrderedDict, defaultdict

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

EPSILON = "ε"
EPSILON_ALIASES = {"", "eps", "epsilon", "ε", "e"}


# BAGIAN 1: MESIN FSA (DFA/NFA/Moore/Mealy).
# Representasi seragam: dict {states, alphabet, start, finals, transitions}.

class AutomataError(Exception):
    """Dilempar ketika definisi mesin otomata tidak valid."""


def _split_list(value):
    return [v.strip() for v in value.split(",") if v.strip() != ""]


def parse_fsa_definition(text):
    """Parsing definisi DFA/NFA: 'states:/alphabet:/start:/final:' lalu baris 'asal simbol tujuan'."""
    states, alphabet, start, finals = [], [], None, []
    transitions = defaultdict(set)
    raw_transitions = []

    if not text or not text.strip():
        raise AutomataError("Definisi mesin tidak boleh kosong.")

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lower = line.lower()
        if lower.startswith("states"):
            states = _split_list(line.split(":", 1)[1]) if ":" in line else []
        elif lower.startswith("alphabet"):
            alphabet = _split_list(line.split(":", 1)[1]) if ":" in line else []
        elif lower.startswith("start"):
            value = line.split(":", 1)[1].strip() if ":" in line else ""
            start = value
        elif lower.startswith("final"):
            finals = _split_list(line.split(":", 1)[1]) if ":" in line else []
        elif lower.startswith("transitions"):
            continue
        else:
            parts = line.split()
            if len(parts) != 3:
                raise AutomataError(
                    f"Baris {lineno} tidak dikenali: '{raw_line.strip()}'. "
                    "Gunakan format 'state_asal simbol state_tujuan'."
                )
            frm, sym, to = parts
            if sym.lower() in EPSILON_ALIASES:
                sym = EPSILON
            raw_transitions.append((frm, sym, to))

    if not states:
        raise AutomataError("Daftar 'states' wajib diisi.")
    if start is None or start == "":
        raise AutomataError("State awal ('start') wajib diisi.")
    if start not in states:
        raise AutomataError(f"State awal '{start}' tidak terdaftar pada daftar states.")
    for f in finals:
        if f not in states:
            raise AutomataError(f"State akhir '{f}' tidak terdaftar pada daftar states.")

    for frm, sym, to in raw_transitions:
        if frm not in states:
            raise AutomataError(f"State '{frm}' pada transisi tidak terdaftar di 'states'.")
        if to not in states:
            raise AutomataError(f"State '{to}' pada transisi tidak terdaftar di 'states'.")
        if sym != EPSILON and alphabet and sym not in alphabet:
            alphabet.append(sym)
        transitions[(frm, sym)].add(to)

    if not alphabet:
        alphabet = sorted({sym for (_, sym) in transitions.keys() if sym != EPSILON})

    is_dfa = all(
        len(v) == 1 for v in transitions.values()
    ) and not any(sym == EPSILON for (_, sym) in transitions.keys())
    # DFA sejati juga harus punya tepat satu transisi utk setiap (state, simbol)
    if is_dfa:
        for s in states:
            for a in alphabet:
                if len(transitions.get((s, a), set())) > 1:
                    is_dfa = False

    return {
        "states": states,
        "alphabet": alphabet,
        "start": start,
        "finals": finals,
        "transitions": transitions,
        "type": "DFA" if is_dfa else "NFA",
    }


def epsilon_closure(state_set, transitions):
    stack = list(state_set)
    closure = set(state_set)
    while stack:
        s = stack.pop()
        for nxt in transitions.get((s, EPSILON), set()):
            if nxt not in closure:
                closure.add(nxt)
                stack.append(nxt)
    return closure


def automaton_to_json(automaton):
    trans_list = []
    for (frm, sym), targets in automaton["transitions"].items():
        trans_list.append({"from": frm, "symbol": sym, "to": sorted(targets)})
    return {
        "states": automaton["states"],
        "alphabet": automaton["alphabet"],
        "start": automaton["start"],
        "finals": automaton["finals"],
        "type": automaton.get("type", "DFA"),
        "transitions": trans_list,
    }


def simulate_fsa(automaton, input_str):
    transitions = automaton["transitions"]
    current = epsilon_closure({automaton["start"]}, transitions)
    trace = [{"step": 0, "symbol": None, "states": sorted(current)}]

    for idx, ch in enumerate(input_str):
        moved = set()
        for s in current:
            moved |= transitions.get((s, ch), set())
        if not moved:
            trace.append({"step": idx + 1, "symbol": ch, "states": []})
            current = set()
            break
        current = epsilon_closure(moved, transitions)
        trace.append({"step": idx + 1, "symbol": ch, "states": sorted(current)})

    accepted = any(s in automaton["finals"] for s in current)
    return {"trace": trace, "accepted": accepted, "final_states": sorted(current)}


def nfa_to_dfa(automaton):
    transitions = automaton["transitions"]
    alphabet = automaton["alphabet"]

    def label(frozen):
        if not frozen:
            return "∅"
        return "{" + ",".join(sorted(frozen)) + "}"

    start_set = frozenset(epsilon_closure({automaton["start"]}, transitions))
    unmarked = [start_set]
    seen = {start_set}
    dfa_transitions = {}
    dfa_finals = set()
    steps = []

    if any(s in automaton["finals"] for s in start_set):
        dfa_finals.add(start_set)

    while unmarked:
        cur = unmarked.pop(0)
        for sym in alphabet:
            moved = set()
            for s in cur:
                moved |= transitions.get((s, sym), set())
            if not moved:
                continue
            target = frozenset(epsilon_closure(moved, transitions))
            steps.append({
                "from": label(cur), "symbol": sym, "to": label(target),
                "from_set": sorted(cur), "to_set": sorted(target),
            })
            dfa_transitions[(cur, sym)] = target
            if target not in seen:
                seen.add(target)
                unmarked.append(target)
                if any(s in automaton["finals"] for s in target):
                    dfa_finals.add(target)

    dfa_states = sorted(seen, key=lambda s: (len(s), label(s)))
    state_names = {s: label(s) for s in dfa_states}

    trans_json = []
    for (frm, sym), to in dfa_transitions.items():
        trans_json.append({"from": state_names[frm], "symbol": sym, "to": [state_names[to]]})

    dfa_json = {
        "states": [state_names[s] for s in dfa_states],
        "alphabet": alphabet,
        "start": state_names[start_set],
        "finals": [state_names[s] for s in dfa_finals],
        "type": "DFA",
        "transitions": trans_json,
    }
    return dfa_json, steps


def parse_output_definition(text, kind):
    """Parsing definisi Moore/Mealy. kind = 'moore' atau 'mealy'."""
    states, alphabet, start, finals = [], [], None, []
    transitions = {}
    outputs = {}
    raw_transitions = []

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lower = line.lower()
        if lower.startswith("states"):
            states = _split_list(line.split(":", 1)[1])
        elif lower.startswith("alphabet"):
            alphabet = _split_list(line.split(":", 1)[1])
        elif lower.startswith("start"):
            start = line.split(":", 1)[1].strip()
        elif lower.startswith("final"):
            finals = _split_list(line.split(":", 1)[1])
        elif lower.startswith("outputs"):
            pairs = _split_list(line.split(":", 1)[1])
            for p in pairs:
                if "=" not in p:
                    raise AutomataError(f"Baris outputs '{p}' harus berformat state=output.")
                k, v = p.split("=", 1)
                outputs[k.strip()] = v.strip()
        elif lower.startswith("transitions"):
            continue
        else:
            parts = line.split()
            expected = 4 if kind == "mealy" else 3
            if len(parts) != expected:
                raise AutomataError(
                    f"Baris {lineno} tidak sesuai format "
                    f"({'state simbol state_tujuan output' if kind == 'mealy' else 'state simbol state_tujuan'})."
                )
            raw_transitions.append(parts)

    if not states:
        raise AutomataError("Daftar 'states' wajib diisi.")
    if not start:
        raise AutomataError("State awal wajib diisi.")

    if kind == "mealy":
        for frm, sym, to, out in raw_transitions:
            transitions[(frm, sym)] = (to, out)
    else:
        for frm, sym, to in raw_transitions:
            transitions[(frm, sym)] = to
        for s in states:
            if s not in outputs:
                raise AutomataError(f"Output untuk state '{s}' belum didefinisikan pada baris 'outputs:'.")

    if not alphabet:
        alphabet = sorted({sym for (_, sym) in transitions.keys()})

    return {
        "states": states, "alphabet": alphabet, "start": start, "finals": finals,
        "transitions": transitions, "outputs": outputs, "kind": kind,
    }


def simulate_output_machine(machine, input_str):
    kind = machine["kind"]
    state = machine["start"]
    trace = []
    if kind == "moore":
        trace.append({"state": state, "symbol": None, "output": machine["outputs"].get(state, "")})
        for ch in input_str:
            nxt = machine["transitions"].get((state, ch))
            if nxt is None:
                raise AutomataError(f"Tidak ada transisi dari state '{state}' dengan simbol '{ch}'.")
            state = nxt
            trace.append({"state": state, "symbol": ch, "output": machine["outputs"].get(state, "")})
    else:
        for ch in input_str:
            pair = machine["transitions"].get((state, ch))
            if pair is None:
                raise AutomataError(f"Tidak ada transisi dari state '{state}' dengan simbol '{ch}'.")
            nxt, out = pair
            trace.append({"state": state, "symbol": ch, "next": nxt, "output": out})
            state = nxt
    return {"trace": trace, "final_state": state,
            "output_string": "".join(t["output"] for t in trace if t.get("output") is not None)}


def output_machine_to_json(machine):
    trans_list = []
    if machine["kind"] == "mealy":
        for (frm, sym), (to, out) in machine["transitions"].items():
            trans_list.append({"from": frm, "symbol": sym, "to": [to], "output": out})
    else:
        for (frm, sym), to in machine["transitions"].items():
            trans_list.append({"from": frm, "symbol": sym, "to": [to]})
    return {
        "states": machine["states"], "alphabet": machine["alphabet"], "start": machine["start"],
        "finals": machine.get("finals", []), "outputs": machine.get("outputs", {}),
        "kind": machine["kind"], "type": machine["kind"].upper(), "transitions": trans_list,
    }


# BAGIAN 2: TOKENIZER KALKULATOR.
# Lexer DFA manual dengan strategi maximal munch (bukan split() biasa).

def build_tokenizer_automaton():
    """DFA lexer CalcParser; state akhir dipetakan ke kategori token via TOKEN_TAGS."""
    states = ["S", "NUM", "NUMDOT", "NUMFRAC", "PLUS", "MINUS", "STAR",
              "SLASH", "LPAREN", "RPAREN", "WS"]
    transitions = defaultdict(set)
    digits = "0123456789"
    for d in digits:
        transitions[("S", d)].add("NUM")
        transitions[("NUM", d)].add("NUM")
        transitions[("NUMFRAC", d)].add("NUMFRAC")
        transitions[("NUMDOT", d)].add("NUMFRAC")
    transitions[("NUM", ".")].add("NUMDOT")
    transitions[("S", "+")].add("PLUS")
    transitions[("S", "-")].add("MINUS")
    transitions[("S", "*")].add("STAR")
    transitions[("S", "/")].add("SLASH")
    transitions[("S", "(")].add("LPAREN")
    transitions[("S", ")")].add("RPAREN")
    transitions[("S", " ")].add("WS")
    transitions[("WS", " ")].add("WS")

    finals = ["NUM", "NUMFRAC", "PLUS", "MINUS", "STAR", "SLASH", "LPAREN", "RPAREN", "WS"]
    alphabet = list(digits) + ["+", "-", "*", "/", "(", ")", " ", "."]
    automaton = {
        "states": states, "alphabet": alphabet, "start": "S", "finals": finals,
        "transitions": transitions, "type": "DFA",
    }
    tags = {
        "NUM": "NUMBER", "NUMFRAC": "NUMBER", "PLUS": "PLUS", "MINUS": "MINUS",
        "STAR": "STAR", "SLASH": "SLASH", "LPAREN": "LPAREN", "RPAREN": "RPAREN",
        "WS": "WHITESPACE",
    }
    return automaton, tags


TOKENIZER_AUTOMATON, TOKEN_TAGS = build_tokenizer_automaton()
TOKEN_SYMBOL_DISPLAY = {
    "NUMBER": "id", "PLUS": "+", "MINUS": "-", "STAR": "*", "SLASH": "/",
    "LPAREN": "(", "RPAREN": ")",
}


class TokenizeError(Exception):
    pass


def tokenize_expression(expr, keep_whitespace_trace=True):
    automaton = TOKENIZER_AUTOMATON
    transitions = automaton["transitions"]
    tokens, traces = [], []
    i, n = 0, len(expr)

    while i < n:
        state = automaton["start"]
        path = [state]
        last_accept = None
        j = i
        while j < n:
            ch = expr[j]
            targets = transitions.get((state, ch))
            if not targets:
                break
            state = next(iter(targets))
            path.append(state)
            j += 1
            if state in automaton["finals"]:
                last_accept = (j, state, list(path))

        if last_accept is None:
            traces.append({"lexeme": expr[i], "path": [automaton["start"]], "type": "ERROR", "pos": i})
            tokens.append({"type": "ERROR", "lexeme": expr[i], "pos": i})
            i += 1
            continue

        end, state, path = last_accept
        lexeme = expr[i:end]
        ttype = TOKEN_TAGS.get(state, "UNKNOWN")
        traces.append({"lexeme": lexeme, "path": path, "type": ttype, "pos": i})
        if ttype != "WHITESPACE":
            tokens.append({"type": ttype, "lexeme": lexeme, "pos": i})
        i = end

    return tokens, traces


# BAGIAN 3: MESIN REGULAR EXPRESSION (bukan wrapper modul `re`).
# Alur: parser AST -> Thompson Construction (NFA) -> nfa_to_dfa (Bagian 1).

class RegexError(Exception):
    pass


class _RegexParser:
    """Recursive-descent parser untuk subset regex: | * + ? () [] literal escape."""

    SPECIAL = set("|*+?()[]\\.")

    def __init__(self, pattern):
        self.pattern = pattern
        self.pos = 0
        self.n = len(pattern)

    def peek(self):
        return self.pattern[self.pos] if self.pos < self.n else None

    def advance(self):
        ch = self.pattern[self.pos]
        self.pos += 1
        return ch

    def parse(self):
        if self.n == 0:
            raise RegexError("Pola regex tidak boleh kosong.")
        node = self.parse_expr()
        if self.pos != self.n:
            raise RegexError(f"Karakter tak terduga '{self.peek()}' pada posisi {self.pos}.")
        return node

    def parse_expr(self):
        term = self.parse_term()
        while self.peek() == "|":
            self.advance()
            rhs = self.parse_term()
            term = ("union", term, rhs)
        return term

    def parse_term(self):
        factors = []
        while self.peek() is not None and self.peek() not in ("|", ")"):
            factors.append(self.parse_factor())
        if not factors:
            return ("empty",)
        node = factors[0]
        for f in factors[1:]:
            node = ("concat", node, f)
        return node

    def parse_factor(self):
        base = self.parse_base()
        while self.peek() in ("*", "+", "?"):
            op = self.advance()
            if op == "*":
                base = ("star", base)
            elif op == "+":
                base = ("plus", base)
            else:
                base = ("opt", base)
        return base

    def parse_base(self):
        ch = self.peek()
        if ch is None:
            raise RegexError("Pola regex berakhir tanpa terduga.")
        if ch == "(":
            self.advance()
            node = self.parse_expr()
            if self.peek() != ")":
                raise RegexError("Kurung '(' tidak memiliki pasangan ')'.")
            self.advance()
            return node
        if ch == "[":
            return self.parse_class()
        if ch == "\\":
            self.advance()
            esc = self.peek()
            if esc is None:
                raise RegexError("Escape '\\' di akhir pola tidak valid.")
            self.advance()
            if esc == "d":
                return ("class", set("0123456789"))
            if esc == "w":
                return ("class", set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"))
            if esc == "s":
                return ("class", set(" \t"))
            return ("char", esc)
        if ch == ".":
            self.advance()
            return ("wildcard",)
        if ch in self.SPECIAL:
            raise RegexError(f"Karakter khusus '{ch}' pada posisi {self.pos} butuh escape '\\{ch}'.")
        self.advance()
        return ("char", ch)

    def parse_class(self):
        self.advance()  # consume '['
        negate = False
        if self.peek() == "^":
            negate = True
            self.advance()
        chars = set()
        while self.peek() is not None and self.peek() != "]":
            c1 = self.advance()
            if self.peek() == "-" and self.pos + 1 < self.n and self.pattern[self.pos + 1] != "]":
                self.advance()
                c2 = self.advance()
                for code in range(ord(c1), ord(c2) + 1):
                    chars.add(chr(code))
            else:
                chars.add(c1)
        if self.peek() != "]":
            raise RegexError("Character class '[' tidak memiliki pasangan ']'.")
        self.advance()
        return ("class_neg", chars) if negate else ("class", chars)


def _collect_alphabet(node, alphabet):
    tag = node[0]
    if tag == "char":
        alphabet.add(node[1])
    elif tag == "class":
        alphabet |= node[1]
    elif tag == "class_neg":
        pass
    elif tag in ("concat", "union"):
        _collect_alphabet(node[1], alphabet)
        _collect_alphabet(node[2], alphabet)
    elif tag in ("star", "plus", "opt"):
        _collect_alphabet(node[1], alphabet)


class _ThompsonBuilder:
    def __init__(self):
        self.counter = 0
        self.transitions = defaultdict(set)
        self.states = set()

    def new_state(self):
        name = f"n{self.counter}"
        self.counter += 1
        self.states.add(name)
        return name

    def add(self, frm, sym, to):
        self.transitions[(frm, sym)].add(to)

    def build(self, node, alphabet):
        tag = node[0]
        if tag == "empty":
            s, e = self.new_state(), self.new_state()
            self.add(s, EPSILON, e)
            return s, e
        if tag == "char":
            s, e = self.new_state(), self.new_state()
            self.add(s, node[1], e)
            return s, e
        if tag == "class":
            s, e = self.new_state(), self.new_state()
            for c in node[1]:
                self.add(s, c, e)
            return s, e
        if tag == "class_neg":
            s, e = self.new_state(), self.new_state()
            for c in alphabet:
                if c not in node[1]:
                    self.add(s, c, e)
            return s, e
        if tag == "wildcard":
            s, e = self.new_state(), self.new_state()
            for c in alphabet:
                self.add(s, c, e)
            return s, e
        if tag == "concat":
            s1, e1 = self.build(node[1], alphabet)
            s2, e2 = self.build(node[2], alphabet)
            self.add(e1, EPSILON, s2)
            return s1, e2
        if tag == "union":
            s, e = self.new_state(), self.new_state()
            s1, e1 = self.build(node[1], alphabet)
            s2, e2 = self.build(node[2], alphabet)
            self.add(s, EPSILON, s1)
            self.add(s, EPSILON, s2)
            self.add(e1, EPSILON, e)
            self.add(e2, EPSILON, e)
            return s, e
        if tag == "star":
            s, e = self.new_state(), self.new_state()
            s1, e1 = self.build(node[1], alphabet)
            self.add(s, EPSILON, s1)
            self.add(s, EPSILON, e)
            self.add(e1, EPSILON, s1)
            self.add(e1, EPSILON, e)
            return s, e
        if tag == "plus":
            s1, e1 = self.build(node[1], alphabet)
            s2, e2 = self.build(node[1], alphabet)
            e = self.new_state()
            self.add(e1, EPSILON, s2)
            self.add(e2, EPSILON, s2)
            self.add(e2, EPSILON, e)
            self.add(e1, EPSILON, e)
            return s1, e
        if tag == "opt":
            s, e = self.new_state(), self.new_state()
            s1, e1 = self.build(node[1], alphabet)
            self.add(s, EPSILON, s1)
            self.add(s, EPSILON, e)
            self.add(e1, EPSILON, e)
            return s, e
        raise RegexError(f"Simpul AST tidak dikenal: {tag}")


def compile_regex(pattern):
    ast = _RegexParser(pattern).parse()
    alphabet = set()
    _collect_alphabet(ast, alphabet)
    if not alphabet:
        alphabet = set("abcdefghijklmnopqrstuvwxyz0123456789")
    builder = _ThompsonBuilder()
    start, accept = builder.build(ast, alphabet)
    nfa = {
        "states": sorted(builder.states),
        "alphabet": sorted(alphabet),
        "start": start,
        "finals": [accept],
        "transitions": builder.transitions,
        "type": "NFA",
    }
    dfa_json, _steps = nfa_to_dfa(nfa)
    return nfa, dfa_json


def regex_to_right_linear_grammar(dfa_json):
    """Mengubah DFA hasil kompilasi regex menjadi tata bahasa reguler (linear kanan)."""
    name_map = {s: f"A{idx}" for idx, s in enumerate(dfa_json["states"])}
    lines = []
    productions = OrderedDict()
    for s in dfa_json["states"]:
        productions[name_map[s]] = []
    for t in dfa_json["transitions"]:
        productions[name_map[t["from"]]].append(f"{t['symbol']} {name_map[t['to'][0]]}")
    for s in dfa_json["finals"]:
        productions[name_map[s]].append("ε")
    for nt, alts in productions.items():
        if alts:
            lines.append(f"{nt} → " + " | ".join(alts))
    start_line = f"S = {name_map[dfa_json['start']]}"
    return [start_line] + lines


# BAGIAN 4: GRAMMAR BEBAS KONTEKS (CFG).
# Grammar = dict {start, nonterminals, terminals, productions}; diparsing di parse_cfg.

class GrammarError(Exception):
    pass


def parse_cfg(text):
    productions = OrderedDict()
    order = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "->" not in line:
            raise GrammarError(f"Baris {lineno} tidak memiliki tanda '->': '{raw_line.strip()}'")
        lhs, rhs = line.split("->", 1)
        lhs = lhs.strip()
        if not lhs:
            raise GrammarError(f"Baris {lineno}: ruas kiri (nonterminal) kosong.")
        if lhs not in productions:
            productions[lhs] = []
            order.append(lhs)
        for alt in rhs.split("|"):
            alt = alt.strip()
            if alt.lower() in EPSILON_ALIASES or alt == "":
                productions[lhs].append([])
            else:
                productions[lhs].append(alt.split())
    if not productions:
        raise GrammarError("Grammar tidak boleh kosong.")
    nonterminals = set(order)
    terminals = set()
    for alts in productions.values():
        for alt in alts:
            for sym in alt:
                if sym not in nonterminals:
                    terminals.add(sym)
    return {
        "start": order[0], "nonterminals": nonterminals, "terminals": terminals,
        "productions": productions, "order": order,
    }


def format_grammar(grammar, order=None):
    lines = []
    keys = order if order is not None else grammar.get("order") or list(grammar["productions"].keys())
    for nt in keys:
        alts = grammar["productions"].get(nt, [])
        if not alts:
            continue
        rendered = []
        for alt in alts:
            rendered.append(" ".join(alt) if alt else "ε")
        lines.append(f"{nt} → " + " | ".join(rendered))
    return lines


def clone_grammar(grammar):
    return {
        "start": grammar["start"],
        "nonterminals": set(grammar["nonterminals"]),
        "terminals": set(grammar["terminals"]),
        "productions": {k: [list(a) for a in v] for k, v in grammar["productions"].items()},
        "order": list(grammar.get("order") or grammar["productions"].keys()),
    }


# Tiap langkah CNF jadi fungsi terpisah agar mudah dites satu-satu.
# Urutan sesuai textbook: START -> DEL (nullable) -> UNIT -> TERM+BIN.

def cnf_step_start(grammar):
    g = clone_grammar(grammar)
    old_start = g["start"]
    new_start = old_start + "0"
    while new_start in g["nonterminals"]:
        new_start += "0"
    g["nonterminals"].add(new_start)
    g["productions"][new_start] = [[old_start]]
    g["order"] = [new_start] + g["order"]
    g["start"] = new_start
    return g


def cnf_step_remove_epsilon(grammar):
    g = clone_grammar(grammar)
    prods = g["productions"]
    nullable = set()
    changed = True
    while changed:
        changed = False
        for nt, alts in prods.items():
            if nt in nullable:
                continue
            for alt in alts:
                if all(s in nullable for s in alt):
                    nullable.add(nt)
                    changed = True
                    break

    new_prods = {nt: [] for nt in prods}
    for nt, alts in prods.items():
        seen = set()
        for alt in alts:
            if len(alt) == 0:
                continue
            idxs = [i for i, s in enumerate(alt) if s in nullable]
            for r in range(len(idxs) + 1):
                for combo in itertools.combinations(idxs, r):
                    new_alt = [s for i, s in enumerate(alt) if i not in combo]
                    if len(new_alt) == 0:
                        continue
                    tup = tuple(new_alt)
                    if tup not in seen:
                        seen.add(tup)
                        new_prods[nt].append(list(new_alt))
    if g["start"] in nullable:
        new_prods[g["start"]].append([])
    g["productions"] = new_prods
    return g, nullable


def cnf_step_remove_unit(grammar):
    g = clone_grammar(grammar)
    prods = g["productions"]
    nts = g["nonterminals"]
    unit_pairs = {nt: {nt} for nt in nts}
    changed = True
    while changed:
        changed = False
        for a in nts:
            for b in list(unit_pairs[a]):
                for alt in prods.get(b, []):
                    if len(alt) == 1 and alt[0] in nts and alt[0] not in unit_pairs[a]:
                        unit_pairs[a].add(alt[0])
                        changed = True
    new_prods = {nt: [] for nt in nts}
    for a in nts:
        seen = set()
        for b in unit_pairs[a]:
            for alt in prods.get(b, []):
                if len(alt) == 1 and alt[0] in nts:
                    continue
                tup = tuple(alt)
                if tup not in seen:
                    seen.add(tup)
                    new_prods[a].append(list(alt))
    g["productions"] = new_prods
    return g


def cnf_step_remove_useless(grammar):
    g = clone_grammar(grammar)
    prods = g["productions"]
    nts = g["nonterminals"]

    generating = set()
    changed = True
    while changed:
        changed = False
        for nt, alts in prods.items():
            if nt in generating:
                continue
            for alt in alts:
                if all((s not in nts) or (s in generating) for s in alt):
                    generating.add(nt)
                    changed = True
                    break
    reachable = {g["start"]}
    stack = [g["start"]]
    while stack:
        cur = stack.pop()
        for alt in prods.get(cur, []):
            for s in alt:
                if s in nts and s not in reachable:
                    reachable.add(s)
                    stack.append(s)

    keep = generating & reachable
    keep.add(g["start"])
    new_prods = {}
    for nt in keep:
        new_alts = []
        for alt in prods.get(nt, []):
            if all((s not in nts) or (s in keep) for s in alt):
                new_alts.append(alt)
        new_prods[nt] = new_alts
    g["nonterminals"] = keep
    g["productions"] = new_prods
    g["order"] = [nt for nt in g["order"] if nt in keep]
    return g


def _sanitize_terminal_name(t):
    mapping = {"+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH",
               "(": "LP", ")": "RP"}
    return mapping.get(t, "".join(ch if ch.isalnum() else "_" for ch in t).upper())


def cnf_step_term_bin(grammar):
    g = clone_grammar(grammar)
    original_nts = set(g["nonterminals"])
    prods = g["productions"]
    nts = set(g["nonterminals"])
    term_map = {}
    counter = {"n": 0}
    new_prods = defaultdict(list)
    extra_order = []

    def get_term_nt(t):
        if t in term_map:
            return term_map[t]
        base = f"T_{_sanitize_terminal_name(t)}"
        name = base
        i = 1
        while name in nts:
            name = f"{base}{i}"
            i += 1
        nts.add(name)
        term_map[t] = name
        extra_order.append(name)
        return name

    def new_nt(prefix):
        counter["n"] += 1
        name = f"{prefix}{counter['n']}"
        while name in nts:
            counter["n"] += 1
            name = f"{prefix}{counter['n']}"
        nts.add(name)
        extra_order.append(name)
        return name

    for nt in g["order"]:
        for alt in prods.get(nt, []):
            if len(alt) == 0:
                new_prods[nt].append([])
                continue
            if len(alt) == 1:
                new_prods[nt].append(list(alt))
                continue
            replaced = [s if s in original_nts else get_term_nt(s) for s in alt]
            if len(replaced) == 2:
                new_prods[nt].append(replaced)
            else:
                prev = nt
                for i in range(len(replaced) - 2):
                    mid = new_nt(f"{nt}X")
                    new_prods[prev].append([replaced[i], mid])
                    prev = mid
                new_prods[prev].append([replaced[-2], replaced[-1]])

    for t, nt in term_map.items():
        new_prods[nt].append([t])

    g["productions"] = dict(new_prods)
    g["nonterminals"] = nts
    g["order"] = g["order"] + extra_order
    return g


def convert_to_cnf(grammar_text):
    original = parse_cfg(grammar_text)
    steps = [{"title": "Grammar Awal", "grammar": format_grammar(original)}]

    g1 = cnf_step_start(original)
    steps.append({"title": "Langkah START - tambahkan simbol awal baru", "grammar": format_grammar(g1)})

    g2, nullable = cnf_step_remove_epsilon(g1)
    steps.append({
        "title": "Langkah DEL - hilangkan produksi ε (nullable: " +
                 (", ".join(sorted(nullable)) if nullable else "tidak ada") + ")",
        "grammar": format_grammar(g2),
    })

    g3 = cnf_step_remove_unit(g2)
    steps.append({"title": "Langkah UNIT - hilangkan produksi tunggal (A → B)", "grammar": format_grammar(g3)})

    g4 = cnf_step_remove_useless(g3)
    steps.append({"title": "Hilangkan simbol useless (tidak generating / tidak reachable)",
                  "grammar": format_grammar(g4)})

    g5 = cnf_step_term_bin(g4)
    steps.append({"title": "Langkah TERM + BIN - bentuk akhir Chomsky Normal Form", "grammar": format_grammar(g5)})

    return original, g5, steps


# GNF (bonus): produksi bisa meledak untuk grammar besar (saling substitusi).
# convert_to_gnf dibungkus try/except - gagal berarti pesan jujur, bukan hasil salah.

def convert_to_gnf(cnf_grammar):
    """Best-effort GNF dari grammar CNF; return (berhasil, grammar_or_none, pesan)."""
    try:
        g = clone_grammar(cnf_grammar)
        order = [nt for nt in g["order"] if any(g["productions"].get(nt))]
        if not order:
            return False, None, "Grammar tidak memiliki produksi yang dapat dikonversi."
        prods = {nt: [list(a) for a in g["productions"].get(nt, [])] for nt in order}
        n = len(order)
        idx = {nt: i for i, nt in enumerate(order)}
        counter = [0]

        def fresh(prefix):
            counter[0] += 1
            name = f"{prefix}Z{counter[0]}"
            while name in prods:
                counter[0] += 1
                name = f"{prefix}Z{counter[0]}"
            return name

        for i in range(n):
            ai = order[i]
            for j in range(i):
                aj = order[j]
                new_alts = []
                for alt in prods[ai]:
                    if alt and alt[0] == aj:
                        rest = alt[1:]
                        for sub in prods[aj]:
                            new_alts.append(sub + rest)
                    else:
                        new_alts.append(alt)
                prods[ai] = new_alts

            direct = [a for a in prods[ai] if a and a[0] == ai]
            indirect = [a for a in prods[ai] if not (a and a[0] == ai)]
            if direct:
                z = fresh(ai)
                new_indirect = []
                for a in indirect:
                    new_indirect.append(a + [z])
                    new_indirect.append(a)
                new_direct_z = []
                for a in direct:
                    tail = a[1:]
                    new_direct_z.append(tail + [z])
                    new_direct_z.append(tail)
                prods[ai] = new_indirect
                prods[z] = new_direct_z
                order.append(z)
                idx[z] = len(order) - 1

        original_set = set(order[:n])
        for i in range(n - 1, -1, -1):
            ai = order[i]
            changed = True
            guard = 0
            while changed and guard < 200:
                changed = False
                guard += 1
                new_alts = []
                for alt in prods[ai]:
                    head = alt[0] if alt else None
                    if head is not None and head in idx and idx[head] > i:
                        rest = alt[1:]
                        for sub in prods[head]:
                            new_alts.append(sub + rest)
                        changed = True
                    else:
                        new_alts.append(alt)
                prods[ai] = new_alts

        for z_nt in order[n:]:
            changed = True
            guard = 0
            while changed and guard < 200:
                changed = False
                guard += 1
                new_alts = []
                for alt in prods[z_nt]:
                    head = alt[0] if alt else None
                    if head is not None and head in original_set:
                        rest = alt[1:]
                        for sub in prods[head]:
                            new_alts.append(sub + rest)
                        changed = True
                    else:
                        new_alts.append(alt)
                prods[z_nt] = new_alts

        all_nts = set(prods.keys())
        for nt, alts in prods.items():
            for alt in alts:
                if alt and alt[0] in all_nts:
                    return False, None, ("GNF tidak dapat diselesaikan secara utuh untuk grammar ini "
                                          "karena terdapat rekursi tak langsung yang kompleks. "
                                          "Fitur GNF bersifat eksperimental (bonus).")

        result = {
            "start": g["start"], "nonterminals": set(prods.keys()),
            "terminals": g["terminals"], "productions": prods, "order": list(prods.keys()),
        }
        return True, result, "Konversi GNF berhasil."
    except Exception as exc:  # pragma: no cover - safety net utk grammar tak lazim
        return False, None, f"GNF tidak tersedia untuk grammar ini ({exc})."


def _starts_with_terminal_or_self(sym, prods, nts):
    for alt in prods.get(sym, []):
        if alt and alt[0] not in nts:
            return True
    return False


# CYK butuh grammar CNF (PDA generik selalu panggil convert_to_cnf dulu).
# table[(i, l)] = himpunan nonterminal yang bisa menurunkan substring sepanjang l dari indeks i.

def cyk_parse(cnf_grammar, terminal_seq):
    prods = cnf_grammar["productions"]
    n = len(terminal_seq)
    table = {}

    if n == 0:
        accepted = [] in prods.get(cnf_grammar["start"], [])
        return accepted, table, None

    for i in range(n):
        table[(i, 1)] = {}
        for nt, alts in prods.items():
            for alt in alts:
                if len(alt) == 1 and alt[0] == terminal_seq[i]:
                    table[(i, 1)].setdefault(nt, ("term", terminal_seq[i]))

    for l in range(2, n + 1):
        for i in range(0, n - l + 1):
            table[(i, l)] = {}
            for k in range(1, l):
                left = table.get((i, k), {})
                right = table.get((i + k, l - k), {})
                if not left or not right:
                    continue
                for nt, alts in prods.items():
                    if nt in table[(i, l)]:
                        continue
                    for alt in alts:
                        if len(alt) == 2 and alt[0] in left and alt[1] in right:
                            table[(i, l)][nt] = ("split", k, alt[0], alt[1])
                            break

    accepted = cnf_grammar["start"] in table.get((0, n), {})
    tree = None
    if accepted:
        tree = _build_cyk_tree(table, cnf_grammar["start"], 0, n)
    return accepted, table, tree


def _build_cyk_tree(table, nt, i, l):
    info = table[(i, l)][nt]
    if info[0] == "term":
        return {"symbol": nt, "children": [{"symbol": info[1], "children": []}]}
    _, k, b, c = info
    left = _build_cyk_tree(table, b, i, k)
    right = _build_cyk_tree(table, c, i + k, l - k)
    return {"symbol": nt, "children": [left, right]}


def cyk_table_to_json(table, n):
    rows = []
    for l in range(1, n + 1):
        row = []
        for i in range(0, n - l + 1):
            cell = table.get((i, l), {})
            row.append(sorted(cell.keys()))
        rows.append(row)
    return rows


# Fungsi generik untuk pohon berbentuk {symbol, children}.
# Dipakai ulang oleh parser aritmatika (Bagian 5) dan hasil CYK (Bagian 4).

def tree_symbols(nodes):
    return [nd["symbol"] for nd in nodes]


def tree_to_leftmost_derivation(root):
    form = [root]
    derivations = [" ".join(tree_symbols(form))]
    guard = 0
    while any(nd["children"] for nd in form) and guard < 500:
        guard += 1
        for idx, nd in enumerate(form):
            if nd["children"]:
                form = form[:idx] + nd["children"] + form[idx + 1:]
                break
        derivations.append(" ".join(tree_symbols(form)))
    return derivations


def tree_to_rightmost_derivation(root):
    form = [root]
    derivations = [" ".join(tree_symbols(form))]
    guard = 0
    while any(nd["children"] for nd in form) and guard < 500:
        guard += 1
        for idx in range(len(form) - 1, -1, -1):
            if form[idx]["children"]:
                form = form[:idx] + form[idx]["children"] + form[idx + 1:]
                break
        derivations.append(" ".join(tree_symbols(form)))
    return derivations


def tree_leaves(root):
    if not root["children"]:
        return [root["symbol"]]
    leaves = []
    for c in root["children"]:
        leaves.extend(tree_leaves(c))
    return leaves


def tree_to_pda_trace(root):
    actions = []

    def visit(node):
        if not node["children"]:
            actions.append({"action": "SHIFT", "symbol": node["symbol"]})
        else:
            for c in node["children"]:
                visit(c)
            prod = f"{node['symbol']} → " + " ".join(c["symbol"] for c in node["children"])
            actions.append({"action": "REDUCE", "symbol": node["symbol"], "count": len(node["children"]),
                             "production": prod})

    visit(root)
    remaining = tree_leaves(root)
    stack = []
    steps = []
    for act in actions:
        if act["action"] == "SHIFT":
            stack.append(act["symbol"])
            remaining = remaining[1:]
            desc = f"SHIFT '{act['symbol']}'"
        else:
            for _ in range(act["count"]):
                stack.pop()
            stack.append(act["symbol"])
            desc = f"REDUCE dengan {act['production']}"
        steps.append({"stack": list(stack), "remaining": list(remaining), "action": desc})
    return steps


# BAGIAN 5: PARSER EKSPRESI ARITMATIKA.
# Grammar E/T/F left-recursive -> dipakai teknik precedence climbing, pohon hasilnya tetap sama.

class ParseError(Exception):
    pass


ARITHMETIC_GRAMMAR_TEXT = """E -> E + T | E - T | T
T -> T * F | T / F | F
F -> ( E ) | id"""


def parse_arithmetic_expression(expr):
    tokens, _traces = tokenize_expression(expr)
    error_tok = next((t for t in tokens if t["type"] == "ERROR"), None)
    if error_tok:
        raise ParseError(f"Karakter tidak dikenali '{error_tok['lexeme']}' pada posisi {error_tok['pos']}.")
    if not tokens:
        raise ParseError("Input ekspresi kosong.")

    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def advance():
        tok = tokens[pos[0]]
        pos[0] += 1
        return tok

    def parse_F():
        tok = peek()
        if tok is None:
            raise ParseError("Ekspresi tidak lengkap, sebuah nilai atau '(' diharapkan.")
        if tok["type"] == "NUMBER":
            advance()
            return {"symbol": "F", "children": [{"symbol": tok["lexeme"], "children": []}]}
        if tok["type"] == "LPAREN":
            advance()
            inner = parse_E()
            tok2 = peek()
            if tok2 is None or tok2["type"] != "RPAREN":
                raise ParseError("Tanda kurung tutup ')' diharapkan tetapi tidak ditemukan.")
            advance()
            return {"symbol": "F", "children": [
                {"symbol": "(", "children": []}, inner, {"symbol": ")", "children": []}]}
        raise ParseError(f"Token tak terduga '{tok['lexeme']}' pada posisi {tok['pos']}.")

    def parse_T():
        node = {"symbol": "T", "children": [parse_F()]}
        while True:
            tok = peek()
            if tok and tok["type"] in ("STAR", "SLASH"):
                op = advance()
                right = parse_F()
                node = {"symbol": "T", "children": [node, {"symbol": op["lexeme"], "children": []}, right]}
            else:
                break
        return node

    def parse_E():
        node = {"symbol": "E", "children": [parse_T()]}
        while True:
            tok = peek()
            if tok and tok["type"] in ("PLUS", "MINUS"):
                op = advance()
                right = parse_T()
                node = {"symbol": "E", "children": [node, {"symbol": op["lexeme"], "children": []}, right]}
            else:
                break
        return node

    tree = parse_E()
    if pos[0] != len(tokens):
        tok = tokens[pos[0]]
        raise ParseError(f"Token berlebih '{tok['lexeme']}' pada posisi {tok['pos']}.")
    return tree, tokens


def evaluate_tree(node):
    if not node["children"]:
        try:
            return float(node["symbol"])
        except ValueError:
            return None
    if node["symbol"] == "F":
        if len(node["children"]) == 1:
            return evaluate_tree(node["children"][0])
        return evaluate_tree(node["children"][1])
    if len(node["children"]) == 1:
        return evaluate_tree(node["children"][0])
    left = evaluate_tree(node["children"][0])
    op = node["children"][1]["symbol"]
    right = evaluate_tree(node["children"][2])
    if left is None or right is None:
        return None
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return left / right if right != 0 else None
    return None


# ROUTES FLASK: terima JSON, panggil fungsi di atas, balas JSON.
# Error input pengguna ditangkap dan dibalas sebagai pesan jelas, bukan 500.

@app.route("/")
def home():
    return render_template("home.html", active="home")


@app.route("/tokenizer")
def tokenizer_page():
    return render_template("tokenizer.html", active="tokenizer")


@app.route("/regex")
def regex_page():
    return render_template("regex.html", active="regex")


@app.route("/parser")
def parser_page():
    return render_template("parser.html", active="parser")


@app.route("/cnf")
def cnf_page():
    return render_template("cnf.html", active="cnf")


def _err(msg, code=400):
    return jsonify({"error": msg}), code


@app.route("/api/tokenize", methods=["POST"])
def api_tokenize():
    data = request.get_json(force=True, silent=True) or {}
    expr = data.get("expression", "")
    if not expr.strip():
        return _err("Masukkan ekspresi terlebih dahulu.")
    tokens, traces = tokenize_expression(expr)
    return jsonify({
        "tokens": tokens, "traces": traces,
        "automaton": automaton_to_json(TOKENIZER_AUTOMATON),
        "tags": TOKEN_TAGS,
    })


@app.route("/api/fsa/simulate", methods=["POST"])
def api_fsa_simulate():
    data = request.get_json(force=True, silent=True) or {}
    try:
        automaton = parse_fsa_definition(data.get("definition", ""))
        result = simulate_fsa(automaton, data.get("input", ""))
    except AutomataError as e:
        return _err(str(e))
    return jsonify({**result, "automaton": automaton_to_json(automaton)})


@app.route("/api/fsa/nfa2dfa", methods=["POST"])
def api_fsa_nfa2dfa():
    data = request.get_json(force=True, silent=True) or {}
    try:
        automaton = parse_fsa_definition(data.get("definition", ""))
        dfa_json, steps = nfa_to_dfa(automaton)
    except AutomataError as e:
        return _err(str(e))
    return jsonify({
        "nfa": automaton_to_json(automaton), "dfa": dfa_json, "steps": steps,
    })


@app.route("/api/fsa/moore", methods=["POST"])
def api_fsa_moore():
    data = request.get_json(force=True, silent=True) or {}
    try:
        machine = parse_output_definition(data.get("definition", ""), "moore")
        result = simulate_output_machine(machine, data.get("input", ""))
    except AutomataError as e:
        return _err(str(e))
    return jsonify({**result, "machine": output_machine_to_json(machine)})


@app.route("/api/fsa/mealy", methods=["POST"])
def api_fsa_mealy():
    data = request.get_json(force=True, silent=True) or {}
    try:
        machine = parse_output_definition(data.get("definition", ""), "mealy")
        result = simulate_output_machine(machine, data.get("input", ""))
    except AutomataError as e:
        return _err(str(e))
    return jsonify({**result, "machine": output_machine_to_json(machine)})


@app.route("/api/regex/compile", methods=["POST"])
def api_regex_compile():
    data = request.get_json(force=True, silent=True) or {}
    pattern = data.get("pattern", "")
    try:
        nfa, dfa_json = compile_regex(pattern)
        grammar_lines = regex_to_right_linear_grammar(dfa_json)
    except RegexError as e:
        return _err(str(e))
    return jsonify({
        "nfa": automaton_to_json(nfa), "dfa": dfa_json, "grammar": grammar_lines,
    })


@app.route("/api/regex/test", methods=["POST"])
def api_regex_test():
    data = request.get_json(force=True, silent=True) or {}
    pattern = data.get("pattern", "")
    test_input = data.get("input", "")
    try:
        _nfa, dfa_json = compile_regex(pattern)
        dummy = {
            "states": dfa_json["states"], "alphabet": dfa_json["alphabet"],
            "start": dfa_json["start"], "finals": dfa_json["finals"],
            "transitions": defaultdict(set),
        }
        for t in dfa_json["transitions"]:
            dummy["transitions"][(t["from"], t["symbol"])] |= set(t["to"])
        result = simulate_fsa(dummy, test_input)
    except RegexError as e:
        return _err(str(e))
    return jsonify({**result, "dfa": dfa_json})


@app.route("/api/cfg/arithmetic/parse", methods=["POST"])
def api_cfg_arithmetic_parse():
    data = request.get_json(force=True, silent=True) or {}
    expr = data.get("expression", "")
    try:
        tree, tokens = parse_arithmetic_expression(expr)
    except ParseError as e:
        return _err(str(e))
    value = evaluate_tree(tree)
    return jsonify({
        "tree": tree, "tokens": tokens,
        "leftmost": tree_to_leftmost_derivation(tree),
        "rightmost": tree_to_rightmost_derivation(tree),
        "pda_trace": tree_to_pda_trace(tree),
        "grammar": ARITHMETIC_GRAMMAR_TEXT,
        "value": value,
        "accepted": True,
    })


@app.route("/api/cfg/generic/parse", methods=["POST"])
def api_cfg_generic_parse():
    data = request.get_json(force=True, silent=True) or {}
    grammar_text = data.get("grammar", "")
    input_text = data.get("input", "")
    terminal_seq = input_text.split()
    try:
        _original, cnf, steps = convert_to_cnf(grammar_text)
        accepted, table, tree = cyk_parse(cnf, terminal_seq)
    except GrammarError as e:
        return _err(str(e))

    response = {
        "cnf_grammar": format_grammar(cnf),
        "cnf_steps": steps,
        "cyk_table": cyk_table_to_json(table, len(terminal_seq)) if terminal_seq else [],
        "terminal_seq": terminal_seq,
        "accepted": accepted,
        "tree": None, "leftmost": [], "rightmost": [], "pda_trace": [],
    }
    if accepted and tree is not None:
        response["tree"] = tree
        response["leftmost"] = tree_to_leftmost_derivation(tree)
        response["rightmost"] = tree_to_rightmost_derivation(tree)
        response["pda_trace"] = tree_to_pda_trace(tree)
    return jsonify(response)


@app.route("/api/cfg/cnf", methods=["POST"])
def api_cfg_cnf():
    data = request.get_json(force=True, silent=True) or {}
    grammar_text = data.get("grammar", "")
    try:
        _original, cnf, steps = convert_to_cnf(grammar_text)
    except GrammarError as e:
        return _err(str(e))
    gnf_ok, gnf_grammar, gnf_msg = convert_to_gnf(cnf)
    return jsonify({
        "steps": steps,
        "cnf_grammar": format_grammar(cnf),
        "gnf": {
            "success": gnf_ok,
            "grammar": format_grammar(gnf_grammar) if gnf_ok else None,
            "message": gnf_msg,
        },
    })


@app.route("/api/pipeline/run", methods=["POST"])
def api_pipeline_run():
    data = request.get_json(force=True, silent=True) or {}
    expr = data.get("expression", "")
    tokens, traces = tokenize_expression(expr)
    error_tok = next((t for t in tokens if t["type"] == "ERROR"), None)
    stage_lexer_ok = error_tok is None and len(tokens) > 0
    tree = None
    value = None
    stage_parser_ok = False
    parse_message = ""
    if stage_lexer_ok:
        try:
            tree, _tok = parse_arithmetic_expression(expr)
            value = evaluate_tree(tree)
            stage_parser_ok = True
        except ParseError as e:
            parse_message = str(e)
    else:
        parse_message = (f"Karakter tidak dikenali '{error_tok['lexeme']}'"
                          if error_tok else "Tidak ada token yang ditemukan.")
    return jsonify({
        "tokens": tokens,
        "lexer_ok": stage_lexer_ok,
        "parser_ok": stage_parser_ok,
        "message": parse_message,
        "value": value,
        "token_count": len(tokens),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
