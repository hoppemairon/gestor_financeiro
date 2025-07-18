import pandas as pd
import streamlit as st
import os
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, Dict
import numpy as np
from datetime import datetime

def formatar_brl(valor: float) -> str:
    """Formata um valor para o formato de moeda brasileira."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def carregar_dados(path_fluxo: str, path_dre: str = None) -> Optional[pd.DataFrame]:
    """Carrega os dados do fluxo de caixa e, se disponível, do DRE. Valida presença de índices essenciais."""
    if not os.path.exists(path_fluxo):
        st.error("Arquivo de fluxo não encontrado.")
        return None, None
    try:
        df_fluxo = pd.read_excel(path_fluxo, index_col=0)
        df_fluxo = df_fluxo[~df_fluxo.index.str.startswith(("🟦", "🟥"))]
        # Validação dos índices essenciais
        indices_essenciais = ["🔷 Total de Receitas", "🔻 Total de Despesas", "🏦 Resultado do Período"]
        for idx in indices_essenciais:
            if idx not in df_fluxo.index:
                st.error(f"Índice essencial '{idx}' não encontrado no fluxo de caixa.")
                return None, None
        df_dre = None
        if path_dre and os.path.exists(path_dre):
            df_dre = pd.read_excel(path_dre, index_col=0)
        return df_fluxo, df_dre
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None, None

def extrair_metricas_principais(df_fluxo: pd.DataFrame, df_dre: pd.DataFrame = None) -> Dict[str, pd.Series]:
    """Extrai métricas principais do fluxo de caixa e DRE. Aceita variações nos nomes dos índices."""
    def buscar_indice(df, nomes):
        for nome in nomes:
            if nome in df.index:
                return df.loc[nome]
        st.warning(f"Índice(s) {nomes} não encontrado(s).")
        return pd.Series(dtype=float)
    metricas = {
        "total_receita": buscar_indice(df_fluxo, ["🔷 Total de Receitas", "Total de Receitas"]),
        "total_despesa": buscar_indice(df_fluxo, ["🔻 Total de Despesas", "Total de Despesas"]),
        "resultado": buscar_indice(df_fluxo, ["🏦 Resultado do Período", "Resultado do Período"])
    }
    if buscar_indice(df_fluxo, ["📦 Estoque Final", "Estoque Final"]).size > 0:
        metricas["estoque"] = buscar_indice(df_fluxo, ["📦 Estoque Final", "Estoque Final"])
    if df_dre is not None:
        metricas["margem_contribuicao"] = buscar_indice(df_dre, ["MARGEM CONTRIBUIÇÃO", "Margem de Contribuição"])
        metricas["lucro_operacional"] = buscar_indice(df_dre, ["LUCRO OPERACIONAL", "Lucro Operacional"])
        metricas["lucro_liquido"] = buscar_indice(df_dre, ["LUCRO LIQUIDO", "Lucro Líquido"])
    return metricas

def calcular_indicadores(metricas: Dict[str, pd.Series]) -> Dict[str, float]:
    """Calcula indicadores financeiros avançados. Compara com benchmarks do setor."""
    indicadores = {}
    meses = metricas["total_receita"].index

    # Médias
    indicadores["receita_media"] = metricas["total_receita"].mean()
    indicadores["despesa_media"] = metricas["total_despesa"].mean()
    indicadores["resultado_medio"] = metricas["resultado"].mean()

    # Margem média (baseada no fluxo)
    indicadores["margem_media"] = (indicadores["resultado_medio"] / indicadores["receita_media"]) * 100 if indicadores["receita_media"] != 0 else 0

    # Margem bruta e operacional (se DRE disponível)
    if "margem_contribuicao" in metricas:
        indicadores["margem_bruta"] = (metricas["margem_contribuicao"].mean() / indicadores["receita_media"]) * 100 if indicadores["receita_media"] != 0 else 0
        indicadores["margem_operacional"] = (metricas["lucro_operacional"].mean() / indicadores["receita_media"]) * 100 if indicadores["receita_media"] != 0 else 0
    else:
        indicadores["margem_bruta"] = 0
        indicadores["margem_operacional"] = 0

    # Volatilidade
    indicadores["volatilidade_resultado"] = metricas["resultado"].std() / abs(indicadores["resultado_medio"]) if indicadores["resultado_medio"] != 0 else 0

    # Tendências
    for key, name in [("total_receita", "tendencia_receita"), ("total_despesa", "tendencia_despesa"), ("resultado", "tendencia_resultado")]:
        try:
            x = np.arange(len(meses))
            y = np.array(metricas[key], dtype=np.float64)
            if len(y) >= 2 and np.isfinite(y).all():
                indicadores[name] = np.polyfit(x, y, 1)[0]
            else:
                indicadores[name] = np.nan
        except Exception:
            indicadores[name] = np.nan

    # Giro de estoque (se disponível)
    if "estoque" in metricas:
        indicadores["estoque_medio"] = metricas["estoque"].mean()
        indicadores["giro_estoque"] = metricas["total_receita"].sum() / indicadores["estoque_medio"] if indicadores["estoque_medio"] != 0 else np.nan

    # Benchmarks (exemplo: setor varejo)
    benchmarks = {
        "margem_media": 15,
        "margem_bruta": 35,
        "margem_operacional": 12,
        "giro_estoque": 6
    }
    indicadores["benchmarks"] = benchmarks
    return indicadores

def exibir_metricas_principais(metricas: Dict[str, pd.Series], indicadores: Dict[str, float]):
    """Exibe métricas principais em cards com comparativos e benchmarks."""
    st.subheader("📊 Indicadores Financeiros Principais")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Receita Média", formatar_brl(indicadores["receita_media"]), f"{indicadores['tendencia_receita']:+.2f}", delta_color="normal")
    with col2:
        st.metric("Despesa Média", formatar_brl(indicadores["despesa_media"]), f"{indicadores['tendencia_despesa']:+.2f}", delta_color="inverse")
    with col3:
        st.metric("Resultado Médio", formatar_brl(indicadores["resultado_medio"]), f"{indicadores['tendencia_resultado']:+.2f}", delta_color="normal")
    
    # Comparativo com benchmarks
    st.markdown("##### Benchmarks do setor (varejo):")
    st.markdown(f"- Margem média esperada: {indicadores['benchmarks']['margem_media']}%")
    st.markdown(f"- Margem bruta esperada: {indicadores['benchmarks']['margem_bruta']}%")
    st.markdown(f"- Margem operacional esperada: {indicadores['benchmarks']['margem_operacional']}%")
    st.markdown(f"- Giro de estoque esperado: {indicadores['benchmarks']['giro_estoque']:.2f}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Margem Média", f"{indicadores['margem_media']:.1f}%", help="Resultado Médio / Receita Média")
    with col2:
        st.metric("Volatilidade", f"{indicadores['volatilidade_resultado']:.2f}", help="Desvio padrão do resultado / Média")
    with col3:
        if "giro_estoque" in indicadores:
            st.metric("Giro de Estoque", f"{indicadores['giro_estoque']:.2f}", help="Receita Total / Estoque Médio")
    
    if "margem_bruta" in indicadores and indicadores["margem_bruta"] != 0:
        col1, col2, _ = st.columns(3)
        with col1:
            st.metric("Margem Bruta", f"{indicadores['margem_bruta']:.1f}%", help="Margem de Contribuição / Receita Média")
        with col2:
            st.metric("Margem Operacional", f"{indicadores['margem_operacional']:.1f}%", help="Lucro Operacional / Receita Média")

def criar_grafico_resultado(metricas: Dict[str, pd.Series]) -> go.Figure:
    """Cria um gráfico da evolução do resultado."""
    resultado = metricas["resultado"]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=resultado.index,
        y=resultado.values,
        mode='lines+markers',
        name='Resultado',
        line=dict(color='#2E86C1', width=3),
        marker=dict(size=8),
        fill='tozeroy',
        fillcolor='rgba(46, 134, 193, 0.2)'
    ))
    
    x_range = list(range(len(resultado)))
    y = resultado.values
    if len(y) >= 2 and np.isfinite(y).all():
        z = np.polyfit(x_range, y, 1)
        p = np.poly1d(z)
        fig.add_trace(go.Scatter(
            x=resultado.index,
            y=p(x_range),
            mode='lines',
            name='Tendência',
            line=dict(color='#E74C3C', width=2, dash='dash')
        ))
    
    fig.add_shape(
        type="line",
        x0=resultado.index[0],
        y0=0,
        x1=resultado.index[-1],
        y1=0,
        line=dict(color="black", width=1, dash="dot"),
    )
    
    fig.update_layout(
        title="Evolução do Resultado Mensal",
        xaxis_title="Mês",
        yaxis_title="Valor (R$)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white"
    )
    
    return fig

def criar_grafico_receita_despesa(metricas: Dict[str, pd.Series]) -> go.Figure:
    """Cria um gráfico comparativo entre receita e despesa."""
    receita = metricas["total_receita"]
    despesa = metricas["total_despesa"]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=receita.index,
        y=receita.values,
        name='Receitas',
        marker_color='#27AE60',
        opacity=0.8
    ))
    fig.add_trace(go.Bar(
        x=despesa.index,
        y=despesa.values * -1,
        name='Despesas',
        marker_color='#C0392B',
        opacity=0.8
    ))
    fig.add_trace(go.Scatter(
        x=metricas["resultado"].index,
        y=metricas["resultado"].values,
        mode='lines+markers',
        name='Resultado',
        line=dict(color='#2E86C1', width=3),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title="Receitas vs Despesas",
        xaxis_title="Mês",
        yaxis_title="Valor (R$)",
        barmode='relative',
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white"
    )
    
    return fig

def criar_grafico_estoque(metricas: Dict[str, pd.Series]) -> Optional[go.Figure]:
    """Cria um gráfico da evolução do estoque, se disponível."""
    if "estoque" not in metricas:
        return None
    
    estoque = metricas["estoque"]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=estoque.index,
        y=estoque.values,
        name='Estoque Final',
        marker_color='#8E44AD',
        opacity=0.8
    ))
    
    media_estoque = estoque.mean()
    fig.add_shape(
        type="line",
        x0=estoque.index[0],
        y0=media_estoque,
        x1=estoque.index[-1],
        y1=media_estoque,
        line=dict(color="#E67E22", width=2, dash="dash"),
    )
    
    fig.add_annotation(
        x=estoque.index[-1],
        y=media_estoque,
        text=f"Média: {formatar_brl(media_estoque)}",
        showarrow=True,
        arrowhead=1,
        ax=50,
        ay=-30,
        bgcolor="#E67E22",
        font=dict(color="white")
    )
    
    fig.update_layout(
        title="Evolução do Estoque Final",
        xaxis_title="Mês",
        yaxis_title="Valor (R$)",
        hovermode="x unified",
        template="plotly_white"
    )
    
    return fig

def criar_grafico_margens(metricas: Dict[str, pd.Series]) -> Optional[go.Figure]:
    """Cria gráfico de margens (se DRE disponível)."""
    if "margem_contribuicao" not in metricas:
        return None
    fig = go.Figure()
    margem_bruta = metricas["margem_contribuicao"] / metricas["total_receita"] * 100
    margem_operacional = metricas["lucro_operacional"] / metricas["total_receita"] * 100
    fig.add_trace(go.Scatter(x=margem_bruta.index, y=margem_bruta, mode="lines+markers", name="Margem Bruta", line=dict(color="#27AE60")))
    fig.add_trace(go.Scatter(x=margem_operacional.index, y=margem_operacional, mode="lines+markers", name="Margem Operacional", line=dict(color="#E74C3C")))
    fig.update_layout(
        title="Evolução das Margens (%)",
        xaxis_title="Mês",
        yaxis_title="Margem (%)",
        template="plotly_white",
        hovermode="x unified"
    )
    return fig

def gerar_insights(metricas: Dict[str, pd.Series], indicadores: Dict[str, float]) -> Dict[str, Dict]:
    """Gera insights estratégicos baseados em benchmarks."""
    insights = {"positivos": {}, "negativos": {}, "neutros": {}, "operacional": {}, "financeiro": {}, "estrategico": {}}
    
    # Análise de resultado
    if indicadores["resultado_medio"] > 0:
        insights["positivos"]["resultado"] = f"✅ Resultado positivo médio de {formatar_brl(indicadores['resultado_medio'])}."
    else:
        insights["negativos"]["resultado"] = f"🚨 Resultado médio negativo de {formatar_brl(indicadores['resultado_medio'])}. Atenção aos custos operacionais."
    
    # Análise de tendência
    if indicadores["tendencia_resultado"] > 0:
        insights["positivos"]["tendencia"] = f"📈 Tendência de crescimento no resultado: {formatar_brl(indicadores['tendencia_resultado'])}/mês."
    elif indicadores["tendencia_resultado"] < 0:
        insights["negativos"]["tendencia"] = f"📉 Tendência de queda no resultado: {formatar_brl(abs(indicadores['tendencia_resultado']))}/mês."
    
    # Análise de receita vs despesa
    if indicadores["tendencia_receita"] > 0 and indicadores["tendencia_despesa"] > 0:
        if indicadores["tendencia_receita"] > indicadores["tendencia_despesa"]:
            insights["positivos"]["crescimento"] = "📊 Receitas crescendo mais que despesas, favorecendo a margem."
        else:
            insights["negativos"]["crescimento"] = "⚠️ Despesas crescendo mais que receitas, comprometendo a margem futura."
    
    # Análise de volatilidade
    if indicadores["volatilidade_resultado"] > 0.5:
        insights["neutros"]["volatilidade"] = f"🔄 Alta volatilidade no resultado ({indicadores['volatilidade_resultado']:.2f}). Considere fundo de reserva."
    
    # Análise de estoque
    if "estoque" in metricas:
        ultimo_estoque = metricas["estoque"].iloc[-1]
        if ultimo_estoque > indicadores["estoque_medio"] * 1.2:
            insights["operacional"]["estoque"] = f"📦 Estoque atual {(ultimo_estoque/indicadores['estoque_medio']-1)*100:.1f}% acima da média. Possível excesso."
        elif ultimo_estoque < indicadores["estoque_medio"] * 0.8:
            insights["neutros"]["estoque"] = f"📦 Estoque atual {(1-ultimo_estoque/indicadores['estoque_medio'])*100:.1f}% abaixo da média. Verifique risco de desabastecimento."
        
        if indicadores["giro_estoque"] < 3:
            insights["operacional"]["giro"] = f"🔄 Giro de estoque baixo ({indicadores['giro_estoque']:.2f}). Avalie estratégias para aumentar vendas ou reduzir estoque."
        elif indicadores["giro_estoque"] > 10:
            insights["positivos"]["giro"] = f"🔄 Giro de estoque excelente ({indicadores['giro_estoque']:.2f}), indicando eficiência na gestão de inventário."
    
    # Análise de margens (se DRE disponível)
    if indicadores["margem_bruta"] != 0 and indicadores["margem_bruta"] < 30:
        insights["operacional"]["margem_baixa"] = "Margem bruta abaixo de 30%. Considere otimizar custos operacionais ou revisar preços."
    if indicadores["margem_operacional"] != 0 and indicadores["margem_operacional"] < 10:
        insights["financeiro"]["margem_operacional"] = "Margem operacional abaixo de 10%. Avalie eficiência operacional e despesas fixas."

    return insights

def exibir_insights(insights: Dict[str, Dict]):
    """Exibe insights organizados por categoria."""
    st.subheader("🧠 Análise Automática")
    
    for categoria in ["positivos", "negativos", "neutros", "operacional", "financeiro", "estrategico"]:
        if insights[categoria]:
            st.markdown(f"#### {categoria.capitalize()}")
            for key, insight in insights[categoria].items():
                st.markdown(f"- {insight}")

def gerar_recomendacoes(insights: Dict[str, Dict], indicadores: Dict[str, float]) -> list:
    """Gera recomendações práticas com prazos e prioridades."""
    recomendacoes = []
    
    if "resultado" in insights["negativos"]:
        recomendacoes.append({
            "texto": "Realizar análise detalhada de despesas em 30 dias, identificando cortes viáveis sem impacto operacional.",
            "prioridade": "Alta",
            "prazo": "1 mês"
        })
    if "tendencia" in insights["negativos"]:
        recomendacoes.append({
            "texto": "Elaborar plano de ação em 45 dias para reverter a queda no resultado, focando em novas fontes de receita.",
            "prioridade": "Alta",
            "prazo": "1,5 meses"
        })
    if "crescimento" in insights["negativos"]:
        recomendacoes.append({
            "texto": "Implementar controles rigorosos de despesas em 30 dias para equilibrar o crescimento com as receitas.",
            "prioridade": "Alta",
            "prazo": "1 mês"
        })
    if "estoque" in insights["operacional"]:
        recomendacoes.append({
            "texto": "Reavaliar política de compras em 60 dias e considerar promoções para reduzir estoque excedente.",
            "prioridade": "Média",
            "prazo": "2 meses"
        })
    if "giro" in insights["operacional"]:
        recomendacoes.append({
            "texto": "Desenvolver estratégias de marketing em 60 dias para aumentar vendas e melhorar giro de estoque.",
            "prioridade": "Média",
            "prazo": "2 meses"
        })
    if "volatilidade" in insights["neutros"]:
        recomendacoes.append({
            "texto": "Estabelecer fundo de reserva equivalente a 3 meses de despesas médias em 90 dias.",
            "prioridade": "Média",
            "prazo": "3 meses"
        })
    if "margem_baixa" in insights["operacional"]:
        recomendacoes.append({
            "texto": "Revisar política de preços em 45 dias para alinhar com valor percebido pelo cliente.",
            "prioridade": "Média",
            "prazo": "1,5 meses"
        })
    if "margem_operacional" in insights["financeiro"]:
        recomendacoes.append({
            "texto": "Analisar despesas fixas em 30 dias para identificar oportunidades de redução e melhorar margem operacional.",
            "prioridade": "Alta",
            "prazo": "1 mês"
        })
    
    if not recomendacoes:
        recomendacoes.append({
            "texto": "Continuar monitorando indicadores financeiros e manter boas práticas de gestão.",
            "prioridade": "Baixa",
            "prazo": "Contínuo"
        })
    
    return recomendacoes

def exibir_recomendacoes(recomendacoes: list):
    """Exibe recomendações com formatação clara."""
    st.subheader("🎯 Recomendações Estratégicas")
    for rec in recomendacoes:
        st.markdown(f"- **{rec['texto']}** (Prioridade: {rec['prioridade']}, Prazo: {rec['prazo']})")

def exibir_projecoes_cenario(projecoes: dict):
    """Exibe projeções de cenários futuros na análise do parecer."""
    st.subheader("📈 Projeções de Cenário")
    for nome, dados in projecoes.items():
        st.markdown(f"**Cenário {nome.capitalize()}**")
        if "df" in dados:
            st.dataframe(dados["df"], use_container_width=True)
        if "grafico" in dados:
            st.plotly_chart(dados["grafico"], use_container_width=True)
        if "comentario" in dados:
            st.markdown(f"_Comentário: {dados['comentario']}_")

def gerar_parecer_automatico(df_fluxo=None, df_dre=None, path_fluxo="./logic/CSVs/transacoes_numericas.xlsx", projecoes=None):
    """Função principal para gerar o parecer financeiro. Permite exportação e seleção personalizada de datas."""
    st.header("📄 Diagnóstico Financeiro Interativo")
    
    # Inicializar session_state para o período selecionado
    if "periodo_selecionado" not in st.session_state:
        st.session_state.periodo_selecionado = "Todo o período"
    
    # Adiciona seletor de período
    periodo_options = ["Últimos 3 meses", "Últimos 6 meses", "Último ano", "Todo o período"]
    periodo_selecionado = st.selectbox(
        "Selecione o período para análise:",
        options=periodo_options,
        index=periodo_options.index(st.session_state.periodo_selecionado),
        key="periodo_selector"
    )
    
    # Atualizar session_state apenas se o valor mudar
    if periodo_selecionado != st.session_state.periodo_selecionado:
        st.session_state.periodo_selecionado = periodo_selecionado
    
    # Carregar dados
    if df_fluxo is None:
        df_fluxo, df_dre = carregar_dados(path_fluxo)
        if df_fluxo is None:
            return
    
    # Filtrar por período selecionado
    if st.session_state.periodo_selecionado != "Todo o período":
        num_meses = 3 if "3" in st.session_state.periodo_selecionado else (6 if "6" in st.session_state.periodo_selecionado else 12)
        if len(df_fluxo.columns) > num_meses:
            df_fluxo = df_fluxo.iloc[:, -num_meses:]
        if df_dre is not None and len(df_dre.columns) > num_meses:
            df_dre = df_dre.iloc[:, -num_meses:]
    
    # Extrair métricas e calcular indicadores
    metricas = extrair_metricas_principais(df_fluxo, df_dre)
    indicadores = calcular_indicadores(metricas)
    
    # Exibir métricas principais
    exibir_metricas_principais(metricas, indicadores)
    
    # Criar abas para visualizações
    tab1, tab2 = st.tabs(["📊 Gráficos", "🧠 Análise e Recomendações"])
    
    with tab1:
        st.plotly_chart(criar_grafico_resultado(metricas), use_container_width=True)
        st.plotly_chart(criar_grafico_receita_despesa(metricas), use_container_width=True)
        fig_estoque = criar_grafico_estoque(metricas)
        if fig_estoque:
            st.plotly_chart(fig_estoque, use_container_width=True)
        fig_margens = criar_grafico_margens(metricas)
        if fig_margens:
            st.plotly_chart(fig_margens, use_container_width=True)
    
    with tab2:
        insights = gerar_insights(metricas, indicadores)
        exibir_insights(insights)
        recomendacoes = gerar_recomendacoes(insights, indicadores)
        exibir_recomendacoes(recomendacoes)
        # Exibe projeções de cenário se fornecidas
        if projecoes:
            exibir_projecoes_cenario(projecoes)
    
    # Adiciona botão para exportar parecer
    st.markdown("#### Exportar parecer:")
    if st.button("Exportar para Excel"):
        parecer_df = pd.DataFrame({"Indicador": list(indicadores.keys()), "Valor": list(indicadores.values())})
        parecer_df.to_excel("parecer_financeiro.xlsx")
        st.success("Parecer exportado para 'parecer_financeiro.xlsx'.")