# 数据字典与计算口径

所有数据按品种分别运算。金额为作者说明的名义 2023 年 CLP，整段历史固定参考价是本项目假设。匿名编号未映射真实药名；数量不擅自解释为盒、支或片。

## 公开原始数据

`data/source/monthly_demand_long.csv`：每行一个匿名品种的一期月度请求需求。主键为 `(Medication, MonthIndex)`，13 × 48 = 624 行。

| 字段 | 类型 / 单位 | 来源与意义 |
| --- | --- | --- |
| Medication | 文本 M01–M13 | 作者匿名药品编号 |
| MonthIndex | 整数 1–48 | 连续月序号；未提供公历日期 |
| Demand | 非负整数 / 原数据单位 | 请求需求，不等同已经完成的销售 |

`data/source/empirical_inputs.csv`：每行一个品种，13 行，主键 `Medication`。原字段全部保留，选用范围如下。

| 字段 | 类型 / 单位 | 本项目用途 |
| --- | --- | --- |
| Medication | 文本 | 关联需求 |
| unit_price | 数值 / CLP每单位 | 参考采购价；成本加权，不假设价格谈判 |
| o | 数值 / CLP每次 | 作者参考下单处理成本，用于每个品种每月下单成本 |
| stock_initial | 非负整数 / 原数据单位 | 最终评价期开始前库存；仅用于第48月前风险快照 |
| h | 数值 | 作者模型中的持有成本参数；未使用，本项目持有率另设 |
| s_factor | 数值 | 作者短缺惩罚相关参数；未使用 |
| C_money | 数值 / 金额 | 作者模型参数；未使用 |
| real_demand | 数值 / 原数据单位 | 作者最终期输入；未作为预测输入，避免泄漏 |
| q_real | 数值 / 原数据单位 | 作者观测/推导订单参考量；仅保留为来源参考，不作为本项目真实订单流水 |

原始精确定义另保留于 `data/source/data_dictionary.csv`、`AUTHOR_README.md`。`source_manifest.json` 记录文件哈希；许可元数据快照为 `research/zenodo_metadata.json`。

## 清洗字段与审计

`Batch` 仅用于合成压力测试，区分复制的独立导入批次；源数据清洗时为 0，正式清洗结果移除。不是实际采购批次，更不是药品生产批号。

`input_rows` / `invalid_rows` / `duplicate_rows` / `output_rows` 为输入、隔离非法、去除重复和最终有效行数，满足四者的行数平衡。重复按标准化后全字段一致定义；同一主键不同需求值为冲突并停算。原始需求本次非法和重复均为 0。

压力测试复制 160 组源表，通过固定索引规则注入空白、大小写、千分位、空需求、非法月份及重复；过程确定，不依赖随机种子。两种实现使用同一输入、相同规则，先比对输出与计数，再各预热并交替计时 5 轮。`time_reduction_pct = (1 − Pandas中位耗时 / 逐行中位耗时) × 100`。

## 预测输出

`forecast_validation.csv`：品种 × 候选方法，共 78 行。`method` 为方法代码、`method_name` 为中文名，`validation_mae` 为第25–36月平均绝对误差，按品种择最小值，平局按固定方法顺序选择。

`forecast_test.csv`：品种 × 第37–48月，共156行。

| 字段 | 意义 |
| --- | --- |
| Medication / MonthIndex | 品种、被预测月份 |
| actual | 当月实际请求需求；只能在本月履约阶段读取 |
| baseline_forecast | 决策前近12月均值 |
| selected_forecast | 验证期选定方法，用当前时点以前历史预测 |
| method | mean12、mean6、mean3、ses、seasonal、tsb 之一 |
| unit_price | 参考价格；总体 WAPE 用于统一价值权重 |

均值方法分别取最近3/6/12期。指数平滑 α=0.3；季节朴素使用上一年同月；间歇方法将发生概率与正需求量分开平滑，系数均0.2。前12月用于其初始化。所有系数固定，不用最终测试期调参。

## 模拟库存流水

`simulation_ledger.csv`：品种 × 月 × 策略 = 13×12×2 = 312行。`stress_lead2_ledger.csv` 为交期2月的同结构结果。均为**模拟**记录，不是实际采购订单或库存台账。

| 字段 | 计算或意义 |
| --- | --- |
| policy | baseline 固定覆盖；optimized 动态预测，仅为代码标识，不表示全局最优 |
| initial_stock | 第25–36月均需求×3向上取整，两策略一致 |
| received_qty | 以前下单、在本期约定到达的数量 |
| opening_after_arrival | 上月结存 + 本期到货 |
| pending_before_order | 本期到货后、下单前的剩余在途 |
| forecast | 当期决策使用的月预测 |
| safety_stock | 过去完整保护期预测误差第95百分位，向上取整，最少0 |
| safety_samples | 缓冲估计的历史误差样本数，最多24 |
| target_stock | 对照：3×预测；动态：（交期+1）×预测+缓冲；向上取整 |
| ordered_qty | max(0, 目标 − 到货后库存 − 剩余在途) |
| pending_end | 上月在途 + 本月下单 − 本月到货；期末不清零 |
| actual_demand | 当月请求需求 |
| served_qty | min(到货后库存, 本月需求) |
| shortage_qty | 本月需求 − 已满足数量，后续不补单 |
| closing_stock | 到货后库存 − 已满足数量 |
| unit_price | 固定参考单价 |
| average_stock_value | (到货后期初 + 期末)÷2×参考价 |
| consumption_value / demand_value | 已满足数量 / 请求数量 × 参考价 |
| ordered_value / received_value | 下单数量 / 到货数量 × 参考价 |
| closing_value | 期末在库数量×参考价 |
| holding_cost | 本月平均库存金额×20%÷12 |
| ordering_cost | 下单量大于0时使用该品种的公开参考 `o`，否则0 |

保护期误差 = 过去某决策时点之后完整保护期的已知真实需求之和 − 当时预测月需求×保护期。只纳入在当前决策时点已经完整发生的窗口。月预测平推保护期是简化，不是逐月季节预测之和，也不宣称达到95%未来服务水平。

组合汇总：每月各品种金额相加后对12月求平均；周转以全年已满足需求的成本估算额作分子；`weighted_fill_rate` 为已满足成本÷请求成本。`order_count` 是发生下单的“品种×月”次数，未模拟多个品种合并为供应商订单。

## 公开库存快照风险

`inventory_risks.csv` 只使用需求第1–47月及公开 `stock_initial`，不是模拟第48月结存。

| 字段 | 意义 / 规则 |
| --- | --- |
| abc / annual_demand_value / abc_share | 第36–47月请求需求×价格、金额分组和占比；每个跨越边界的品种放入跨越前的类别 |
| stock / stock_value | 作者期初库存、参考库存价值 |
| mean_recent6 / coverage_months | 第42–47月平均需求、库存÷该均值；均值0时覆盖不定义，保留空值 |
| stagnant | 库存>0且第45–47月请求需求均0 |
| excess | 库存>0且近期均需0或覆盖>6月 |
| high_risk | 呆销或高覆盖任一满足 |
| forecast / method / method_name | 决策前47月历史预测、方法及中文名 |
| safety_stock / safety_samples | 同保护期误差缓冲及样本数 |
| reorder_point | ceil(交期×预测+缓冲)；数量关注阈值，不是自动采购授权 |
| reference_order_qty | 假设在途0、账面量全部可用时未经审核的模型量 |
| conflicting_signals | 同时存在积压/呆销与补货关注信号 |
| hold_for_review | 高积压/呆销需要先人工核查 |
| advisory_order_qty | 高风险时留空；其他仅作待核实的数量参考，仍不表示审核通过 |
| potential_excess_qty | max(0,库存−ceil(6×近期月均需求))；不等于已清理或可退数量 |
| state / reasons / actions | 展示状态、具体依据、核查建议 |

`results.json` 另含逐品种历史曲线 `history`，以及 `simulation` 默认交期和 `stress` 交期2月结果。每条运行结论都能追到上述 CSV、配置及代码。
