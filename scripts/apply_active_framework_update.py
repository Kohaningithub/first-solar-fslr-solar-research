from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_asset_module():
    spec = importlib.util.spec_from_file_location("research_assets", ROOT / "scripts" / "build_research_assets.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    data_path = DATA / "research_data.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    key_metrics = data["key_metrics"]
    ev_ebitda = key_metrics.get("ev_ebitda_fy2026_mid", 11.0)
    pe_ttm = key_metrics.get("pe_ttm_company_basis", 19.0)

    data["research_path"][0] = {
        "key_question": "Is FSLR fairly valued, overvalued, or still underappreciated given 2026 EBITDA power and policy-adjusted risk?",
        "why_it_matters": "当前估值已不便宜，但公司质量、45X、backlog 和净现金使 $290-$310 区间的风险收益仍偏正。",
        "data_to_track": "FY2026 EBITDA run-rate, EV/FY2026 EBITDA, TTM P/E, net cash, policy-adjusted multiple.",
        "threshold_or_signpost": "$290-$310 主动建仓；$260-$280 且 thesis intact 加仓；$360-$380 无经营上修则减仓；跌破 $250-$255 且出现 thesis break 则认错。",
        "current_read": f"At ~{ev_ebitda:.1f}x FY2026 EBITDA and ~{pe_ttm:.1f}x TTM P/E, FSLR is not deep value, but current-price risk/reward supports active building with explicit stop/reassessment triggers.",
        "source_id": "S1;S3;S11;S12",
    }

    action_framework = [
        {
            "action": "主动建仓",
            "price_zone": "$290-$310",
            "position_action": "建立 40%-60% 目标仓位",
            "operating_triggers": "无 45X、backlog、OCF 或 FY2026 guide 的 thesis break",
            "risk_control": "不是一把梭；后续用经营触发器决定补仓或减仓",
            "source_id": "S1;S3;S11;S12",
        },
        {
            "action": "回撤加仓",
            "price_zone": "$260-$280",
            "position_action": "补到 70%-90% 目标仓位",
            "operating_triggers": "backlog ASP 稳定、无重大取消/延迟，45X 现金化路径未恶化",
            "risk_control": "若回撤来自政策或订单实质恶化，不加仓",
            "source_id": "S1;S3;S6;S7",
        },
        {
            "action": "确认加仓",
            "price_zone": "$310-$330",
            "position_action": "最多补到满仓",
            "operating_triggers": "新增 bookings ASP 接近/高于 $0.30/W；45X cash realization 清晰；OCF-capex 转正；2027-2029 收入桥更清楚，至少满足两项",
            "risk_control": "只为经营确认加仓，不为单日政策新闻追价",
            "source_id": "S1;S3;S6;S7;S8;S9",
        },
        {
            "action": "持有观察",
            "price_zone": "$330-$360",
            "position_action": "持有，不主动扩仓",
            "operating_triggers": "FY2026 EBITDA run-rate、毛利率和 backlog conversion 与模型一致",
            "risk_control": "若估值先涨而经营未上修，准备减仓",
            "source_id": "S1;S3;S12",
        },
        {
            "action": "减仓",
            "price_zone": "$360-$380",
            "position_action": "降低 20%-40% 仓位",
            "operating_triggers": "股价接近 bull case，但没有 EBITDA、backlog ASP 或 45X 确定性上修；或 EV/FY2026 EBITDA 高于约 13x",
            "risk_control": "保留核心仓位等待下一轮数据，不把 bull case 当 base case",
            "source_id": "S1;S3;S12",
        },
        {
            "action": "认错/止损",
            "price_zone": "<$250-$255 或经营触发器失效",
            "position_action": "减至小仓或退出并重做模型",
            "operating_triggers": "FY2026 EBITDA run-rate/guide 低于约 $2.5bn；新增 bookings ASP < $0.27/W；重大取消/延迟；45X 现金化受阻；OCF-capex 连续两个季度不恢复；2027-2029 收入桥断档",
            "risk_control": "价格跌破区间必须结合 thesis break；经营触发器失效时不等价格确认",
            "source_id": "S1;S3;S6;S7;S11;S12",
        },
    ]
    data["investment_action_framework"] = action_framework

    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(DATA / "research_path.csv", data["research_path"])
    write_csv(DATA / "investment_action_framework.csv", action_framework)

    assets = load_asset_module()
    assets.ensure_dirs()
    font_path = assets.font_setup()
    scenarios = data["valuation_scenarios"]
    scenario_labels = [s["scenario"] for s in scenarios]
    scenario_values = [s["implied_price_usd"] for s in scenarios]

    assets.save_card(
        "01_core_thesis.png",
        "FSLR：美国太阳能制造的稀缺资产",
        "不是普通太阳能 beta，而是政策、贸易保护、backlog 和执行力共同定价",
        [
            "Q1 2026：收入 $1.044bn，调整后 EBITDA $520mn，EPS $3.22",
            "backlog 47.9GW / $14.4bn，隐含约 $0.30/W",
            f"当前约 {key_metrics['ev_ebitda_fy2026_mid']:.1f}x EV/FY2026 EBITDA midpoint，接近基本情景",
            "投资方向：$290-$310 偏买/主动建仓；用价格带和经营触发器控风险",
        ],
        font_path,
        "#0E7C66",
    )
    assets.save_bar_card(
        "05_investment_framework.png",
        "投资框架：主动建仓，但有纪律",
        "$290-$310 偏买；$260-$280 加仓；$360-$380 减仓；<$250-$255 且 thesis break 认错",
        scenario_labels,
        scenario_values,
        "$",
        font_path,
        "#365F91",
    )
    assets.save_tweet_card(
        "tweet_01_conclusion.png",
        "FSLR：当前偏买 / 主动建仓",
        "不是深度低估，但 $290-$310 区间的风险收益支持先建仓。",
        [
            ("核心价值", "美国本土 CdTe 薄膜组件产能，叠加政策信用、净现金和已签 backlog。"),
            ("动作", "$290-$310 建 40%-60% 目标仓位；不是一把梭。"),
            ("加仓", "$260-$280 thesis intact；或新增 ASP、45X、OCF、收入桥至少两项确认。"),
            ("认错", "<$250-$255 且 thesis break；经营触发器失效时不等价格确认。"),
        ],
        font_path,
        "#0E7C66",
    )
    assets.save_tweet_card(
        "tweet_02_numbers_logic.png",
        "数字逻辑：买的不是收入爆发",
        "2026 指引显示，收入不是主要亮点，margin 和 backlog 才是估值核心。",
        [
            ("收入没有爆发", "Net sales：2023A $3.319bn，2024A $4.206bn，2025A $5.219bn；2026E midpoint $5.050bn。"),
            ("利润更强", "2026E gross profit midpoint $2.5bn，gross margin 49.5%，高于 2025A 的 40.6%。"),
            ("45X 是核心变量", "2026 指引嵌入约 $2.145bn 45X benefit；估值不能只看 EBITDA，要看 cash realization。"),
            ("backlog 给可见度", "47.9GW / $14.4bn，backlog ASP 约 $0.3006/W；下一步看新增 ASP 和取消风险。"),
        ],
        font_path,
        "#365F91",
    )
    assets.save_tweet_valuation_card("tweet_03_valuation_scenarios.png", key_metrics["current_price_usd"], scenarios, font_path)
    assets.save_tweet_card(
        "tweet_04_peers_context.png",
        "Peers：FSLR 要单独处理",
        "同行表是 solar ecosystem 的方向性对比，不能把同一个 multiple 直接套到 FSLR。",
        [
            ("组件厂对比", "CSIQ/JKS 更接近全球商品化组件；FSLR 因美国制造和 CdTe 路线应有溢价。"),
            ("设备链对比", "ENPH/SEDG、ARRY/SHLS/NXT 分别是逆变器、tracker、EBOS，商业模式和 margin 不同。"),
            ("公司口径 EV", f"FSLR peers 行已统一为公司口径 EV 约 ${key_metrics['ev_usd_bn_company_basis']:.1f}bn。"),
            ("结论", "FSLR 的溢价有理由；当前偏买，但高位继续加仓要看订单和政策兑现。"),
        ],
        font_path,
        "#6E5AA8",
    )
    assets.save_tweet_card(
        "tweet_05_policy_risk.png",
        "Policy Risk：护城河 + 风险折现",
        "FSLR 是政策受益者，但政策收益不能当作无风险普通利润。",
        [
            ("45X", "决定 gross margin 和现金流质量；重点看 credit recognition、cash realization 和税务口径。"),
            ("OBBBA / FEOC / PFE", "影响客户项目能否拿 credit，进而影响真实需求和融资。"),
            ("AD/CVD / Section 232", "提高进口竞争成本，也可能推高项目成本、拖累需求。"),
            ("Backlog conversion", "新增 risk：取消、延迟、ASP 下滑都会削弱 2027-2029 收入桥。"),
        ],
        font_path,
        "#8A5B20",
    )
    assets.save_tweet_card(
        "tweet_06_monitoring_checklist.png",
        "建仓纪律：价格带 + 经营触发器",
        "结论是偏买，但仓位不能脱离数据。",
        [
            ("建仓", "$290-$310 建 40%-60% 目标仓位。"),
            ("加仓", "$260-$280 thesis intact；$310-$330 只为经营确认加。"),
            ("减仓", "$360-$380 且无 EBITDA/backlog ASP/政策上修，减 20%-40%。"),
            ("认错", "<$250-$255 + thesis break；ASP<$0.27/W、45X受阻、OCF-capex连续不恢复即改判断。"),
        ],
        font_path,
        "#10231F",
    )


if __name__ == "__main__":
    main()
