"""
可视化模块
封装审计场景常用图表，支持按风险等级着色与交互式探索
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any, Optional, List


RISK_COLORS = {
    "高风险": "#d32f2f",
    "中风险": "#f9a825",
    "低风险": "#1976d2",
    "": "#9e9e9e",
}


def plot_amount_histogram(df: pd.DataFrame, amount_col: str, anomalies: Optional[pd.DataFrame] = None) -> go.Figure:
    """金额分布直方图，异常点用风险颜色叠加显示"""
    fig = px.histogram(df, x=amount_col, nbins=50, title="金额分布直方图", opacity=0.7)
    fig.update_traces(marker_color="#90caf9")

    if anomalies is not None and not anomalies.empty and amount_col in anomalies.columns:
        for risk in ["高风险", "中风险", "低风险"]:
            subset = anomalies[anomalies.get("风险等级") == risk]
            if len(subset) > 0:
                fig.add_trace(go.Scatter(
                    x=subset[amount_col],
                    y=[0] * len(subset),
                    mode="markers",
                    marker=dict(color=RISK_COLORS.get(risk, "#000"), size=10, symbol="x"),
                    name=f"{risk}异常",
                ))

    fig.update_layout(
        xaxis_title=amount_col,
        yaxis_title="频数",
        legend_title="风险等级",
        hovermode="x unified",
    )
    return fig


def plot_trend_line(trend_data: Dict[str, Any], date_col: str, amount_col: str) -> Optional[go.Figure]:
    """月度趋势折线图，标记突变点"""
    if not trend_data.get("has_data"):
        return None

    monthly = trend_data["monthly"]
    if monthly.empty or date_col not in monthly.columns:
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly[date_col],
        y=monthly[amount_col],
        mode="lines+markers",
        name="月度金额",
        line=dict(color="#003087", width=2),
        marker=dict(size=6),
    ))

    # 标记突变点
    if trend_data.get("spikes"):
        spike_df = pd.DataFrame(trend_data["spikes"])
        spike_df["month_dt"] = pd.to_datetime(spike_df["month"])
        fig.add_trace(go.Scatter(
            x=spike_df["month_dt"],
            y=spike_df["amount"],
            mode="markers",
            name="趋势突变点",
            marker=dict(color="#d32f2f", size=12, symbol="star"),
            hovertemplate="月份: %{x|%Y-%m}<br>金额: %{y:,.2f}<extra></extra>",
        ))

    fig.update_layout(
        title="月度金额趋势（突变点已标记）",
        xaxis_title="月份",
        yaxis_title=f"{amount_col} 合计",
        hovermode="x unified",
    )
    return fig


def plot_anomaly_composition(anomalies: pd.DataFrame) -> Optional[go.Figure]:
    """异常类型构成饼图 + 风险等级条形图"""
    if anomalies.empty:
        return None

    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "domain"}, {"type": "bar"}]],
        subplot_titles=("异常类型构成", "风险等级分布"),
    )

    # 饼图：异常类型
    type_counts = anomalies["异常类型"].value_counts()
    fig.add_trace(go.Pie(
        labels=type_counts.index,
        values=type_counts.values,
        hole=0.35,
        name="异常类型",
    ), row=1, col=1)

    # 条形图：风险等级
    if "风险等级" in anomalies.columns:
        risk_counts = anomalies["风险等级"].value_counts()
        colors = [RISK_COLORS.get(r, "#9e9e9e") for r in risk_counts.index]
        fig.add_trace(go.Bar(
            x=risk_counts.index,
            y=risk_counts.values,
            marker_color=colors,
            name="风险等级",
        ), row=1, col=2)

    fig.update_layout(title_text="异常交易风险概览", showlegend=False)
    return fig


def plot_heatmap(df: pd.DataFrame, date_col: str, amount_col: str, category_col: Optional[str] = None) -> Optional[go.Figure]:
    """
    热力图：科目 × 月份金额矩阵
    如果没有科目列，则使用全部数据按月份聚合
    """
    if date_col not in df.columns or amount_col not in df.columns:
        return None

    df_work = df.copy()
    df_work[amount_col] = pd.to_numeric(df_work[amount_col], errors="coerce")
    df_work = df_work.dropna(subset=[date_col, amount_col])

    if not pd.api.types.is_datetime64_any_dtype(df_work[date_col]):
        try:
            df_work[date_col] = pd.to_datetime(df_work[date_col], errors="coerce")
        except Exception:
            return None

    df_work = df_work.dropna(subset=[date_col])
    df_work["年月"] = df_work[date_col].dt.to_period("M").astype(str)

    if category_col and category_col in df_work.columns:
        # 取前15个高频科目，避免图表过宽
        top_cats = df_work[category_col].value_counts().head(15).index.tolist()
        df_work = df_work[df_work[category_col].isin(top_cats)]
        pivot = df_work.groupby(["年月", category_col])[amount_col].sum().unstack(fill_value=0)
        title = f"{category_col} × 月份 金额热力图（Top 15）"
        y_label = category_col
    else:
        pivot = df_work.groupby("年月")[amount_col].sum().to_frame("总金额").T
        title = "月度总金额热力图"
        y_label = "总金额"

    if pivot.empty:
        return None

    fig = px.imshow(
        pivot,
        labels=dict(x="月份", y=y_label, color="金额"),
        title=title,
        color_continuous_scale="Blues",
        aspect="auto",
    )
    fig.update_layout(height=500 if category_col else 250)
    return fig


def plot_risk_scatter(anomalies: pd.DataFrame, amount_col: str, date_col: Optional[str] = None) -> Optional[go.Figure]:
    """异常风险散点图：金额 vs 时间（如有日期）或索引，颜色区分风险等级"""
    if anomalies.empty or amount_col not in anomalies.columns:
        return None

    df = anomalies.copy()
    df["_x"] = df[date_col] if date_col and date_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[date_col]) else df.index

    fig = px.scatter(
        df,
        x="_x",
        y=amount_col,
        color="风险等级" if "风险等级" in df.columns else None,
        color_discrete_map=RISK_COLORS,
        symbol="异常类型" if "异常类型" in df.columns else None,
        title="异常交易风险散点图",
        hover_data=[col for col in ["异常类型", "Z分数"] if col in df.columns],
    )
    fig.update_layout(
        xaxis_title=date_col if date_col else "索引",
        yaxis_title=amount_col,
    )
    return fig
