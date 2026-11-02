// 只把 Python 的已运行结果导出为可核对报表；不在 Excel 中重建预测引擎。
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'outputs', 'demo');
const d = JSON.parse(await fs.readFile(path.join(out, 'results.json'), 'utf8'));
const wb = Workbook.create();
const font = 'Microsoft YaHei';
const sheets = ['策略对比', 'ABC与风险', '预测明细', '数据核查'].map(name => wb.worksheets.add(name));
const [summary, risks, forecast, audit] = sheets;
const fmt = (sheet, range, values) => { sheet.getRange(range).values = values; };
function base(sheet, end, widths, title, note) {
  sheet.showGridLines = false;
  const area = sheet.getRange(`A1:${end}`);
  area.format.font = { name: font, size: 10, color: '#243c4b' };
  area.format.rowHeight = 24;
  area.format.verticalAlignment = 'center';
  widths.forEach((w,i) => sheet.getRangeByIndexes(0,i,Number(end.match(/\d+/)[0]),1).format.columnWidth = w);
  fmt(sheet, 'A2', [[title]]);
  sheet.getRange('A2').format.font = {name:font,size:15,bold:true,color:'#183c49'};
  sheet.getRange('A2').format.rowHeight = 31;
  fmt(sheet, 'A3', [[note]]);
  sheet.getRange('A3').format.font = {name:font,size:10,italic:true,color:'#677987'};
}
function header(sheet, range) {
  const r=sheet.getRange(range);
  r.format.fill='#214d5d';
  r.format.font={name:font,size:10,bold:true,color:'#ffffff'};
  r.format.horizontalAlignment='center';
  r.format.rowHeight=30;
}
function body(sheet, range) { sheet.getRange(range).setNumberFormat('#,##0.00'); }
const b=d.simulation.summaries.baseline,a=d.simulation.summaries.optimized;
base(summary,'F25',[30,14,21,21,19,48],'药品采购策略比较','第 37–48 月模拟回测；交期 1 个月；两策略初始库存相同。金额为 CLP。');
summary.tabColor='#214d5d';
fmt(summary,'A5:F5',[['指标','单位','固定覆盖对照','动态预测补货','变化','解释']]);header(summary,'A5:F5');
const rows=[
 ['库存周转次数','次 / 12月',b.turnover,a.turnover,null,'实际满足需求成本 ÷ 平均库存金额'],
 ['平均库存金额','CLP',b.average_stock_value,a.average_stock_value,null,'按月期初与期末均值估计'],
 ['库存持有成本','CLP',b.holding_cost,a.holding_cost,null,'年化持有成本率模拟为 20%'],
 ['下单处理成本','CLP',b.ordering_cost,a.ordering_cost,null,'每品种每月有下单即计一次'],
 ['相关运营成本','CLP',null,null,null,'持有 + 下单，不含缺货和效期损失'],
 ['加权需求满足率','比例',b.weighted_fill_rate,a.weighted_fill_rate,null,'变化列为百分点；不能忽略下降'],
 ['下单次数','次',b.order_count,a.order_count,null,'采购承诺次数，不是供应商订单数'],
 ['发出订单对应金额','CLP',b.ordered_value,a.ordered_value,null,'未考虑账期，不代表实际付款'],
 ['本期到货对应金额','CLP',b.received_value,a.received_value,null,'按相同参考价估值'],
 ['期末在库金额','CLP',b.closing_value,a.closing_value,null,'期末边界差异需要同时查看'],
 ['期末在途金额','CLP',b.pending_value,a.pending_value,null,'已下单、尚未到货'],
 ['预测加权 WAPE','比例',d.forecast_errors.baseline,d.forecast_errors.selected,null,'绝对误差×价格 / 实际需求×价格']
];fmt(summary,'A6:F17',rows);body(summary,'C6:E17');
summary.getRange('C10:D10').formulas=[['=SUM(C8:C9)','=SUM(D8:D9)']];
for(const row of [6,7,8,9,10,12,13,14,15,16,17])summary.getRange(`E${row}`).formulas=[[`=D${row}/C${row}-1`]];
summary.getRange('E6:E17').setNumberFormat('0.00%');
summary.getRange('E11').formulas=[['=(D11-C11)*100']];summary.getRange('E11').setNumberFormat('0.00');
summary.getRange('C11:D11').setNumberFormat('0.00%');summary.getRange('C17:D17').setNumberFormat('0.00%');summary.getRange('C12:D12').setNumberFormat('#,##0');
summary.getRange('A10:F10').format.fill='#edf5f3';
summary.getRange('E11').conditionalFormats.add('cellIs',{operator:'lessThan',formula:0,format:{font:{color:'#a34837',bold:true},fill:'#fff2e3'}});
fmt(summary,'A20',[['注意：周转改善伴随满足率下降，属于候选策略回测，不能直接宣称企业降本。']]);
fmt(summary,'A22',[['本表为 Python 分析结果快照。更改政策需重新运行项目；变化列按“动态 / 固定 − 1”计算。']]);
fmt(summary,'A24',[['来源与许可见“数据核查”。完整库存流水见同目录 simulation_ledger.csv。']]);

base(risks,'J23',[12,10,17,18,16,18,19,22,40,45],'ABC 与库存风险清单','第 48 月开始前的公开库存快照；需求仅用前 47 月。数量单位沿用原数据。');
fmt(risks,'A5:J5',[['药品编码','ABC','快照库存','近6月均需求','覆盖月数','安全库存','参考下单量','状态','触发原因','采购核查建议']]);
fmt(risks,'A6:J18',d.risks.map(r=>[r.Medication,r.abc,r.stock,r.mean_recent6,null,r.safety_stock,r.advisory_order_qty,r.state,r.reasons.join('；'),r.hold_for_review?'信号冲突或高积压，暂缓按模型下单；先人工复核':'核实在途、可用状态及真实交期']));
for(let i=6;i<=18;i++)risks.getRange(`E${i}`).formulas=[[`=IF(D${i}=0,"",C${i}/D${i})`]];
risks.tables.add('A5:J18',true,'InventoryRisks').showFilterButton=true;header(risks,'A5:J5');
risks.getRange('C6:G18').setNumberFormat('#,##0');risks.getRange('D6:E18').setNumberFormat('#,##0.00');
risks.getRange('I6:J18').format.wrapText=true;risks.getRange('A6:J18').format.rowHeight=40;
risks.getRange('A6:J6').format.rowHeight=67;
risks.getRange('H6:H18').conditionalFormats.add('containsText',{text:'积压',format:{fill:'#fff0d5',font:{color:'#985b14'}}});
risks.freezePanes.freezeRows(5);risks.freezePanes.freezeColumns(2);
fmt(risks,'A21',[['参考下单假设在途为 0、库存全部可用；高积压品种建议量留空待人工复核；均须核对包装与质量状态。']]);
fmt(risks,'A22',[['积压规则：覆盖超过 6 月。呆销规则：连续 3 月无需求且有库存；本次实际触发 0 个呆销品种。']]);

base(forecast,'I163',[13,12,19,20,20,22,20,20,20],'测试期预测明细','第 37–48 月逐品种记录；方法仅按第 25–36 月选择；误差以原数据数量单位表示。');
fmt(forecast,'A5:I5',[['药品编码','月序号','实际需求','固定均值预测','所选方法预测','方法','固定绝对误差','所选绝对误差','单价 / CLP']]);
fmt(forecast,'A6:I161',d.forecast_rows.map(r=>[r.Medication,r.MonthIndex,r.actual,r.baseline_forecast,r.selected_forecast,d.methods[r.method],null,null,r.unit_price]));
forecast.getRange('G6:H6').formulas=[['=ABS(D6-C6)','=ABS(E6-C6)']];forecast.getRange('G6:H161').fillDown();
forecast.tables.add('A5:I161',true,'ForecastResults').showFilterButton=true;header(forecast,'A5:I5');
forecast.getRange('B6:C161').setNumberFormat('#,##0');forecast.getRange('D6:E161').setNumberFormat('#,##0.00');forecast.getRange('G6:I161').setNumberFormat('#,##0.00');
forecast.freezePanes.freezeRows(5);forecast.freezePanes.freezeColumns(1);

base(audit,'E38',[31,23,23,28,45],'数据来源与清洗计时','Fernando Rojas；CC BY 4.0；公开数据：https://zenodo.org/records/22286723');
fmt(audit,'A5:E5',[['核查项目','原始需求','合成压力测试','说明','']]);header(audit,'A5:D5');
const bm=d.benchmark;
fmt(audit,'A6:D9',Object.keys(d.audit).map((k,i)=>[['输入行数','非法记录数','重复记录数','有效记录数'][i],d.audit[k],bm.audit[k],i===0?'压力测试复制并注入异常':'按相同清洗规则计数']));
audit.getRange('B6:C9').setNumberFormat('#,##0');
fmt(audit,'A12',[['计时对照：同一内存输入、各预热一次、交替顺序；不含文件读取与网络。']]);
fmt(audit,'A14:D14',[['轮次','逐行 Python / 秒','Pandas / 秒','耗时减少比例']]);header(audit,'A14:D14');
fmt(audit,'A15:D19',bm.timings_seconds.pandas.map((v,i)=>[i+1,bm.timings_seconds.row_loop[i],v,null]));
audit.getRange('D15').formulas=[['=1-C15/B15']];audit.getRange('D15:D19').fillDown();
fmt(audit,'A21',[['中位数']]);audit.getRange('B21:D21').formulas=[['=MEDIAN(B15:B19)','=MEDIAN(C15:C19)','=1-C21/B21']];
audit.getRange('B15:C21').setNumberFormat('0.0000');audit.getRange('D15:D21').setNumberFormat('0.00%');
fmt(audit,'A24:B30',[
 ['输出一致性',bm.outputs_equal?'两实现结果与核查计数一致':'不一致'],
 ['测试通过数',d.tests.run],['Python / Pandas',`${d.runtime.python} / ${d.runtime.pandas}`],
 ['计时生成时间 / UTC',new Date(d.generated_at)],['源压缩包 MD5',d.source.archive_md5],
 ['公开数据说明','医院药房匿名需求；不是广州医药经营数据'],['参考价格口径','名义 2023 年智利比索 CLP；所有月沿用参考价']]);
audit.getRange('B24:B30').format.wrapText=false;
audit.getRange('B27').setNumberFormat('yyyy-mm-dd hh:mm:ss');
fmt(audit,'A33',[['数据字段及未使用字段见项目 DATA_DICTIONARY.md；原始文件完整保留。']]);
fmt(audit,'A35',[['处理效率仅为本次机器计时；不能写成人工 Excel 效率或企业实习成果。']]);
fmt(audit,'A37',[['模型预警不替代资质、质量、收货验收及退换报废程序。']]);

wb.recalculate();
const checks={
  turnover_change:summary.getRange('E6').values[0][0],
  cost_base:summary.getRange('C10').values[0][0],
  cost_candidate:summary.getRange('D10').values[0][0],
  fill_change_pp:summary.getRange('E11').values[0][0],
  benchmark_reduction:audit.getRange('D21').values[0][0],
};
for(const [got,want] of [[checks.turnover_change,d.simulation.changes.turnover_improvement_pct/100],[checks.cost_base,b.operating_cost],[checks.cost_candidate,a.operating_cost],[checks.fill_change_pp,d.simulation.changes.fill_rate_change_pp],[checks.benchmark_reduction,bm.time_reduction_pct/100]]){
 if(typeof got!=='number'||Math.abs(got-want)>1e-7*Math.max(1,Math.abs(want)))throw new Error('Excel 关键公式结果与 Python 不一致：'+JSON.stringify({got,want}));
}
const inspection=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:40},summary:'formula error scan'});
await fs.mkdir(path.join(out,'verification'),{recursive:true});
await fs.writeFile(path.join(out,'verification','workbook_checks.json'),JSON.stringify({checks,inspection},null,2));
for(const [sheet,range,name] of [[summary,'A1:F24','strategy'],[risks,'A1:J22','risk'],[forecast,'A1:I20','forecast'],[audit,'A1:E37','audit']]){
 if(process.argv.length>2&&!process.argv.slice(2).includes(name))continue;
 const image=await wb.render({sheetName:sheet.name,range,scale:1.3,format:'png'});
 await fs.writeFile(path.join(out,'verification',`excel_${name}.png`),new Uint8Array(await image.arrayBuffer()));
}
const exported=await SpreadsheetFile.exportXlsx(wb);
await exported.save(path.join(out,'procurement_analysis.xlsx'));
console.log(JSON.stringify({file:path.join(out,'procurement_analysis.xlsx'),sheets:4,checks},null,2));
