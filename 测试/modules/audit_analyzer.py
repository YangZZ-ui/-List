"""
审计分析引擎模块
基于安永风险导向审计原则，实现异常分级检测、趋势分析与相关性扫描
所有分析结果附带 evidence_chain，满足审计证据可追溯要求
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from scipy import stats
import sys
import os

# 加载配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import AUDIT_CONFIG


def _compute_zscore(series: pd.Series) -> pd.Series:
    """计算 Z-score，处理常数列"""
    mean_val = series.mean()
    std_val = series.std()
    if std_val == 0 or pd.isna(std_val):
        return pd.Series(0.0, index=series.index)
    return (series - mean_val) / std_val


def _risk_level_from_zscore(z: float) -> str:
    """根据 Z-score 判定风险等级"""
    cfg = AUDIT_CONFIG["anomaly"]
    abs_z = abs(z)
    if abs_z >= cfg["high_zscore"]:
        return "高风险"
    elif abs_z >= cfg["medium_zscore"]:
        return "中风险"
    elif abs_z >= cfg["low_zscore"]:
        return "低风险"
    return ""


def detect_anomalies(df: pd.DataFrame, amount_col: str, date_col: Optional[str] = None) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    异常交易检测（升级版）
    返回：异常 DataFrame + evidence_chain 列表
    """
    anomalies = pd.DataFrame()
    evidence_chain: List[Dict[str, Any]] = []

    if amount_col is None or amount_col not in df.columns:
        return anomalies, evidence_chain

    df_work = df.copy()
    df_work[amount_col] = pd.to_numeric(df_work[amount_col], errors="coerce")
    df_work = df_work.dropna(subset=[amount_col])

    if len(df_work) == 0:
        return anomalies, evidence_chain

    # ---------- 1. 大额规整金额 ----------
    median_amt = df_work[amount_col].abs().median()
    round_mask = df_work[amount_col].astype(str).str.match(r'^-?\d+\.?0*$', na=False)
    round_mask &= df_work[amount_col].abs() >= max(median_amt, AUDIT_CONFIG["anomaly"]["round_amount_threshold"])
    int_amt = df_work[round_mask].copy()
    if len(int_amt) > 0:
        int_amt["异常类型"] = "大额规整金额"
        int_amt["风险等级"] = "中风险"
        int_amt["Z分数"] = _compute_zscore(df_work[amount_col]).reindex(int_amt.index)
        anomalies = pd.concat([anomalies, int_amt], ignore_index=True)
        evidence_chain.append({
            "type": "大额规整金额",
            "count": len(int_amt),
            "formula": f"|金额| >= max(中位数={median_amt:,.2f}, 阈值={AUDIT_CONFIG['anomaly']['round_amount_threshold']}) 且为整数",
            "assumption": "人为调账或舞弊倾向使用整数金额",
            "sample_size": len(df_work),
        })

    # ---------- 2. 统计极端值（风险分级） ----------
    if len(df_work) > 1:
        z_scores = _compute_zscore(df_work[amount_col])
        for level, threshold in [
            ("高风险", AUDIT_CONFIG["anomaly"]["high_zscore"]),
            ("中风险", AUDIT_CONFIG["anomaly"]["medium_zscore"]),
            ("低风险", AUDIT_CONFIG["anomaly"]["low_zscore"]),
        ]:
            mask = z_scores.abs() >= threshold
            if mask.sum() > 0:
                subset = df_work[mask].copy()
                subset["异常类型"] = "统计极端值"
                subset["风险等级"] = level
                subset["Z分数"] = z_scores[mask]
                anomalies = pd.concat([anomalies, subset], ignore_index=True)
                evidence_chain.append({
                    "type": "统计极端值",
                    "risk_level": level,
                    "count": int(mask.sum()),
                    "formula": f"|Z-score| >= {threshold}，其中 Z = (X - μ) / σ",
                    "assumption": "假设金额近似正态分布，极端偏离均值的记录需重点核查",
                    "sample_size": len(df_work),
                    "mean": float(df_work[amount_col].mean()),
                    "std": float(df_work[amount_col].std()),
                })

    # ---------- 3. 节假日凭证（高风险） ----------
    if date_col and date_col in df_work.columns and pd.api.types.is_datetime64_any_dtype(df_work[date_col]):
        holidays = AUDIT_CONFIG["holidays"]
        df_work_temp = df_work.copy()
        df_work_temp["月日"] = df_work_temp[date_col].dt.strftime("%m-%d")
        holiday_rows = df_work_temp[df_work_temp["月日"].isin(holidays)].copy()
        if len(holiday_rows) > 0:
            holiday_rows["异常类型"] = "节假日凭证"
            holiday_rows["风险等级"] = "高风险"
            holiday_rows["Z分数"] = np.nan
            anomalies = pd.concat([anomalies, holiday_rows], ignore_index=True)
            evidence_chain.append({
                "type": "节假日凭证",
                "count": len(holiday_rows),
                "formula": f"记账日期月日在节假日列表中",
                "assumption": "法定节假日或年末记账可能存在跨期调节或突击入账风险",
                "sample_size": len(df_work),
                "holiday_list": holidays,
            })

    # 去重：按所有原始列去重
    if not anomalies.empty:
        anomalies = anomalies.drop_duplicates(keep="first")

    return anomalies, evidence_chain


def analyze_trends(df: pd.DataFrame, amount_col: str, date_col: str) -> Dict[str, Any]:
    """
    月度金额趋势分析，自动标记突变点
    返回趋势摘要字典，附带证据链
    """
    result = {
        "has_data": False,
        "monthly": pd.DataFrame(),
        "spikes": [],
        "evidence": {},
    }

    if date_col not in df.columns or amount_col not in df.columns:
        return result

    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        return result

    df_ts = df[[date_col, amount_col]].copy()
    df_ts[amount_col] = pd.to_numeric(df_ts[amount_col], errors="coerce")
    df_ts = df_ts.dropna()

    if len(df_ts) < AUDIT_CONFIG["evidence"]["min_sample_size"]:
        result["evidence"] = {
            "note": f"样本量不足趋势分析（当前{len(df_ts)}条，最低要求{AUDIT_CONFIG['evidence']['min_sample_size']}条）"
        }
        return result

    # 按月聚合
    monthly = df_ts.set_index(date_col).resample('M')[amount_col].sum().reset_index()
    monthly = monthly[monthly[amount_col] != 0]

    if len(monthly) < 3:
        result["evidence"] = {"note": "有效月份少于3个月，无法进行可靠趋势分析"}
        return result

    result["has_data"] = True
    result["monthly"] = monthly

    # 突变点检测：月度环比变化超过 2 倍标准差
    monthly["环比变化"] = monthly[amount_col].pct_change()
    monthly["环比Z分数"] = _compute_zscore(monthly["环比变化"])
    spikes = monthly[monthly["环比Z分数"].abs() >= 2.0].copy()

    if len(spikes) > 0:
        spike_records = []
        for _, row in spikes.iterrows():
            spike_records.append({
                "month": row[date_col].strftime("%Y-%m"),
                "amount": float(row[amount_col]),
                "change_pct": float(row["环比变化"]) if pd.notna(row["环比变化"]) else None,
                "zscore": float(row["环比Z分数"]),
            })
        result["spikes"] = spike_records

    result["evidence"] = {
        "type": "月度趋势分析",
        "formula": "月度金额 = SUM(当月所有记录金额)；环比Z-score = (环比变化 - 均值) / 标准差",
        "assumption": "假设月度金额序列相对稳定，异常波动可能暗示截止性问题或收入操纵",
        "sample_size": len(df_ts),
        "months_analyzed": len(monthly),
        "spike_count": len(spikes),
    }

    return result


def correlation_scan(df: pd.DataFrame, amount_col: str, text_col: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    相关性扫描：检测摘要文本与金额之间的异常匹配
    例如：摘要含"招待费"但金额显著低于该科目历史均值
    """
    findings = []

    if text_col is None or text_col not in df.columns or amount_col not in df.columns:
        return findings

    df_work = df.copy()
    df_work[amount_col] = pd.to_numeric(df_work[amount_col], errors="coerce")
    df_work = df_work.dropna(subset=[amount_col, text_col])

    if len(df_work) < 10:
        return findings

    # 定义敏感关键词与预期方向
    keyword_patterns = [
        {"keywords": ["招待", "接待", "宴请", "餐费", "dining"], "name": "业务招待费", "direction": "high"},
        {"keywords": ["礼品", "gift", "送礼"], "name": "礼品费用", "direction": "high"},
        {"keywords": ["咨询", "consulting", "顾问"], "name": "咨询服务费", "direction": "high"},
        {"keywords": ["工资", "薪金", "salary", "薪酬"], "name": "工资薪金", "direction": "low"},
    ]

    overall_median = df_work[amount_col].abs().median()
    overall_mean = df_work[amount_col].abs().mean()

    for pattern in keyword_patterns:
        mask = df_work[text_col].astype(str).str.lower().str.contains("|".join(pattern["keywords"]), na=False)
        subset = df_work[mask]
        if len(subset) < 3:
            continue

        subset_median = subset[amount_col].abs().median()
        subset_mean = subset[amount_col].abs().mean()

        # 检测逻辑
        flagged = False
        reason = ""
        if pattern["direction"] == "high" and subset_median < overall_median * 0.3:
            flagged = True
            reason = f"{pattern['name']} 金额中位数（{subset_median:,.2f}）显著低于整体中位数（{overall_median:,.2f}），可能存在拆分交易规避审批"
        elif pattern["direction"] == "low" and subset_median > overall_median * 3:
            flagged = True
            reason = f"{pattern['name']} 金额中位数（{subset_median:,.2f}）显著高于整体中位数（{overall_median:,.2f}），需关注异常发放或费用归属"

        if flagged:
            findings.append({
                "category": pattern["name"],
                "risk_level": "中风险",
                "reason": reason,
                "affected_records": len(subset),
                "evidence": {
                    "type": "相关性扫描",
                    "formula": "子集金额中位数 vs 整体金额中位数",
                    "assumption": f"'{pattern['name']}' 类交易金额应符合该科目的一般水平，显著偏离提示异常",
                    "sample_size": len(subset),
                    "overall_median": float(overall_median),
                    "subset_median": float(subset_median),
                }
            })

    return findings
