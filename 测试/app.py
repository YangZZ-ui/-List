"""
智能审计洞察与协作平台 - 主应用
基于安永会计师事务所专业原则设计
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import json
import zipfile
from datetime import datetime

from config import EY_REVIEW_NOTICE, HAS_AI, DB_DRIVERS
from modules.data_connector import load_data as connector_load_data
from modules.data_cleaner import clean_data
from modules.audit_analyzer import detect_anomalies, analyze_trends, correlation_scan
from modules.visualizer import (
    plot_amount_histogram, plot_trend_line, plot_anomaly_composition,
    plot_heatmap, plot_risk_scatter,
)
from modules.ai_insight import generate_insight
from modules.memo_generator import generate_markdown_memo, generate_html_memo
from modules.client_communication import generate_client_response
from modules.project_dashboard import render_dashboard, export_dashboard_data
from modules.report_styler import generate_word_report, generate_html_report
from modules.nl_query import detect_amount_col, detect_date_col, detect_text_col, detect_account_col, parse_nl_query

st.set_page_config(page_title="智能审计洞察与协作平台", layout="wide")
st.markdown("<h1 style='color:#003087;'>智能审计洞察与协作平台</h1>", unsafe_allow_html=True)
st.markdown("<div style='color:#666;font-size:14px;'>数据处理 · AI洞察 · 可视化 · 客户协作 · 基于安永专业原则</div>", unsafe_allow_html=True)

# ---------- Session State ----------
defaults = {
    "df_raw": None,
    "df_cleaned": None,
    "data_meta": None,
    "clean_log": None,
    "amount_col": None,
    "date_col": None,
    "text_col": None,
    "account_col": None,
    "anomalies": pd.DataFrame(),
    "trend": {},
    "correlations": [],
    "insight": {},
    "evidence_chain": [],
    "nl_query": "",
    "query_scope": "全部数据",
    "project_name": "",
    "audit_period": "",
    "db_type": "mysql",
    "db_host": "localhost",
    "db_port": 3306,
    "db_user": "",
    "db_password": "",
    "db_name": "",
    "db_sql": "SELECT * FROM your_table LIMIT 10000",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------- 侧边栏 ----------
with st.sidebar:
    st.header("导航")
    nav = st.radio("", ["数据洞察", "项目协作", "客户沟通"], label_visibility="collapsed")

    st.divider()
    st.header("项目信息")
    st.session_state.project_name = st.text_input("项目名称", value=st.session_state.project_name)
    st.session_state.audit_period = st.text_input("审计期间", value=st.session_state.audit_period)

    st.divider()
    if st.session_state.df_cleaned is not None:
        st.success(f"已加载 {len(st.session_state.df_cleaned)} 行数据")
        if st.button("🗑️ 清除数据"):
            for k in ["df_raw", "df_cleaned", "data_meta", "clean_log", "anomalies", "trend", "correlations", "insight", "evidence_chain"]:
                st.session_state[k] = defaults[k]
            st.rerun()

# ==================== 数据洞察 ====================
if nav == "数据洞察":
    tab_load, tab_query, tab_viz, tab_ai, tab_export = st.tabs(["📂 数据加载", "🔍 查询分析", "📈 可视化看板", "🤖 AI洞察", "📤 导出交付"])

    # ---------- 数据加载 ----------
    with tab_load:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("文件上传")
            uploaded = st.file_uploader("上传试算平衡表/序时账/费用明细（Excel/CSV/JSON）", type=["xlsx", "csv", "json"])
            if uploaded and st.button("加载文件"):
                df, meta = connector_load_data("file", uploaded)
                if df is not None:
                    st.session_state.df_raw = df
                    st.session_state.data_meta = meta.to_dict() if meta else {}
                    st.success(f"文件加载成功：{meta.rows} 行 × {meta.cols} 列")
                    st.rerun()

        with col2:
            st.subheader("数据库连接")
            with st.expander("配置数据库连接"):
                st.session_state.db_type = st.selectbox("数据库类型", list(DB_DRIVERS.keys()))
                st.session_state.db_host = st.text_input("主机", value=st.session_state.db_host)
                st.session_state.db_port = st.number_input("端口", value=st.session_state.db_port)
                st.session_state.db_user = st.text_input("用户名")
                st.session_state.db_password = st.text_input("密码", type="password")
                st.session_state.db_name = st.text_input("数据库名")
                st.session_state.db_sql = st.text_area("SQL 查询", value=st.session_state.db_sql, height=80)
                if st.button("执行查询"):
                    tmpl = DB_DRIVERS[st.session_state.db_type]
                    conn_str = tmpl.format(
                        user=st.session_state.db_user,
                        password=st.session_state.db_password,
                        host=st.session_state.db_host,
                        port=st.session_state.db_port,
                        database=st.session_state.db_name,
                    )
                    df, meta = connector_load_data("database", conn_str, st.session_state.db_sql)
                    if df is not None:
                        st.session_state.df_raw = df
                        st.session_state.data_meta = meta.to_dict() if meta else {}
                        st.success(f"查询成功：{meta.rows} 行 × {meta.cols} 列")
                        st.rerun()

        if st.session_state.df_raw is not None:
            st.divider()
            st.subheader("数据预览与清洗")
            c1, c2, c3 = st.columns(3)
            c1.metric("原始行数", len(st.session_state.df_raw))
            c2.metric("原始列数", len(st.session_state.df_raw.columns))
            c3.metric("来源", st.session_state.data_meta.get("source_type", "未知"))

            if st.button("🧹 执行数据清洗"):
                df_cleaned, clean_log = clean_data(st.session_state.df_raw)
                st.session_state.df_cleaned = df_cleaned
                st.session_state.clean_log = clean_log.summary()
                st.session_state.amount_col = detect_amount_col(df_cleaned)
                st.session_state.date_col = detect_date_col(df_cleaned)
                st.session_state.text_col = detect_text_col(df_cleaned)
                st.session_state.account_col = detect_account_col(df_cleaned)
                st.success("清洗完成")
                st.rerun()

            if st.session_state.df_cleaned is not None:
                st.info(f"清洗后：{len(st.session_state.df_cleaned)} 行，金额列={st.session_state.amount_col}，日期列={st.session_state.date_col}")
                with st.expander("预览清洗后数据（前50行）"):
                    st.dataframe(st.session_state.df_cleaned.head(50), use_container_width=True)
                if st.session_state.clean_log:
                    with st.expander("清洗日志"):
                        for step in st.session_state.clean_log.get("steps", []):
                            affected = f"（影响 {step.get('affected_rows', 0)} 行）" if step.get('affected_rows', 0) > 0 else ""
                            st.write(f"- **{step['step']}**：{step['detail']}{affected}")
            else:
                with st.expander("预览原始数据（前50行）"):
                    st.dataframe(st.session_state.df_raw.head(50), use_container_width=True)

    # ---------- 查询分析 ----------
    with tab_query:
        if st.session_state.df_cleaned is None:
            st.info("请先加载并清洗数据")
        else:
            df = st.session_state.df_cleaned
            amount_col = st.session_state.amount_col
            date_col = st.session_state.date_col

            st.subheader("自然语言数据查询")
            col_scope, _ = st.columns([1, 3])
            with col_scope:
                query_scope = st.radio("查询范围", ["全部数据", "异常数据"],
                                       index=0 if st.session_state.query_scope == "全部数据" else 1,
                                       horizontal=True, key="query_scope_radio")
                st.session_state.query_scope = query_scope

            col1, col2 = st.columns([3, 1])
            with col1:
                query = st.text_input("输入问题", value=st.session_state.nl_query, key="nl_query_input")
                st.session_state.nl_query = query
            with col2:
                st.write("快速提问：")
                if st.button("💰 金额最高15笔"):
                    st.session_state.nl_query = "金额最高15笔"
                    st.rerun()
                if st.button("📅 节假日记账"):
                    st.session_state.nl_query = "节假日凭证"
                    st.rerun()
                if st.button("🔴 高风险异常"):
                    st.session_state.nl_query = "风险等级等于高风险"
                    st.rerun()

            if query:
                if query_scope == "异常数据" and st.session_state.anomalies.empty:
                    st.warning("当前没有异常数据，请先点击「开始检测异常」")
                else:
                    result, explain = parse_nl_query(df, st.session_state.anomalies, query, scope=query_scope)
                    st.info(f"查询解析：{explain}")
                    if result.empty:
                        st.warning("未查询到符合条件的记录")
                    else:
                        st.dataframe(result, use_container_width=True)
                        if amount_col and len(result) > 0:
                            fig = px.bar(result, x=result.index, y=amount_col, title=f"查询结果金额分布 ({len(result)}条)")
                            st.plotly_chart(fig, use_container_width=True)

            st.subheader("异常交易检测")
            if st.button("开始检测异常", type="primary"):
                with st.spinner("正在分析..."):
                    anomalies, evidence = detect_anomalies(df, amount_col, date_col)
                    trend = analyze_trends(df, amount_col, date_col) if date_col else {}
                    correlations = correlation_scan(df, amount_col, st.session_state.text_col)
                    st.session_state.anomalies = anomalies
                    st.session_state.trend = trend
                    st.session_state.correlations = correlations
                    st.session_state.evidence_chain = evidence
                    if not anomalies.empty:
                        st.warning(f"发现 {len(anomalies)} 条异常记录")
                        st.dataframe(anomalies, use_container_width=True)
                    else:
                        st.success("未发现明显异常")

            if not st.session_state.anomalies.empty:
                with st.expander("异常明细"):
                    st.dataframe(st.session_state.anomalies, use_container_width=True)

    # ---------- 可视化看板 ----------
    with tab_viz:
        if st.session_state.df_cleaned is None:
            st.info("请先加载数据")
        else:
            df = st.session_state.df_cleaned
            amount_col = st.session_state.amount_col
            date_col = st.session_state.date_col
            anomalies = st.session_state.anomalies

            v1, v2 = st.tabs(["分布与构成", "趋势与热力图"])
            with v1:
                c1, c2 = st.columns(2)
                with c1:
                    if amount_col:
                        fig = plot_amount_histogram(df, amount_col, anomalies)
                        st.plotly_chart(fig, use_container_width=True)
                with c2:
                    if not anomalies.empty:
                        fig = plot_anomaly_composition(anomalies)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("暂无异常数据")
                if not anomalies.empty:
                    fig = plot_risk_scatter(anomalies, amount_col, date_col)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

            with v2:
                if date_col and amount_col:
                    fig = plot_trend_line(st.session_state.trend, date_col, amount_col)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    fig2 = plot_heatmap(df, date_col, amount_col, st.session_state.account_col)
                    if fig2:
                        st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("缺少日期列或金额列，无法生成趋势与热力图")

    # ---------- AI洞察 ----------
    with tab_ai:
        if st.session_state.df_cleaned is None:
            st.info("请先加载数据")
        else:
            if not HAS_AI:
                st.info("未配置 AI API，将使用规则引擎生成洞察（设置环境变量 OPENAI_API_KEY 可启用 AI）")

            if st.button("生成 AI 审计洞察", type="primary"):
                with st.spinner("正在生成洞察..."):
                    insight = generate_insight(
                        st.session_state.df_cleaned,
                        st.session_state.anomalies,
                        st.session_state.trend,
                        st.session_state.correlations,
                        st.session_state.evidence_chain,
                    )
                    st.session_state.insight = insight

            if st.session_state.insight:
                insight = st.session_state.insight
                st.markdown(f"""
                <div style="background:#e8f0fe;border-left:4px solid #003087;padding:12px 16px;margin:12px 0;border-radius:0 6px 6px 0;">
                    <b>整体风险评级：</b><span style="font-size:18px;font-weight:bold;">{insight.get('overall_risk', 'N/A')}</span><br>
                    <span style="font-size:12px;color:#666;">模型：{insight.get('model_used', 'N/A')}</span>
                </div>
                """, unsafe_allow_html=True)

                for idx, item in enumerate(insight.get("insights", []), 1):
                    with st.expander(f"{idx}. {item.get('title', '')} [{item.get('risk_level', '')}]"):
                        st.write(f"**风险等级：** {item.get('risk_level', '')}")
                        st.write(f"**置信度：** {item.get('confidence', '')}")
                        st.write(f"**分析：** {item.get('content', '')}")
                        st.write(f"**建议：** {item.get('recommendation', '')}")

                if insight.get("key_concerns"):
                    st.warning(f"**重点关注：** {insight['key_concerns']}")
                if insight.get("next_steps"):
                    st.info(f"**建议下一步：** {insight['next_steps']}")

                st.divider()
                st.subheader("分析备忘录导出")
                project_info = {
                    "name": st.session_state.project_name or "未命名项目",
                    "period": st.session_state.audit_period or "未指定期间",
                    "preparer": "智能审计系统",
                }
                df_summary = {
                    "total_rows": len(st.session_state.df_cleaned),
                    "clean_rows": len(st.session_state.df_cleaned),
                    "amount_col": st.session_state.amount_col,
                    "date_col": st.session_state.date_col,
                    "total_amount": 0,
                }
                if st.session_state.amount_col:
                    df_summary["total_amount"] = pd.to_numeric(st.session_state.df_cleaned[st.session_state.amount_col], errors="coerce").sum()

                col_md, col_html = st.columns(2)
                with col_md:
                    md_memo = generate_markdown_memo(
                        project_info["name"], project_info["period"],
                        df_summary, insight, st.session_state.evidence_chain, st.session_state.clean_log or {}
                    )
                    st.download_button("📥 下载 Markdown 备忘录", md_memo, "audit_memo.md", "text/markdown")
                with col_html:
                    html_memo = generate_html_memo(
                        project_info["name"], project_info["period"],
                        df_summary, insight, st.session_state.evidence_chain, st.session_state.clean_log or {}
                    )
                    st.download_button("📥 下载 HTML 备忘录", html_memo, "audit_memo.html", "text/html")

    # ---------- 导出交付 ----------
    with tab_export:
        if st.session_state.df_cleaned is None:
            st.info("请先加载数据")
        else:
            st.subheader("报告与底稿导出")
            project_info = {
                "name": st.session_state.project_name or "未命名项目",
                "period": st.session_state.audit_period or "未指定期间",
                "preparer": "智能审计系统",
            }

            c1, c2 = st.columns(2)
            with c1:
                if st.button("生成 Word 底稿报告"):
                    try:
                        buffer = generate_word_report(
                            st.session_state.df_cleaned,
                            st.session_state.anomalies,
                            st.session_state.trend,
                            st.session_state.insight or {},
                            st.session_state.evidence_chain,
                            project_info,
                        )
                        st.download_button("📥 下载 Word 报告", buffer, "audit_report.docx",
                                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    except Exception as e:
                        st.error(f"Word 报告生成失败：{e}")
            with c2:
                if st.button("生成 HTML 交付报告"):
                    html_content = generate_html_report(
                        st.session_state.df_cleaned,
                        st.session_state.anomalies,
                        st.session_state.trend,
                        st.session_state.insight or {},
                        st.session_state.evidence_chain,
                        project_info,
                        st.session_state.clean_log,
                    )
                    st.download_button("📥 下载 HTML 报告", html_content, "audit_report.html", "text/html")

            st.divider()
            st.subheader("一键导出完整审计底稿包")
            if st.button("📦 生成 ZIP 底稿包"):
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    # 原始数据
                    if st.session_state.df_raw is not None:
                        csv_raw = st.session_state.df_raw.to_csv(index=False).encode("utf-8-sig")
                        zf.writestr("01_raw_data.csv", csv_raw)
                    # 清洗后数据
                    if st.session_state.df_cleaned is not None:
                        csv_clean = st.session_state.df_cleaned.to_csv(index=False).encode("utf-8-sig")
                        zf.writestr("02_cleaned_data.csv", csv_clean)
                    # 异常数据
                    if not st.session_state.anomalies.empty:
                        csv_anom = st.session_state.anomalies.to_csv(index=False).encode("utf-8-sig")
                        zf.writestr("03_anomalies.csv", csv_anom)
                    # 清洗日志
                    if st.session_state.clean_log:
                        zf.writestr("04_clean_log.json", json.dumps(st.session_state.clean_log, ensure_ascii=False, indent=2))
                    # 证据链
                    if st.session_state.evidence_chain:
                        zf.writestr("05_evidence_chain.json", json.dumps(st.session_state.evidence_chain, ensure_ascii=False, indent=2))
                    # AI 洞察
                    if st.session_state.insight:
                        zf.writestr("06_ai_insight.json", json.dumps(st.session_state.insight, ensure_ascii=False, indent=2))
                    # Markdown 备忘录
                    df_summary = {
                        "total_rows": len(st.session_state.df_cleaned),
                        "clean_rows": len(st.session_state.df_cleaned),
                        "amount_col": st.session_state.amount_col,
                        "date_col": st.session_state.date_col,
                        "total_amount": 0,
                    }
                    if st.session_state.amount_col:
                        df_summary["total_amount"] = float(pd.to_numeric(st.session_state.df_cleaned[st.session_state.amount_col], errors="coerce").sum())
                    md = generate_markdown_memo(
                        project_info["name"], project_info["period"],
                        df_summary, st.session_state.insight or {}, st.session_state.evidence_chain, st.session_state.clean_log or {}
                    )
                    zf.writestr("07_audit_memo.md", md)
                    # 项目看板数据
                    dashboard_data = export_dashboard_data()
                    zf.writestr("08_project_dashboard.json", json.dumps(dashboard_data, ensure_ascii=False, indent=2, default=str))
                    # README
                    readme = f"""审计底稿包导出说明
项目名称：{project_info['name']}
审计期间：{project_info['period']}
导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

文件清单：
01_raw_data.csv      - 原始数据
02_cleaned_data.csv  - 清洗后数据
03_anomalies.csv     - 异常交易明细
04_clean_log.json    - 数据清洗日志
05_evidence_chain.json - 分析证据链
06_ai_insight.json   - AI 洞察结果
07_audit_memo.md     - 审计分析备忘录
08_project_dashboard.json - 项目看板数据
"""
                    zf.writestr("README.txt", readme)

                zip_buffer.seek(0)
                st.download_button("📥 下载 ZIP 底稿包", zip_buffer, "audit_workpapers.zip", "application/zip")

# ==================== 项目协作 ====================
elif nav == "项目协作":
    render_dashboard()

# ==================== 客户沟通 ====================
elif nav == "客户沟通":
    st.header("客户问询自动回复")
    st.markdown("基于模板库与 AI 生成标准化回复，所有回复自动附加审计独立性免责声明。")

    col_ctx, _ = st.columns([1, 1])
    with col_ctx:
        context_phase = st.text_input("当前阶段", value="外勤执行")
        context_date = st.text_input("预计完成日期", value="待定")
        context_summary = st.text_area("项目背景（可选）", placeholder="简述项目范围或特殊背景...")

    client_question = st.text_area("客户问询内容", placeholder="请输入客户的询问，例如：审计进度如何？还需要什么资料？")

    if st.button("生成回复", type="primary"):
        if not client_question.strip():
            st.warning("请输入问询内容")
        else:
            with st.spinner("生成中..."):
                context = {
                    "phase": context_phase,
                    "expected_date": context_date,
                    "project_summary": context_summary,
                }
                resp = generate_client_response(client_question, context)
                st.markdown(f"**{resp['title']}**  ")
                st.markdown(resp['content'])
                st.caption(f"回复类型：{resp.get('type', 'unknown')}")

    st.divider()
    st.subheader("常用问询模板")
    templates = {
        "audit_progress": "审计进度如何？",
        "document_list": "还需要我们提供什么资料？",
        "variance_explanation": "我们发现了一些差异，请解释一下。",
        "fee_billing": "审计费用怎么算？",
        "report_timeline": "报告什么时候能出来？",
    }
    cols = st.columns(len(templates))
    for idx, (key, example) in enumerate(templates.items()):
        with cols[idx]:
            if st.button(example, key=f"template_{key}"):
                st.session_state[f"client_q_{key}"] = example
                # 使用 JS 不太方便，这里直接显示
                with st.spinner("生成中..."):
                    context = {"phase": context_phase, "expected_date": context_date, "project_summary": context_summary}
                    resp = generate_client_response(example, context)
                    st.markdown(f"**{resp['title']}**")
                    st.markdown(resp['content'])
