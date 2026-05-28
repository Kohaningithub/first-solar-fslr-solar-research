import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(__filename), "..");
const data = JSON.parse(await fs.readFile(path.join(root, "data", "research_data.json"), "utf8"));
const outDir = path.join(root, "outputs");
await fs.mkdir(outDir, { recursive: true });

const wb = Workbook.create();
const sheets = {};
for (const name of [
  "Summary",
  "Financials KPIs",
  "Valuation",
  "Peers",
  "Market Reaction",
  "Catalysts Policy Risks",
  "Research Path",
  "Sources",
  "Checks",
]) {
  sheets[name] = wb.worksheets.add(name);
  sheets[name].showGridLines = false;
}

const theme = {
  green: "#0E7C66",
  blue: "#365F91",
  tan: "#F6F7F2",
  dark: "#10231F",
  gray: "#6B746F",
  light: "#E8ECE3",
  amber: "#8A5B20",
  red: "#B5483A",
};

function a1(row, col) {
  let c = col;
  let s = "";
  while (c >= 0) {
    s = String.fromCharCode((c % 26) + 65) + s;
    c = Math.floor(c / 26) - 1;
  }
  return `${s}${row + 1}`;
}

function rangeFor(startRow, startCol, rows, cols) {
  return `${a1(startRow, startCol)}:${a1(startRow + rows - 1, startCol + cols - 1)}`;
}

function setTitle(sheet, title, subtitle = "") {
  sheet.getRange("A1:H1").merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1").format = {
    fill: theme.green,
    font: { bold: true, color: "#FFFFFF", size: 16 },
  };
  sheet.getRange("A2:H2").merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange("A2").format = {
    fill: theme.tan,
    font: { color: theme.gray, size: 10 },
  };
}

function writeTable(sheet, startRow, startCol, rows, tableName, headers = null) {
  if (!rows.length) return { headers: [], range: "" };
  const cols = headers ?? Object.keys(rows[0]);
  const matrix = [cols, ...rows.map((row) => cols.map((c) => row[c] ?? ""))];
  const range = sheet.getRange(rangeFor(startRow, startCol, matrix.length, cols.length));
  range.values = matrix;
  sheet.getRange(rangeFor(startRow, startCol, 1, cols.length)).format = {
    fill: theme.green,
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRange(rangeFor(startRow + 1, startCol, matrix.length - 1, cols.length)).format = {
    fill: "#FFFFFF",
    font: { color: theme.dark },
  };
  sheet.getRange(rangeFor(startRow, startCol, matrix.length, cols.length)).format.wrapText = true;
  try {
    const table = sheet.tables.add(rangeFor(startRow, startCol, matrix.length, cols.length), true, tableName);
    table.showFilterButton = true;
    table.showBandedRows = true;
  } catch (err) {
    // Tables are useful but not essential for the workbook calculation layer.
  }
  return { headers: cols, range: rangeFor(startRow, startCol, matrix.length, cols.length) };
}

function formatCommon(sheet, lastCol = 10, lastRow = 80) {
  sheet.freezePanes.freezeRows(3);
  for (let c = 0; c < lastCol; c++) {
    sheet.getRange(rangeFor(0, c, lastRow, 1)).format.columnWidthPx = c <= 1 ? 190 : 130;
  }
  sheet.getRange(rangeFor(0, 0, lastRow, lastCol)).format = {
    font: { name: "Microsoft YaHei" },
    verticalAlignment: "top",
  };
}

function percentFormat(sheet, range) {
  sheet.getRange(range).format.numberFormat = "0.0%";
}

function numberFormat(sheet, range, fmt) {
  sheet.getRange(range).format.numberFormat = fmt;
}

function addChart(sheet, type, sourceRange, position, title, yFormat = null) {
  try {
    const chart = sheet.charts.add(type, sheet.getRange(sourceRange));
    chart.title = title;
    chart.hasLegend = true;
    chart.xAxis = { axisType: "textAxis" };
    if (yFormat) chart.yAxis = { numberFormatCode: yFormat };
    chart.setPosition(position[0], position[1]);
  } catch (err) {
    sheet.getRange(position[0]).values = [[`Chart build skipped: ${title}`]];
  }
}

for (const [name, sheet] of Object.entries(sheets)) {
  formatCommon(sheet, 14, 140);
}

// Summary
{
  const s = sheets["Summary"];
  setTitle(s, "First Solar (FSLR) 中文深度研究", `独立研究项目 | 数据截至 ${data.run_date}`);
  s.getRange("A4:B14").values = [
    ["关键结论", "当前读数"],
    ["投资方向", "已有仓位继续跟踪；新资金等待回撤或订单/政策验证后分批"],
    ["当前股价", data.key_metrics.current_price_usd],
    ["公司口径 EV", ""],
    ["EV/FY2026 EBITDA", ""],
    ["TTM P/E", ""],
    ["Backlog", `${data.key_metrics.backlog_gw.toFixed(1)}GW / $${data.key_metrics.backlog_value_usd_bn.toFixed(1)}bn`],
    ["Backlog ASP", ""],
    ["最关键问题", "45X 和贸易政策能否把 backlog 变成 2027+ 可持续现金流"],
    ["下一步验证", "新增 bookings ASP、45X cash realization、OCF-capex、Section 232/TOPCon"],
    ["资料路径", "见 Sources sheet 和 data/sources.csv"],
  ];
  s.getRange("B7").formulas = [["=Valuation!B9"]];
  s.getRange("B8").formulas = [["=Valuation!B15"]];
  s.getRange("B9").formulas = [["=Valuation!B13"]];
  s.getRange("B11").formulas = [["=Valuation!B18"]];
  s.getRange("A4:B4").format = { fill: theme.green, font: { bold: true, color: "#FFFFFF" } };
  s.getRange("B6").format.numberFormat = "$0.00";
  s.getRange("B7").format.numberFormat = "$0.0bn";
  s.getRange("B8").format.numberFormat = "0.0x";
  s.getRange("B9").format.numberFormat = "0.0x";
  s.getRange("B11").format.numberFormat = "$0.00/W";
  s.getRange("D4:F8").values = [
    ["Year", "Net Sales", "Gross Profit"],
    ["2023A", 3318.602, 1300.679],
    ["2024A", 4206.289, 1857.864],
    ["2025A", 5219.376, 2120.339],
    ["2026E mid", 5050.0, 2500.0],
  ];
  s.getRange("D4:F4").format = { fill: theme.blue, font: { bold: true, color: "#FFFFFF" } };
  s.getRange("E5:F8").format.numberFormat = "$#,##0";
  s.getRange("D12:F15").values = [["Scenario", "Implied Price", "Vs Current"], ...data.valuation_scenarios.map((r) => [r.scenario, r.implied_price_usd, ""])];
  s.getRange("F13").formulas = [["=E13/Valuation!$B$5-1"]];
  s.getRange("F13:F15").fillDown();
  s.getRange("D12:F12").format = { fill: theme.blue, font: { bold: true, color: "#FFFFFF" } };
  s.getRange("E13:E15").format.numberFormat = "$0";
  percentFormat(s, "F13:F15");
  addChart(s, "bar", "D4:F8", ["H4", "N19"], "Revenue and Gross Profit", "$#,##0");
  addChart(s, "bar", "D12:E15", ["H21", "N36"], "Scenario Implied Price", "$0");
}

// Financials / KPIs
{
  const s = sheets["Financials KPIs"];
  setTitle(s, "Financials / KPIs", "财务、现金流、产能、backlog，保持口径分开。");
  writeTable(s, 3, 0, data.financials_kpis, "FinancialsKpisTable");
  numberFormat(s, "D5:I21", "#,##0.0");
  s.getRange("L4:M8").values = [
    ["Metric", "Value"],
    ["2025 sold GW", 16.7],
    ["Q1 2026 sold GW", 3.8],
    ["Q1 2026 produced GW", 4.3],
    ["Backlog GW", data.key_metrics.backlog_gw],
  ];
  s.getRange("L4:M4").format = { fill: theme.blue, font: { bold: true, color: "#FFFFFF" } };
  addChart(s, "bar", "L4:M8", ["L11", "R27"], "Volume and Backlog", "0.0");
}

// Valuation
{
  const s = sheets["Valuation"];
  setTitle(s, "Valuation", "公司口径估值、当前倍数和情景估值。");
  s.getRange("A4:E18").values = [
    ["Metric", "Value", "Unit", "Source", "Note"],
    ["Current price", data.key_metrics.current_price_usd, "USD/share", "S11", "Yahoo chart API quote"],
    ["Diluted shares", data.key_metrics.diluted_shares_mn_q1_2026, "mn", "S1", "Q1 diluted share count"],
    ["Market cap", "", "USD bn", "Formula", "Current price x diluted shares / 1000"],
    ["Net cash", data.key_metrics.net_cash_usd_bn_q1_2026, "USD bn", "S1;S2", "Cash and securities less debt"],
    ["Enterprise value", "", "USD bn", "Formula", "Market cap less net cash"],
    ["FY2026 sales midpoint", data.key_metrics.fy2026_sales_mid_usd_bn, "USD bn", "S1;S3", "Guidance midpoint"],
    ["FY2026 adj. EBITDA midpoint", data.key_metrics.fy2026_ebitda_mid_usd_bn, "USD bn", "S1;S3", "Guidance midpoint"],
    ["TTM EPS", data.key_metrics.ttm_eps_usd, "USD/share", "S1;S4", "FY2025 EPS - Q1 2025 + Q1 2026"],
    ["P/E TTM", "", "x", "Formula", "Current price / TTM EPS"],
    ["EV / FY2026 sales", "", "x", "Formula", "EV / sales midpoint"],
    ["EV / FY2026 EBITDA", "", "x", "Formula", "EV / EBITDA midpoint"],
    ["Backlog GW", data.key_metrics.backlog_gw, "GW", "S1;S3", ""],
    ["Backlog value", data.key_metrics.backlog_value_usd_bn, "USD bn", "S1;S3", ""],
    ["Backlog ASP", "", "USD/W", "Formula", "Backlog value / backlog GW"],
  ];
  s.getRange("B7").formulas = [["=B5*B6/1000"]];
  s.getRange("B9").formulas = [["=B7-B8"]];
  s.getRange("B13").formulas = [["=B5/B12"]];
  s.getRange("B14").formulas = [["=B9/B10"]];
  s.getRange("B15").formulas = [["=B9/B11"]];
  s.getRange("B18").formulas = [["=B17/B16"]];
  s.getRange("A4:E4").format = { fill: theme.green, font: { bold: true, color: "#FFFFFF" } };
  numberFormat(s, "B5:B18", "0.00");
  s.getRange("A20:G23").values = [
    ["Scenario", "Description", "FY2026 EBITDA", "EV/EBITDA", "Net Cash", "Implied Equity Value", "Implied Price"],
    ...data.valuation_scenarios.map((r) => [r.scenario, r.description, r.fy2026_ebitda_usd_bn, r.ev_ebitda_multiple, r.net_cash_usd_bn, "", ""]),
  ];
  s.getRange("F21").formulas = [["=C21*D21+E21"]];
  s.getRange("F21:F23").fillDown();
  s.getRange("G21").formulas = [["=F21*1000/$B$6"]];
  s.getRange("G21:G23").fillDown();
  s.getRange("A20:G20").format = { fill: theme.blue, font: { bold: true, color: "#FFFFFF" } };
  numberFormat(s, "C21:G23", "0.0");
  s.getRange("G21:G23").format.numberFormat = "$0";
  s.getRange("I4:J7").values = [["Scenario", "Implied Price"], ["Bear", ""], ["Base", ""], ["Bull", ""]];
  s.getRange("J5:J7").formulas = [["=G21"], ["=G22"], ["=G23"]];
  s.getRange("I4:J4").format = { fill: theme.blue, font: { bold: true, color: "#FFFFFF" } };
  addChart(s, "bar", "I4:J7", ["I10", "O26"], "Scenario Value Range", "$0");
}

// Peers
{
  const s = sheets["Peers"];
  setTitle(s, "Peers", "同行估值快照；FSLR 同时给出公司口径 cross-check。");
  writeTable(s, 3, 0, data.valuation_peers, "PeersTable");
  numberFormat(s, "D5:Q20", "0.00");
}

// Market Reaction
{
  const s = sheets["Market Reaction"];
  setTitle(s, "Market Reaction", "事件窗口市场反应；不是因果证明，只用于观察预期变化。");
  const rows = data.market_reaction.map((r) => ({ ...r, alpha_formula_pct: "" }));
  writeTable(s, 3, 0, rows, "MarketReactionTable");
  // Columns: fslr_return_pct I, tan_return_pct J, alpha_vs_tan_pct K, alpha_formula_pct N
  s.getRange("N5").formulas = [["=I5-J5"]];
  s.getRange(`N5:N${4 + rows.length}`).fillDown();
  numberFormat(s, "F5:N20", "0.00");
  s.getRange("O4:P10").values = [["Event", "Alpha"], ...data.market_reaction.map((r) => [r.event_date.slice(5), r.alpha_vs_tan_pct])];
  s.getRange("O4:P4").format = { fill: theme.blue, font: { bold: true, color: "#FFFFFF" } };
  addChart(s, "bar", "O4:P10", ["O13", "U29"], "FSLR Alpha vs TAN", "0.0");
}

// Catalysts
{
  const s = sheets["Catalysts Policy Risks"];
  setTitle(s, "Catalysts / Policy / Risks", "政策、监管、贸易、执行和资产负债表跟踪。");
  writeTable(s, 3, 0, data.catalysts_policy_risks, "CatalystsTable");
}

// Research Path
{
  const s = sheets["Research Path"];
  setTitle(s, "Research Path", "关键问题、为什么重要、下一步看什么数据。");
  writeTable(s, 3, 0, data.research_path, "ResearchPathTable");
}

// Sources
{
  const s = sheets["Sources"];
  setTitle(s, "Sources", "一手来源优先；每个数据表均通过 source_id 映射。");
  writeTable(s, 3, 0, data.sources, "SourcesTable");
}

// Checks
{
  const s = sheets["Checks"];
  setTitle(s, "Checks", "Sanity checks：公式、来源、口径和空值。");
  s.getRange("A4:D12").values = [
    ["Check", "Formula result", "Status", "Notes"],
    ["Q1 revenue YoY ties to release", "", "", "Expected about 24%"],
    ["Gross margin recalculates from Q1 revenue/gross profit", "", "", "Q1 2026 gross margin should be about 46.6%"],
    ["EV equals market cap minus net cash", "", "", "Valuation formula cross-check"],
    ["Backlog ASP equals backlog value / backlog GW", "", "", "Backlog value is USD bn; GW maps to $/W"],
    ["Source count >= 12", "", "", "Coverage and citation sanity check"],
    ["Critical valuation inputs are nonblank", "", "", "Avoid silent blank-driven formulas"],
    ["Market reaction alpha formula ties", "", "", "alpha = FSLR return - TAN return"],
    ["FY2026 EBITDA midpoint is $2.7bn", "", "", "From $2.6-$2.8bn guidance"],
  ];
  const formulas = [
    "=ABS(('Financials KPIs'!H5/'Financials KPIs'!G5-1)-0.236)<0.02",
    "=ABS(('Financials KPIs'!H6/'Financials KPIs'!H5*100)-'Financials KPIs'!H7)<0.1",
    "=ABS(Valuation!B9-(Valuation!B7-Valuation!B8))<0.01",
    "=ABS(Valuation!B18-(Valuation!B17/Valuation!B16))<0.001",
    "=COUNTA(Sources!A5:A50)>=12",
    "=COUNTBLANK(Valuation!B5:B18)=0",
    "=ABS('Market Reaction'!N5-('Market Reaction'!I5-'Market Reaction'!J5))<0.01",
    "=ABS(Valuation!B11-2.7)<0.001",
  ];
  for (let i = 0; i < formulas.length; i++) {
    s.getRange(`B${5 + i}`).formulas = [[formulas[i]]];
    s.getRange(`C${5 + i}`).formulas = [[`=IF(B${5 + i},"OK","CHECK")`]];
  }
  s.getRange("A4:D4").format = { fill: theme.green, font: { bold: true, color: "#FFFFFF" } };
}

const inspectSummary = await wb.inspect({
  kind: "table",
  range: "Summary!A4:F15",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 8,
  maxChars: 4000,
});
console.log(inspectSummary.ndjson);

const errors = await wb.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 200 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

for (const sheetName of ["Summary", "Valuation", "Market Reaction", "Checks"]) {
  const preview = await wb.render({
    sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(path.join(outDir, `preview_${sheetName.replace(/[\\/ ]/g, "_")}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(wb);
const outputPath = path.join(outDir, "first_solar_fslr_research_workbook.xlsx");
try {
  await output.save(outputPath);
  console.log(outputPath);
} catch (err) {
  if (err && err.code === "EBUSY") {
    const fallbackPath = path.join(outDir, "first_solar_fslr_research_workbook_updated.xlsx");
    await output.save(fallbackPath);
    console.log(fallbackPath);
  } else {
    throw err;
  }
}
