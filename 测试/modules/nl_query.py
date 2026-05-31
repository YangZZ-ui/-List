"""
自然语言查询模块
保留原有审计查询能力，支持在全部数据与异常数据范围内查询
"""

import re
import pandas as pd
import streamlit as st
from typing import Tuple


def detect_amount_col(df: pd.DataFrame) -> str:
    for col in df.columns:
        col_lower = col.lower()
        if any(k in col_lower for k in ["金额", "amount", "借方", "贷方", "balance", "amt", "本地货币"]):
            return col
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) and col not in ["年", "月", "日"]:
            return col
    return None


def detect_date_col(df: pd.DataFrame) -> str:
    for col in df.columns:
        if any(k in col.lower() for k in ["日期", "date", "记账日期", "凭证日期", "posting"]):
            return col
    return None


def detect_text_col(df: pd.DataFrame) -> str:
    for col in df.columns:
        if any(k in col.lower() for k in ["摘要", "描述", "text", "header", "说明"]):
            return col
    return None


def detect_account_col(df: pd.DataFrame) -> str:
    for col in df.columns:
        col_lower = col.lower()
        if any(k in col_lower for k in ["科目", "account", "gl", "代码", "assignment"]):
            return col
    return None


def parse_nl_query(df: pd.DataFrame, anomalies_df: pd.DataFrame, query_text: str, scope: str = "全部数据") -> Tuple[pd.DataFrame, str]:
    if scope == "异常数据" and not anomalies_df.empty:
        data_df = anomalies_df.copy()
        scope_desc = "异常数据"
    else:
        data_df = df.copy()
        scope_desc = "全部数据"
        if scope == "异常数据" and anomalies_df.empty:
            st.warning("当前没有异常数据，已切换为查询全部数据")

    query_original = query_text.strip()
    query_lower = query_original.lower()
    amount_col = detect_amount_col(data_df)
    date_col = detect_date_col(data_df)
    account_col = detect_account_col(data_df)
    text_col = detect_text_col(data_df)

    # 最高/最低金额
    if "最高" in query_lower or "最大" in query_lower:
        if amount_col:
            n = 15
            match_n = re.search(r"(\d+)\s*笔", query_lower)
            if match_n:
                n = int(match_n.group(1))
            result = data_df.nlargest(n, amount_col)
            return result, f"在{scope_desc}中，金额最大的 {len(result)} 笔交易"
    if "最低" in query_lower or "最小" in query_lower:
        if amount_col:
            n = 15
            match_n = re.search(r"(\d+)\s*笔", query_lower)
            if match_n:
                n = int(match_n.group(1))
            result = data_df.nsmallest(n, amount_col)
            return result, f"在{scope_desc}中，金额最小的 {len(result)} 笔交易"

    # 节假日凭证
    if "节假日" in query_lower and date_col:
        if pd.api.types.is_datetime64_any_dtype(data_df[date_col]):
            from config import AUDIT_CONFIG
            holidays = AUDIT_CONFIG["holidays"]
            data_df_temp = data_df.copy()
            data_df_temp["月日"] = data_df_temp[date_col].dt.strftime("%m-%d")
            result = data_df_temp[data_df_temp["月日"].isin(holidays)].drop(columns=["月日"])
            return result, f"在{scope_desc}中，节假日记账记录，共 {len(result)} 条"

    # 等于匹配
    eq_pattern = r'(.+?)\s*(?:等于|==|=)\s*(.+)'
    match_eq = re.search(eq_pattern, query_original)
    if match_eq:
        col_part = match_eq.group(1).strip()
        value_part = match_eq.group(2).strip()
        if (value_part.startswith('"') or value_part.startswith("'")) and (value_part.endswith('"') or value_part.endswith("'")):
            value_part = value_part[1:-1]
        matched_col = None
        if col_part in data_df.columns:
            matched_col = col_part
        else:
            for col in data_df.columns:
                if col_part.lower() in col.lower():
                    matched_col = col
                    break
            if not matched_col and "account" in col_part.lower():
                matched_col = detect_account_col(data_df)
        if matched_col:
            try:
                val_num = float(value_part)
                if pd.api.types.is_numeric_dtype(data_df[matched_col]):
                    result = data_df[data_df[matched_col] == val_num]
                else:
                    result = data_df[data_df[matched_col].astype(str).str.strip() == value_part]
            except ValueError:
                result = data_df[data_df[matched_col].astype(str).str.strip() == value_part]
            if not result.empty:
                return result, f"在{scope_desc}中，筛选 {matched_col} = {value_part}，共 {len(result)} 条"
            else:
                return pd.DataFrame(), f"在{scope_desc}中未找到 {matched_col} = {value_part} 的记录"

    # 包含匹配
    contain_pattern = r'(.+?)\s*包含\s*(.+)'
    match_cont = re.search(contain_pattern, query_original)
    if match_cont:
        col_part = match_cont.group(1).strip()
        keyword = match_cont.group(2).strip()
        matched_col = None
        if col_part in data_df.columns:
            matched_col = col_part
        else:
            for col in data_df.columns:
                if col_part.lower() in col.lower():
                    matched_col = col
                    break
        if matched_col:
            result = data_df[data_df[matched_col].astype(str).str.contains(keyword, na=False, case=False)]
            if not result.empty:
                return result, f"在{scope_desc}中，筛选 {matched_col} 包含 '{keyword}'，共 {len(result)} 条"
            else:
                return pd.DataFrame(), f"在{scope_desc}中未找到 {matched_col} 包含 '{keyword}' 的记录"

    # 大于/小于
    match_gt = re.search(r"大于\s*([0-9,.]+)", query_lower)
    if match_gt and amount_col:
        val = float(match_gt.group(1).replace(',', ''))
        result = data_df[data_df[amount_col] > val]
        return result, f"在{scope_desc}中，{amount_col} > {val:,.2f}，共 {len(result)} 条"
    match_lt = re.search(r"小于\s*([0-9,.]+)", query_lower)
    if match_lt and amount_col:
        val = float(match_lt.group(1).replace(',', ''))
        result = data_df[data_df[amount_col] < val]
        return result, f"在{scope_desc}中，{amount_col} < {val:,.2f}，共 {len(result)} 条"

    # 关键词匹配
    if text_col:
        keywords = ["收入", "费用", "销售", "管理", "工资", "租金", "transfer", "salary"]
        matched_kw = [kw for kw in keywords if kw in query_lower]
        if matched_kw:
            result = data_df[data_df[text_col].str.contains("|".join(matched_kw), na=False, case=False)]
            if not result.empty:
                return result, f"在{scope_desc}中，筛选 {text_col} 包含 {', '.join(matched_kw)}，共 {len(result)} 条"
            else:
                return pd.DataFrame(), f"在{scope_desc}中未找到 {text_col} 包含相关关键词的记录"

    return data_df.head(100), f"在{scope_desc}中未识别到明确条件，显示前100行（共{len(data_df)}行）"
