"""
AI 洞察生成模块
封装大模型调用，无 API Key 时自动降级为规则引擎
所有输出强制包含置信度、风险等级与复核提示，符合安永职业怀疑原则
"""

import json
import os
import sys
from typing import Dict, Any, List, Optional
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, HAS_AI, AUDIT_CONFIG, EY_REVIEW_NOTICE


def _rule_based_insight(df: pd.DataFrame, anomalies: pd.DataFrame, trend: Dict[str, Any], correlations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """规则引擎降级方案：当无 AI API 时，基于审计规则生成结构化洞察"""
    insights = []
    overall_risk = "低风险"

    # 异常统计
    if not anomalies.empty:
        high_risk = len(anomalies[anomalies["风险等级"] == "高风险"])
        medium_risk = len(anomalies[anomalies["风险等级"] == "中风险"])
        low_risk = len(anomalies[anomalies["风险等级"] == "低风险"])

        if high_risk > 0:
            overall_risk = "高风险"
            insights.append({
                "title": f"发现 {high_risk} 条高风险异常记录",
                "content": "包含统计极端值或节假日记账等高风险特征，建议立即执行进一步实质性程序。",
                "confidence": "高",
                "risk_level": "高风险",
                "recommendation": "抽取全部高风险记录，检查原始凭证、审批流程与业务实质。",
            })
        elif medium_risk > 0:
            overall_risk = "中风险"
            insights.append({
                "title": f"发现 {medium_risk} 条中等风险异常记录",
                "content": "存在大额规整金额或中等偏离的统计极端值，需审计师关注。",
                "confidence": "中",
                "risk_level": "中风险",
                "recommendation": "对中等风险记录执行抽样检查，验证交易真实性与商业合理性。",
            })
        else:
            insights.append({
                "title": f"发现 {low_risk} 条低风险异常记录",
                "content": "异常程度较低，但仍建议纳入关注范围。",
                "confidence": "中",
                "risk_level": "低风险",
                "recommendation": "结合审计重要性水平，判断是否需进一步核查。",
            })
    else:
        insights.append({
            "title": "未发现明显异常",
            "content": "基于当前规则与阈值，数据未触发异常检测条件。",
            "confidence": "中",
            "risk_level": "低风险",
            "recommendation": "不应因此减少审计程序，仍需执行计划中的实质性测试。",
        })

    # 趋势突变
    if trend.get("has_data") and trend.get("spikes"):
        spike_count = len(trend["spikes"])
        if spike_count > 0:
            overall_risk = max(overall_risk, "中风险") if overall_risk != "高风险" else overall_risk
            insights.append({
                "title": f"月度趋势检测到 {spike_count} 个突变点",
                "content": "某些月份金额环比波动异常，可能存在截止性认定问题或收入操纵迹象。",
                "confidence": "中",
                "risk_level": "中风险",
                "recommendation": "检查突变月份前后的凭证截止性，关注期末前后大额交易的入账时点。",
            })

    # 相关性扫描
    if correlations:
        for finding in correlations[:3]:  # 只取前3条
            insights.append({
                "title": f"相关性扫描：{finding['category']}",
                "content": finding["reason"],
                "confidence": "中",
                "risk_level": finding.get("risk_level", "中风险"),
                "recommendation": f"核查 {finding['category']} 相关交易的审批记录与业务背景，确认费用归属与金额合理性。",
            })

    return {
        "overall_risk": overall_risk,
        "insights": insights,
        "model_used": "规则引擎（无 AI API）",
        "disclaimer": EY_REVIEW_NOTICE,
    }


def _call_llm(prompt: str, system_prompt: str = "") -> Optional[str]:
    """调用大模型 API（OpenAI 兼容格式）"""
    if not HAS_AI:
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI 调用失败：{e}")
        return None


def generate_insight(
    df: pd.DataFrame,
    anomalies: pd.DataFrame,
    trend: Dict[str, Any],
    correlations: List[Dict[str, Any]],
    evidence_chain: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    生成 AI 审计洞察
    优先使用大模型，失败或不可用则降级为规则引擎
    """
    if not HAS_AI:
        return _rule_based_insight(df, anomalies, trend, correlations)

    # 构造 Prompt
    anomaly_summary = "未发现异常。"
    if not anomalies.empty:
        risk_counts = anomalies["风险等级"].value_counts().to_dict()
        anomaly_summary = "；".join([f"{k}：{v}条" for k, v in risk_counts.items()])

    trend_summary = "无趋势数据。"
    if trend.get("has_data"):
        spike_info = f"突变点 {len(trend.get('spikes', []))} 个" if trend.get("spikes") else "无显著突变"
        trend_summary = f"分析月份数：{trend['evidence'].get('months_analyzed', 0)}，{spike_info}"

    corr_summary = "无相关性异常。"
    if correlations:
        corr_summary = "；".join([f"{c['category']}({c['risk_level']})" for c in correlations[:5]])

    system_prompt = (
        "你是一位资深安永审计合伙人，拥有丰富的风险导向审计经验。"
        "你的任务是基于数据分析结果，生成结构化的审计洞察。"
        "必须保持职业怀疑态度，不得给出绝对结论，所有判断必须标注置信度。"
        "输出必须是严格的 JSON 格式，不要包含任何 markdown 代码块标记。"
    )

    prompt = f"""
基于以下审计数据分析结果，生成 JSON 格式的洞察报告：

【数据概览】
- 总记录数：{len(df)} 条
- 金额列统计：均值={df[df.select_dtypes(include='number').columns[0]].mean():,.2f if len(df.select_dtypes(include='number').columns)>0 else 'N/A'}，中位数={df[df.select_dtypes(include='number').columns[0]].median():,.2f if len(df.select_dtypes(include='number').columns)>0 else 'N/A'}

【异常检测结果】
{anomaly_summary}

【趋势分析】
{trend_summary}

【相关性扫描】
{corr_summary}

【证据链摘要】
{json.dumps(evidence_chain, ensure_ascii=False, indent=2)[:2000]}

请输出以下 JSON 结构（不要添加 markdown 标记）：
{{
  "overall_risk": "高风险|中风险|低风险",
  "insights": [
    {{
      "title": "洞察标题",
      "content": "详细分析内容",
      "confidence": "高|中|低",
      "risk_level": "高风险|中风险|低风险",
      "recommendation": "具体审计建议"
    }}
  ],
  "key_concerns": "需要重点关注的领域总结（1-2句话）",
  "next_steps": "建议执行的下一步审计程序"
}}
"""

    llm_response = _call_llm(prompt, system_prompt)
    if llm_response is None:
        return _rule_based_insight(df, anomalies, trend, correlations)

    # 解析 JSON
    try:
        # 尝试提取 JSON
        text = llm_response.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        result = json.loads(text)
        result["model_used"] = OPENAI_MODEL
        result["disclaimer"] = EY_REVIEW_NOTICE
        return result
    except Exception as e:
        print(f"AI 输出解析失败：{e}，回退到规则引擎")
        return _rule_based_insight(df, anomalies, trend, correlations)
