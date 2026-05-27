"""
Entry point unico do Streamlit. Apresenta um menu inicial com dois blocos:

  1. Sistema antigo (Controle de Estornos)
  2. Nova feature (Estornos Suelane)

A escolha eh persistida em st.session_state.page. Cada subpagina expoe um
botao "Voltar ao menu" para retornar.

Como rodar:
    streamlit run files/estorno_suelane/app.py
"""

import os
import sys

import streamlit as st


_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from estorno_suelane import new_view, old_view


st.set_page_config(
    page_title="Controle de Estornos",
    page_icon=":clipboard:",
    layout="centered",
)


def _go_to(page: str) -> None:
    st.session_state.page = page


def _render_menu() -> None:
    st.title("Controle de Estornos - Menu")
    st.markdown(
        "Escolha qual fluxo deseja utilizar. O sistema antigo continua "
        "funcionando exatamente como antes; o novo fluxo trata os estornos "
        "da Suelane com base nas colunas de comissao da planilha."
    )
    st.write("")

    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        with st.container(border=True):
            st.subheader("Sistema antigo")
            st.markdown(
                "**Gerador de Controle de Estornos**\n\n"
                "Fluxo original: cruza PDFs com comissao negativa contra "
                "planilhas de comissoes e gera o controle com valor fixo "
                "(R$ 30 ou R$ 50) por linha."
            )
            st.button(
                "Abrir sistema antigo",
                key="menu_old_btn",
                type="primary",
                use_container_width=True,
                on_click=_go_to,
                args=("old",),
            )

    with col_b:
        with st.container(border=True):
            st.subheader("Nova feature")
            st.markdown(
                "**Estornos Suelane**\n\n"
                "Cruza PDFs com a planilha (incluindo a Suelane) e calcula o "
                "valor do estorno a partir das colunas COM CORRETORA "
                "(quando vendedor = SUELANE) ou COMISSAO VENDEDOR "
                "(demais vendedores)."
            )
            st.button(
                "Abrir nova feature",
                key="menu_new_btn",
                type="primary",
                use_container_width=True,
                on_click=_go_to,
                args=("new",),
            )


def _render_back_button() -> None:
    st.button(
        "Voltar ao menu",
        key=f"back_to_menu_{st.session_state.page}",
        on_click=_go_to,
        args=("menu",),
    )
    st.markdown("---")


def main() -> None:
    if "page" not in st.session_state:
        st.session_state.page = "menu"

    page = st.session_state.page

    if page == "menu":
        _render_menu()
    elif page == "old":
        _render_back_button()
        old_view.render()
    elif page == "new":
        _render_back_button()
        new_view.render()
    else:
        st.session_state.page = "menu"
        _render_menu()


main()
