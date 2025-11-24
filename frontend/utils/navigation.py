import streamlit as st

def navigate(page: str, **params):
    """Обновляет URL и делает переход на страницу"""
    qp = {"page": page}
    if params:
        qp.update(params)
    st.query_params.clear()
    st.query_params.update(qp)
    st.rerun()
