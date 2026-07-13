# -*- coding: utf-8 -*-
"""
Test suite Otomatika
======================
Berisi 41 test case (40 inti + 1 regresi guard GNF) yang dapat dijalankan dengan:

    python -m unittest tests.test_app -v

Hasil dari file ini dapat dijadikan bahan Bab V (Pengujian & Analisis)
pada laporan ilmiah: setiap fungsi tes di bawah merepresentasikan satu
baris pada tabel hasil pengujian.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as calcparser  # noqa: E402


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        calcparser.app.testing = True
        self.client = calcparser.app.test_client()

    def post(self, url, payload):
        return self.client.post(url, json=payload)


# MODUL 1 : FINITE STATE AUTOMATA (10 test case)
class TestModul1FiniteStateAutomata(BaseTestCase):

    def test_01_tokenize_ekspresi_valid(self):
        resp = self.post("/api/tokenize", {"expression": "12 + 3 * (4 - 1)"})
        data = resp.get_json()
        types = [t["type"] for t in data["tokens"]]
        self.assertEqual(types, ["NUMBER", "PLUS", "NUMBER", "STAR", "LPAREN",
                                  "NUMBER", "MINUS", "NUMBER", "RPAREN"])

    def test_02_tokenize_bilangan_desimal(self):
        resp = self.post("/api/tokenize", {"expression": "4.5"})
        data = resp.get_json()
        self.assertEqual(data["tokens"][0]["lexeme"], "4.5")

    def test_03_tokenize_karakter_tidak_valid(self):
        tokens, _ = calcparser.tokenize_expression("12 + x")
        self.assertTrue(any(t["type"] == "ERROR" for t in tokens))

    def test_04_dfa_kustom_diterima(self):
        automaton = calcparser.parse_fsa_definition(
            "states: q0,q1\nalphabet: 0,1\nstart: q0\nfinal: q0\n"
            "q0 0 q0\nq0 1 q1\nq1 0 q1\nq1 1 q0")
        result = calcparser.simulate_fsa(automaton, "1100")
        self.assertTrue(result["accepted"])  # jumlah 1 genap

    def test_05_dfa_kustom_ditolak(self):
        automaton = calcparser.parse_fsa_definition(
            "states: q0,q1\nalphabet: 0,1\nstart: q0\nfinal: q0\n"
            "q0 0 q0\nq0 1 q1\nq1 0 q1\nq1 1 q0")
        result = calcparser.simulate_fsa(automaton, "111")
        self.assertFalse(result["accepted"])  # jumlah 1 ganjil

    def test_06_deteksi_tipe_nfa(self):
        automaton = calcparser.parse_fsa_definition(
            "states: q0,q1,q2\nalphabet: a,b\nstart: q0\nfinal: q2\n"
            "q0 a q0\nq0 a q1\nq1 b q2")
        self.assertEqual(automaton["type"], "NFA")

    def test_07_konversi_nfa_ke_dfa(self):
        automaton = calcparser.parse_fsa_definition(
            "states: q0,q1,q2\nalphabet: a,b\nstart: q0\nfinal: q2\n"
            "q0 a q0\nq0 a q1\nq0 b q0\nq1 b q2")
        dfa_json, steps = calcparser.nfa_to_dfa(automaton)
        self.assertEqual(dfa_json["type"], "DFA")
        self.assertGreater(len(steps), 0)

    def test_08_moore_machine_output(self):
        machine = calcparser.parse_output_definition(
            "states: q0,q1\nalphabet: 0,1\nstart: q0\noutputs: q0=GENAP, q1=GANJIL\n"
            "q0 0 q0\nq0 1 q1\nq1 0 q1\nq1 1 q0", "moore")
        result = calcparser.simulate_output_machine(machine, "011")
        self.assertEqual(len(result["trace"]), 4)  # state awal + 3 simbol dibaca
        self.assertEqual(result["final_state"], "q0")

    def test_09_mealy_machine_output(self):
        machine = calcparser.parse_output_definition(
            "states: q0,q1\nalphabet: 0,1\nstart: q0\n"
            "q0 0 q0 GENAP\nq0 1 q1 GANJIL\nq1 0 q1 GANJIL\nq1 1 q0 GENAP", "mealy")
        result = calcparser.simulate_output_machine(machine, "11")
        self.assertEqual(result["final_state"], "q0")

    def test_10_definisi_mesin_tidak_valid_ditolak(self):
        with self.assertRaises(calcparser.AutomataError):
            calcparser.parse_fsa_definition("")


# MODUL 2 : REGULAR EXPRESSION (10 test case)
class TestModul2RegularExpression(BaseTestCase):

    def _accepted(self, pattern, text):
        _nfa, dfa = calcparser.compile_regex(pattern)
        from collections import defaultdict
        dummy = {"states": dfa["states"], "alphabet": dfa["alphabet"],
                 "start": dfa["start"], "finals": dfa["finals"], "transitions": defaultdict(set)}
        for t in dfa["transitions"]:
            dummy["transitions"][(t["from"], t["symbol"])] |= set(t["to"])
        return calcparser.simulate_fsa(dummy, text)["accepted"]

    def test_11_literal_cocok(self):
        self.assertTrue(self._accepted("abc", "abc"))

    def test_12_literal_tidak_cocok(self):
        self.assertFalse(self._accepted("abc", "abd"))

    def test_13_union(self):
        self.assertTrue(self._accepted("a|b", "b"))

    def test_14_kleene_star(self):
        self.assertTrue(self._accepted("a*", ""))
        self.assertTrue(self._accepted("a*", "aaaa"))

    def test_15_plus_minimal_satu(self):
        self.assertFalse(self._accepted("a+", ""))
        self.assertTrue(self._accepted("a+", "a"))

    def test_16_opsional(self):
        self.assertTrue(self._accepted("colou?r", "color"))
        self.assertTrue(self._accepted("colou?r", "colour"))

    def test_17_character_class(self):
        self.assertTrue(self._accepted("[0-9]+", "2026"))
        self.assertFalse(self._accepted("[0-9]+", "20a6"))

    def test_18_shorthand_digit(self):
        self.assertTrue(self._accepted(r"\d\d?:\d\d", "9:30"))

    def test_19_pola_bilangan_desimal(self):
        self.assertTrue(self._accepted(r"[0-9]+(\.[0-9]+)?", "12.5"))
        self.assertTrue(self._accepted(r"[0-9]+(\.[0-9]+)?", "12"))

    def test_20_grammar_linear_kanan_terbentuk(self):
        _nfa, dfa = calcparser.compile_regex("ab")
        grammar = calcparser.regex_to_right_linear_grammar(dfa)
        self.assertTrue(any("ε" in line for line in grammar))


# MODUL 3 : PUSHDOWN AUTOMATA & CFG (10 test case)
class TestModul3PdaCfg(BaseTestCase):

    def test_21_penjumlahan_sederhana(self):
        tree, _ = calcparser.parse_arithmetic_expression("1 + 2")
        self.assertEqual(calcparser.evaluate_tree(tree), 3.0)

    def test_22_precedence_perkalian(self):
        tree, _ = calcparser.parse_arithmetic_expression("2 + 3 * 4")
        self.assertEqual(calcparser.evaluate_tree(tree), 14.0)

    def test_23_kurung_mengubah_urutan(self):
        tree, _ = calcparser.parse_arithmetic_expression("(2 + 3) * 4")
        self.assertEqual(calcparser.evaluate_tree(tree), 20.0)

    def test_24_pembagian_dan_desimal(self):
        tree, _ = calcparser.parse_arithmetic_expression("9 / 2")
        self.assertEqual(calcparser.evaluate_tree(tree), 4.5)

    def test_25_ekspresi_bersarang(self):
        tree, _ = calcparser.parse_arithmetic_expression("12 + 3 * (4 - 1)")
        self.assertEqual(calcparser.evaluate_tree(tree), 21.0)

    def test_26_operator_ganda_ditolak(self):
        with self.assertRaises(calcparser.ParseError):
            calcparser.parse_arithmetic_expression("1 + * 2")

    def test_27_kurung_tidak_seimbang_ditolak(self):
        with self.assertRaises(calcparser.ParseError):
            calcparser.parse_arithmetic_expression("(1 + 2")

    def test_28_pda_trace_seimbang(self):
        tree, _ = calcparser.parse_arithmetic_expression("1 + 2")
        steps = calcparser.tree_to_pda_trace(tree)
        self.assertEqual(steps[-1]["stack"], ["E"])
        self.assertEqual(steps[-1]["remaining"], [])

    def test_29_cfg_generik_anbn_diterima(self):
        _orig, cnf, _steps = calcparser.convert_to_cnf("S -> a S b | a b")
        accepted, _t, _tree = calcparser.cyk_parse(cnf, ["a", "a", "b", "b"])
        self.assertTrue(accepted)

    def test_30_cfg_generik_anbn_ditolak(self):
        _orig, cnf, _steps = calcparser.convert_to_cnf("S -> a S b | a b")
        accepted, _t, _tree = calcparser.cyk_parse(cnf, ["a", "b", "b"])
        self.assertFalse(accepted)


# MODUL 4 : HIERARKI CHOMSKY & CNF (10 test case)
class TestModul4ChomskyCnf(BaseTestCase):

    def _assert_valid_cnf(self, cnf_grammar):
        for nt, alts in cnf_grammar["productions"].items():
            for alt in alts:
                if len(alt) == 0:
                    self.assertEqual(nt, cnf_grammar["start"], "produksi-ε hanya boleh pada start symbol")
                elif len(alt) == 1:
                    self.assertNotIn(alt[0], cnf_grammar["nonterminals"], "produksi tunggal harus terminal")
                elif len(alt) == 2:
                    self.assertIn(alt[0], cnf_grammar["nonterminals"])
                    self.assertIn(alt[1], cnf_grammar["nonterminals"])
                else:
                    self.fail("produksi CNF tidak boleh memiliki lebih dari 2 simbol di ruas kanan")

    def test_31_cnf_grammar_aritmatika_valid(self):
        _orig, cnf, _steps = calcparser.convert_to_cnf(calcparser.ARITHMETIC_GRAMMAR_TEXT)
        self._assert_valid_cnf(cnf)

    def test_32_cnf_anbn_valid(self):
        _orig, cnf, _steps = calcparser.convert_to_cnf("S -> a S b | a b")
        self._assert_valid_cnf(cnf)

    def test_33_deteksi_nullable(self):
        g1 = calcparser.cnf_step_start(calcparser.parse_cfg("S -> A B\nA -> a A | eps\nB -> b"))
        _g2, nullable = calcparser.cnf_step_remove_epsilon(g1)
        self.assertIn("A", nullable)

    def test_34_epsilon_start_dipertahankan(self):
        _orig, cnf, _steps = calcparser.convert_to_cnf("S -> A B\nA -> a A | eps\nB -> b B | eps")
        self.assertIn([], cnf["productions"].get(cnf["start"], []))

    def test_35_unit_production_dihilangkan(self):
        g = calcparser.parse_cfg("S -> A\nA -> a")
        g0 = calcparser.cnf_step_start(g)
        g1, _n = calcparser.cnf_step_remove_epsilon(g0)
        g2 = calcparser.cnf_step_remove_unit(g1)
        for alts in g2["productions"].values():
            for alt in alts:
                self.assertFalse(len(alt) == 1 and alt[0] in g2["nonterminals"])

    def test_36_simbol_useless_dihilangkan(self):
        g = calcparser.parse_cfg("S -> a\nX -> y")  # X tidak reachable dari S
        g0 = calcparser.cnf_step_start(g)
        g1, _n = calcparser.cnf_step_remove_epsilon(g0)
        g2 = calcparser.cnf_step_remove_unit(g1)
        g3 = calcparser.cnf_step_remove_useless(g2)
        self.assertNotIn("X", g3["nonterminals"])

    def test_37_binarisasi_produksi_panjang(self):
        _orig, cnf, _steps = calcparser.convert_to_cnf("S -> a b c d")
        self._assert_valid_cnf(cnf)

    def test_38_cyk_menggunakan_cnf_konsisten(self):
        _orig, cnf, _steps = calcparser.convert_to_cnf("S -> ( S ) S | eps")
        accepted, _t, _tree = calcparser.cyk_parse(cnf, ["(", ")", "(", ")"])
        self.assertTrue(accepted)

    def test_39_gnf_berhasil_untuk_grammar_sederhana(self):
        _orig, cnf, _steps = calcparser.convert_to_cnf("S -> a S b | a b")
        ok, gnf_grammar, _msg = calcparser.convert_to_gnf(cnf)
        self.assertTrue(ok)
        for alts in gnf_grammar["productions"].values():
            for alt in alts:
                if alt:
                    self.assertNotIn(alt[0], gnf_grammar["nonterminals"])

    def test_40_grammar_kosong_ditolak(self):
        with self.assertRaises(calcparser.GrammarError):
            calcparser.parse_cfg("")

    def test_41_gnf_besar_tetap_berhasil_dengan_catatan(self):
        _orig, cnf, _steps = calcparser.convert_to_cnf(calcparser.ARITHMETIC_GRAMMAR_TEXT)
        ok, grammar, msg = calcparser.convert_to_gnf(cnf)
        self.assertTrue(ok)
        self.assertIsNotNone(grammar)
        self.assertIn("substitusi berantai", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
