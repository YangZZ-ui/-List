"""
智能审计洞察与协作平台 - 全局配置
基于安永会计师事务所专业原则设计
"""

import os
import streamlit as st

# ---------- AI 配置 ----------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 优先尝试从 streamlit secrets 读取（部署时更安全）
try:
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", OPENAI_API_KEY)
    OPENAI_BASE_URL = st.secrets.get("OPENAI_BASE_URL", OPENAI_BASE_URL)
    OPENAI_MODEL = st.secrets.get("OPENAI_MODEL", OPENAI_MODEL)
except Exception:
    pass

HAS_AI = bool(OPENAI_API_KEY)

# ---------- 审计参数（安永风险导向原则） ----------
AUDIT_CONFIG = {
    "anomaly": {
        "high_zscore": 4.0,      # Z-score >= 4 为高风险
        "medium_zscore": 3.0,    # Z-score >= 3 为中等风险
        "low_zscore": 2.5,       # Z-score >= 2.5 为低风险
        "round_amount_threshold": 1000,  # 规整金额最低阈值
    },
    "holidays": [
        "12-31", "01-01", "01-02", "01-03",
        "04-04", "04-05", "04-06",
        "05-01", "05-02", "05-03", "05-04", "05-05",
        "06-10", "06-11", "06-12",
        "09-17", "09-18", "09-19",
        "10-01", "10-02", "10-03", "10-04", "10-05", "10-06", "10-07"
    ],
    "evidence": {
        "min_sample_size": 30,   # 趋势分析最小样本量
        "confidence_levels": {
            "high": 0.85,
            "medium": 0.70,
            "low": 0.55,
        }
    }
}

# ---------- 安永原则文案（独立性保护） ----------
EY_DISCLAIMER = (
    "【免责声明】本回复由智能辅助系统生成，仅供信息参考与内部工作便利，"
    "不构成安永会计师事务所的审计意见、保证或任何专业结论。"
    "所有重大判断仍需由项目审计团队独立做出并复核。"
)

EY_REVIEW_NOTICE = (
    "【职业怀疑提示】以下分析结果基于算法模型与历史数据模式，"
    "存在固有局限性。审计师应保持职业怀疑态度，对异常结果执行进一步的实质性程序。"
)

# ---------- 数据库连接模板 ----------
DB_DRIVERS = {
    "mysql": "mysql+pymysql://{user}:{password}@{host}:{port}/{database}",
    "postgresql": "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}",
    "mssql": "mssql+pyodbc://{user}:{password}@{host}:{port}/{database}?driver=ODBC+Driver+17+for+SQL+Server",
    "sqlite": "sqlite:///{database}",
}

# ---------- 项目阶段定义 ----------
PROJECT_PHASES = [
    {"key": "planning", "name": "计划阶段", "weight": 15},
    {"key": "fieldwork", "name": "外勤执行", "weight": 50},
    {"key": "reporting", "name": "报告编制", "weight": 25},
    {"key": "review", "name": "质量复核", "weight": 10},
]
