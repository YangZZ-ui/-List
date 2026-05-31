"""
项目协作看板模块
支持项目进度追踪、团队任务分配、客户资料收取与团队留言
所有数据通过 Streamlit session_state 持久化，满足安永项目文档化要求
"""

import pandas as pd
import streamlit as st
from typing import Dict, Any, List
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PROJECT_PHASES


# ---------- 初始化 session_state ----------
def init_dashboard_state():
    defaults = {
        "project_name": "",
        "audit_period": "",
        "current_phase": "planning",
        "phase_completion": {p["key"]: 0 for p in PROJECT_PHASES},
        "tasks": pd.DataFrame(columns=["任务", "负责人", "截止日期", "状态", "优先级", "备注"]),
        "documents": pd.DataFrame(columns=["资料名称", "要求提供日期", "实际收到日期", "状态", "备注"]),
        "messages": [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ---------- 项目阶段进度 ----------
def render_project_phases():
    """渲染项目阶段进度条与权重计算"""
    st.subheader("项目阶段进度")

    cols = st.columns(len(PROJECT_PHASES))
    total_weight = sum(p["weight"] for p in PROJECT_PHASES)
    weighted_progress = 0.0

    for idx, phase in enumerate(PROJECT_PHASES):
        with cols[idx]:
            key = phase["key"]
            name = phase["name"]
            weight = phase["weight"]
            current_pct = st.session_state.phase_completion.get(key, 0)

            # 颜色根据当前阶段判断
            is_current = (st.session_state.current_phase == key)
            border_color = "#003087" if is_current else "#e0e0e0"
            bg_color = "#e8f0fe" if is_current else "#fafafa"

            st.markdown(
                f"""
                <div style="border: 2px solid {border_color}; border-radius: 8px; padding: 10px; background: {bg_color}; text-align: center;">
                    <div style="font-size: 12px; color: #666;">{name}</div>
                    <div style="font-size: 20px; font-weight: bold; color: #003087;">{current_pct}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 编辑进度
            new_pct = st.slider(
                f"{name}进度",
                min_value=0,
                max_value=100,
                value=int(current_pct),
                key=f"phase_slider_{key}",
                label_visibility="collapsed",
            )
            st.session_state.phase_completion[key] = new_pct
            weighted_progress += (new_pct / 100) * (weight / total_weight)

    # 总进度
    st.progress(min(weighted_progress, 1.0), text=f"整体进度：{weighted_progress*100:.1f}%")

    # 设置当前阶段
    phase_options = {p["key"]: p["name"] for p in PROJECT_PHASES}
    current = st.selectbox("当前所处阶段", options=list(phase_options.keys()), format_func=lambda x: phase_options[x], index=list(phase_options.keys()).index(st.session_state.current_phase))
    st.session_state.current_phase = current


# ---------- 团队任务分配 ----------
def render_task_table():
    """渲染可编辑的团队任务表"""
    st.subheader("团队任务分配")

    # 确保 DataFrame 有正确的列
    required_cols = ["任务", "负责人", "截止日期", "状态", "优先级", "备注"]
    if st.session_state.tasks.empty:
        # 预填充示例任务
        example_data = {
            "任务": ["了解内控环境", "穿行测试", "样本选取", "差异汇总", "报告初稿"],
            "负责人": ["", "", "", "", ""],
            "截止日期": [(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")] * 5,
            "状态": ["待开始", "待开始", "待开始", "待开始", "待开始"],
            "优先级": ["高", "高", "中", "中", "高"],
            "备注": ["", "", "", "", ""],
        }
        st.session_state.tasks = pd.DataFrame(example_data)
    else:
        for col in required_cols:
            if col not in st.session_state.tasks.columns:
                st.session_state.tasks[col] = ""

    edited_df = st.data_editor(
        st.session_state.tasks,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "状态": st.column_config.SelectboxColumn(
                "状态", options=["待开始", "进行中", "已完成", "阻塞"], required=True
            ),
            "优先级": st.column_config.SelectboxColumn(
                "优先级", options=["高", "中", "低"], required=True
            ),
            "截止日期": st.column_config.DateColumn("截止日期"),
        },
        key="task_editor",
    )
    st.session_state.tasks = edited_df

    # 统计
    if not edited_df.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总任务", len(edited_df))
        c2.metric("已完成", len(edited_df[edited_df["状态"] == "已完成"]))
        c3.metric("进行中", len(edited_df[edited_df["状态"] == "进行中"]))
        c4.metric("阻塞", len(edited_df[edited_df["状态"] == "阻塞"]))


# ---------- 客户资料提交追踪 ----------
def render_document_tracker():
    """渲染客户资料收取状态追踪表"""
    st.subheader("客户资料提交追踪")

    required_cols = ["资料名称", "要求提供日期", "实际收到日期", "状态", "备注"]
    if st.session_state.documents.empty:
        example_docs = {
            "资料名称": ["银行对账单", "存货盘点表", "重大合同", "关联方清单", "诉讼清单"],
            "要求提供日期": [(datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")] * 5,
            "实际收到日期": [""] * 5,
            "状态": ["未发送", "未发送", "未发送", "未发送", "未发送"],
            "备注": ["", "", "", "", ""],
        }
        st.session_state.documents = pd.DataFrame(example_docs)
    else:
        for col in required_cols:
            if col not in st.session_state.documents.columns:
                st.session_state.documents[col] = ""

    edited_docs = st.data_editor(
        st.session_state.documents,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "状态": st.column_config.SelectboxColumn(
                "状态", options=["未发送", "已发送", "客户已提供", "需补充", "不适用"], required=True
            ),
            "要求提供日期": st.column_config.DateColumn("要求提供日期"),
            "实际收到日期": st.column_config.DateColumn("实际收到日期"),
        },
        key="doc_editor",
    )
    st.session_state.documents = edited_docs

    if not edited_docs.empty:
        received = len(edited_docs[edited_docs["状态"] == "客户已提供"])
        total = len(edited_docs[edited_docs["状态"] != "不适用"])
        if total > 0:
            st.progress(received / total, text=f"资料收取进度：{received}/{total}")


# ---------- 团队留言板 ----------
def render_message_board():
    """渲染关键节点留言板"""
    st.subheader("团队留言板")

    with st.form("message_form", clear_on_submit=True):
        author = st.text_input("留言人", value="", placeholder="请输入姓名")
        msg_text = st.text_area("留言内容", placeholder="记录关键发现、待办提醒或协作信息...")
        submitted = st.form_submit_button("发布留言")
        if submitted and msg_text.strip():
            st.session_state.messages.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "author": author.strip() or "匿名",
                "content": msg_text.strip(),
            })

    # 显示留言（倒序）
    if st.session_state.messages:
        for msg in reversed(st.session_state.messages):
            with st.container():
                st.markdown(
                    f"""
                    <div style="border-left: 3px solid #003087; padding-left: 12px; margin-bottom: 10px;">
                        <div style="font-size: 12px; color: #666;">{msg['time']} · {msg['author']}</div>
                        <div style="margin-top: 4px;">{msg['content']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("暂无留言")


# ---------- 主渲染入口 ----------
def render_dashboard():
    """渲染完整的项目协作看板"""
    init_dashboard_state()

    # 项目信息
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.project_name = st.text_input("项目名称", value=st.session_state.project_name)
    with col2:
        st.session_state.audit_period = st.text_input("审计期间", value=st.session_state.audit_period, placeholder="如：2025年1月1日至2025年12月31日")

    st.divider()

    # 阶段进度
    render_project_phases()
    st.divider()

    # 任务与资料（并排）
    tab1, tab2, tab3 = st.tabs(["团队任务", "资料追踪", "团队留言"])
    with tab1:
        render_task_table()
    with tab2:
        render_document_tracker()
    with tab3:
        render_message_board()


def export_dashboard_data() -> Dict[str, Any]:
    """导出看板数据，用于底稿归档"""
    return {
        "project_name": st.session_state.get("project_name", ""),
        "audit_period": st.session_state.get("audit_period", ""),
        "current_phase": st.session_state.get("current_phase", ""),
        "phase_completion": st.session_state.get("phase_completion", {}),
        "tasks": st.session_state.get("tasks", pd.DataFrame()).to_dict("records"),
        "documents": st.session_state.get("documents", pd.DataFrame()).to_dict("records"),
        "messages": st.session_state.get("messages", []),
        "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
