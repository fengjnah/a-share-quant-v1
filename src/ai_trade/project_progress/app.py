"""Standalone offline progress view; the same renderer is in the Demo navigation."""
import streamlit as st
from ai_trade.project_progress.page import render

st.set_page_config(page_title="项目进度 · A股量化 V1.3", page_icon="📋", layout="wide")
render()
