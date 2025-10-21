import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional, Tuple
from .utils import formatar_valor_br, formatar_valor_simples_br

def calcular_receita_por_cultura(dados_plantio: Dict, df_transacoes: pd.DataFrame) -> Dict:
    """
    Calcula receita por cultura baseada nos dados de plantio e transações
    """
    receitas_cultura = {}
    
    # Receita estimada baseada nos plantios
    for plantio in dados_plantio.values():
        if not plantio.get('ativo', True):
            continue
            
        cultura = plantio.get('cultura', 'Outros')
        receita_estimada = plantio.get('receita_estimada', 0)
        
        if cultura not in receitas_cultura:
            receitas_cultura[cultura] = {
                'receita_estimada': 0,
                'receita_realizada': 0,
                'hectares': 0,
                'sacas_estimadas': 0
            }
        
        receitas_cultura[cultura]['receita_estimada'] += receita_estimada
        receitas_cultura[cultura]['hectares'] += plantio.get('hectares', 0)
        receitas_cultura[cultura]['sacas_estimadas'] += (
            plantio.get('hectares', 0) * plantio.get('sacas_por_hectare', 0)
        )
    
    # Receita realizada das transações (se disponível)
    if not df_transacoes.empty and 'centro_custo' in df_transacoes.columns:
        receitas_realizadas = df_transacoes[
            (df_transacoes['Valor (R$)'] > 0) & 
            (df_transacoes['centro_custo'].notna())
        ].groupby('centro_custo')['Valor (R$)'].sum()
        
        for cultura, valor in receitas_realizadas.items():
            if cultura in receitas_cultura:
                receitas_cultura[cultura]['receita_realizada'] = valor
    
    return receitas_cultura

def calcular_custo_por_cultura(dados_plantio: Dict, df_transacoes: pd.DataFrame) -> Dict:
    """
    Calcula custos por cultura com rateio administrativo
    """
    custos_cultura = {}
    
    # Inicializar custos por cultura
    for plantio in dados_plantio.values():
        if not plantio.get('ativo', True):
            continue
            
        cultura = plantio.get('cultura', 'Outros')
        if cultura not in custos_cultura:
            custos_cultura[cultura] = {
                'custo_direto': 0,
                'custo_administrativo': 0,
                'custo_total': 0,
                'hectares': plantio.get('hectares', 0)
            }
    
    if df_transacoes.empty:
        return custos_cultura
    
    # Calcular custos diretos por centro de custo
    custos_diretos = df_transacoes[
        (df_transacoes['Valor (R$)'] < 0) & 
        (df_transacoes['centro_custo'].notna()) &
        (df_transacoes['centro_custo'] != 'Administrativo')
    ].groupby('centro_custo')['Valor (R$)'].sum()
    
    for cultura, valor in custos_diretos.items():
        if cultura in custos_cultura:
            custos_cultura[cultura]['custo_direto'] = abs(valor)
    
    # Calcular rateio administrativo
    custos_admin = abs(df_transacoes[
        (df_transacoes['Valor (R$)'] < 0) & 
        ((df_transacoes['centro_custo'] == 'Administrativo') | 
         (df_transacoes['centro_custo'].isna()))
    ]['Valor (R$)'].sum())
    
    if custos_admin > 0:
        total_hectares = sum(c['hectares'] for c in custos_cultura.values())
        
        if total_hectares > 0:
            for cultura, dados in custos_cultura.items():
                percentual_rateio = dados['hectares'] / total_hectares
                dados['custo_administrativo'] = custos_admin * percentual_rateio
    
    # Calcular custo total
    for cultura, dados in custos_cultura.items():
        dados['custo_total'] = dados['custo_direto'] + dados['custo_administrativo']
    
    return custos_cultura

def calcular_indicadores_por_cultura(receitas_cultura: Dict, custos_cultura: Dict) -> Dict:
    """
    Calcula indicadores financeiros por cultura
    """
    indicadores = {}
    
    for cultura in receitas_cultura.keys():
        receita_data = receitas_cultura[cultura]
        custo_data = custos_cultura.get(cultura, {})
        
        receita_total = receita_data.get('receita_estimada', 0)
        custo_total = custo_data.get('custo_total', 0)
        hectares = receita_data.get('hectares', 0)
        sacas = receita_data.get('sacas_estimadas', 0)
        
        indicadores[cultura] = {
            'receita_total': receita_total,
            'custo_total': custo_total,
            'margem_bruta': receita_total - custo_total,
            'margem_percentual': ((receita_total - custo_total) / receita_total * 100) if receita_total > 0 else 0,
            'receita_por_hectare': receita_total / hectares if hectares > 0 else 0,
            'custo_por_hectare': custo_total / hectares if hectares > 0 else 0,
            'margem_por_hectare': (receita_total - custo_total) / hectares if hectares > 0 else 0,
            'custo_por_saca': custo_total / sacas if sacas > 0 else 0,
            'receita_por_saca': receita_total / sacas if sacas > 0 else 0,
            'hectares': hectares,
            'sacas_estimadas': sacas
        }
    
    return indicadores

def interface_analise_por_cultura():
    """
    Interface principal para análise financeira por cultura
    """
    st.subheader("📊 Análise Financeira por Cultura")
    
    # Verificar se há dados necessários
    if 'plantios_agro' not in st.session_state or not st.session_state['plantios_agro']:
        st.warning("📋 Cadastre plantios primeiro para visualizar a análise por cultura.")
        return
    
    if 'df_transacoes_total_vyco' not in st.session_state:
        st.warning("💰 Importe dados financeiros primeiro para análise completa.")
        df_transacoes = pd.DataFrame()
    else:
        df_transacoes = st.session_state['df_transacoes_total_vyco']
    
    # Calcular análises
    dados_plantio = st.session_state['plantios_agro']
    receitas_cultura = calcular_receita_por_cultura(dados_plantio, df_transacoes)
    custos_cultura = calcular_custo_por_cultura(dados_plantio, df_transacoes)
    indicadores = calcular_indicadores_por_cultura(receitas_cultura, custos_cultura)
    
    # Tabs para diferentes visualizações
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Resumo Geral", 
        "💰 Receitas vs Custos", 
        "🎯 Indicadores", 
        "📊 Gráficos"
    ])
    
    with tab1:
        exibir_resumo_geral(indicadores)
    
    with tab2:
        exibir_receitas_custos(receitas_cultura, custos_cultura)
    
    with tab3:
        exibir_indicadores_detalhados(indicadores)
    
    with tab4:
        exibir_graficos_analise(indicadores)

def exibir_resumo_geral(indicadores: Dict):
    """
    Exibe resumo geral da análise por cultura
    """
    if not indicadores:
        st.info("Nenhum dado para exibir.")
        return
    
    # Totais gerais
    total_receita = sum(ind['receita_total'] for ind in indicadores.values())
    total_custo = sum(ind['custo_total'] for ind in indicadores.values())
    total_margem = total_receita - total_custo
    total_hectares = sum(ind['hectares'] for ind in indicadores.values())
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Receita Total", 
            formatar_valor_br(total_receita),
            help="Receita total estimada de todas as culturas"
        )
    
    with col2:
        st.metric(
            "Custo Total", 
            formatar_valor_br(total_custo),
            help="Custo total incluindo rateio administrativo"
        )
    
    with col3:
        st.metric(
            "Margem Bruta", 
            formatar_valor_br(total_margem),
            delta=f"{(total_margem/total_receita*100):.1f}%".replace(".", ",") if total_receita > 0 else None,
            help="Margem bruta total e percentual"
        )
    
    with col4:
        st.metric(
            "Área Total", 
            f"{total_hectares:,.1f} ha",
            help="Área total plantada"
        )
    
    # Ranking de culturas por margem
    st.subheader("🏆 Ranking por Margem Bruta")
    
    ranking_data = []
    for cultura, ind in indicadores.items():
        ranking_data.append({
            'Cultura': cultura,
            'Margem Bruta': formatar_valor_br(ind['margem_bruta']),
            'Margem %': f"{ind['margem_percentual']:.1f}%".replace(".", ","),
            'Receita/ha': formatar_valor_br(ind['receita_por_hectare']),
            'Custo/ha': formatar_valor_br(ind['custo_por_hectare']),
            'Hectares': f"{ind['hectares']:,.1f}".replace(",", ".").replace(".", ",", 1),
            'Status': get_status_cultura(ind['margem_percentual'])
        })
    
    df_ranking = pd.DataFrame(ranking_data)
    df_ranking = df_ranking.sort_values('Margem %', ascending=False, key=lambda x: pd.to_numeric(x.str.replace('%', ''), errors='coerce'))
    
    st.dataframe(df_ranking, use_container_width=True)

def exibir_receitas_custos(receitas_cultura: Dict, custos_cultura: Dict):
    """
    Exibe detalhamento de receitas e custos por cultura
    """
    st.subheader("💰 Detalhamento Receitas vs Custos")
    
    for cultura in receitas_cultura.keys():
        with st.expander(f"🌾 {cultura}"):
            receita_data = receitas_cultura[cultura]
            custo_data = custos_cultura.get(cultura, {})
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📈 Receitas**")
                st.metric("Receita Estimada", formatar_valor_br(receita_data.get('receita_estimada', 0)))
                st.metric("Receita Realizada", formatar_valor_br(receita_data.get('receita_realizada', 0)))
                st.metric("Hectares", f"{receita_data.get('hectares', 0):,.1f} ha".replace(",", ".").replace(".", ",", 1))
                st.metric("Sacas Estimadas", f"{receita_data.get('sacas_estimadas', 0):,.0f}".replace(",", "."))
            
            with col2:
                st.markdown("**📉 Custos**")
                st.metric("Custo Direto", formatar_valor_br(custo_data.get('custo_direto', 0)))
                st.metric("Custo Administrativo", formatar_valor_br(custo_data.get('custo_administrativo', 0)))
                st.metric("Custo Total", formatar_valor_br(custo_data.get('custo_total', 0)))
                
                # Percentual de rateio
                total_admin = sum(c.get('custo_administrativo', 0) for c in custos_cultura.values())
                perc_rateio = (custo_data.get('custo_administrativo', 0) / total_admin * 100) if total_admin > 0 else 0
                st.metric("% Rateio Administrativo", f"{perc_rateio:.1f}%".replace(".", ","))

def exibir_indicadores_detalhados(indicadores: Dict):
    """
    Exibe indicadores financeiros detalhados
    """
    st.subheader("🎯 Indicadores Financeiros Detalhados")
    
    # Criar DataFrame com todos os indicadores
    dados_indicadores = []
    
    for cultura, ind in indicadores.items():
        dados_indicadores.append({
            'Cultura': cultura,
            'Receita Total': ind['receita_total'],
            'Custo Total': ind['custo_total'],
            'Margem Bruta': ind['margem_bruta'],
            'Margem %': ind['margem_percentual'],
            'Receita/ha': ind['receita_por_hectare'],
            'Custo/ha': ind['custo_por_hectare'],
            'Margem/ha': ind['margem_por_hectare'],
            'Custo/saca': ind['custo_por_saca'],
            'Receita/saca': ind['receita_por_saca'],
            'Hectares': ind['hectares'],
            'Sacas': ind['sacas_estimadas']
        })
    
    if dados_indicadores:
        df_indicadores = pd.DataFrame(dados_indicadores)
        
        # Formatar valores monetários
        colunas_monetarias = ['Receita Total', 'Custo Total', 'Margem Bruta', 
                             'Receita/ha', 'Custo/ha', 'Margem/ha', 
                             'Custo/saca', 'Receita/saca']
        
        df_formatado = df_indicadores.copy()
        for col in colunas_monetarias:
            if col in df_formatado.columns:
                df_formatado[col] = df_formatado[col].apply(lambda x: formatar_valor_br(x))
        
        if 'Margem %' in df_formatado.columns:
            df_formatado['Margem %'] = df_formatado['Margem %'].apply(lambda x: f"{x:.1f}%".replace(".", ","))
        if 'Hectares' in df_formatado.columns:
            df_formatado['Hectares'] = df_formatado['Hectares'].apply(lambda x: f"{x:,.1f}".replace(",", ".").replace(".", ",", 1))
        if 'Sacas' in df_formatado.columns:
            df_formatado['Sacas'] = df_formatado['Sacas'].apply(lambda x: f"{x:,.0f}".replace(",", "."))
        
        st.dataframe(df_formatado, use_container_width=True)

def exibir_graficos_analise(indicadores: Dict):
    """
    Exibe gráficos para análise visual
    """
    if not indicadores:
        st.info("Nenhum dado para exibir.")
        return
    
    culturas = list(indicadores.keys())
    
    # Gráfico 1: Receita vs Custo por Cultura
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Receita vs Custo")
        receitas = [indicadores[c]['receita_total'] for c in culturas]
        custos = [indicadores[c]['custo_total'] for c in culturas]
        
        fig_receita_custo = go.Figure()
        fig_receita_custo.add_trace(go.Bar(name='Receita', x=culturas, y=receitas, marker_color='green'))
        fig_receita_custo.add_trace(go.Bar(name='Custo', x=culturas, y=custos, marker_color='red'))
        
        fig_receita_custo.update_layout(
            title="Receita vs Custo por Cultura",
            xaxis_title="Cultura",
            yaxis_title="Valor (R$)",
            barmode='group'
        )
        
        st.plotly_chart(fig_receita_custo, use_container_width=True)
    
    with col2:
        st.subheader("📈 Margem Percentual")
        margens = [indicadores[c]['margem_percentual'] for c in culturas]
        cores = ['green' if m > 20 else 'orange' if m > 10 else 'red' for m in margens]
        
        fig_margem = go.Figure(data=[
            go.Bar(x=culturas, y=margens, marker_color=cores)
        ])
        
        fig_margem.update_layout(
            title="Margem Percentual por Cultura",
            xaxis_title="Cultura",
            yaxis_title="Margem (%)"
        )
        
        st.plotly_chart(fig_margem, use_container_width=True)
    
    # Gráfico 2: Indicadores por Hectare
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("🌾 Receita por Hectare")
        receita_ha = [indicadores[c]['receita_por_hectare'] for c in culturas]
        
        fig_receita_ha = px.pie(
            values=receita_ha, 
            names=culturas, 
            title="Distribuição da Receita por Hectare"
        )
        
        st.plotly_chart(fig_receita_ha, use_container_width=True)
    
    with col4:
        st.subheader("💰 Análise Custo-Benefício")
        
        x_valores = [indicadores[c]['custo_por_hectare'] for c in culturas]
        y_valores = [indicadores[c]['receita_por_hectare'] for c in culturas]
        
        fig_scatter = go.Figure()
        
        for i, cultura in enumerate(culturas):
            fig_scatter.add_trace(go.Scatter(
                x=[x_valores[i]], 
                y=[y_valores[i]], 
                mode='markers+text',
                text=[cultura],
                textposition="top center",
                marker=dict(size=15, color=i),
                name=cultura
            ))
        
        # Linha diagonal (break-even)
        max_val = max(max(x_valores), max(y_valores))
        fig_scatter.add_trace(go.Scatter(
            x=[0, max_val], 
            y=[0, max_val], 
            mode='lines',
            line=dict(dash='dash', color='gray'),
            name='Break-even'
        ))
        
        fig_scatter.update_layout(
            title="Custo vs Receita por Hectare",
            xaxis_title="Custo por Hectare (R$)",
            yaxis_title="Receita por Hectare (R$)",
            showlegend=False
        )
        
        st.plotly_chart(fig_scatter, use_container_width=True)

def get_status_cultura(margem_percentual: float) -> str:
    """
    Retorna status da cultura baseado na margem percentual
    """
    if margem_percentual >= 25:
        return "🟢 Excelente"
    elif margem_percentual >= 15:
        return "🟡 Boa"
    elif margem_percentual >= 5:
        return "🟠 Regular"
    else:
        return "🔴 Crítica"

def exportar_analise_cultura(indicadores: Dict, receitas_cultura: Dict, custos_cultura: Dict) -> pd.DataFrame:
    """
    Exporta análise por cultura para DataFrame
    """
    dados_export = []
    
    for cultura, ind in indicadores.items():
        receita_data = receitas_cultura[cultura]
        custo_data = custos_cultura.get(cultura, {})
        
        dados_export.append({
            'Cultura': cultura,
            'Hectares': ind['hectares'],
            'Sacas_Estimadas': ind['sacas_estimadas'],
            'Receita_Total': ind['receita_total'],
            'Custo_Direto': custo_data.get('custo_direto', 0),
            'Custo_Administrativo': custo_data.get('custo_administrativo', 0),
            'Custo_Total': ind['custo_total'],
            'Margem_Bruta': ind['margem_bruta'],
            'Margem_Percentual': ind['margem_percentual'],
            'Receita_por_Hectare': ind['receita_por_hectare'],
            'Custo_por_Hectare': ind['custo_por_hectare'],
            'Margem_por_Hectare': ind['margem_por_hectare'],
            'Custo_por_Saca': ind['custo_por_saca'],
            'Receita_por_Saca': ind['receita_por_saca'],
            'Status': get_status_cultura(ind['margem_percentual'])
        })
    
    return pd.DataFrame(dados_export)