"""报告中的量化结论只引用本次运行结果。"""


def write_report(data, path):
    sim, bench = data["simulation"], data["benchmark"]
    b, a, c = sim["summaries"]["baseline"], sim["summaries"]["optimized"], sim["changes"]
    errors = data["forecast_errors"]
    high = [r for r in data["risks"] if r["high_risk"]]
    m13 = next(r for r in data["risks"] if r["Medication"] == "M13")
    sb, sa = data["stress"]["summaries"]["baseline"], data["stress"]["summaries"]["optimized"]
    rows = [
        ("12 个月库存周转次数", b["turnover"], a["turnover"], "次"),
        ("平均库存金额", b["average_stock_value"], a["average_stock_value"], "CLP"),
        ("库存持有成本", b["holding_cost"], a["holding_cost"], "CLP"),
        ("下单处理成本", b["ordering_cost"], a["ordering_cost"], "CLP"),
        ("相关运营成本合计", b["operating_cost"], a["operating_cost"], "CLP"),
        ("下单次数（品种×月）", b["order_count"], a["order_count"], "次"),
        ("发出订单对应金额", b["ordered_value"], a["ordered_value"], "CLP"),
        ("本期到货对应金额", b["received_value"], a["received_value"], "CLP"),
        ("期末在库金额", b["closing_value"], a["closing_value"], "CLP"),
        ("期末未到货订单金额", b["pending_value"], a["pending_value"], "CLP"),
    ]
    table = "\n".join(f"| {name} | {x:,.2f} | {y:,.2f} | {unit} |" for name, x, y, unit in rows)
    path.write_text(f"""# 药品采购成本与库存周转优化分析报告

计算批次时间（UTC）：{data['generated_at'][:16].replace('T', ' ')}。报告、网页与 Excel 使用同批计算结果。

## 结论与适用边界

在第 37–48 月的模拟回测中，动态预测补货相对固定 3 个月覆盖对照，库存周转提高 **{c['turnover_improvement_pct']:.2f}%**，平均库存金额下降 **{c['stock_reduction_pct']:.2f}%**，相关运营成本下降 **{c['operating_cost_reduction_pct']:.2f}%**。

参考价格加权的需求满足率从 **{b['weighted_fill_rate']:.2%} 降至 {a['weighted_fill_rate']:.2%}**，变化 **{c['fill_rate_change_pp']:.2f} 个百分点**，下单次数由 {b['order_count']} 增至 {a['order_count']}。候选策略降低了库存占用，同时存在供应保障与补货频次的权衡。实际应用前应明确品种服务目标；本项目尚未计入缺货造成的临床或商誉损失。

需求来自公开匿名医院药房数据。采购政策、连续库存流水与成本估算由本项目模拟，不是广州医药经营数据或实际降本成绩。原始金额使用参考年度的名义智利比索 CLP，不是人民币。

## 数据与评价方法

使用 Fernando Rojas 公开数据包中的 13 个匿名药品、48 个连续月序号、624 条请求需求，以及参考价格、下单成本和最终期之前的库存快照。来源：[Zenodo 数据集](https://zenodo.org/records/22286723)，DOI 10.5281/zenodo.22286723，CC BY 4.0；作者 README 和完整来源校验保留在 `data/source/`。作者的优化代码和结果表未用于本项目计算。

第 1–24 月建立历史，第 25–36 月以每个品种的平均绝对误差选择方法，第 37–48 月做最终评价。两种政策使用相同期初库存、一个月交期、每月复核。改进政策目标为“保护期预测需求 + 历史误差缓冲”，扣除库存和在途后补货。每月决策仅使用之前已知需求；未满足需求当期记缺口，不在下一期补单。

金额按同一参考单价计算；月均库存近似为（到货后期初库存 + 月末库存）÷2，再对 12 期求平均。周转次数 = 实际满足需求的成本估算额÷平均库存金额。该近似不反映月内真实出入库时点。持有成本按年化 20% 模拟，下单处理成本使用公开参考值；所有品种沿用同一缓冲规则，不因 C 类而降低保障目标。

## 默认交期结果

| 指标 | 固定覆盖对照 | 动态预测补货 | 单位 |
| --- | ---: | ---: | --- |
{table}

订单金额代表采购承诺，到货金额按假设价格估值；没有付款账期和发票数据，不能解释为实际现金流。运营成本仅含持有与下单成本，不包含药品采购本金、缺货损失、效期损耗或运输成本。两种策略的期末库存与在途不同，采购金额下降不能直接视为利润增加。

## 预测误差评价

测试期参考价格加权 WAPE 从 {errors['baseline']:.2%} 变为 {errors['selected']:.2%}，相对误差下降 {(1-errors['selected']/errors['baseline'])*100:.2f}%。公式为 Σ(绝对预测误差×参考价)÷Σ(实际需求×参考价)。不用不同品种数量的直接相加掩盖计量差异。预测误差下降并不保证每个品种都不缺货；可在网页查看逐品种预测和满足率。

## M13 库存风险与冲突信号分析

风险清单的时点是第 48 月开始之前，只使用前 47 个月需求和公开库存快照，与回测末期模拟库存分开。

识别到 **{len(high)} 个高积压风险品种**，连续 3 个月无需求规则触发 **{sum(r['stagnant'] for r in data['risks'])} 个呆销品种**。M13 的库存为 {m13['stock']} 原数据单位，近 6 月平均需求 {m13['mean_recent6']:.2f}，覆盖 {m13['coverage_months']:.2f} 个月，超过预设 6 个月阈值；库存价值 {m13['stock_value']:,.0f} CLP。按 6 月覆盖量计算，超出参考量为 {m13['potential_excess_qty']} 单位，但不是已经清理或可直接退货的数量。

M13 在第 45 月仍有需求，因此“积压风险”与“连续 3 个月呆销”不能混用。历史大额波动还令其模型安全库存达到 {m13['safety_stock']}，未经审核的模型下单量为 {m13['reference_order_qty']}，与积压信号冲突。本项目因此将采购建议量留空并标记人工复核，不同时执行补货和清理建议。采购先核实偶发需求、在途、有效期和质量状态，再与销售/仓储核对消化可能、与供应商核实协议退换条件。清理后的回款和损失未模拟，更未宣称落地。

## 交期变化的压力测试

交期改为 2 个月，其余政策和起始库存保持不变，动态策略按新保护期重新计算缓冲。固定覆盖与动态策略的满足率分别为 {sb['weighted_fill_rate']:.2%}、{sa['weighted_fill_rate']:.2%}；周转分别为 {sb['turnover']:.2f}、{sa['turnover']:.2f} 次。

该场景评估已知交期变化的影响，未模拟无法预知的临时延误。测试前没有重新增加期初库存，因此也含切换初期影响。交期准确性应成为供应商沟通重点；实际使用还需要品种重要性、真实到货波动、包装倍数、购进限额和服务要求。

## 清洗与处理效率

原始 624 条需求记录通过完整性核查，未发现非法记录或重复。另构造 {bench['audit']['input_rows']:,} 行压力测试数据，明确注入格式差异、非法值和重复，隔离 {bench['audit']['invalid_rows']:,} 行非法记录、移除 {bench['audit']['duplicate_rows']:,} 行重复，保留 {bench['audit']['output_rows']:,} 行。

同一内存数据、同样清洗规则、各预热一次、交替执行 {len(bench['timings_seconds']['pandas'])} 轮：逐行 Python 中位耗时 {bench['median_seconds']['row_loop']:.4f} 秒，Pandas {bench['median_seconds']['pandas']:.4f} 秒，耗时减少 **{bench['time_reduction_pct']:.2f}%**，结果与核查计数一致。计时不包含文件读取和网络，也不代表人工 Excel 工作效率。机器负载会使复跑计时波动。

## 验证与采购建议

本次 {data['tests']['run']} 项核心测试通过。覆盖手算周转与安全库存、清洗冲突、未来数据隔离、两策略相同初始条件、库存与在途守恒、零需求、人工构造呆销、两个月交期。

建议先验证高金额品种的服务保障，再评估动态补货的资金收益；对 M13 先做需求核实和采购收缩，不预设可以退货；对低库存品种核实在途及可用状态，避免仅凭账面数重复下单。未提供有效期、批号、质量和供应商资质，本项目不据此判断药品是否可以销售或采购。

业务边界依据市场监管总局公开的[《药品经营质量管理规范》](https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_bc07ffdb7a1c4e46be371ac5a4a65f9c.html)第 17、61、72、81、85、87 条：采购合法性、收货验收、效期控制及不合格品处理应依照相应程序；这里的数量预警不能替代质量审核。具体适用要求以实施时现行法规及企业制度为准。

## 项目定位与结果使用范围

本项目基于公开匿名数据，展示采购分析、时序验证、库存模拟及风险核查方法。回测相对变化以预设的固定覆盖策略为比较基准，不表示全局最优策略或真实企业经营改善。

开发过程采用 AI 辅助编程；计算依据、参数及验证记录随项目提供。未涉及真实企业实施、供应商合作或临床决策，模型结果不替代法定及企业审核程序。
""", encoding="utf-8")
