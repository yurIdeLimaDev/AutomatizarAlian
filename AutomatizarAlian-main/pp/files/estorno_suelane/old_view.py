"""
Replica a UI do sistema antigo (files/app.py) usando os mesmos modulos
sem modifica-los. A logica de processamento eh identica - apenas a
estrutura do Streamlit eh redesenhada para conviver com o menu inicial.
"""

import os
import hashlib
import sys
import tempfile

import streamlit as st


_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from matcher import match_records  # noqa: E402
from pdf_parser import extract_negative_commission_records  # noqa: E402
from report_builder import build_report  # noqa: E402
from vendor_sales_counter import count_sales_per_vendor_month  # noqa: E402
from xlsx_parser import extract_client_vendor_pairs  # noqa: E402


def _spreadsheet_suffix(uploaded_file) -> str:
    suffix = os.path.splitext(getattr(uploaded_file, "name", "") or "")[1].lower()
    if suffix in (".xlsx", ".xls"):
        return suffix
    return ".xlsx"


def _uploaded_files_signature(files) -> tuple:
    if not files:
        return ()

    def _digest(file) -> str | None:
        getvalue = getattr(file, "getvalue", None)
        if not callable(getvalue):
            return None
        try:
            return hashlib.sha256(getvalue()).hexdigest()
        except Exception:
            return None

    return tuple(
        (
            getattr(file, "name", ""),
            getattr(file, "size", None),
            getattr(file, "type", ""),
            _digest(file),
        )
        for file in files
    )


def render() -> None:
    st.title("Gerador de Controle de Estornos")
    st.markdown("**Versao: 2.1.0**")
    st.markdown(
        "Faca o upload do(s) **relatorio(s) PDF** e da(s) **planilha(s) "
        "de comissoes (XLSX)** para gerar automaticamente o controle de "
        "estornos."
    )

    st.info(
        "Em caso de mudanca no formato dos arquivos ou problemas encontrados, "
        "contacte o estagiario responsavel."
    )

    # Estado isolado por feature
    if "old_output_bytes" not in st.session_state:
        st.session_state.old_output_bytes = None
    if "old_input_signature" not in st.session_state:
        st.session_state.old_input_signature = None

    col_pdf, col_xlsx = st.columns(2)
    with col_pdf:
        pdf_files = st.file_uploader(
            "Relatorio(s) de repasse (PDF)",
            type=["pdf"],
            accept_multiple_files=True,
            key="old_pdf_uploader",
        )
    with col_xlsx:
        xlsx_files = st.file_uploader(
            "Planilha(s) de comissoes (XLSX)",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key="old_xlsx_uploader",
        )

    current_input_signature = (
        _uploaded_files_signature(pdf_files),
        _uploaded_files_signature(xlsx_files),
    )
    if current_input_signature != st.session_state.old_input_signature:
        st.session_state.old_output_bytes = None
        st.session_state.old_input_signature = current_input_signature

    if st.button(
        "Gerar relatorio",
        type="primary",
        disabled=not (pdf_files and xlsx_files),
        key="old_run_btn",
    ):
        st.session_state.old_output_bytes = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "controle_estornos.xlsx")

            all_pdf_records = []
            with st.spinner(f"Lendo {len(pdf_files)} PDF(s)..."):
                for idx, pdf_file in enumerate(pdf_files):
                    pdf_path = os.path.join(tmp_dir, f"input_{idx}.pdf")
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_file.read())

                    try:
                        records = extract_negative_commission_records(pdf_path)
                    except Exception as e:
                        st.error(f"Erro ao ler o PDF '{pdf_file.name}': {e}")
                        st.stop()

                    for rec in records:
                        existing_idx = -1
                        for i, e in enumerate(all_pdf_records):
                            if (
                                e.segurado.upper() == rec.segurado.upper()
                                and e.inicio_vig == rec.inicio_vig
                            ):
                                if e.apolice == rec.apolice:
                                    existing_idx = i
                                    break
                                elif not e.apolice:
                                    existing_idx = i
                                    break
                                elif not rec.apolice:
                                    existing_idx = i
                                    break

                        if existing_idx == -1:
                            all_pdf_records.append(rec)
                        else:
                            e = all_pdf_records[existing_idx]
                            if not e.apolice and rec.apolice:
                                all_pdf_records[existing_idx] = rec

            if not all_pdf_records:
                st.warning(
                    "Nenhum registro com comissao negativa encontrado nos PDFs."
                )
                st.stop()

            st.info(
                f"{len(all_pdf_records)} registro(s) com comissao negativa "
                f"encontrado(s) em {len(pdf_files)} PDF(s)."
            )

            all_xlsx_records = []
            all_xlsx_warnings = []
            with st.spinner(f"Lendo {len(xlsx_files)} planilha(s)..."):
                for idx, xlsx_file in enumerate(xlsx_files):
                    suffix = _spreadsheet_suffix(xlsx_file)
                    xlsx_path = os.path.join(tmp_dir, f"input_{idx}{suffix}")
                    with open(xlsx_path, "wb") as f:
                        f.write(xlsx_file.read())

                    try:
                        records, warnings = extract_client_vendor_pairs(xlsx_path)
                    except Exception as e:
                        st.error(
                            f"Erro ao ler a planilha '{xlsx_file.name}': {e}"
                        )
                        st.stop()

                    all_xlsx_records.extend(records)
                    all_xlsx_warnings.extend(warnings)

            if all_xlsx_warnings:
                with st.expander(
                    "Problemas encontrados nas abas das planilhas",
                    expanded=True,
                ):
                    for w in all_xlsx_warnings:
                        st.warning(w)

            with st.spinner("Cruzando dados..."):
                matched_records, not_found = match_records(
                    all_pdf_records, all_xlsx_records
                )

            vendor_sales_counts = count_sales_per_vendor_month(all_xlsx_records)

            if not_found:
                with st.expander(
                    f"{len(not_found)} segurado(s) NAO encontrado(s) na planilha",
                    expanded=True,
                ):
                    st.markdown(
                        "Os seguintes segurados estao no PDF com comissao "
                        "negativa, mas **nao foram localizados** em nenhuma "
                        "aba da planilha:"
                    )
                    for rec in not_found:
                        st.markdown(
                            f"- `{rec.segurado}` (Inicio: {rec.inicio_vig} | "
                            f"Apolice: {rec.apolice})"
                        )

            if not matched_records:
                st.error("Nenhum registro pode ser cruzado. Relatorio nao gerado.")
                st.stop()

            st.info(f"{len(matched_records)} linha(s) gerada(s) no relatorio.")

            with st.spinner("Gerando XLSX..."):
                try:
                    build_report(
                        matched_records,
                        output_path,
                        not_found=not_found,
                        vendor_sales_counts=vendor_sales_counts,
                    )
                except Exception as e:
                    st.error(f"Erro ao gerar o relatorio: {e}")
                    st.stop()

            with open(output_path, "rb") as f:
                st.session_state.old_output_bytes = f.read()

            st.success("Relatorio gerado com sucesso!")

    if st.session_state.old_output_bytes is not None:
        st.download_button(
            label="Baixar controle_estornos.xlsx",
            data=st.session_state.old_output_bytes,
            file_name="controle_estornos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="old_download_btn",
        )
