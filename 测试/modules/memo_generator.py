"""
分析备忘录生成模块
基于 AI 洞察与审计证据链，自动生成格式化的分析备忘录
支持 Markdown 与 HTML 两种输出格式
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import EY_REVIEW_NOTICE, EY_DISCLAIMER


def generate_markdown_memo(
    project_name: str,
    period: str,
    df_summary: Dict[str, Any],
    insight: Dict[str, Any],
    evidence_chain: List[Dict[str, Any]],
    clean_log: Dict[str, Any],
) -> str:
    """生成 Markdown 格式的审计分析备忘录"""

    lines = []
    lines.append(f"# 审计分析备忘录")
    lines.append("")
    lines.append(f"**项目名称：** {project_name}  ")
    lines.append(f"**审计期间：** {period}  ")
    lines.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"**生成模型：** {insight.get('model_used', '规则引擎')}  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 免责声明
    lines.append("> **独立性声明与职业怀疑提示**")
    lines.append("> ")
    lines.append(f"> {EY_REVIEW_NOTICE}")
    lines.append("")

    # 数据概览
    lines.append("## 一、数据概览")
    lines.append("")
    lines.append(f"- 原始记录数：{df_summary.get('total_rows', 'N/A')} 条")
    lines.append(f"- 清洗后记录数：{df_summary.get('clean_rows', 'N/A')} 条")
    lines.append(f"- 金额列：{df_summary.get('amount_col', 'N/A')}")
    lines.append(f"- 日期列：{df_summary.get('date_col', 'N/A')}")
    lines.append(f"- 总金额：{df_summary.get('total_amount', 'N/A'):,.2f}")
    lines.append("")

    # 清洗日志
    if clean_log and clean_log.get("steps"):
        lines.append("### 数据清洗记录")
        lines.append("")
        for step in clean_log["steps"]:
            affected = f"（影响 {step.get('affected_rows', 0)} 行）" if step.get('affected_rows', 0) > 0 else ""
            lines.append(f"- **{step['step']}**：{step['detail']}{affected}")
        lines.append("")

    # 整体风险评级
    lines.append("## 二、整体风险评级")
    lines.append("")
    risk = insight.get("overall_risk", "低风险")
    risk_emoji = {"高风险": "🔴", "中风险": "🟡", "低风险": "🟢"}.get(risk, "⚪")
    lines.append(f"**{risk_emoji} {risk}**")
    lines.append("")

    # 关键洞察
    lines.append("## 三、关键审计洞察")
    lines.append("")
    for idx, item in enumerate(insight.get("insights", []), 1):
        conf = item.get("confidence", "中")
        rl = item.get("risk_level", "低风险")
        lines.append(f"### 3.{idx} {item.get('title', '未命名洞察')}")
        lines.append("")
        lines.append(f"- **风险等级：** {rl}")
        lines.append(f"- **置信度：** {conf}")
        lines.append(f"- **分析内容：** {item.get('content', '')}")
        lines.append(f"- **审计建议：** {item.get('recommendation', '')}")
        lines.append("")

    if insight.get("key_concerns"):
        lines.append("### 重点关注")
        lines.append("")
        lines.append(insight["key_concerns"])
        lines.append("")

    if insight.get("next_steps"):
        lines.append("### 建议下一步程序")
        lines.append("")
        lines.append(insight["next_steps"])
        lines.append("")

    # 证据链
    if evidence_chain:
        lines.append("## 四、证据链记录")
        lines.append("")
        lines.append("以下记录满足安永审计证据充分性与适当性要求：")
        lines.append("")
        for idx, ev in enumerate(evidence_chain, 1):
            lines.append(f"### 4.{idx} {ev.get('type', '未命名证据')}")
            lines.append("")
            lines.append(f"- **检测样本量：** {ev.get('sample_size', 'N/A')} 条")
            lines.append(f"- **命中记录数：** {ev.get('count', 'N/A')} 条")
            lines.append(f"- **计算公式：** {ev.get('formula', 'N/A')}")
            lines.append(f"- **适用假设：** {ev.get('assumption', 'N/A')}")
            if "mean" in ev:
                lines.append(f"- **样本均值：** {ev['mean']:,.2f}")
            if "std" in ev:
                lines.append(f"- **样本标准差：** {ev['std']:,.2f}")
            lines.append("")

    # 免责声明
    lines.append("---")
    lines.append("")
    lines.append(f"*{EY_DISCLAIMER}*")

    return "\n".join(lines)


def generate_html_memo(
    project_name: str,
    period: str,
    df_summary: Dict[str, Any],
    insight: Dict[str, Any],
    evidence_chain: List[Dict[str, Any]],
    clean_log: Dict[str, Any],
) -> str:
    """生成 HTML 格式的审计分析备忘录（可直接转 PDF）"""

    # 复用 Markdown 内容再包装为 HTML
    md_content = generate_markdown_memo(project_name, period, df_summary, insight, evidence_chain, clean_log)

    try:
        import markdown
        html_body = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
    except ImportError:
        # 降级：简单替换
        html_body = f"<pre>{md_content}</pre>"

    # 读取主题样式
    css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "audit_theme.css")
    custom_css = ""
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            custom_css = f.read()

    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>审计分析备忘录 - {project_name}</title>
<style>
body {{
    font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    line-height: 1.7;
    max-width: 900px;
    margin: 40px auto;
    padding: 0 20px;
    color: #333;
}}
h1 {{ color: #003087; border-bottom: 3px solid #003087; padding-bottom: 10px; }}
h2 {{ color: #005eb8; margin-top: 30px; }}
h3 {{ color: #0072ce; }}
blockquote {{
    background: #f0f4f8;
    border-left: 5px solid #003087;
    margin: 0;
    padding: 12px 18px;
    font-size: 0.95em;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 15px 0;
}}
th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
th {{ background: #003087; color: white; }}
pre {{ background: #f5f5f5; padding: 12px; overflow-x: auto; }}
{custom_css}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

    return html_template
