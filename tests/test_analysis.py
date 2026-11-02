import copy
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.cleaning import clean_pandas, clean_loop, load_and_validate
from analysis.forecast import predict, safety_stock, choose_methods
from analysis.inventory import abc_classes, simulate_item, simulate, risk_snapshot

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT/"config.json").read_text(encoding="utf-8"))


class CleaningTests(unittest.TestCase):
    def sample(self, rows):
        return pd.DataFrame(rows, columns=["Batch", "Medication", "MonthIndex", "Demand"])

    def test_standardizes_and_deduplicates(self):
        source = self.sample([[0, " m01 ", "1.0", "1,000"], [0, "M01", 1, 1000]])
        clean, log, _ = clean_pandas(source)
        self.assertEqual(clean.Demand.tolist(), [1000])
        self.assertEqual(log["duplicate_rows"], 1)
        self.assertEqual(source.iloc[0].Medication, " m01 ")

    def test_invalid_rows_are_not_zero(self):
        source = self.sample([[0, "M01", 1, ""], [0, "M02", 49, 3], [0, "M03", 1, -1], [0, "M04", 1, "1,2"]])
        clean, log, rejected = clean_pandas(source)
        self.assertEqual(len(clean), 0)
        self.assertEqual(len(rejected), 4)
        self.assertEqual(log["invalid_rows"], 4)

    def test_conflicting_keys_fail(self):
        with self.assertRaisesRegex(ValueError, "冲突"):
            clean_pandas(self.sample([[0,"M01",1,10],[0,"M01",1,11]]))

    def test_two_implementations_agree(self):
        source = self.sample([[0," m01 ",1,"3,000"],[0,"M02","2.0",0],[0,"M03",4,None],[0,"M01",1,3000],[1,"M01",1,4]])
        fast, log, _ = clean_pandas(source)
        slow, other = clean_loop(source)
        pd.testing.assert_frame_equal(fast, slow, check_dtype=False)
        self.assertEqual(log, other)


class CalculationTests(unittest.TestCase):
    def test_abc_threshold_and_zero(self):
        self.assertEqual(abc_classes({"a":80,"b":15,"c":5,"d":0}), {"a":"A","b":"B","c":"C","d":"C"})
        self.assertEqual(abc_classes({"a":0,"b":0}), {"a":"C","b":"C"})

    def test_abc_crossing_threshold(self):
        self.assertEqual(abc_classes({"a":90,"b":10}), {"a":"A","b":"B"})

    def test_forecasts_constant_and_zero(self):
        for method in ["mean12","mean6","mean3","ses","seasonal","tsb"]:
            self.assertEqual(predict([10]*36, method), 10)
            self.assertEqual(predict([0]*36, method), 0)

    def test_invalid_history_fails(self):
        with self.assertRaises(ValueError):
            predict([10,float("nan")], "mean3")

    def test_safety_stock_constant_is_zero(self):
        buffer, samples = safety_stock([10]*36, "mean12", 2, .95)
        self.assertEqual(buffer, 0)
        self.assertGreater(samples, 0)

    def test_safety_stock_two_period_error_by_hand(self):
        # 唯一可校准窗口：此前12月恒为10，随后2月合计50，误差30。
        self.assertEqual(safety_stock([10]*12+[20,30], "mean12", 2, .95), (30,1))

    def test_orders_arrive_next_month(self):
        cfg = dict(CFG, initial_cover_months=0)
        rows = simulate_item(np.array([10]*48), "T", 2, 3, "mean12", cfg, "baseline", 1)
        self.assertEqual((rows[0]["ordered_qty"], rows[0]["served_qty"], rows[0]["shortage_qty"]), (30,0,10))
        self.assertEqual(rows[1]["received_qty"], 30)

    def test_average_inventory_and_turnover_hand_case(self):
        rows = simulate_item(np.array([10]*48), "T", 2, 3, "mean12", CFG, "baseline", 1)
        avg = sum(r["average_stock_value"] for r in rows)/12
        self.assertAlmostEqual(avg, (25+15*11)*2/12)
        self.assertEqual(sum(r["consumption_value"] for r in rows), 240)
        self.assertAlmostEqual(240/avg, 144/19)

    def test_future_change_does_not_change_earlier_decisions(self):
        original = np.array([10]*48)
        changed = original.copy()
        changed[40:] = 9999
        a = simulate_item(original, "T", 2, 3, "mean6", CFG, "optimized", 1)
        b = simulate_item(changed, "T", 2, 3, "mean6", CFG, "optimized", 1)
        self.assertEqual(a[:4], b[:4])


class PublicDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.master, cls.audit, _ = load_and_validate(ROOT/"data/source")
        cls.selected, _ = choose_methods(cls.data, CFG)
        cls.ledger, cls.result = simulate(cls.data, cls.master, cls.selected, CFG)

    def test_source_calendar_and_identity(self):
        self.assertEqual((len(self.data),self.data.Medication.nunique()), (624,13))
        self.assertTrue(self.data.groupby("Medication").MonthIndex.nunique().eq(48).all())
        self.assertEqual(self.audit["invalid_rows"], 0)

    def test_heldout_values_do_not_select_models(self):
        changed = self.data.copy()
        changed.loc[changed.MonthIndex > 36, "Demand"] *= 20
        selected, _ = choose_methods(changed, CFG)
        self.assertEqual(selected, self.selected)

    def test_inventory_and_pipeline_conserve_units(self):
        for _, group in self.ledger.groupby(["Medication","policy"]):
            stock = int(group.iloc[0].initial_stock)
            pending = 0
            for row in group.itertuples():
                self.assertEqual(stock+row.received_qty-row.served_qty, row.closing_stock)
                self.assertEqual(pending+row.ordered_qty-row.received_qty, row.pending_end)
                self.assertEqual(row.served_qty+row.shortage_qty, row.actual_demand)
                self.assertGreaterEqual(row.closing_stock, 0)
                stock, pending = row.closing_stock, row.pending_end

    def test_strategies_have_same_initial_stock(self):
        starts = self.ledger.loc[self.ledger.MonthIndex == 37].pivot(index="Medication", columns="policy", values="initial_stock")
        self.assertTrue(starts.baseline.eq(starts.optimized).all())

    def test_published_snapshot_uses_no_month48_demand(self):
        original = risk_snapshot(self.data, self.master, self.selected, CFG)
        altered = self.data.copy()
        altered.loc[altered.MonthIndex == 48, "Demand"] += 1000000
        self.assertEqual(risk_snapshot(altered, self.master, self.selected, CFG), original)

    def test_stagnant_rule_with_explicit_synthetic_fixture(self):
        fixture = self.data.copy()
        fixture.loc[(fixture.Medication == "M13") & fixture.MonthIndex.between(45,47), "Demand"] = 0
        row = next(r for r in risk_snapshot(fixture,self.master,self.selected,CFG) if r["Medication"] == "M13")
        self.assertTrue(row["stagnant"])
        self.assertTrue(row["high_risk"])
        self.assertEqual(row["stock"], 170)

    def test_zero_portfolio_has_no_infinite_ratios(self):
        fixture = self.data.copy()
        fixture["Demand"] = 0
        _, result = simulate(fixture,self.master,self.selected,CFG)
        self.assertIsNone(result["summaries"]["baseline"]["turnover"])
        self.assertIsNone(result["summaries"]["optimized"]["weighted_fill_rate"])

    def test_accumulation_and_reorder_conflict_requires_review(self):
        row = next(r for r in risk_snapshot(self.data,self.master,self.selected,CFG) if r["Medication"] == "M13")
        self.assertTrue(row["high_risk"])
        self.assertTrue(row["conflicting_signals"])
        self.assertGreater(row["reference_order_qty"], 0)
        self.assertIsNone(row["advisory_order_qty"])
        self.assertTrue(row["hold_for_review"])

    def test_operating_cost_includes_ordering_tradeoff(self):
        for policy, summary in self.result["summaries"].items():
            part = self.ledger.loc[self.ledger.policy == policy]
            self.assertAlmostEqual(summary["operating_cost"], float(part.holding_cost.sum()+part.ordering_cost.sum()))
            self.assertAlmostEqual(summary["ordered_value"]-summary["received_value"], summary["pending_value"])

    def test_lead_two_still_reconciles(self):
        ledger, result = simulate(self.data,self.master,self.selected,CFG,lead=2)
        self.assertEqual(len(ledger), 312)
        self.assertTrue(ledger.closing_stock.ge(0).all())
        for rate in [result["summaries"][p]["weighted_fill_rate"] for p in ["baseline","optimized"]]:
            self.assertTrue(0 <= rate <= 1)


if __name__ == "__main__":
    unittest.main()
