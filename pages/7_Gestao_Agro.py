import streamlit as st
import pandas as pd
import sys
import os

# Adicionar o diretório raiz ao path para importações
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.business_types.business_manager import (
    verificar_modo_agro, 
    ativar_modo_agro,
    carregar_template_negocio,
    obter_centros_custo
)
from logic.business_types.agro.plantio_manager import (
    interface_cadastro_plantio,
    interface_lista_plantios,
    interface_resumo_por_cultura,
    salvar_dados_plantio,
    carregar_dados_plantio,
    calcular_totais_plantio
)
from logic.business_types.agro.culturas_financeiro import (
    interface_analise_por_cultura,
    calcular_receita_por_cultura,
    calcular_custo_por_cultura,
    calcular_indicadores_por_cultura,
    exportar_analise_cultura
)

# Configuração da página
st.set_page_config(page_title="Gestão Agronegócio", layout="wide")

def verificar_prerrequisitos():
    """
    Verifica se os pré-requisitos para o módulo agro estão atendidos
    """
    # Verificar se está no modo agro
    if not verificar_modo_agro():
        st.warning("⚠️ Esta página só está disponível quando o tipo de negócio é 'Agronegócio'.")
        st.info("Configure o tipo de negócio na página **Integração Vyco** primeiro.")
        return False
    
    return True

def interface_configuracao_agro():
    """
    Interface para configurações específicas do agronegócio
    """
    st.sidebar.header("⚙️ Configurações Agro")
    
    # Verificar licença atual
    licenca_atual = st.session_state.get('licenca_atual', 'Não definida')
    st.sidebar.info(f"📄 **Licença:** {licenca_atual}")
    
    # Botões de ação
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("💾 Salvar Dados", help="Salvar dados de plantio"):
            if licenca_atual != 'Não definida':
                if salvar_dados_plantio(licenca_atual):
                    st.success("✅ Dados salvos com sucesso!")
                else:
                    st.error("❌ Erro ao salvar dados")
            else:
                st.error("❌ Licença não definida")
    
    with col2:
        if st.button("📥 Carregar Dados", help="Carregar dados salvos"):
            if licenca_atual != 'Não definida':
                if carregar_dados_plantio(licenca_atual):
                    st.success("✅ Dados carregados!")
                    st.rerun()
                else:
                    st.info("ℹ️ Nenhum dado salvo encontrado")
            else:
                st.error("❌ Licença não definida")
    
    # Mostrar template de referência
    with st.sidebar.expander("📋 Configurações do Template"):
        template = carregar_template_negocio("agro")
        if template:
            st.json({
                "Centros de Custo": template.get("centros_custo_padrao", []),
                "Culturas Disponíveis": list(template.get("metricas_producao", {}).get("produtividade_media", {}).keys()),
                "Indicadores": [ind["nome"] for ind in template.get("indicadores_especificos", [])]
            })

def interface_dashboard_agro():
    """
    Dashboard principal do módulo agronegócio
    """
    st.title("🌾 Gestão Agronegócio - Análise Financeira")
    st.markdown("---")
    
    # Verificar se há dados de plantio
    if 'plantios_agro' not in st.session_state or not st.session_state['plantios_agro']:
        st.info("📋 **Bem-vindo ao módulo de Agronegócio!**")
        st.markdown("""
        ### 🚀 Para começar:
        1. **Cadastre seus plantios** na aba "Cadastro Plantio"
        2. **Importe dados financeiros** na página "Integração Vyco"
        3. **Analise os resultados** por cultura nas demais abas
        """)
        return
    
    # Dashboard com métricas principais
    totais = calcular_totais_plantio()
    
    st.subheader("📊 Resumo Operacional")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "🌾 Total Hectares", 
            f"{totais['total_hectares']:,.1f} ha",
            help="Área total plantada"
        )
    
    with col2:
        st.metric(
            "📦 Total Sacas", 
            f"{totais['total_sacas']:,.0f}",
            help="Produção estimada total"
        )
    
    with col3:
        st.metric(
            "💰 Receita Estimada", 
            f"R$ {totais['receita_total_estimada']:,.2f}",
            help="Receita bruta estimada"
        )
    
    with col4:
        st.metric(
            "🌱 Plantios Ativos", 
            totais['numero_plantios'],
            help="Número de plantios cadastrados"
        )
    
    # Gráfico de distribuição por cultura
    if totais['hectares_por_cultura']:
        st.subheader("📈 Distribuição por Cultura")
        
        import plotly.express as px
        
        # Preparar dados para o gráfico
        culturas = list(totais['hectares_por_cultura'].keys())
        hectares = list(totais['hectares_por_cultura'].values())
        receitas = list(totais['receita_por_cultura'].values())
        
        col_grafico1, col_grafico2 = st.columns(2)
        
        with col_grafico1:
            # Gráfico de pizza - Hectares
            fig_hectares = px.pie(
                values=hectares,
                names=culturas,
                title="Distribuição de Hectares por Cultura"
            )
            st.plotly_chart(fig_hectares, use_container_width=True)
        
        with col_grafico2:
            # Gráfico de barras - Receita
            fig_receita = px.bar(
                x=culturas,
                y=receitas,
                title="Receita Estimada por Cultura",
                labels={'x': 'Cultura', 'y': 'Receita (R$)'}
            )
            st.plotly_chart(fig_receita, use_container_width=True)

def interface_cenarios_agro():
    """
    Interface para análise de cenários específicos do agronegócio
    """
    st.subheader("🎯 Cenários Agronegócio")
    
    # Verificar se há dados
    if 'plantios_agro' not in st.session_state or not st.session_state['plantios_agro']:
        st.warning("📋 Cadastre plantios primeiro para análise de cenários.")
        return
    
    # Carregar template com cenários padrão
    template = carregar_template_negocio("agro")
    if not template:
        st.error("❌ Erro ao carregar template do agronegócio")
        return
    
    cenarios_padrao = template.get("cenarios_padrao", {})
    
    st.markdown("""
    ### 📊 Análise de Cenários
    Simule diferentes condições climáticas e de mercado para avaliar o impacto na rentabilidade.
    """)
    
    # Seleção de cenário
    nome_cenarios = list(cenarios_padrao.keys())
    cenario_selecionado = st.selectbox(
        "Selecione o cenário:",
        nome_cenarios,
        format_func=lambda x: f"{x.title()} - {cenarios_padrao[x]['descricao']}"
    )
    
    if cenario_selecionado:
        cenario_config = cenarios_padrao[cenario_selecionado]
        
        # Mostrar configurações do cenário
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Ajuste Produtividade", 
                f"{cenario_config['ajuste_produtividade']:+d}%",
                help="Variação na produtividade esperada"
            )
        
        with col2:
            st.metric(
                "Ajuste Preço", 
                f"{cenario_config['ajuste_preco']:+d}%",
                help="Variação no preço de venda"
            )
        
        with col3:
            st.metric(
                "Ajuste Custo", 
                f"{cenario_config['ajuste_custo']:+d}%",
                help="Variação nos custos de produção"
            )
        
        # Aplicar cenário aos dados
        if st.button("🎯 Aplicar Cenário"):
            aplicar_cenario_plantios(cenario_config)
            st.success(f"✅ Cenário '{cenario_selecionado.title()}' aplicado!")
            st.rerun()

def aplicar_cenario_plantios(cenario_config: dict):
    """
    Aplica ajustes de cenário aos plantios cadastrados
    """
    if 'plantios_agro' not in st.session_state:
        return
    
    ajuste_prod = cenario_config.get('ajuste_produtividade', 0) / 100
    ajuste_preco = cenario_config.get('ajuste_preco', 0) / 100
    
    for plantio_id, plantio in st.session_state['plantios_agro'].items():
        if not plantio.get('ativo', True):
            continue
        
        # Salvar valores originais se ainda não foram salvos
        if 'valores_originais' not in plantio:
            plantio['valores_originais'] = {
                'sacas_por_hectare': plantio['sacas_por_hectare'],
                'preco_saca': plantio['preco_saca']
            }
        
        # Aplicar ajustes
        valores_orig = plantio['valores_originais']
        plantio['sacas_por_hectare'] = valores_orig['sacas_por_hectare'] * (1 + ajuste_prod)
        plantio['preco_saca'] = valores_orig['preco_saca'] * (1 + ajuste_preco)
        
        # Recalcular receita estimada
        plantio['receita_estimada'] = (
            plantio['hectares'] * 
            plantio['sacas_por_hectare'] * 
            plantio['preco_saca']
        )

def interface_indicadores_agro():
    """
    Interface para indicadores específicos do agronegócio
    """
    st.subheader("📈 Indicadores Agronegócio")
    
    # Verificar dados necessários
    if 'plantios_agro' not in st.session_state or not st.session_state['plantios_agro']:
        st.warning("📋 Cadastre plantios primeiro.")
        return
    
    # Carregar template com indicadores
    template = carregar_template_negocio("agro")
    if template and "indicadores_especificos" in template:
        indicadores_template = template["indicadores_especificos"]
        
        st.markdown("### 📊 Indicadores Disponíveis")
        
        for indicador in indicadores_template:
            with st.expander(f"📈 {indicador['nome']}"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"**Fórmula:** `{indicador['formula']}`")
                    st.markdown(f"**Interpretação:** {indicador['interpretacao']}")
                
                with col2:
                    st.markdown(f"**Unidade:** {indicador['unidade']}")
        
        # Calcular e exibir indicadores se houver dados financeiros
        if 'df_transacoes_total_vyco' in st.session_state:
            st.markdown("---")
            calcular_e_exibir_indicadores_agro()

def calcular_e_exibir_indicadores_agro():
    """
    Calcula e exibe indicadores específicos do agronegócio
    """
    dados_plantio = st.session_state['plantios_agro']
    df_transacoes = st.session_state.get('df_transacoes_total_vyco', pd.DataFrame())
    
    if df_transacoes.empty:
        st.info("💰 Importe dados financeiros para cálculo dos indicadores.")
        return
    
    # Calcular dados para indicadores
    receitas_cultura = calcular_receita_por_cultura(dados_plantio, df_transacoes)
    custos_cultura = calcular_custo_por_cultura(dados_plantio, df_transacoes)
    indicadores = calcular_indicadores_por_cultura(receitas_cultura, custos_cultura)
    
    if not indicadores:
        st.warning("⚠️ Não foi possível calcular indicadores com os dados disponíveis.")
        return
    
    st.subheader("🎯 Indicadores Calculados")
    
    # Indicadores consolidados
    total_receita = sum(ind['receita_total'] for ind in indicadores.values())
    total_custo = sum(ind['custo_total'] for ind in indicadores.values())
    total_hectares = sum(ind['hectares'] for ind in indicadores.values())
    total_sacas = sum(ind['sacas_estimadas'] for ind in indicadores.values())
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        receita_ha = total_receita / total_hectares if total_hectares > 0 else 0
        st.metric("💰 Receita por Hectare", f"R$ {receita_ha:,.2f}/ha")
        
        custo_ha = total_custo / total_hectares if total_hectares > 0 else 0
        st.metric("💸 Custo por Hectare", f"R$ {custo_ha:,.2f}/ha")
    
    with col2:
        margem_ha = (total_receita - total_custo) / total_hectares if total_hectares > 0 else 0
        st.metric("📊 Margem por Hectare", f"R$ {margem_ha:,.2f}/ha")
        
        custo_saca = total_custo / total_sacas if total_sacas > 0 else 0
        st.metric("🌾 Custo por Saca", f"R$ {custo_saca:.2f}/saca")
    
    with col3:
        margem_percent = ((total_receita - total_custo) / total_receita * 100) if total_receita > 0 else 0
        st.metric("📈 Margem Percentual", f"{margem_percent:.1f}%")
        
        # Break-even simplificado
        if total_receita > 0 and total_hectares > 0:
            preco_medio = total_receita / total_sacas if total_sacas > 0 else 0
            break_even = (total_custo / total_hectares / preco_medio) if preco_medio > 0 else 0
            st.metric("⚖️ Break-Even Yield", f"{break_even:.1f} sacas/ha")

def main():
    """
    Função principal da página de gestão agronegócio
    """
    # Verificar pré-requisitos
    if not verificar_prerrequisitos():
        return
    
    # Interface de configuração na sidebar
    interface_configuracao_agro()
    
    # Tabs principais
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏠 Dashboard",
        "🌱 Cadastro Plantio", 
        "📊 Análise por Cultura", 
        "🎯 Cenários",
        "📈 Indicadores"
    ])
    
    with tab1:
        interface_dashboard_agro()
    
    with tab2:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            interface_cadastro_plantio()
        
        with col2:
            interface_resumo_por_cultura()
            
        st.markdown("---")
        interface_lista_plantios()
    
    with tab3:
        interface_analise_por_cultura()
    
    with tab4:
        interface_cenarios_agro()
    
    with tab5:
        interface_indicadores_agro()

if __name__ == "__main__":
    main()