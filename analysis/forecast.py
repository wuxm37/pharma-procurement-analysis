"""少量可解释预测方法。函数只能接收决策时点以前的历史。"""
import math

import numpy as np
import pandas as pd

METHODS = {
    "mean12": "近12月均值", "mean6": "近6月均值", "mean3": "近3月均值",
    "ses": "指数平滑", "seasonal": "上一年同月", "tsb": "间歇需求分解",
}


def predict(history, method):
    y = np.asarray(history, dtype=float)
    if len(y) == 0 or np.any(~np.isfinite(y)) or np.any(y < 0):
        raise ValueError("预测需要完整、有限、非负的历史记录")
    if method.startswith("mean"):
        result = y[-int(method[4:]):].mean()
    elif method == "seasonal":
        result = y[-12] if len(y) >= 12 else y.mean()
    elif method == "ses":
        result = y[0]
        for value in y[1:]:
            result = 0.3*value + 0.7*result
    elif method == "tsb":
        initial = y[:min(12, len(y))]
        probability = float((initial > 0).mean())
        size = float(initial[initial > 0].mean()) if np.any(initial > 0) else 0.0
        for value in y[len(initial):]:
            probability = 0.2*int(value > 0) + 0.8*probability
            if value > 0:
                size = 0.2*value + 0.8*size
        result = probability*size
    else:
        raise ValueError(f"未知预测方法 {method}")
    return max(0.0, float(result))


def safety_stock(history, method, protection_months, quantile, origins=24):
    """缓冲=P95(过去保护期需求总量 - 当时预测总量)，最低为0。

    保护期采用一个月的预测值平推，和补货目标保持一致。
    不是临床服务保证；样本外满足率另行回测。
    """
    y = np.asarray(history, dtype=float)
    residuals = []
    start = max(12, len(y)-protection_months-origins+1)
    for origin in range(start, len(y)-protection_months+1):
        actual = float(y[origin:origin+protection_months].sum())
        residuals.append(actual-protection_months*predict(y[:origin], method))
    if not residuals:
        return 0, 0
    return max(0, math.ceil(float(np.quantile(residuals, quantile)))), len(residuals)


def choose_methods(demand, cfg):
    methods, records = {}, []
    for med, group in demand.groupby("Medication", sort=True):
        y = group.sort_values("MonthIndex").Demand.to_numpy()
        scores = {}
        for method in METHODS:
            errors = [abs(float(y[m-1])-predict(y[:m-1], method)) for m in range(cfg["training_end"]+1, cfg["selection_end"]+1)]
            scores[method] = float(np.mean(errors))
            records.append({"Medication": med, "method": method, "method_name": METHODS[method], "validation_mae": scores[method]})
        # 相同时保留方法字典中的简单方法；不以最终测试效果挑选。
        methods[med] = min(scores, key=scores.get)
    return methods, pd.DataFrame(records)


def forecast_test(demand, master, selected, cfg):
    prices = master.set_index("Medication").unit_price.to_dict()
    rows = []
    for med, group in demand.groupby("Medication", sort=True):
        y = group.sort_values("MonthIndex").Demand.to_numpy()
        for month in range(cfg["selection_end"]+1, cfg["evaluation_end"]+1):
            actual = int(y[month-1])
            rows.append({"Medication": med, "MonthIndex": month, "actual": actual,
                "baseline_forecast": predict(y[:month-1], "mean12"), "selected_forecast": predict(y[:month-1], selected[med]),
                "method": selected[med], "unit_price": prices[med]})
    frame = pd.DataFrame(rows)
    denom = float((frame.actual*frame.unit_price).sum())
    errors = {name: float(((frame[column]-frame.actual).abs()*frame.unit_price).sum()/denom) if denom else None
        for name, column in [("baseline", "baseline_forecast"), ("selected", "selected_forecast")]}
    return frame, errors
