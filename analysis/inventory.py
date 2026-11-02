"""按月库存结转；未来需求仅在当月履约时进入，不进入先前决策。"""
import math

import numpy as np
import pandas as pd

from .forecast import METHODS, predict, safety_stock


def abc_classes(values, thresholds=(0.8, 0.95)):
    if any(v < 0 for v in values.values()):
        raise ValueError("ABC 金额不能为负")
    ordered = sorted(values.items(), key=lambda pair: (-pair[1], pair[0]))
    total, cumulative = sum(values.values()), 0.0
    result = {}
    for key, value in ordered:
        before = cumulative/total if total else 1
        result[key] = "C" if not value else ("A" if before < thresholds[0] else ("B" if before < thresholds[1] else "C"))
        cumulative += value
    return result


def simulate_item(y, med, price, order_cost, method, cfg, policy, lead, multiplier=1.0):
    if lead < 1:
        raise ValueError("月度模型交期必须至少1个月")
    start, end = cfg["selection_end"]+1, cfg["evaluation_end"]
    initial = math.ceil(float(np.mean(y[start-13:start-1]))*cfg["initial_cover_months"])
    stock, pipeline, rows = initial, {}, []
    for month in range(start, end+1):
        history = y[:month-1]
        arriving = pipeline.pop(month, 0)
        opening = stock+arriving
        pending_before = sum(pipeline.values())
        pred = predict(history, "mean12" if policy == "baseline" else method)
        if policy == "baseline":
            buffer, count = 0, 0
            target = math.ceil(cfg["baseline_cover_months"]*pred)
        else:
            buffer, count = safety_stock(history, method, lead+cfg["review_months"], cfg["safety_quantile"], cfg["safety_history_origins"])
            target = math.ceil((lead+cfg["review_months"])*pred+buffer)
        quantity = max(0, target-opening-pending_before)
        if quantity:
            pipeline[month+lead] = pipeline.get(month+lead, 0)+quantity
        demand = math.ceil(float(y[month-1])*multiplier)
        served = min(opening, demand)
        shortage = demand-served
        stock = opening-served
        average = (opening+stock)/2
        rows.append({"Medication": med, "MonthIndex": month, "policy": policy,
            "initial_stock": initial, "opening_after_arrival": opening, "received_qty": arriving,
            "ordered_qty": quantity, "pending_before_order": pending_before, "pending_end": sum(pipeline.values()),
            "actual_demand": demand, "served_qty": served, "shortage_qty": shortage, "closing_stock": stock,
            "forecast": pred, "safety_stock": buffer, "safety_samples": count, "target_stock": target,
            "average_stock_value": average*price, "consumption_value": served*price, "demand_value": demand*price,
            "ordered_value": quantity*price, "received_value": arriving*price, "closing_value": stock*price,
            "holding_cost": average*price*cfg["annual_holding_rate"]/12,
            "ordering_cost": order_cost if quantity else 0.0, "unit_price": price})
    return rows


def simulate(demand, master, selected, cfg, lead=None):
    lead = cfg["lead_months"] if lead is None else lead
    inputs = master.set_index("Medication")
    rows = []
    for med, group in demand.groupby("Medication", sort=True):
        y = group.sort_values("MonthIndex").Demand.to_numpy()
        for policy in ["baseline", "optimized"]:
            rows.extend(simulate_item(y, med, float(inputs.loc[med, "unit_price"]), float(inputs.loc[med, "o"]), selected[med], cfg, policy, lead))
    ledger = pd.DataFrame(rows)
    summaries, monthly, items = {}, [], []
    for policy, part in ledger.groupby("policy"):
        aggregated = part.groupby("MonthIndex").agg(average_stock_value=("average_stock_value", "sum"),
            holding_cost=("holding_cost", "sum"), ordering_cost=("ordering_cost", "sum"),
            consumption_value=("consumption_value", "sum"), demand_value=("demand_value", "sum"),
            closing_value=("closing_value", "sum")).reset_index()
        aggregated["policy"] = policy
        monthly.extend(aggregated.to_dict("records"))
        avg = float(aggregated.average_stock_value.mean())
        cost = float(part.holding_cost.sum()+part.ordering_cost.sum())
        last = part.loc[part.MonthIndex == cfg["evaluation_end"]]
        summaries[policy] = {"average_stock_value": avg, "turnover": float(part.consumption_value.sum()/avg) if avg else None,
            "holding_cost": float(part.holding_cost.sum()), "ordering_cost": float(part.ordering_cost.sum()),
            "operating_cost": cost, "ordered_value": float(part.ordered_value.sum()), "received_value": float(part.received_value.sum()),
            "closing_value": float(last.closing_value.sum()), "pending_value": float((last.pending_end*last.unit_price).sum()),
            "weighted_fill_rate": float(part.consumption_value.sum()/part.demand_value.sum()) if part.demand_value.sum() else None,
            "shortage_skus": int(part.loc[part.shortage_qty > 0, "Medication"].nunique()),
            "shortage_item_months": int((part.shortage_qty > 0).sum()), "order_count": int((part.ordered_qty > 0).sum())}
        for med, group in part.groupby("Medication"):
            dem = float(group.actual_demand.sum())
            items.append({"Medication": med, "policy": policy, "fill_rate": float(group.served_qty.sum()/dem) if dem else None,
                "average_stock_value": float(group.average_stock_value.mean()), "operating_cost": float(group.holding_cost.sum()+group.ordering_cost.sum()),
                "shortage_qty": int(group.shortage_qty.sum()), "closing_stock": int(group.iloc[-1].closing_stock)})
    b, a = summaries["baseline"], summaries["optimized"]
    changes = {"turnover_improvement_pct": (a["turnover"]/b["turnover"]-1)*100 if b["turnover"] else None,
        "stock_reduction_pct": (1-a["average_stock_value"]/b["average_stock_value"])*100 if b["average_stock_value"] else None,
        "operating_cost_reduction_pct": (1-a["operating_cost"]/b["operating_cost"])*100 if b["operating_cost"] else None,
        "fill_rate_change_pp": (a["weighted_fill_rate"]-b["weighted_fill_rate"])*100 if b["weighted_fill_rate"] is not None else None}
    return ledger, {"lead_months": lead, "summaries": summaries, "changes": changes, "monthly": monthly, "items": items}


def risk_snapshot(demand, master, selected, cfg):
    # stock_initial 是第48期之前的快照：所有判断只使用第1–47期需求。
    historical = demand.loc[demand.MonthIndex < 48]
    values = historical.loc[historical.MonthIndex >= 36].groupby("Medication").Demand.sum()
    inputs = master.set_index("Medication")
    annual_values = (values*inputs.unit_price).to_dict()
    classes = abc_classes(annual_values, cfg["abc_thresholds"])
    total_value = sum(annual_values.values())
    rows = []
    for med, part in historical.groupby("Medication", sort=True):
        y = part.sort_values("MonthIndex").Demand.to_numpy()
        stock = int(inputs.loc[med, "stock_initial"])
        price = float(inputs.loc[med, "unit_price"])
        demand6 = float(y[-6:].mean())
        coverage = stock/demand6 if demand6 else None
        stagnant = bool(stock > 0 and y[-cfg["stagnant_months"]:].sum() == 0)
        excess = bool(stock > 0 and (demand6 == 0 or coverage > cfg["excess_cover_months"]))
        pred = predict(y, selected[med])
        ss, samples = safety_stock(y, selected[med], cfg["lead_months"]+cfg["review_months"], cfg["safety_quantile"], cfg["safety_history_origins"])
        reorder = math.ceil(cfg["lead_months"]*pred+ss)
        target = math.ceil((cfg["lead_months"]+cfg["review_months"])*pred+ss)
        reasons, actions = [], []
        if stagnant:
            reasons.append(f"连续{cfg['stagnant_months']}个月无请求需求且仍有库存")
            actions.append("先核实是否停售、替换或偶发需求；暂停常规补货，评估协议调剂/退换")
        if excess:
            reasons.append("库存超过近6月需求估计的6个月覆盖量" if demand6 else "近6月没有需求记录，库存尚未消化")
            actions.append("复核需求后减少采购；退换、报废须另经协议和质量程序")
        if stock < ss:
            reasons.append("期初库存低于模型安全库存")
        if stock < reorder:
            if stock >= ss:
                reasons.append("库存低于覆盖交期需求与缓冲的补货阈值")
            actions.append("核实在途与可用状态，再确认采购交期和补货数量")
        high = stagnant or excess
        conflict = bool(high and stock < reorder)
        if conflict:
            reasons.append("近期覆盖量与历史波动缓冲发出相反信号")
            actions = ["暂缓按模型直接下单；先核实偶发大额需求、在途与库存可用性", "由采购结合销售/用药需求复核补货或调剂退换，不同时执行矛盾建议"]
        state = "呆销待核实" if stagnant else ("高积压风险" if excess else ("安全库存预警" if stock < ss else ("补货关注" if stock < reorder else "正常观察")))
        rows.append({"Medication": med, "abc": classes[med], "annual_demand_value": annual_values[med],
            "abc_share": annual_values[med]/total_value if total_value else 0, "stock": stock, "unit_price": price, "stock_value": stock*price,
            "mean_recent6": demand6, "coverage_months": coverage, "stagnant": stagnant, "excess": excess, "high_risk": high,
            "forecast": pred, "safety_stock": ss, "safety_samples": samples, "reorder_point": reorder,
            "reference_order_qty": max(0, target-stock), "method": selected[med], "method_name": METHODS[selected[med]],
            "conflicting_signals": conflict, "hold_for_review": high,
            "advisory_order_qty": None if high else max(0, target-stock),
            "state": state, "reasons": reasons or ["当前简化规则未触发特别预警"], "actions": list(dict.fromkeys(actions)) or ["按月复核需求与供货"],
            "potential_excess_qty": max(0, stock-math.ceil(cfg["excess_cover_months"]*demand6)),
            "history": [{"month": int(t), "demand": int(q)} for t, q in zip(part.MonthIndex, part.Demand)]})
    return sorted(rows, key=lambda r: (-r["high_risk"], -r["stock_value"], r["Medication"]))
