import pandas as pd
import streamlit as st
import os
import plotly.graph_objects as go
from typing import Dict, List, Tuple, Optional

# Constantes
GRUPOS_DESPESAS = ["Despesas", "Investimentos", "Retiradas", "Extra Operacional"]
ESTILO_LINHAS = {
    "FATURAMENTO": ("#5d65c8", "white"),
    "RECEITA": ("#152357", "white"),
    "MARGEM CONTRIBUIÇÃO": ("#39b79c", "black"),
    "LUCRO OPERACIONAL": ("#39b79c", "black"),
    "LUCRO LIQUIDO": ("#39b79c", "black"),
    "RESULTADO": ("#216a5a", "black"),
    "RESULTADO GERENCIAL": ("#216a5a", "white"),
}

def formatar_brl(valor: float) -> str:
    """Formata um valor para o formato de moeda brasileira."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def carregar_dados(path_fluxo: str, path_plano: str) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Carrega os dados dos arquivos e retorna os DataFrames."""
    if not os.path.exists(path_fluxo) or not os.path.exists(path_plano):
        st.error("Dados necessários não encontrados.")
        return None, None
    
    try:
        df_fluxo = pd.read_excel(path_fluxo, index_col=0)
        plano = pd.read_csv(path_plano)
        return df_fluxo, plano
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None, None

def soma_por_grupo(df_fluxo: pd.DataFrame, plano: pd.DataFrame, grupo: str) -> pd.Series:
    """Soma valores por grupo de categorias."""
    cats = plano[plano["Grupo"] == grupo]["Categoria"].tolist()
    valores = df_fluxo.loc[df_fluxo.index.isin(cats)].sum()
    
    # Se for despesa, inverter o sinal para positivo
    if any(desp in grupo for desp in GRUPOS_DESPESAS):
        valores = valores.abs()
    return valores

def soma_por_categoria(df_fluxo: pd.DataFrame, *categorias) -> pd.Series:
    """Soma valores por categorias específicas."""
    # Debug: verificar quais categorias existem no fluxo
    categorias_encontradas = [cat for cat in categorias if cat in df_fluxo.index]
    if not categorias_encontradas:
        # Se não encontrou nenhuma categoria exata, tentar busca parcial
        for categoria in categorias:
            linhas_parciais = df_fluxo.index[df_fluxo.index.str.contains(categoria, case=False, na=False)]
            if len(linhas_parciais) > 0:
                categorias_encontradas.extend(linhas_parciais.tolist())
    
    if categorias_encontradas:
        return df_fluxo.loc[df_fluxo.index.isin(categorias_encontradas)].sum()
    else:
        # Retornar série zerada com as colunas do df_fluxo
        return pd.Series(0, index=df_fluxo.columns)

def debug_linhas_fluxo_caixa(df_fluxo: pd.DataFrame):
    """Debug: mostra as linhas disponíveis no fluxo de caixa"""
    import streamlit as st
    
    if st.checkbox("🔍 Debug - Linhas do Fluxo de Caixa"):
        st.subheader("Debug: Análise do Fluxo de Caixa")
        
        # Mostrar todas as linhas do fluxo
        st.markdown("**📋 Todas as linhas disponíveis no fluxo:**")
        linhas_disponiveis = list(df_fluxo.index)
        for i, linha in enumerate(linhas_disponiveis):
            if i < 20:  # Mostrar primeiras 20 linhas
                # Verificar se tem valores
                valores_linha = df_fluxo.loc[linha]
                soma_linha = valores_linha.sum()
                st.write(f"- {linha} (Soma: {soma_linha:,.2f})")
        
        if len(linhas_disponiveis) > 20:
            st.write(f"... e mais {len(linhas_disponiveis) - 20} linhas")
        
        # Buscar especificamente por receitas extra
        st.markdown("**💰 Linhas relacionadas a Receitas Extra:**")
        termos_busca = ['receita', 'extra', 'operacional', 'outros', 'recebimentos', 'juros']
        for termo in termos_busca:
            linhas_encontradas = [linha for linha in linhas_disponiveis 
                                if termo.lower() in linha.lower()]
            if linhas_encontradas:
                st.write(f"**{termo.title()}:** {linhas_encontradas}")

def criar_dre(df_fluxo: pd.DataFrame, plano: pd.DataFrame) -> pd.DataFrame:
    """Cria o DataFrame do DRE com todos os cálculos."""
    meses = df_fluxo.columns.tolist()
    
    # Função auxiliar para criar linhas
    def linha(nome, serie):
        return pd.DataFrame([serie], index=[nome])

    # Construção do DRE por etapas
    dre = pd.DataFrame()
    
    # Verificar se Faturamento Bruto existe no fluxo
    if "💰 Faturamento Bruto" in df_fluxo.index:
        linha_faturamento = df_fluxo.loc["💰 Faturamento Bruto"]
    else:
        st.warning("⚠️ Linha 'Faturamento Bruto' não encontrada no fluxo de caixa. Verifique se os dados foram salvos.")
        linha_faturamento = pd.Series(0, index=meses)
    
    # Bloco 1: Faturamento e Margem de Contribuição
    dre = pd.concat([
        linha("FATURAMENTO", linha_faturamento),
        linha("RECEITA", soma_por_categoria(df_fluxo, "Receita de Vendas", "Receita de Serviços")),
        linha("IMPOSTOS", soma_por_grupo(df_fluxo, plano, "Despesas Impostos")),
        linha("DESPESA OPERACIONAL", soma_por_grupo(df_fluxo, plano, "Despesas Operacionais")),
    ])
    
    dre.loc["MARGEM CONTRIBUIÇÃO"] = dre.loc["RECEITA"] - dre.loc["IMPOSTOS"] - dre.loc["DESPESA OPERACIONAL"]
    
    # Bloco 2: Lucro Operacional
    dre = pd.concat([
        dre,
        linha("DESPESAS COM PESSOAL", soma_por_grupo(df_fluxo, plano, "Despesas RH")),
        linha("DESPESA ADMINISTRATIVA", soma_por_grupo(df_fluxo, plano, "Despesas Administrativas")),
    ])
    
    dre.loc["LUCRO OPERACIONAL"] = dre.loc["MARGEM CONTRIBUIÇÃO"] - dre.loc["DESPESAS COM PESSOAL"] - dre.loc["DESPESA ADMINISTRATIVA"]
    
    # Bloco 3: Lucro Líquido
    dre = pd.concat([
        dre,
        linha("INVESTIMENTOS", soma_por_grupo(df_fluxo, plano, "Investimentos / Aplicações")),
        linha("DESPESA EXTRA OPERACIONAL", soma_por_grupo(df_fluxo, plano, "Extra Operacional")),
    ])
    
    dre.loc["LUCRO LIQUIDO"] = dre.loc["LUCRO OPERACIONAL"] - dre.loc["INVESTIMENTOS"] - dre.loc["DESPESA EXTRA OPERACIONAL"]
    
    # Bloco 4: Resultado Final
    dre = pd.concat([
        dre,
        linha("RETIRADAS SÓCIOS", soma_por_grupo(df_fluxo, plano, "Retiradas")),
        linha("RECEITA EXTRA OPERACIONAL", soma_por_categoria(df_fluxo, "Receita Extra Operacional", "Juros Recebidos", "Outros Recebimentos")),
    ])
    
    dre.loc["RESULTADO"] = dre.loc["LUCRO LIQUIDO"] - dre.loc["RETIRADAS SÓCIOS"] + dre.loc["RECEITA EXTRA OPERACIONAL"]
    
    # Bloco 5: Resultado Gerencial
    if "📦 Estoque Final" in df_fluxo.index:
        dre.loc["ESTOQUE"] = df_fluxo.loc["📦 Estoque Final"]
    else:
        st.warning("⚠️ Linha 'Estoque Final' não encontrada no fluxo de caixa. Verifique se os dados foram salvos.")
        dre.loc["ESTOQUE"] = 0
        
    dre.loc["SALDO"] = 0  # TODO: puxar saldo dos relatórios
    dre.loc["RESULTADO GERENCIAL"] = dre.loc["RESULTADO"] + dre.loc["ESTOQUE"] + dre.loc["SALDO"]
    
    # Cálculos finais
    dre["TOTAL"] = dre[meses].sum(axis=1)
    total_receita = dre.loc["RECEITA", "TOTAL"]
    dre["%"] = dre["TOTAL"] / total_receita * 100 if total_receita != 0 else 0
    
    return dre

def formatar_dre(dre: pd.DataFrame, meses: List[str]) -> pd.DataFrame:
    """Formata o DRE para exibição."""
    dre_formatado = dre.copy()
    
    # Identificar colunas de totais
    colunas_totais = [col for col in dre_formatado.columns if isinstance(col, str) and "TOTAL" in col.upper()]
    
    # Formata valores monetários e percentuais
    for col in meses + colunas_totais:
        if col in dre_formatado.columns:
            dre_formatado[col] = dre_formatado[col].apply(formatar_brl)
            
    if "%" in dre_formatado.columns:
        dre_formatado["%"] = dre["%"].apply(lambda x: f"{x:.1f}%")
    
    # Resetando índice para que a primeira coluna seja exibida normalmente
    dre_formatado = dre_formatado.reset_index()
    dre_formatado.columns.values[0] = "Descrição"
    
    return dre_formatado

def highlight_rows(row):
    """Aplica estilos às linhas do DRE."""
    # Verificar se a coluna "Descrição" existe
    if "Descrição" in row.index:
        descricao = row["Descrição"]
    elif hasattr(row, 'name') and row.name:
        # Se não tem coluna "Descrição", usar o nome do índice
        descricao = row.name
    else:
        # Se não conseguir identificar a descrição, usar estilo padrão
        return ["" for _ in row]
    
    bg_color, text_color = ESTILO_LINHAS.get(descricao, ("", "black"))
    return [f"background-color: {bg_color}; color: {text_color}; font-weight: bold;" if bg_color else "" for _ in row]

def criar_grafico_dre(dre: pd.DataFrame) -> go.Figure:
    """Cria um gráfico de barras para visualizar os principais indicadores do DRE."""
    # Selecionar apenas as linhas principais para o gráfico
    indicadores = ["RECEITA", "MARGEM CONTRIBUIÇÃO", "LUCRO OPERACIONAL", "LUCRO LIQUIDO", "RESULTADO"]
    dados_grafico = dre.loc[indicadores, "TOTAL"].reset_index()
    dados_grafico.columns = ["Indicador", "Valor"]
    
    # Definir cores para cada indicador
    cores = {
        "RECEITA": "#152357", 
        "MARGEM CONTRIBUIÇÃO": "#39b79c", 
        "LUCRO OPERACIONAL": "#39b79c", 
        "LUCRO LIQUIDO": "#39b79c", 
        "RESULTADO": "#216a5a"
    }
    
    # Criar gráfico
    fig = go.Figure()
    
    for indicador in indicadores:
        valor = dre.loc[indicador, "TOTAL"]
        fig.add_trace(go.Bar(
            x=[indicador],
            y=[valor],
            name=indicador,
            marker_color=cores.get(indicador, "#1f77b4"),
            text=[formatar_brl(valor)],
            textposition='auto'
        ))
    
    fig.update_layout(
        title="Principais Indicadores Financeiros",
        xaxis_title="Indicador",
        yaxis_title="Valor (R$)",
        barmode='group',
        height=400,
        template="plotly_white"
    )
    
    return fig

def exibir_dre(df_fluxo=None, path_fluxo="./logic/CSVs/transacoes_numericas.xlsx", path_plano="./logic/CSVs/plano_de_contas.csv", path_faturamento="./logic/CSVs/faturamentos.csv", path_estoque="./logic/CSVs/estoques.csv"):
    """Função principal que exibe o DRE no Streamlit."""
    st.markdown("## 📊 Demonstrativo de Resultados (DRE)")

    # Se não vier DataFrame, carrega do Excel
    if df_fluxo is None:
        df_fluxo, _ = carregar_dados(path_fluxo, path_plano)
        if df_fluxo is None:
            return

    # Garantir que Faturamento e Estoque estejam no DataFrame do fluxo
    if "💰 Faturamento Bruto" not in df_fluxo.index and os.path.exists(path_faturamento):
        try:
            df_fat = pd.read_csv(path_faturamento)
            meses = df_fluxo.columns.tolist()
            linha_fat = df_fat.set_index("Mes").T.reindex(columns=meses).fillna(0)
            linha_fat.index = ["💰 Faturamento Bruto"]
            df_fluxo = pd.concat([linha_fat, df_fluxo])
        except Exception as e:
            st.warning(f"⚠️ Erro ao carregar dados de faturamento: {e}")
    
    if "📦 Estoque Final" not in df_fluxo.index and os.path.exists(path_estoque):
        try:
            df_estoque = pd.read_csv(path_estoque)
            meses = df_fluxo.columns.tolist()
            linha_estoque = df_estoque.set_index("Mes").T.reindex(columns=meses).fillna(0)
            linha_estoque.index = ["📦 Estoque Final"]
            df_fluxo = pd.concat([df_fluxo, linha_estoque])
        except Exception as e:
            st.warning(f"⚠️ Erro ao carregar dados de estoque: {e}")

    plano = pd.read_csv(path_plano)
    meses = df_fluxo.columns.tolist()

    # Criar abas para diferentes visualizações
    tab1, tab2 = st.tabs(["Tabela DRE", "Visualização Gráfica"])
    
    with tab1:
        # Debug do fluxo de caixa
        debug_linhas_fluxo_caixa(df_fluxo)
        
        # Criar e formatar o DRE
        dre = criar_dre(df_fluxo, plano)
        dre_formatado = formatar_dre(dre, meses)
        
        # Exibir o DRE formatado
        st.dataframe(
            dre_formatado.style.apply(highlight_rows, axis=1).hide(axis="index"),
            use_container_width=True, hide_index=True, height=650
        )
        
        # Adicionar opção para download
        csv = dre_formatado.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar DRE como CSV",
            data=csv,
            file_name="dre_report.csv",
            mime="text/csv",
        )
    
    with tab2:
        # Criar e exibir o gráfico
        dre = criar_dre(df_fluxo, plano)
        fig = criar_grafico_dre(dre)
        st.plotly_chart(fig, use_container_width=True)
        
        # Exibir métricas importantes
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Margem de Contribuição", 
                formatar_brl(dre.loc["MARGEM CONTRIBUIÇÃO", "TOTAL"]),
                f"{dre.loc['MARGEM CONTRIBUIÇÃO', '%']:.1f}%"
            )
        with col2:
            st.metric(
                "Lucro Operacional", 
                formatar_brl(dre.loc["LUCRO OPERACIONAL", "TOTAL"]),
                f"{dre.loc['LUCRO OPERACIONAL', '%']:.1f}%"
            )
        with col3:
            st.metric(
                "Resultado Final", 
                formatar_brl(dre.loc["RESULTADO", "TOTAL"]),
                f"{dre.loc['RESULTADO', '%']:.1f}%"
            )
    
    return dre