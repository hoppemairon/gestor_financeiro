import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional, Tuple
from .utils import formatar_valor_br, formatar_valor_simples_br

def calcular_receita_por_cultura(dados_plantio: Dict, df_transacoes: pd.DataFrame) -> Dict:
    """
    Calcula receita por cultura baseada nos dados de plantio e transações do Vyco
    
    Metodologia:
    1. Receita Estimada: Soma dos valores planejados por cultura nos plantios
    2. Receita Realizada: Transações operacionais positivas do Vyco
       - Se tem centro de custo: agrupa por centro de custo
       - Se não tem: rateia proporcionalmente por hectares da cultura
    """
    receitas_cultura = {}
    
    # 1. Receita estimada e dados base dos plantios
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
                'sacas_estimadas': 0,
                'metodo_calculo_receita': 'Estimativa de plantio'
            }
        
        receitas_cultura[cultura]['receita_estimada'] += receita_estimada
        receitas_cultura[cultura]['hectares'] += plantio.get('hectares', 0)
        receitas_cultura[cultura]['sacas_estimadas'] += (
            plantio.get('hectares', 0) * plantio.get('sacas_por_hectare', 0)
        )
    
    # 2. Receita realizada das transações operacionais do Vyco
    if not df_transacoes.empty:
        # Filtrar apenas receitas operacionais (valores positivos)
        receitas_operacionais = df_transacoes[df_transacoes['Valor (R$)'] > 0].copy()
        
        if not receitas_operacionais.empty:
            # Método 1: Por centro de custo definido
            if 'centro_custo' in receitas_operacionais.columns:
                receitas_com_centro = receitas_operacionais[
                    receitas_operacionais['centro_custo'].notna() & 
                    (receitas_operacionais['centro_custo'] != '') &
                    (receitas_operacionais['centro_custo'].str.strip() != '')
                ]
                
                if not receitas_com_centro.empty:
                    receitas_por_centro = receitas_com_centro.groupby('centro_custo')['Valor (R$)'].sum()
                    
                    for centro_custo, valor in receitas_por_centro.items():
                        if centro_custo in receitas_cultura:
                            receitas_cultura[centro_custo]['receita_realizada'] += valor
                            receitas_cultura[centro_custo]['metodo_calculo_receita'] = 'Vyco - Por centro de custo'
                
                # Método 2: Rateio proporcional por hectares para receitas sem centro de custo
                receitas_sem_centro = receitas_operacionais[
                    receitas_operacionais['centro_custo'].isna() | 
                    (receitas_operacionais['centro_custo'] == '') |
                    (receitas_operacionais['centro_custo'].str.strip() == '')
                ]
                
                if not receitas_sem_centro.empty and receitas_cultura:
                    valor_total_sem_centro = receitas_sem_centro['Valor (R$)'].sum()
                    total_hectares = sum(r['hectares'] for r in receitas_cultura.values())
                    
                    if total_hectares > 0:
                        for cultura in receitas_cultura:
                            proporcao = receitas_cultura[cultura]['hectares'] / total_hectares
                            valor_rateado = valor_total_sem_centro * proporcao
                            receitas_cultura[cultura]['receita_realizada'] += valor_rateado
                            
                            # Atualizar método se houve rateio
                            if valor_rateado > 0:
                                metodo_atual = receitas_cultura[cultura]['metodo_calculo_receita']
                                if 'Vyco' not in metodo_atual:
                                    receitas_cultura[cultura]['metodo_calculo_receita'] = 'Vyco - Rateio por hectares'
                                else:
                                    receitas_cultura[cultura]['metodo_calculo_receita'] += ' + Rateio por hectares'
            
            else:
                # Se não há coluna centro_custo, ratear tudo por hectares
                valor_total_receitas = receitas_operacionais['Valor (R$)'].sum()
                total_hectares = sum(r['hectares'] for r in receitas_cultura.values())
                
                if total_hectares > 0:
                    for cultura in receitas_cultura:
                        proporcao = receitas_cultura[cultura]['hectares'] / total_hectares
                        receitas_cultura[cultura]['receita_realizada'] = valor_total_receitas * proporcao
                        receitas_cultura[cultura]['metodo_calculo_receita'] = 'Vyco - Rateio por hectares'
    
    return receitas_cultura

def calcular_custo_por_cultura(dados_plantio: Dict, df_transacoes: pd.DataFrame) -> Dict:
    """
    Calcula custos por cultura baseado nas transações do Vyco com separação por grupos
    
    Metodologia:
    1. Custos Diretos: Despesas dos grupos "Despesas Operacionais" e "Despesas RH"
       - Se tem centro de custo: atribuído diretamente à cultura
       - Se não tem: rateado proporcionalmente por hectares
    2. Custos Administrativos: Demais despesas (outros grupos ou sem grupo)
       - Sempre rateados proporcionalmente por hectares
    3. Custo Total: Soma dos custos diretos + administrativos
    """
    custos_cultura = {}
    
    # Inicializar custos por cultura baseado nos plantios
    for plantio in dados_plantio.values():
        if not plantio.get('ativo', True):
            continue
            
        cultura = plantio.get('cultura', 'Outros')
        if cultura not in custos_cultura:
            custos_cultura[cultura] = {
                'custo_direto': 0,
                'custo_administrativo': 0,
                'custo_total': 0,
                'hectares': plantio.get('hectares', 0),
                'metodo_calculo_custo_direto': 'Nenhum custo direto identificado',
                'metodo_calculo_custo_admin': 'Rateio por hectares',
                'percentual_rateio_admin': 0,
                'percentual_rateio_direto': 0
            }
    
    if df_transacoes.empty:
        return custos_cultura
    
    # Grupos que são considerados custos diretos operacionais
    grupos_custo_direto = ['Despesas Operacionais', 'Despesas RH']
    
    # Filtrar apenas despesas (valores negativos)
    despesas_total = df_transacoes[df_transacoes['Valor (R$)'] < 0].copy()
    
    if despesas_total.empty:
        return custos_cultura
    
    # 1. CUSTOS DIRETOS (Despesas Operacionais + RH)
    # Verificar se existe coluna de grupo
    if 'Grupo' in despesas_total.columns:
        despesas_diretas = despesas_total[
            despesas_total['Grupo'].isin(grupos_custo_direto)
        ]
    else:
        # Se não há coluna Grupo, considerar todas as despesas como diretas inicialmente
        despesas_diretas = despesas_total.copy()
    
    if not despesas_diretas.empty:
        # 1a. Custos diretos com centro de custo específico
        despesas_diretas_com_centro = despesas_diretas[
            (despesas_diretas['centro_custo'].notna()) &
            (despesas_diretas['centro_custo'] != '') &
            (despesas_diretas['centro_custo'].str.strip() != '')
        ]
        
        if not despesas_diretas_com_centro.empty:
            custos_diretos_por_centro = despesas_diretas_com_centro.groupby('centro_custo')['Valor (R$)'].sum()
            
            for centro_custo, valor in custos_diretos_por_centro.items():
                if centro_custo in custos_cultura:
                    custos_cultura[centro_custo]['custo_direto'] += abs(valor)
                    custos_cultura[centro_custo]['metodo_calculo_custo_direto'] = 'Vyco - Despesas Operacionais/RH por centro de custo'
        
        # 1b. Custos diretos sem centro de custo - ratear por hectares
        despesas_diretas_sem_centro = despesas_diretas[
            (despesas_diretas['centro_custo'].isna()) |
            (despesas_diretas['centro_custo'] == '') |
            (despesas_diretas['centro_custo'].str.strip() == '')
        ]
        
        if not despesas_diretas_sem_centro.empty and custos_cultura:
            valor_direto_sem_centro = abs(despesas_diretas_sem_centro['Valor (R$)'].sum())
            total_hectares = sum(c['hectares'] for c in custos_cultura.values())
            
            if total_hectares > 0:
                for cultura, dados in custos_cultura.items():
                    percentual_rateio = dados['hectares'] / total_hectares
                    valor_rateado = valor_direto_sem_centro * percentual_rateio
                    dados['custo_direto'] += valor_rateado
                    dados['percentual_rateio_direto'] = percentual_rateio * 100
                    
                    # Atualizar método
                    if dados['custo_direto'] > valor_rateado:
                        dados['metodo_calculo_custo_direto'] += f' + Rateio Operacional/RH ({percentual_rateio*100:.1f}%)'
                    else:
                        dados['metodo_calculo_custo_direto'] = f'Vyco - Rateio Despesas Operacionais/RH ({percentual_rateio*100:.1f}%)'
    
    # 2. CUSTOS ADMINISTRATIVOS (demais despesas)
    if 'Grupo' in despesas_total.columns:
        despesas_administrativas = despesas_total[
            ~despesas_total['Grupo'].isin(grupos_custo_direto) |
            despesas_total['Grupo'].isna()
        ]
    else:
        # Se não há coluna Grupo, considerar despesas sem centro de custo como administrativas
        despesas_administrativas = despesas_total[
            (despesas_total['centro_custo'].isna()) |
            (despesas_total['centro_custo'] == '') |
            (despesas_total['centro_custo'].str.strip() == '')
        ]
    
    if not despesas_administrativas.empty and custos_cultura:
        custos_admin_total = abs(despesas_administrativas['Valor (R$)'].sum())
        total_hectares = sum(c['hectares'] for c in custos_cultura.values())
        
        if total_hectares > 0:
            for cultura, dados in custos_cultura.items():
                percentual_rateio = dados['hectares'] / total_hectares
                dados['custo_administrativo'] = custos_admin_total * percentual_rateio
                dados['percentual_rateio_admin'] = percentual_rateio * 100
                dados['metodo_calculo_custo_admin'] = f'Rateio despesas administrativas ({percentual_rateio*100:.1f}%)'
    
    # 4. Calcular custo total e finalizar
    for cultura, dados in custos_cultura.items():
        dados['custo_total'] = dados['custo_direto'] + dados['custo_administrativo']
        
        # Se não teve custo direto, ajustar a descrição
        if dados['custo_direto'] == 0:
            dados['metodo_calculo_custo_direto'] = 'Nenhum custo direto identificado no Vyco'
    
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

def exibir_metodologia_calculos():
    """
    Exibe a metodologia de cálculo para o usuário
    """
    with st.expander("📚 Metodologia de Cálculos", expanded=False):
        st.markdown("""
        ### 💰 **Receita Realizada**
        
        **Fonte:** Transações operacionais (valores positivos) da integração Vyco
        
        **Métodos de cálculo:**
        1. **Por Centro de Custo:** Quando a transação tem centro de custo definido, é atribuída diretamente à cultura correspondente
        2. **Rateio por Hectares:** Quando não há centro de custo, o valor é distribuído proporcionalmente pelos hectares de cada cultura
        
        **Fórmula do Rateio:**
        ```
        Valor da Cultura = Valor Total × (Hectares da Cultura / Total de Hectares)
        ```
        
        ---
        
        ### 💸 **Custos por Cultura**
        
        **Fonte:** Transações de despesas (valores negativos) da integração Vyco
        
        #### **1. Custos Diretos Operacionais:**
        **Grupos incluídos:** "Despesas Operacionais" e "Despesas RH"
        
        **Método A:** Com centro de custo definido
        - Atribuídos diretamente à cultura do centro de custo
        
        **Método B:** Sem centro de custo definido
        - Rateados proporcionalmente pelos hectares de cada cultura
        
        **Fórmula do Rateio Direto:**
        ```
        Custo Direto da Cultura = Custo Operacional/RH × (Hectares da Cultura / Total de Hectares)
        ```
        
        #### **2. Custos Administrativos:**
        **Grupos incluídos:** Todos os demais grupos ou despesas sem grupo
        - Sempre rateados proporcionalmente pelos hectares de cada cultura
        
        **Fórmula do Rateio Administrativo:**
        ```
        Custo Admin da Cultura = Custo Admin Total × (Hectares da Cultura / Total de Hectares)
        ```
        
        #### **3. Custo Total:**
        ```
        Custo Total = Custos Diretos + Custos Administrativos
        ```
        
        ---
        
        ### 📊 **Indicadores Calculados**
        
        - **Margem Bruta:** Receita Total - Custo Total
        - **Margem %:** (Margem Bruta / Receita Total) × 100
        - **Receita/ha:** Receita Total / Hectares
        - **Custo/ha:** Custo Total / Hectares  
        - **Custo/saca:** Custo Total / Sacas Estimadas
        """)

def interface_analise_por_cultura():
    """
    Interface principal para análise financeira por cultura
    """
    st.subheader("📊 Análise Financeira por Cultura")
    
    # Exibir metodologia de cálculo
    exibir_metodologia_calculos()
    
    # Verificar se há dados necessários
    if 'plantios_agro' not in st.session_state or not st.session_state['plantios_agro']:
        st.warning("📋 Cadastre plantios primeiro para visualizar a análise por cultura.")
        return
    
    if 'df_transacoes_total_vyco' not in st.session_state:
        st.warning("� Integre dados do Vyco primeiro para análise completa.")
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
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📈 Receitas**")
                st.metric("Receita Estimada", formatar_valor_br(receita_data.get('receita_estimada', 0)))
                st.metric("Receita Realizada", formatar_valor_br(receita_data.get('receita_realizada', 0)))
                
                # Mostrar método de cálculo da receita
                metodo_receita = receita_data.get('metodo_calculo_receita', 'Estimativa de plantio')
                st.info(f"**Método:** {metodo_receita}")
                
                st.metric("Hectares", f"{receita_data.get('hectares', 0):,.1f} ha".replace(",", ".").replace(".", ",", 1))
                st.metric("Sacas Estimadas", f"{receita_data.get('sacas_estimadas', 0):,.0f}".replace(",", "."))
            
            with col2:
                st.markdown("**📉 Custos**")
                
                # Custo Direto com detalhes
                custo_direto = custo_data.get('custo_direto', 0)
                st.metric("Custo Direto (Operacional + RH)", formatar_valor_br(custo_direto))
                
                # Mostrar método de cálculo do custo direto
                metodo_direto = custo_data.get('metodo_calculo_custo_direto', 'Nenhum custo identificado')
                st.info(f"**Método Direto:** {metodo_direto}")
                
                # Mostrar percentual de rateio direto se houver
                perc_rateio_direto = custo_data.get('percentual_rateio_direto', 0)
                if perc_rateio_direto > 0:
                    st.caption(f"💡 Rateio direto: {perc_rateio_direto:.1f}% dos custos operacionais sem centro de custo")
                
                # Custo Administrativo
                st.metric("Custo Administrativo", formatar_valor_br(custo_data.get('custo_administrativo', 0)))
                
                # Mostrar método de cálculo administrativo
                metodo_admin = custo_data.get('metodo_calculo_custo_admin', 'Rateio por hectares')
                st.info(f"**Método Admin:** {metodo_admin}")
                
                st.metric("Custo Total", formatar_valor_br(custo_data.get('custo_total', 0)))

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