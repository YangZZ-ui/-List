"""
多源数据连接模块
支持文件上传与数据库直连，基于安永数据完整性原则设计
"""

import io
import pandas as pd
import streamlit as st
from typing import Optional, Dict, Any, Tuple


class DataSourceMeta:
    """数据源元数据，用于证据链追溯"""
    def __init__(self, source_type: str, source_name: str, rows: int, cols: int, extra: Dict[str, Any] = None):
        self.source_type = source_type      # file / database / api
        self.source_name = source_name      # 文件名或连接信息摘要
        self.rows = rows
        self.cols = cols
        self.extra = extra or {}
        self.load_time = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "rows": self.rows,
            "cols": self.cols,
            "load_time": self.load_time,
            **self.extra,
        }


def load_from_file(uploaded_file) -> Tuple[Optional[pd.DataFrame], Optional[DataSourceMeta]]:
    """从上传文件加载数据，支持 CSV / Excel / JSON"""
    if uploaded_file is None:
        return None, None

    try:
        file_name = uploaded_file.name.lower()
        if file_name.endswith(".csv"):
            try:
                df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding="gbk")
        elif file_name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file, engine="openpyxl")
        elif file_name.endswith(".json"):
            df = pd.read_json(uploaded_file)
        else:
            st.error(f"不支持的文件格式：{uploaded_file.name}")
            return None, None

        df.columns = df.columns.str.strip()
        meta = DataSourceMeta(
            source_type="file",
            source_name=uploaded_file.name,
            rows=len(df),
            cols=len(df.columns),
        )
        return df, meta
    except Exception as e:
        st.error(f"文件读取失败：{e}")
        return None, None


def load_from_database(connection_string: str, sql: str) -> Tuple[Optional[pd.DataFrame], Optional[DataSourceMeta]]:
    """从数据库加载数据（基于 SQLAlchemy）"""
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(connection_string, pool_pre_ping=True)
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
        df.columns = df.columns.str.strip()
        meta = DataSourceMeta(
            source_type="database",
            source_name=connection_string.split("@")[-1].split("/")[-1],
            rows=len(df),
            cols=len(df.columns),
            extra={"sql": sql[:500]},  # 记录查询语句前500字符用于追溯
        )
        return df, meta
    except ImportError:
        st.error("数据库连接需要安装 sqlalchemy，请运行：pip install sqlalchemy")
        return None, None
    except Exception as e:
        st.error(f"数据库查询失败：{e}")
        return None, None


def load_data(source_type: str, source, sql: str = "") -> Tuple[Optional[pd.DataFrame], Optional[DataSourceMeta]]:
    """统一数据加载入口"""
    if source_type == "file":
        return load_from_file(source)
    elif source_type == "database":
        return load_from_database(source, sql)
    else:
        st.error(f"未知数据源类型：{source_type}")
        return None, None
