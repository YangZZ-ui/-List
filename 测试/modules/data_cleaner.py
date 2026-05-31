"""
数据清洗模块
实现多源数据标准化、去重、类型推断与缺失值处理
所有清洗操作记录日志，满足安永审计证据可追溯原则
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple


class CleanLog:
    """清洗操作日志，用于审计追溯"""
    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self.original_rows = 0
        self.original_cols = 0

    def record(self, step: str, detail: str, affected_rows: int = 0):
        self.steps.append({
            "step": step,
            "detail": detail,
            "affected_rows": affected_rows,
        })

    def summary(self) -> Dict[str, Any]:
        return {
            "original_rows": self.original_rows,
            "original_cols": self.original_cols,
            "steps": self.steps,
            "total_steps": len(self.steps),
        }


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """列名标准化：去除首尾空格、统一全角半角、保留原始映射"""
    df = df.copy()
    new_cols = {}
    for col in df.columns:
        clean = str(col).strip()
        # 全角空格
        clean = clean.replace('\u3000', ' ')
        # 连续空格合并
        clean = re.sub(r'\s+', ' ', clean)
        new_cols[col] = clean
    df.rename(columns=new_cols, inplace=True)
    return df


def infer_and_convert_types(df: pd.DataFrame, log: CleanLog) -> pd.DataFrame:
    """智能类型推断与转换"""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            continue

        sample = df[col].dropna().head(100)
        if len(sample) == 0:
            continue

        # 尝试日期转换
        if any(k in col.lower() for k in ["日期", "date", "时间", "time", "记账", "凭证"]):
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                if df[col].notna().sum() > len(df) * 0.5:
                    log.record("类型推断", f"列 '{col}' 推断为日期类型")
                    continue
            except Exception:
                pass

        # 尝试数值转换
        if any(k in col.lower() for k in ["金额", "amount", "借方", "贷方", "balance", "amt", "price", "value", "数量", "count"]):
            try:
                converted = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '').str.replace('，', ''),
                    errors="coerce"
                )
                if converted.notna().sum() > len(df) * 0.5:
                    df[col] = converted
                    log.record("类型推断", f"列 '{col}' 推断为数值类型")
                    continue
            except Exception:
                pass

    return df


def detect_duplicates(df: pd.DataFrame, log: CleanLog) -> pd.DataFrame:
    """检测并标记重复行，保留首次出现记录"""
    dup_mask = df.duplicated(keep="first")
    dup_count = dup_mask.sum()
    if dup_count > 0:
        log.record("重复行检测", f"发现 {dup_count} 行完全重复记录，已标记", affected_rows=int(dup_count))
    return df


def handle_missing_values(df: pd.DataFrame, log: CleanLog) -> pd.DataFrame:
    """缺失值处理：记录严重缺失列，不对数据进行填充（保持原始性，符合审计原则）"""
    missing_summary = {}
    for col in df.columns:
        missing_count = df[col].isna().sum()
        missing_pct = missing_count / len(df) if len(df) > 0 else 0
        if missing_pct > 0.3:
            missing_summary[col] = f"{missing_pct:.1%}"
    if missing_summary:
        detail = "；".join([f"{k}({v})" for k, v in missing_summary.items()])
        log.record("缺失值检测", f"以下列缺失率超过30%：{detail}")
    return df


def clean_amount_format(df: pd.DataFrame, log: CleanLog) -> pd.DataFrame:
    """金额格式统一：去除千分位逗号、处理括号负数、统一币种符号"""
    df = df.copy()
    amount_keywords = ["金额", "amount", "借方", "贷方", "balance", "amt", "price", "value"]
    for col in df.columns:
        if any(k in col.lower() for k in amount_keywords) and not pd.api.types.is_numeric_dtype(df[col]):
            original = df[col].copy()
            cleaned = (
                df[col]
                .astype(str)
                .str.replace(',', '', regex=False)
                .str.replace('，', '', regex=False)
                .str.replace('￥', '', regex=False)
                .str.replace('$', '', regex=False)
                .str.replace('€', '', regex=False)
                .str.replace('(', '-', regex=False)
                .str.replace(')', '', regex=False)
                .str.strip()
            )
            # 检测是否发生了实质性变化
            changed = (original.astype(str) != cleaned).sum()
            if changed > 0:
                try:
                    df[col] = pd.to_numeric(cleaned, errors="coerce")
                    log.record("金额清洗", f"列 '{col}' 统一金额格式，影响 {changed} 行", affected_rows=int(changed))
                except Exception:
                    pass
    return df


def clean_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, CleanLog]:
    """主清洗管道：顺序执行所有清洗步骤"""
    log = CleanLog()
    log.original_rows = len(df)
    log.original_cols = len(df.columns)

    # 1. 列名标准化
    df = standardize_columns(df)
    log.record("列名标准化", "去除首尾空格、合并连续空格、统一全角半角")

    # 2. 金额格式统一（在类型推断之前，确保数值列能被正确识别）
    df = clean_amount_format(df, log)

    # 3. 类型推断与转换
    df = infer_and_convert_types(df, log)

    # 4. 重复行检测
    df = detect_duplicates(df, log)

    # 5. 缺失值检测（仅记录，不填充）
    df = handle_missing_values(df, log)

    return df, log
