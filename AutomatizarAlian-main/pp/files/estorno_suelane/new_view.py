"""
UI do novo fluxo (estornos Suelane).

Mesma estetica do sistema antigo, mas chama o pipeline novo:
  - xlsx_parser_suelane (inclui SUELANE, extrai colunas de comissao)
  - matcher_suelane (usa a logica base do matcher antigo com desempate Suelane)
  - report_builder_suelane (saida com regra COM CORRETORA / COMISSAO VEND
    e marcacao laranja por motivo)
"""

import os
import hashlib
import sys
import tempfile

import streamlit as st


_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from pdf_parser import extract_negative_commission_records  # noqa: E402

from estorno_suelane.matcher_suelane import match_records_suelane  # noqa: E402
from estorno_suelane.report_builder_suelane import (  # noqa: E402
    analyze_record_suelane,
    build_report_suelane,
)
from estorno_suelane.xlsx_parser_suelane import (  # noqa: E402
    extract_client_vendor_pairs_suelane,
)


def _safe_upper(value) -> str:
    if value is None:
        return ""
    return str(value).upper()


def _dedupe_pdf_records(existing, new_records):
    """Mesma logica de deduplicacao do sistema antigo, para consistencia."""
    for rec in new_records:
        existing_idx = -1
        for i, e in enumerate(existing):
            if (
                _safe_upper(e.segurado) == _safe_upper(rec.segurado)
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
            existing.append(rec)
        else:
            e = existing[existing_idx]
            if not e.apolice and rec.apolice:
                existing[existing_idx] = rec


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


def _uploaded_file_bytes(uploaded_file) -> bytes:
    getvalue = getattr(uploaded_file, "getvalue", None)
    if callable(getvalue):
        return getvalue()
    return uploaded_file.read()


def render() -> None:
    st.title("Estornos Suelane")
    st.markdown("**Nova feature - Versao: 1.0.10**")
    st.markdown(
        "Faca o upload do(s) **relatorio(s) PDF** e da(s) **planilha(s) de "
        "comissoes (XLSX)**. O sistema vai cruzar os clientes com comissao "
        "negativa do PDF com os vendedores da planilha e calcular o valor "
        "do estorno a partir da coluna correta:"
    )
    st.markdown(
        "- Vendedor **SUELANE** -> coluna **COM CORRETORA** (ou variantes)\n"
        "- Outros vendedores -> coluna **COMISSAO VENDEDOR** (ou variantes)"
    )
    st.info(
        "Linhas com qualquer anomalia (valor negativo, valor zero, coluna "
        "ausente, apolice diferente/ausente, erro de digitacao, duplicidade "
        "ou valor ausente) aparecem em laranja na planilha de saida com o "
        "motivo na ultima coluna."
    )

    if "new_output_bytes" not in st.session_state:
        st.session_state.new_output_bytes = None
    if "new_input_signature" not in st.session_state:
        st.session_state.new_input_signature = None

    col_pdf, col_xlsx = st.columns(2)
    with col_pdf:
        pdf_files = st.file_uploader(
            "Relatorio(s) de repasse (PDF)",
            type=["pdf"],
            accept_multiple_files=True,
            key="new_pdf_uploader",
        )
    with col_xlsx:
        xlsx_files = st.file_uploader(
            "Planilha(s) de comissoes (XLSX)",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
            key="new_xlsx_uploader",
        )

    current_input_signature = (
        _uploaded_files_signature(pdf_files),
        _uploaded_files_signature(xlsx_files),
    )
    if current_input_signature != st.session_state.new_input_signature:
        st.session_state.new_output_bytes = None
        st.session_state.new_input_signature = current_input_signature

    if st.button(
        "Gerar relatorio Suelane",
        type="primary",
        disabled=not (pdf_files and xlsx_files),
        key="new_run_btn",
    ):
        st.session_state.new_output_bytes = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "estornos_suelane.xlsx")

            all_pdf_records = []
            with st.spinner(f"Lendo {len(pdf_files)} PDF(s)..."):
                for idx, pdf_file in enumerate(pdf_files):
                    pdf_path = os.path.join(tmp_dir, f"input_{idx}.pdf")
                    with open(pdf_path, "wb") as f:
                        f.write(_uploaded_file_bytes(pdf_file))
                    try:
                        records = extract_negative_commission_records(pdf_path)
                    except Exception as e:
                        st.error(f"Erro ao ler o PDF '{pdf_file.name}': {e}")
                        st.stop()
                    _dedupe_pdf_records(all_pdf_records, records)

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
                        f.write(_uploaded_file_bytes(xlsx_file))
                    try:
                        records, warnings = extract_client_vendor_pairs_suelane(
                            xlsx_path
                        )
                    except Exception as e:
                        st.error(
                            f"Erro ao ler a planilha '{xlsx_file.name}': {e}"
                        )
                        st.stop()
                    all_xlsx_records.extend(records)
                    all_xlsx_warnings.extend(warnings)

            if all_xlsx_warnings:
                with st.expander(
                    "Avisos sobre as abas das planilhas",
                    expanded=True,
                ):
                    for w in all_xlsx_warnings:
                        st.warning(w)

            with st.spinner("Cruzando dados..."):
                matched_records, not_found = match_records_suelane(
                    all_pdf_records, all_xlsx_records
                )

            if not_found:
                with st.expander(
                    f"{len(not_found)} segurado(s) NAO encontrado(s) "
                    f"na planilha",
                    expanded=True,
                ):
                    for rec in not_found:
                        st.markdown(
                            f"- `{rec.segurado}` (Inicio: {rec.inicio_vig} | "
                            f"Apolice: {rec.apolice})"
                        )

            if not matched_records:
                st.error("Nenhum registro pode ser cruzado. Relatorio nao gerado.")
                st.stop()

            # Resumo das anomalias antes de gerar o XLSX.
            # Usa a mesma regra que pinta linhas no report_builder_suelane.
            anomalias = sum(
                1 for r in matched_records if analyze_record_suelane(r)[1]
            )

            st.info(
                f"{len(matched_records)} linha(s) gerada(s). "
                f"{anomalias} linha(s) marcada(s) em laranja para verificacao."
            )

            with st.spinner("Gerando XLSX..."):
                try:
                    build_report_suelane(
                        matched_records,
                        output_path,
                        not_found=not_found,
                    )
                except Exception as e:
                    st.error(f"Erro ao gerar o relatorio: {e}")
                    st.stop()

            with open(output_path, "rb") as f:
                st.session_state.new_output_bytes = f.read()

            st.success("Relatorio gerado com sucesso!")

    if st.session_state.new_output_bytes is not None:
        st.download_button(
            label="Baixar estornos_suelane.xlsx",
            data=st.session_state.new_output_bytes,
            file_name="estornos_suelane.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="new_download_btn",
        )
