import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime
import numpy as np
from dateutil.relativedelta import relativedelta
import re
import logging

# Módulos do projeto
from extractors.pdf_extractor import extrair_lancamentos_pdf
from extractors.txt_extractor import extrair_lancamentos_txt
from extractors.ofx_extractor import extrair_lancamentos_ofx
from logic.Analises_DFC_DRE.deduplicator import remover_duplicatas
from logic.Analises_DFC_DRE.categorizador import categorizar_transacoes
from logic.Analises_DFC_DRE.fluxo_caixa import exibir_fluxo_caixa
from logic.Analises_DFC_DRE.faturamento import coletar_faturamentos
from logic.Analises_DFC_DRE.estoque import coletar_estoques
from logic.Analises_DFC_DRE.gerador_parecer import gerar_parecer_automatico
from logic.Analises_DFC_DRE.exibir_dre import exibir_dre
from logic.Analises_DFC_DRE.analise_gpt import analisar_dfs_com_gpt
from logic.Analises_DFC_DRE.exibir_dre import highlight_rows

# Configuração da página
st.set_page_config(
    page_title="Pré Análise de Documentos", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuração do logging
logging.basicConfig(level=logging.INFO)

# Funções auxiliares

def validar_arquivo(file):
    """Valida se o arquivo enviado possui um nome e extensão suportada."""
    if not hasattr(file, "name"):
        return False
    nome = file.name
    tipo = os.path.splitext(nome)[-1].lower()
    return tipo in [".pdf", ".ofx", ".xlsx", ".txt", ".xls"]

def formatar_valor_br(valor):
    """Formata um valor numérico para o formato brasileiro (R$)"""
    if pd.isna(valor):
        return ""  # Deixa vazio ao invés de mostrar "nan"
    if isinstance(valor, (int, float)):
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(valor, str):
        try:
            valor_num = float(valor.replace(".", "").replace(",", ".").replace("R$", "").replace("R\\$", "").strip())
            return f"R$ {valor_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return valor
    return valor

def converter_para_float(valor_str):
    """Converte uma string de valor BR para float"""
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    try:
        # Tratar tanto R$ quanto R\$ (escapado)
        return float(str(valor_str).replace("R$", "").replace("R\\$", "").replace(".", "").replace(",", ".").strip())
    except:
        return 0.0

def processar_arquivo(file):
    """Processa um arquivo e retorna os dataframes extraídos"""
    nome = file.name
    tipo = os.path.splitext(nome)[-1].lower()
    
    try:
        if tipo == ".pdf":
            resultado = extrair_lancamentos_pdf(file, nome)
            
            if isinstance(resultado, tuple) and resultado[0] == "debug":
                return {
                    "status": "debug",
                    "mensagem": f"Texto da primeira página do PDF ({nome}):",
                    "conteudo": resultado[1],
                    "tipo": "pdf"
                }
            
            df_resumo = pd.DataFrame(resultado["resumo"])
            df_trans = pd.DataFrame(resultado["transacoes"])
            
            if "Valor" in df_resumo.columns:
                df_resumo["Valor"] = df_resumo["Valor"].apply(formatar_valor_br)
            if "Valor (R$)" in df_trans.columns:
                df_trans["Valor (R$)"] = df_trans["Valor (R$)"].apply(formatar_valor_br)
            
            return {
                "status": "sucesso",
                "resumo": df_resumo,
                "transacoes": df_trans,
                "mensagem": f"📥 {nome} → PDF → {len(df_trans)} transações, {len(df_resumo)} resumos",
                "tipo": "pdf"
            }
            
        elif tipo == ".txt":
            df_trans = pd.DataFrame(extrair_lancamentos_txt(file, nome))
            df_trans["Arquivo"] = nome
            if "Valor (R$)" in df_trans.columns:
                df_trans["Valor (R$)"] = df_trans["Valor (R$)"].apply(formatar_valor_br)
            
            return {
                "status": "sucesso",
                "transacoes": df_trans,
                "mensagem": f"📥 {nome} → TXT → {len(df_trans)} transações",
                "tipo": "txt"
            }
            
        elif tipo in [".xls", ".xlsx"]:
            df = pd.read_excel(file)
            df["Arquivo"] = nome
            if "Valor (R$)" in df.columns:
                df["Valor (R$)"] = df["Valor (R$)"].apply(formatar_valor_br)
            
            return {
                "status": "sucesso",
                "transacoes": df,
                "mensagem": f"📥 {nome} → Excel → {len(df)} linhas",
                "tipo": "excel"
            }
            
        elif tipo == ".ofx":
            transacoes, encoding = extrair_lancamentos_ofx(file, nome)
            
            if isinstance(transacoes, str) or not transacoes:
                return {
                    "status": "erro",
                    "mensagem": f"❌ Erro ao processar {nome}: {encoding}",
                    "tipo": "ofx"
                }
                
            df = pd.DataFrame(transacoes)
            if "Valor (R$)" in df.columns:
                df["Valor (R$)"] = df["Valor (R$)"].apply(formatar_valor_br)
            
            return {
                "status": "sucesso",
                "transacoes": df,
                "mensagem": f"📥 {nome} → OFX → {len(df)} transações (codificação: {encoding})",
                "tipo": "ofx"
            }
            
        else:
            return {
                "status": "erro",
                "mensagem": f"⚠️ Tipo de arquivo não suportado: {nome}",
                "tipo": "desconhecido"
            }
            
    except Exception as e:
        return {
            "status": "erro",
            "mensagem": f"❌ Erro ao processar {nome}: {str(e)}",
            "tipo": tipo.replace(".", "")
        }

def projetar_valores(df, inflacao_anual, meses_futuros, percentual_receita=0, percentual_despesa=0):
    """Projeta valores do DataFrame para meses futuros com base na inflação e percentuais."""
    df_projetado = df.copy()
    colunas_meses = [col for col in df.columns if re.match(r'\d{4}-\d{2}', col)]
    if not colunas_meses:
        raise ValueError("Nenhuma coluna no formato YYYY-MM encontrada no DataFrame.")
    
    ultimo_mes = pd.to_datetime(colunas_meses[-1], format="%Y-%m").to_period("M")
    meses_projetados = [ultimo_mes + i for i in range(1, meses_futuros + 1)]
    meses_projetados = [m.strftime("%Y-%m") for m in meses_projetados]
    
    for mes in meses_projetados:
        df_projetado[mes] = 0
        for idx in df_projetado.index:
            tipo = df_projetado.loc[idx, "__tipo__"] if "__tipo__" in df_projetado.columns else ""
            valor_base = df_projetado.loc[idx, colunas_meses[-1]]
            inflacao_fator = (1 + inflacao_anual / 100) ** (meses_projetados.index(mes) / 12 + 1)
            if tipo == "Crédito":
                df_projetado.loc[idx, mes] = valor_base * inflacao_fator * (1 + percentual_receita / 100)
            elif tipo == "Débito":
                df_projetado.loc[idx, mes] = valor_base * inflacao_fator * (1 + percentual_despesa / 100)
            else:
                df_projetado.loc[idx, mes] = valor_base * inflacao_fator
    
    for col in colunas_meses + meses_projetados:
        if col in df_projetado.columns:
            df_projetado[col] = df_projetado[col].apply(formatar_valor_br)
    
    return df_projetado, meses_projetados

def resumir_por_ano(df, meses_projetados):
    """Resume os valores projetados por ano."""
    df_resumo = df.copy()
    anos = sorted(set(m[:4] for m in meses_projetados))
    resumo_dict = {f"Ano {i+1}": [] for i in range(len(anos))}
    
    for idx in df_resumo.index:
        valores_por_ano = {f"Ano {i+1}": 0 for i in range(len(anos))}
        for mes in meses_projetados:
            ano = mes[:4]
            ano_idx = anos.index(ano)
            valor = converter_para_float(df_resumo.loc[idx, mes]) if mes in df_resumo.columns else 0
            valores_por_ano[f"Ano {ano_idx + 1}"] += valor
        for ano in valores_por_ano:
            df_resumo.loc[idx, ano] = formatar_valor_br(valores_por_ano[ano])
    
    colunas_manter = [col for col in df_resumo.columns if col.startswith("Ano ") or col in ["Categoria", "__tipo__"]]
    return df_resumo[colunas_manter]

# Inicialização do estado da aplicação
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "log_uploads" not in st.session_state:
    st.session_state.log_uploads = []
if "processamento_concluido" not in st.session_state:
    st.session_state.processamento_concluido = False
if "df_transacoes_total" not in st.session_state:
    st.session_state.df_transacoes_total = None
if "df_resumo_total" not in st.session_state:
    st.session_state.df_resumo_total = None

# Interface principal
st.title("📑 Pré-Análise de Documentos Bancários")

# Descrição principal
st.markdown("""
### 🎯 Objetivo
Este sistema realiza a pré-análise de documentos bancários, extraindo transações, categorizando-as e gerando relatórios financeiros.

### 📋 Instruções
1. Envie os arquivos bancários (.ofx, .xlsx, .txt)
2. O sistema extrairá e consolidará os dados
3. Categorize as transações
4. Gere relatórios de fluxo de caixa e DRE
5. Obtenha análises automáticas
""")

# Uploader de arquivos
with st.expander("📎 Upload de Arquivos", expanded=True):
    uploaded_files = st.file_uploader(
        "Selecione os arquivos para análise",
        type=["ofx", "xlsx", "txt"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )

    col1, col2 = st.columns([1, 4])
    processar = col1.button("🔄 Processar Arquivos", use_container_width=True)
    limpar = col2.button("🧹 Limpar Tudo", use_container_width=True)

# Processamento dos arquivos
if processar and uploaded_files:
    with st.spinner("Processando arquivos... ⏳"):
        st.session_state.log_uploads = []
        lista_resumos = []
        lista_transacoes = []
        
        progress_bar = st.progress(0)
        total_files = len(uploaded_files)
        
        for i, file in enumerate(uploaded_files):
            progress_bar.progress((i + 0.5) / total_files)
            
            if not validar_arquivo(file):
                continue
            
            resultado = processar_arquivo(file)
            st.session_state.log_uploads.append(resultado["mensagem"])
            
            if resultado["status"] == "debug":
                st.code(resultado["conteudo"], language="text")
            elif resultado["status"] == "sucesso":
                if "resumo" in resultado and not resultado["resumo"].empty:
                    lista_resumos.append(resultado["resumo"])
                if "transacoes" in resultado and not resultado["transacoes"].empty:
                    lista_transacoes.append(resultado["transacoes"])
            elif resultado["status"] == "erro":
                st.error(resultado["mensagem"])
            
            progress_bar.progress((i + 1) / total_files)
        
        if lista_resumos:
            st.session_state.df_resumo_total = pd.concat(lista_resumos, ignore_index=True)
        else:
            st.session_state.df_resumo_total = None
            
        if lista_transacoes:
            df_transacoes_total = pd.concat(lista_transacoes, ignore_index=True)
            df_transacoes_total = remover_duplicatas(df_transacoes_total)
            
            if "Valor (R$)" in df_transacoes_total.columns:
                df_transacoes_total["Valor (R$)"] = df_transacoes_total["Valor (R$)"].apply(formatar_valor_br)
            
            st.session_state.df_transacoes_total = df_transacoes_total
            st.session_state.processamento_concluido = True
        else:
            st.session_state.df_transacoes_total = None
            
        progress_bar.progress(100)
        st.success("✅ Processamento concluído!")

# Limpar dados
if limpar:
    nova_key = st.session_state.get("uploader_key", 0) + 1
    st.session_state.clear()
    st.session_state.uploader_key = nova_key
    st.rerun()

# Exibir logs de upload
if st.session_state.log_uploads:
    with st.expander("📄 Logs de Processamento", expanded=True):
        for log in st.session_state.log_uploads:
            st.info(log)

# Exibir resumo das contas
if st.session_state.df_resumo_total is not None:
    with st.expander("📋 Resumo das Contas", expanded=True):
        if "Valor" in st.session_state.df_resumo_total.columns:
            st.dataframe(st.session_state.df_resumo_total.style.format({"Valor": formatar_valor_br}), use_container_width=True)
        else:
            st.dataframe(st.session_state.df_resumo_total, use_container_width=True)

# Processar transações
if st.session_state.df_transacoes_total is not None:
    df_transacoes_total = st.session_state.df_transacoes_total
    
    # Separar em abas
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📊 Categorização",
         "💹 Faturamento e Estoque",
         "💰 Fluxo de Caixa / DRE / Projeções",
         "💼 Análise Sistema",
         "🤖 Análise IA"]
    )
    
    with tab1:
        st.header("📊 Categorização de Transações")
        
        df_valores_num = df_transacoes_total.copy()
        if "Valor (R$)" in df_valores_num.columns:
            df_valores_num["Valor_Num"] = df_valores_num["Valor (R$)"].apply(converter_para_float)
            df_creditos = df_valores_num[df_valores_num["Valor_Num"] > 0].copy()
            df_debitos = df_valores_num[df_valores_num["Valor_Num"] <= 0].copy()
            
            if "Valor_Num" in df_creditos.columns:
                df_creditos = df_creditos.drop(columns=["Valor_Num"])
            if "Valor_Num" in df_debitos.columns:
                df_debitos = df_debitos.drop(columns=["Valor_Num"])
            
            st.subheader("💰 Categorizar Créditos")
            df_creditos, df_desc_creditos = categorizar_transacoes(df_creditos, prefixo_key="credito", tipo_lancamento="Crédito")
            if "Valor (R$)" in df_creditos.columns:
                df_creditos["Valor (R$)"] = df_creditos["Valor (R$)"].apply(formatar_valor_br)
            
            if not df_creditos.empty and "Categoria" in df_creditos.columns:
                with st.expander("✅ Resumo da Categorização de Créditos", expanded=True):
                    resumo_creditos = df_creditos.groupby("Categoria").agg(
                        Total=("Valor (R$)", lambda x: sum(converter_para_float(v) for v in x)),
                        Quantidade=("Valor (R$)", "count")
                    ).reset_index()
                    resumo_creditos["Total"] = resumo_creditos["Total"].apply(formatar_valor_br)
                    st.dataframe(resumo_creditos.style.format({"Total": formatar_valor_br}), use_container_width=True)
                    
                    st.markdown("##### 🤖 Itens Categorizados Automaticamente")
                    if not df_desc_creditos.empty and "Total" in df_desc_creditos.columns:
                        df_desc_creditos["Total"] = df_desc_creditos["Total"].apply(formatar_valor_br)
                    df_auto_cat = df_desc_creditos[df_desc_creditos["Categoria"].notna() & (df_desc_creditos["Categoria"] != "")]
                    if not df_auto_cat.empty:
                        for _, row in df_auto_cat.iterrows():
                            desc = row["Descrição"]
                            cat = row["Categoria"]
                            qtd = row["Quantidade"]
                            total = row["Total"]
                            st.markdown(f"**📌 {desc}** — {qtd}x — Total: {total} → ✅ **{cat}**")
                    else:
                        st.info("Nenhum item foi categorizado automaticamente.")
            
            st.subheader("💸 Categorizar Débitos")
            df_debitos, df_desc_debitos = categorizar_transacoes(df_debitos, prefixo_key="debito", tipo_lancamento="Débito")
            if "Valor (R$)" in df_debitos.columns:
                df_debitos["Valor (R$)"] = df_debitos["Valor (R$)"].apply(formatar_valor_br)
            
            if not df_debitos.empty and "Categoria" in df_debitos.columns:
                with st.expander("✅ Resumo da Categorização de Débitos", expanded=True):
                    resumo_debitos = df_debitos.groupby("Categoria").agg(
                        Total=("Valor (R$)", lambda x: sum(abs(converter_para_float(v)) for v in x)),
                        Quantidade=("Valor (R$)", "count")
                    ).reset_index()
                    resumo_debitos["Total"] = resumo_debitos["Total"].apply(formatar_valor_br)
                    st.dataframe(resumo_debitos.style.format({"Total": formatar_valor_br}), use_container_width=True)
                    
                    st.markdown("##### 🤖 Itens Categorizados Automaticamente")
                    if not df_desc_debitos.empty and "Total" in df_desc_debitos.columns:
                        df_desc_debitos["Total"] = df_desc_debitos["Total"].apply(formatar_valor_br)
                    df_auto_cat = df_desc_debitos[df_desc_debitos["Categoria"].notna() & (df_desc_debitos["Categoria"] != "")]
                    if not df_auto_cat.empty:
                        for _, row in df_auto_cat.iterrows():
                            desc = row["Descrição"]
                            cat = row["Categoria"]
                            qtd = row["Quantidade"]
                            total = row["Total"]
                            st.markdown(f"**📌 {desc}** — {qtd}x — Total: {total} → ✅ **{cat}**")
                    else:
                        st.info("Nenhum item foi categorizado automaticamente.")
            
            df_transacoes_total = pd.concat([df_creditos, df_debitos], ignore_index=True)
            if "Valor (R$)" in df_transacoes_total.columns:
                df_transacoes_total["Valor (R$)"] = df_transacoes_total["Valor (R$)"].apply(formatar_valor_br)
            
            if "Considerar" not in df_transacoes_total.columns:
                df_transacoes_total["Considerar"] = "Sim"
            
            st.session_state.df_transacoes_total = df_transacoes_total
            
            st.subheader("📋 Todas as Transações Categorizadas")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                filtro_tipo = st.multiselect(
                    "Filtrar por Tipo:",
                    options=["Crédito", "Débito"],
                    default=["Crédito", "Débito"]
                )
            with col2:
                categorias_disponiveis = sorted(df_transacoes_total["Categoria"].dropna().unique().tolist())
                filtro_categoria = st.multiselect(
                    "Filtrar por Categoria:",
                    options=categorias_disponiveis,
                    default=[]
                )
            with col3:
                filtro_texto = st.text_input("Buscar na descrição:", "")
            
            df_filtrado = df_transacoes_total.copy()
            if "Valor (R$)" in df_filtrado.columns:
                df_filtrado["Valor (R$)"] = df_filtrado["Valor (R$)"].apply(formatar_valor_br)
            
            if filtro_tipo and len(filtro_tipo) < 2:
                if "Crédito" in filtro_tipo:
                    df_filtrado = df_filtrado[df_filtrado["Valor (R$)"].apply(
                        lambda x: converter_para_float(x) > 0 if pd.notna(x) else False
                    )]
                elif "Débito" in filtro_tipo:
                    df_filtrado = df_filtrado[df_filtrado["Valor (R$)"].apply(
                        lambda x: converter_para_float(x) <= 0 if pd.notna(x) else False
                    )]
            
            if filtro_categoria:
                df_filtrado = df_filtrado[df_filtrado["Categoria"].isin(filtro_categoria)]
            
            if filtro_texto:
                df_filtrado = df_filtrado[df_filtrado["Descrição"].str.contains(filtro_texto, case=False, na=False)]
            
            st.dataframe(df_filtrado.style.format({"Valor (R$)": formatar_valor_br}), use_container_width=True)
            
            st.info(f"Exibindo {len(df_filtrado)} de {len(df_transacoes_total)} transações.")
            
            output = io.BytesIO()
            df_download = df_transacoes_total.copy()
            if "Valor (R$)" in df_download.columns:
                df_download["Valor (R$)"] = df_download["Valor (R$)"].apply(converter_para_float)
            df_download.to_excel(output, index=False)
            output.seek(0)
            
            st.download_button(
                label="📥 Baixar transações categorizadas (.xlsx)",
                data=output,
                file_name=f"transacoes_categorizadas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with tab2:
        st.header("💹 Faturamento e Estoque")
        
        df_faturamento = coletar_faturamentos(df_transacoes_total)
        if df_faturamento is not None and "Valor" in df_faturamento.columns:
            df_faturamento["Valor"] = df_faturamento["Valor"].apply(formatar_valor_br)
            st.dataframe(df_faturamento.style.format({"Valor": formatar_valor_br}), use_container_width=True)
        
        coletar_estoques(df_transacoes_total)

    with tab3:
        st.header("📅 Projeções Futuras")

        st.subheader("📊 Configurar Projeções")
        inflacao_anual = st.number_input("Inflação anual esperada (%):", min_value=0.0, max_value=100.0, value=5.0, step=0.1)

        st.subheader("Cenário Pessimista")
        pess_receita = st.number_input("Ajuste de Receitas (%):", min_value=-100.0, max_value=100.0, value=-10.0, step=0.1, key="pess_receita")
        pess_despesa = st.number_input("Ajuste de Despesas (%):", min_value=-100.0, max_value=100.0, value=10.0, step=0.1, key="pess_despesa")

        st.subheader("Cenário Otimista")
        otim_receita = st.number_input("Ajuste de Receitas (%):", min_value=-100.0, max_value=100.0, value=10.0, step=0.1, key="otim_receita")
        otim_despesa = st.number_input("Ajuste de Despesas (%):", min_value=-100.0, max_value=100.0, value=-10.0, step=0.1, key="otim_despesa")

        if st.button("📈 Gerar Projeções", key="btn_projecoes"):
            with st.spinner("Gerando projeções... ⏳"):
                resultado_fluxo = st.session_state.get("resultado_fluxo", exibir_fluxo_caixa(df_transacoes_total))
                resultado_dre = st.session_state.get("resultado_dre", exibir_dre(df_fluxo=resultado_fluxo))

                if resultado_fluxo is None or resultado_dre is None:
                    st.error("⚠️ Gere o Fluxo de Caixa e DRE antes de criar projeções.")
                else:
                    meses_futuros = 60
                    # Salva resultados no session_state para uso em outras abas
                    st.session_state["resultado_fluxo"] = resultado_fluxo
                    st.session_state["resultado_dre"] = resultado_dre

                    abas_cenarios = st.tabs(["Cenário Atual", "Cenário Pessimista", "Cenário Otimista"])

                    # Cenário Atual
                    with abas_cenarios[0]:
                        st.subheader("Cenário Atual (apenas inflação)")
                        fluxo_atual, meses_projetados = projetar_valores(resultado_fluxo, inflacao_anual, meses_futuros)
                        dre_atual, _ = projetar_valores(resultado_dre, inflacao_anual, meses_futuros)

                        with st.expander("Fluxo de Caixa Projetado (Mensal)"):
                            st.dataframe(fluxo_atual.style.format({"Valor": formatar_valor_br}), use_container_width=True)
                            st.markdown("#### DRE Projetado (Mensal)")
                            dre_atual_formatado = dre_atual.reset_index()
                            dre_atual_formatado.columns.values[0] = "Descrição"
                            st.dataframe(
                                dre_atual_formatado.style.apply(highlight_rows, axis=1).format(
                                    formatter={col: formatar_valor_br for col in dre_atual_formatado.columns if col not in ["Descrição", "__tipo__"]}
                                ),
                                use_container_width=True, hide_index=True, height=650
                            )

                        with st.expander("Fluxo de Caixa Projetado (Anual)"):
                            fluxo_anual = resumir_por_ano(fluxo_atual, meses_projetados)
                            st.dataframe(fluxo_anual.style.format({"Valor": formatar_valor_br}), use_container_width=True)
                            st.markdown("#### DRE Projetado (Anual)")
                            dre_anual = resumir_por_ano(dre_atual, meses_projetados)
                            dre_anual_formatado = dre_anual.reset_index()
                            dre_anual_formatado.columns.values[0] = "Descrição"
                            st.dataframe(
                                dre_anual_formatado.style.apply(highlight_rows, axis=1).format(
                                    formatter={col: formatar_valor_br for col in dre_anual_formatado.columns if col not in ["Descrição", "__tipo__"]}
                                ),
                                use_container_width=True, hide_index=True, height=650
                            )

                    # Cenário Pessimista
                    with abas_cenarios[1]:
                        st.subheader("Cenário Pessimista")
                        fluxo_pess, _ = projetar_valores(resultado_fluxo, inflacao_anual, meses_futuros, pess_receita, pess_despesa)
                        dre_pess, _ = projetar_valores(resultado_dre, inflacao_anual, meses_futuros, pess_receita, pess_despesa)

                        with st.expander("Fluxo de Caixa Projetado (Mensal)"):
                            st.dataframe(fluxo_pess.style.format({"Valor": formatar_valor_br}), use_container_width=True)
                            st.markdown("#### DRE Projetado (Mensal)")
                            dre_pess_formatado = dre_pess.reset_index()
                            dre_pess_formatado.columns.values[0] = "Descrição"
                            st.dataframe(
                                dre_pess_formatado.style.apply(highlight_rows, axis=1).format(
                                    formatter={col: formatar_valor_br for col in dre_pess_formatado.columns if col not in ["Descrição", "__tipo__"]}
                                ),
                                use_container_width=True, hide_index=True, height=650
                            )

                        with st.expander("Fluxo de Caixa Projetado (Anual)"):
                            fluxo_anual = resumir_por_ano(fluxo_pess, meses_projetados)
                            st.dataframe(fluxo_anual.style.format({"Valor": formatar_valor_br}), use_container_width=True)
                            st.markdown("#### DRE Projetado (Anual)")
                            dre_anual = resumir_por_ano(dre_pess, meses_projetados)
                            dre_anual_formatado = dre_anual.reset_index()
                            dre_anual_formatado.columns.values[0] = "Descrição"
                            st.dataframe(
                                dre_anual_formatado.style.apply(highlight_rows, axis=1).format(
                                    formatter={col: formatar_valor_br for col in dre_anual_formatado.columns if col not in ["Descrição", "__tipo__"]}
                                ),
                                use_container_width=True, hide_index=True, height=650
                            )

                    # Cenário Otimista
                    with abas_cenarios[2]:
                        st.subheader("Cenário Otimista")
                        fluxo_otim, _ = projetar_valores(resultado_fluxo, inflacao_anual, meses_futuros, otim_receita, otim_despesa)
                        dre_otim, _ = projetar_valores(resultado_dre, inflacao_anual, meses_futuros, otim_receita, otim_despesa)

                        with st.expander("Fluxo de Caixa Projetado (Mensal)"):
                            st.dataframe(fluxo_otim.style.format({"Valor": formatar_valor_br}), use_container_width=True)
                            st.markdown("#### DRE Projetado (Mensal)")
                            dre_otim_formatado = dre_otim.reset_index()
                            dre_otim_formatado.columns.values[0] = "Descrição"
                            st.dataframe(
                                dre_otim_formatado.style.apply(highlight_rows, axis=1).format(
                                    formatter={col: formatar_valor_br for col in dre_otim_formatado.columns if col not in ["Descrição", "__tipo__"]}
                                ),
                                use_container_width=True, hide_index=True, height=650
                            )

                        with st.expander("Fluxo de Caixa Projetado (Anual)"):
                            fluxo_anual = resumir_por_ano(fluxo_otim, meses_projetados)
                            st.dataframe(fluxo_anual.style.format({"Valor": formatar_valor_br}), use_container_width=True)
                            st.markdown("#### DRE Projetado (Anual)")
                            dre_anual = resumir_por_ano(dre_otim, meses_projetados)
                            dre_anual_formatado = dre_anual.reset_index()
                            dre_anual_formatado.columns.values[0] = "Descrição"
                            st.dataframe(
                                dre_anual_formatado.style.apply(highlight_rows, axis=1).format(
                                    formatter={col: formatar_valor_br for col in dre_anual_formatado.columns if col not in ["Descrição", "__tipo__"]}
                                ),
                                use_container_width=True, hide_index=True, height=650
                            )

                    # Exportar tudo
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        fluxo_atual.to_excel(writer, sheet_name="Fluxo_Atual")
                        dre_atual.to_excel(writer, sheet_name="DRE_Atual")
                        fluxo_pess.to_excel(writer, sheet_name="Fluxo_Pessimista")
                        dre_pess.to_excel(writer, sheet_name="DRE_Pessimista")
                        fluxo_otim.to_excel(writer, sheet_name="Fluxo_Otimista")
                        dre_otim.to_excel(writer, sheet_name="DRE_Otimista")
                        resumir_por_ano(fluxo_atual, meses_projetados).to_excel(writer, sheet_name="Fluxo_Atual_Anual")
                        resumir_por_ano(dre_atual, meses_projetados).to_excel(writer, sheet_name="DRE_Atual_Anual")
                        resumir_por_ano(fluxo_pess, meses_projetados).to_excel(writer, sheet_name="Fluxo_Pessimista_Anual")
                        resumir_por_ano(dre_pess, meses_projetados).to_excel(writer, sheet_name="DRE_Pessimista_Anual")
                        resumir_por_ano(fluxo_otim, meses_projetados).to_excel(writer, sheet_name="Fluxo_Otimista_Anual")
                        resumir_por_ano(dre_otim, meses_projetados).to_excel(writer, sheet_name="DRE_Otimista_Anual")
                    output.seek(0)

                    st.download_button(
                        label="📥 Baixar Projeções (.xlsx)",
                        data=output,
                        file_name=f"projecoes_financeiras_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    
    with tab4:
        st.header("💼 Análise Sistema")
        
        if st.button("🧾 Gerar Parecer Diagnóstico", key="btn_parecer"):
            with st.spinner("Gerando parecer diagnóstico... ⏳"):
                df_transacoes_total = st.session_state.df_transacoes_total
                # Usa os resultados salvos no session_state
                resultado_fluxo = st.session_state.get("resultado_fluxo", exibir_fluxo_caixa(df_transacoes_total))
                resultado_dre = st.session_state.get("resultado_dre", exibir_dre(df_fluxo=resultado_fluxo))
                if resultado_dre is not None and any(col in resultado_dre.columns for col in ["Receita", "Despesas", "Lucro"]):
                    for col in ["Receita", "Despesas", "Lucro"]:
                        if col in resultado_dre.columns:
                            resultado_dre[col] = resultado_dre[col].apply(formatar_valor_br)
                    st.dataframe(resultado_dre.style.format({
                        "Receita": formatar_valor_br,
                        "Despesas": formatar_valor_br,
                        "Lucro": formatar_valor_br
                    }), use_container_width=True)
                gerar_parecer_automatico(resultado_fluxo)
    
    with tab5:
        st.header("🤖 Análise GPT - Parecer Financeiro Inteligente")
        
        descricao_empresa = st.text_area(
            "📝 Conte um pouco sobre a empresa:",
            placeholder="Ex.: área de atuação, tempo de mercado, porte, número de funcionários, etc.",
            help="Estas informações ajudarão a IA a gerar um parecer mais preciso e contextualizado."
        )
        
        col1, col2 = st.columns([1, 3])
        
        if col1.button("📊 Gerar Parecer com ChatGPT", use_container_width=True):
            if not descricao_empresa.strip():
                st.warning("⚠️ Por favor, preencha a descrição da empresa antes de gerar o parecer.")
            else:
                with st.spinner("Gerando parecer financeiro com inteligência artificial... ⏳"):
                    resultado_fluxo = st.session_state.get("resultado_fluxo", exibir_fluxo_caixa(df_transacoes_total))
                    resultado_dre = st.session_state.get("resultado_dre", exibir_dre(df_fluxo=resultado_fluxo))
                    
                    parecer = analisar_dfs_com_gpt(resultado_dre, resultado_fluxo, descricao_empresa)
                
                st.success("✅ Parecer gerado com sucesso!")
                
# Rodapé
st.markdown("---")
st.caption("© 2025 Sistema de Análise Financeira | Versão 1.0")