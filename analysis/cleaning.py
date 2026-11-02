"""Pandas 清洗是主实现；逐行实现仅作同规则的计时对照。"""
import math
import re
import statistics
import time

import numpy as np
import pandas as pd

ID_PATTERN = r"M(?:0[1-9]|1[0-3])"
NUMBER_PATTERN = r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.0+)?"
FIELDS = ["Batch", "Medication", "MonthIndex", "Demand"]


def clean_pandas(frame):
    data = frame[FIELDS].copy()
    text = {c: data[c].astype("string").str.strip() for c in FIELDS}
    data["Medication"] = text["Medication"].str.upper()
    data["Batch"] = pd.to_numeric(text["Batch"], errors="coerce")
    valid = data["Medication"].str.fullmatch(ID_PATTERN).fillna(False)
    valid &= data["Batch"].notna() & np.isfinite(data["Batch"]) & data["Batch"].ge(0) & data["Batch"].mod(1).eq(0)
    for col in ["MonthIndex", "Demand"]:
        valid &= text[col].str.fullmatch(NUMBER_PATTERN).fillna(False)
        data[col] = pd.to_numeric(text[col].str.replace(",", "", regex=False), errors="coerce")
        valid &= data[col].notna() & np.isfinite(data[col])
    valid &= data["MonthIndex"].between(1, 48) & data["Demand"].ge(0)
    rejected = frame.loc[~valid, FIELDS].copy()
    good = data.loc[valid].copy()
    good[["Batch", "MonthIndex", "Demand"]] = good[["Batch", "MonthIndex", "Demand"]].astype("int64")
    duplicate_count = int(good.duplicated(FIELDS).sum())
    good = good.drop_duplicates(FIELDS)
    keys = ["Batch", "Medication", "MonthIndex"]
    conflicts = good.duplicated(keys, keep=False)
    if conflicts.any():
        raise ValueError("同一品种月份存在冲突值，不能用保留第一条掩盖冲突。")
    good = good.sort_values(keys).reset_index(drop=True)
    return good, {"input_rows": len(frame), "invalid_rows": len(rejected), "duplicate_rows": duplicate_count, "output_rows": len(good)}, rejected


def clean_loop(frame):
    """同样接受空格、大小写及规范千分位；不把缺失当零。"""
    result, seen = [], {}
    invalid, duplicate = 0, 0
    for batch, med, month, demand in frame[FIELDS].itertuples(index=False, name=None):
        b, m, t, d = str(batch).strip(), str(med).strip().upper(), str(month).strip(), str(demand).strip()
        try:
            bn = float(b)
            ok = math.isfinite(bn) and bn >= 0 and bn.is_integer() and re.fullmatch(ID_PATTERN, m) and re.fullmatch(NUMBER_PATTERN, t) and re.fullmatch(NUMBER_PATTERN, d)
            tn, dn = float(t.replace(",", "")), float(d.replace(",", ""))
            ok = ok and math.isfinite(tn) and math.isfinite(dn) and 1 <= tn <= 48 and dn >= 0
        except (ValueError, TypeError, OverflowError):
            ok = False
        if not ok:
            invalid += 1
            continue
        key = (int(bn), m, int(tn))
        if key in seen:
            if seen[key] != int(dn):
                raise ValueError("同一品种月份存在冲突值")
            duplicate += 1
        else:
            seen[key] = int(dn)
            result.append((*key, int(dn)))
    data = pd.DataFrame(result, columns=FIELDS).sort_values(FIELDS[:3]).reset_index(drop=True)
    return data, {"input_rows": len(frame), "invalid_rows": invalid, "duplicate_rows": duplicate, "output_rows": len(data)}


def load_and_validate(source_dir):
    raw = pd.read_csv(source_dir/"monthly_demand_long.csv", dtype=str, keep_default_na=False)
    if raw.columns.tolist() != ["Medication", "MonthIndex", "Demand"]:
        raise ValueError("源字段与已核查版本不一致")
    raw.insert(0, "Batch", 0)
    cleaned, audit, rejected = clean_pandas(raw)
    expected = {(f"M{i:02}", t) for i in range(1, 14) for t in range(1, 49)}
    if set(zip(cleaned.Medication, cleaned.MonthIndex)) != expected or audit["invalid_rows"]:
        raise ValueError("源数据包含非法记录或缺失月份；不能补零后继续分析。")
    master = pd.read_csv(source_dir/"empirical_inputs.csv")
    if master.Medication.duplicated().any() or set(master.Medication) != {f"M{i:02}" for i in range(1, 14)}:
        raise ValueError("参考价格/库存表主键不完整或重复")
    for field in ["unit_price", "stock_initial", "o"]:
        master[field] = pd.to_numeric(master[field], errors="raise")
        if not np.isfinite(master[field]).all() or (master[field] < 0).any():
            raise ValueError(f"{field} 必须为有限非负数")
    if (master.unit_price <= 0).any():
        raise ValueError("参考价格必须大于零")
    if master.stock_initial.mod(1).ne(0).any():
        raise ValueError("本版的期初库存须为整数单位，不自动截断")
    return cleaned.drop(columns="Batch"), master, audit, raw


def benchmark(raw, config):
    """复制源数据并明确注入脏记录，不把它们说成原数据的问题。"""
    frames = []
    for i in range(config["benchmark_copies"]):
        part = raw.copy()
        part["Batch"] = str(i)
        frames.append(part)
    sample = pd.concat(frames, ignore_index=True)
    base_count = len(sample)
    sample.loc[sample.index % 7 == 0, "Medication"] = " " + sample.loc[sample.index % 7 == 0, "Medication"].str.lower() + " "
    sample.loc[sample.index % 11 == 0, "Demand"] = sample.loc[sample.index % 11 == 0, "Demand"].map(lambda x: f"{int(x):,}")
    sample.loc[sample.index % 97 == 0, "Demand"] = ""
    sample.loc[sample.index % 193 == 1, "MonthIndex"] = "99"
    sample = pd.concat([sample, sample.iloc[::200]], ignore_index=True)
    fast, audit, _ = clean_pandas(sample)
    slow, other = clean_loop(sample)
    pd.testing.assert_frame_equal(fast, slow, check_dtype=False)
    if audit != other:
        raise AssertionError("计时对照的清洗日志不同")
    timings = {"pandas": [], "row_loop": []}
    # 已各预热一次；交替顺序，避免一方总先运行。
    for repeat in range(config["benchmark_repetitions"]):
        order = [("pandas", clean_pandas), ("row_loop", clean_loop)]
        if repeat % 2:
            order.reverse()
        for name, function in order:
            start = time.perf_counter()
            function(sample)
            timings[name].append(time.perf_counter()-start)
    medians = {k: statistics.median(v) for k, v in timings.items()}
    return {"base_rows": base_count, "audit": audit, "timings_seconds": timings, "median_seconds": medians, "time_reduction_pct": (1-medians["pandas"]/medians["row_loop"])*100, "outputs_equal": True, "description": "人工构造的导入压力测试；对照为逐行 Python，同一内存输入，不包括网络与文件读取，不代表人工 Excel 耗时。"}
