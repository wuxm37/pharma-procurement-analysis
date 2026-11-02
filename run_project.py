"""重建分析结果、网页和报告。无网络请求，不调用原作者的分析代码。"""
import hashlib
import io
import json
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.cleaning import benchmark, load_and_validate
from analysis.forecast import METHODS, choose_methods, forecast_test
from analysis.inventory import risk_snapshot, simulate
from analysis.source import prepare_source
from analysis.reporting import write_report
from analysis.presentation import write_public_pages

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs/demo"


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def validate_config(cfg):
    fixed = {"training_end": 24, "selection_end": 36, "evaluation_end": 48,
             "review_months": 1, "baseline_window": 12, "lead_months": 1}
    for key, value in fixed.items():
        if cfg[key] != value:
            raise ValueError(f"当前 demo 的 {key} 固定为 {value}；改变时间结构需要同步修改并测试分析逻辑。")
    if not 0 < cfg["safety_quantile"] < 1 or not 0 <= cfg["annual_holding_rate"] <= 1:
        raise ValueError("分位数/持有成本率超出支持范围")
    if not 0 < cfg["abc_thresholds"][0] < cfg["abc_thresholds"][1] < 1:
        raise ValueError("ABC 阈值须递增且位于 0 与 1 之间")
    for key in ["baseline_cover_months", "initial_cover_months", "safety_history_origins", "stagnant_months", "excess_cover_months", "benchmark_repetitions", "benchmark_copies"]:
        if cfg[key] <= 0 or int(cfg[key]) != cfg[key]:
            raise ValueError(f"{key} 必须是正整数")


def render_presentation(result):
    write_report(result, OUT / "ANALYSIS_REPORT.md")
    template = (ROOT / "web/dashboard.html").read_text(encoding="utf-8")
    embedded = json.dumps(result, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    (OUT / "index.html").write_text(template.replace("__RESULTS_JSON__", embedded), encoding="utf-8")
    write_public_pages(result, OUT)


def write_manifest(result):
    inputs = [ROOT/"config.json", ROOT/"run_project.py", *sorted((ROOT/"analysis").glob("*.py")), *sorted((ROOT/"tests").glob("*.py")), ROOT/"web/dashboard.html"]
    outputs = [OUT/"results.json", OUT/"index.html", OUT/"project.html", OUT/"report.html", OUT/"ANALYSIS_REPORT.md", *sorted(OUT.glob("*.csv"))]
    manifest = {"generated_at": result["generated_at"], "presentation_updated_at": datetime.now(timezone.utc).isoformat(),
                "source_sha256": result["source"]["archive_sha256"],
                "note": "generated_at 为计算及计时的运行时间；presentation_updated_at 为展示文件更新时间。仅刷新展示时不重测处理耗时。",
                "inputs": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                "outputs": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs}}
    dump(OUT / "run_manifest.json", manifest)


def presentation_only():
    """文案调整复用既有结果；计算代码、配置或测试变化时拒绝复用。"""
    previous = json.loads((OUT/"run_manifest.json").read_text(encoding="utf-8"))
    hashes = {k.replace('\\', '/'): v for k, v in previous['inputs'].items()}
    names = ['config.json', 'analysis/cleaning.py', 'analysis/forecast.py', 'analysis/inventory.py', 'analysis/source.py']
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('*.py')]
    for name in names:
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != hashes.get(name):
            raise ValueError(f"计算依据已变化，必须完整重跑：{name}")
    result_path = OUT/'results.json'
    output_hashes = {k.replace('\\', '/'): v for k, v in previous['outputs'].items()}
    if hashlib.sha256(result_path.read_bytes()).hexdigest() != output_hashes['outputs/demo/results.json']:
        raise ValueError('已有计算结果发生变化，不能仅刷新展示')
    prepare_source(ROOT)
    result = json.loads(result_path.read_text(encoding='utf-8'))
    render_presentation(result)
    write_manifest(result)
    print('展示与报告已更新；回测指标和处理耗时沿用已验证的运行结果。')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    validate_config(cfg)
    source_dir, source = prepare_source(ROOT)
    test_stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    tests = unittest.TextTestRunner(stream=test_stream, verbosity=2).run(suite)
    (OUT / "test_results.txt").write_text(test_stream.getvalue(), encoding="utf-8")
    if not tests.wasSuccessful():
        raise RuntimeError("核心测试未通过，停止生成展示结果。详见 test_results.txt")
    demand, master, audit, raw = load_and_validate(source_dir)
    selected, scores = choose_methods(demand, cfg)
    forecast, errors = forecast_test(demand, master, selected, cfg)
    ledger, simulation = simulate(demand, master, selected, cfg)
    stress_ledger, stress = simulate(demand, master, selected, cfg, lead=2)
    risks = risk_snapshot(demand, master, selected, cfg)
    timing = benchmark(raw, cfg)
    csvs = {"cleaned_demand": demand, "forecast_validation": scores,
            "forecast_test": forecast, "simulation_ledger": ledger,
            "stress_lead2_ledger": stress_ledger,
            "inventory_risks": pd.DataFrame([{k: ("；".join(v) if isinstance(v, list) else v) for k, v in row.items() if k != "history"} for row in risks])}
    for name, table in csvs.items():
        table.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")
    result = {"title": "药品采购成本与库存周转优化分析", "config": cfg,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "platform": platform.system()},
        "source": source, "audit": audit, "methods": METHODS, "selected": selected,
        "forecast_errors": errors, "forecast_rows": forecast.to_dict("records"),
        "validation_scores": scores.to_dict("records"), "simulation": simulation,
        "stress": stress, "risks": risks, "benchmark": timing,
        "tests": {"run": tests.testsRun, "failures": len(tests.failures), "errors": len(tests.errors)}}
    dump(OUT / "results.json", result)
    render_presentation(result)
    write_manifest(result)
    print(json.dumps({"tests_passed": tests.testsRun, "changes": simulation["changes"],
        "high_risk_skus": sum(r["high_risk"] for r in risks), "stagnant_skus": sum(r["stagnant"] for r in risks),
        "benchmark_time_reduction_pct": timing["time_reduction_pct"], "output": str(OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if sys.argv[1:] == ['--presentation-only']:
        presentation_only()
    elif sys.argv[1:]:
        raise SystemExit('用法：python run_project.py [--presentation-only]')
    else:
        main()
