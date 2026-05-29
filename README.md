# First Solar (FSLR) 中文深度研究

这是一个独立研究项目，目标不是新闻摘要，而是可审阅、可复用、可发布的 First Solar（NASDAQ: FSLR）投资研究底稿。

## Thesis

FSLR 不是传统“太阳能 beta”交易。它更像一个美国工业政策、贸易保护和稀缺本土产能共同支撑的高波动制造业资产。公司基本面强，backlog 可见度高，资产负债表干净；当前股价不算便宜，但 $290-$310 区间的风险收益仍支持偏买/主动建仓，后续用价格带和经营触发器加减仓。

## 关键结论

- Q1 2026 net sales 为 $1.044bn，调整后 EBITDA 为 $520mn，EPS 为 $3.22；全年指引维持在 net sales $4.9-$5.2bn、调整后 EBITDA $2.6-$2.8bn。
- Q1 末已签约 backlog 为 47.9GW、$14.4bn，隐含约 $0.30/W。backlog 是核心护城河，但未来股价更看新增 bookings 的价格和交付年份。
- 按当前价格约 $294.41、Q1 diluted shares 107.6mn 和净现金约 $2.0bn 估算，EV/FY2026 EBITDA midpoint 约 11.0x，已经接近基本情景。
- 投资框架偏“主动建仓”：$290-$310 建立 40%-60% 目标仓位；$260-$280 且 thesis intact 加仓；$360-$380 若无经营上修则减仓；跌破 $250-$255 且出现 45X/backlog/OCF thesis break 则认错。

## 项目结构

- `investment_memo.md`：中文投资备忘录
- `publish_long_post_zh.md`：可直接发布的中文长帖
- `data/`：整理后的 CSV/JSON 数据表，均带 source_id
- `outputs/first_solar_fslr_research_workbook.xlsx`：Excel workbook；若该文件正在桌面 Excel 中打开，脚本会另存为 `_updated.xlsx` 或 timestamp 版本
- `media/`：中文媒体 PNG 图；`tweet_*.png` 为新版长帖对应推文图
- `scripts/`：重建数据、图片和 workbook 的脚本

## 如何重建

1. 运行 `scripts/build_research_assets.py` 生成数据表、memo、长帖和 PNG。
2. 运行 `scripts/build_workbook.mjs` 生成 Excel workbook。
3. 数据源索引见 `data/sources.csv`；核心模型数据见 `data/research_data.json`。

本项目数据截至 2026-05-28。市场价格和估值会随交易日变化，复用时请先重跑脚本并重新检查 `Checks` sheet。
