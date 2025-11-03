import streamlit as st
import pandas as pd
import sys
import os
import time

# Adicionar o diretório raiz ao path para importações
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.business_types.business_manager import (
    verificar_modo_agro, 
    ativar_modo_agro,
    carregar_template_negocio,
    obter_centros_custo
)
from logic.business_types.agro.utils import formatar_valor_br, formatar_valor_simples_br

# Funções auxiliares para formatação
def formatar_hectares_br(valor):
    """Formatar hectares no padrão brasileiro"""
    try:
        valor_num = float(valor) if not isinstance(valor, (int, float)) else valor
        return f"{valor_num:,.2f} ha".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00 ha"

def formatar_produtividade_br(valor):
    """Formatar produtividade no padrão brasileiro"""
    try:
        valor_num = float(valor) if not isinstance(valor, (int, float)) else valor
        return f"{valor_num:,.2f} sacas/ha".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00 sacas/ha"
from logic.business_types.agro.plantio_manager import (
    interface_cadastro_plantio,
    interface_lista_plantios,
    interface_resumo_por_cultura,
    salvar_dados_plantio,
    carregar_dados_plantio,
    calcular_totais_plantio,
    auto_carregar_dados_plantio,
    auto_salvar_dados_plantio,
    obter_estatisticas_licenca,
    listar_licencas_com_dados
)
from logic.business_types.agro.culturas_financeiro import (
    interface_analise_por_cultura,
    calcular_receita_por_cultura,
    calcular_custo_por_cultura,
    calcular_indicadores_por_cultura,
    exportar_analise_cultura
)

# Novo sistema de análise por hectares
from logic.business_types.agro.analisador_hectares import interface_principal_agro

# Sistema de consultoria avançada
from logic.business_types.agro.consultor_financeiro_agro import interface_principal as interface_consultoria

# Importar gerenciador de cache
from logic.data_cache_manager import cache_manager

# Configuração da página
st.set_page_config(page_title="Gestão Agronegócio", layout="wide")

def verificar_prerrequisitos():
    """
    Verifica se os pré-requisitos para o módulo agro estão atendidos
    """
    # Importar cache manager
    from logic.data_cache_manager import cache_manager
    
    # Verificar se existem empresas com dados no cache
    empresas_disponiveis = cache_manager.listar_empresas_disponiveis()
    
    if not empresas_disponiveis:
        st.warning("⚠️ Nenhuma empresa com dados DRE/Fluxo encontrada no cache.")
        st.info("🔄 **Para usar este módulo:**")
        st.info("1. Importe dados DRE/Fluxo de Caixa de alguma empresa")
        st.info("2. Os dados serão salvos automaticamente no cache")
        st.info("3. Retorne a esta página para usar a Análise por Cultura")
        return False
    
    # Verificar se está no modo agro (opcional, mas recomendado)
    if not verificar_modo_agro():
        st.info("💡 **Dica:** Configure o tipo de negócio como 'Agronegócio' para funcionalidades completas.")
    
    return True

def interface_configuracao_agro():
    """
    Interface para configurações específicas do agronegócio
    """
    st.sidebar.header("⚙️ Configurações Agro")
    
    # Status dos dados
    st.sidebar.markdown("### 📊 Status dos Dados")
    
    # Verificar dados DRE no cache
    empresas_cache = cache_manager.listar_empresas_disponiveis()
    if empresas_cache:
        st.sidebar.success(f"✅ DRE Cache: {len(empresas_cache)} empresa(s)")
        for emp in empresas_cache:
            st.sidebar.caption(f"📋 {emp['nome']}")
    else:
        st.sidebar.error("❌ Nenhum DRE no cache")
    
    # Verificar dados de plantio
    licencas_plantio = listar_licencas_com_dados()
    if licencas_plantio:
        st.sidebar.success(f"✅ Plantios: {len(licencas_plantio)} licença(s)")
    else:
        st.sidebar.warning("⚠️ Nenhum plantio cadastrado")
    
    st.sidebar.markdown("---")
    
    # Verificar licença atual
    licenca_atual = st.session_state.get('licenca_atual', 'Não definida')
    
    if licenca_atual != 'Não definida':
        # Auto-carregar dados da licença
        auto_carregar_dados_plantio(licenca_atual)
        
        # Obter estatísticas da licença
        stats = obter_estatisticas_licenca(licenca_atual)
        
        st.sidebar.success(f"📄 **Licença Ativa:** {licenca_atual}")
        
        # Mostrar estatísticas
        with st.sidebar.expander("📊 Dados Salvos", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Plantios", stats.get('total_plantios', 0))
            with col2:
                st.metric("Hectares", formatar_hectares_br(stats.get('total_hectares', 0)))
            
            if stats.get('culturas'):
                st.write("**Culturas:**")
                for cultura in stats.get('culturas', []):
                    if cultura:  # Não mostrar culturas vazias
                        st.write(f"• {cultura}")
            
            ultima_atualizacao = stats.get('ultima_atualizacao', 'Nunca')
            if ultima_atualizacao != 'Nunca':
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(ultima_atualizacao.replace('Z', '+00:00'))
                    st.caption(f"Última atualização: {dt.strftime('%d/%m/%Y %H:%M')}")
                except:
                    st.caption(f"Última atualização: {ultima_atualizacao}")
        
        # Indicador de salvamento automático
        if st.session_state.get('dados_salvos_automaticamente'):
            st.sidebar.success("💾 Auto-salvamento ativo")
    else:
        st.sidebar.warning("⚠️ **Licença não definida**")
        st.sidebar.info("Configure a licença primeiro.")
    
    # Botões de ação manual (para casos específicos)
    with st.sidebar.expander("🔧 Ações Manuais"):
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("� Salvar", help="Salvar manualmente"):
                if licenca_atual != 'Não definida':
                    if salvar_dados_plantio(licenca_atual):
                        st.success("✅ Salvo!")
                    else:
                        st.error("❌ Erro")
                else:
                    st.error("❌ Sem licença")
        
        with col2:
            if st.button("🔄 Recarregar", help="Recarregar dados"):
                if licenca_atual != 'Não definida':
                    # Forçar recarregamento
                    st.session_state.pop('licenca_plantio_carregada', None)
                    auto_carregar_dados_plantio(licenca_atual)
                    st.rerun()
                else:
                    st.error("❌ Sem licença")
    
    # Lista de todas as licenças com dados
    with st.sidebar.expander("📋 Licenças com Dados Salvos"):
        licencas_com_dados = listar_licencas_com_dados()
        
        if licencas_com_dados:
            for licenca in licencas_com_dados:
                with st.container():
                    st.write(f"**{licenca['nome']}**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption(f"🌾 {licenca['plantios']} plantios")
                        st.caption(f"📏 {formatar_hectares_br(licenca['hectares'])}")
                    with col2:
                        st.caption(f"🌱 {licenca['culturas']} culturas")
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(licenca['ultima_atualizacao'].replace('Z', '+00:00'))
                            st.caption(f"📅 {dt.strftime('%d/%m')}")
                        except:
                            st.caption(f"📅 {licenca['ultima_atualizacao'][:10] if len(licenca['ultima_atualizacao']) > 10 else licenca['ultima_atualizacao']}")
                    st.markdown("---")
        else:
            st.info("Nenhuma licença com dados de plantio encontrada.")
    
    # Mostrar template de referência
    with st.sidebar.expander("⚙️ Configurações do Template"):
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
        2. **Importe dados financeiros** (DRE/Fluxo de Caixa)
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
            formatar_hectares_br(totais['total_hectares']),
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
            formatar_valor_br(totais['receita_total_estimada']),
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
            # Usar timestamp único para evitar conflitos de chave
            key_hectares = f"grafico_hectares_{int(time.time() * 1000) % 100000}"
            st.plotly_chart(fig_hectares, use_container_width=True, key=key_hectares)
        
        with col_grafico2:
            # Gráfico de barras - Receita
            fig_receita = px.bar(
                x=culturas,
                y=receitas,
                title="Receita Estimada por Cultura",
                labels={'x': 'Cultura', 'y': 'Receita (R$)'}
            )
            # Usar timestamp único para evitar conflitos de chave
            key_receita = f"grafico_receita_{int(time.time() * 1000) % 100000}"
            st.plotly_chart(fig_receita, use_container_width=True, key=key_receita)

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
        st.metric("💰 Receita por Hectare", f"{formatar_valor_br(receita_ha)}/ha")
        
        custo_ha = total_custo / total_hectares if total_hectares > 0 else 0
        st.metric("💸 Custo por Hectare", f"{formatar_valor_br(custo_ha)}/ha")
    
    with col2:
        margem_ha = (total_receita - total_custo) / total_hectares if total_hectares > 0 else 0
        st.metric("📊 Margem por Hectare", f"{formatar_valor_br(margem_ha)}/ha")
        
        custo_saca = total_custo / total_sacas if total_sacas > 0 else 0
        st.metric("🌾 Custo por Saca", f"{formatar_valor_br(custo_saca)}/saca")
    
    with col3:
        margem_percent = ((total_receita - total_custo) / total_receita * 100) if total_receita > 0 else 0
        st.metric("📈 Margem Percentual", f"{margem_percent:.1f}%".replace(".", ","))
        
        # Break-even simplificado
        if total_receita > 0 and total_hectares > 0:
            preco_medio = total_receita / total_sacas if total_sacas > 0 else 0
            break_even = (total_custo / total_hectares / preco_medio) if preco_medio > 0 else 0
            st.metric("⚖️ Break-Even Yield", f"{break_even:.1f} sacas/ha")

def main():
    """
    Função principal da página de gestão agronegócio
    """
    st.title("🌾 Gestão Agronegócio")
    st.markdown("### Sistema integrado de análise financeira para propriedades rurais")
    
    # Indicador de fonte dos dados
    st.success("🔄 **INTEGRAÇÃO AUTOMÁTICA:** Dados financeiros extraídos do DRE via Integração Vyco + Dados operacionais de plantios")
    
    # Verificar pré-requisitos
    if not verificar_prerrequisitos():
        return
    
    # Interface de configuração na sidebar
    interface_configuracao_agro()
    
    # Tabs principais
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🏠 Dashboard",
        "🌱 Cadastro Plantio", 
        "📊 Análise por Hectares", 
        "🎯 Consultoria Avançada",
        "� Comparação Temporal",
        "⚙️ Configurações"
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
        # Novo sistema de análise por rateio de hectares
        interface_principal_agro()
    
    with tab4:
        # Sistema de consultoria avançada
        interface_consultoria()
    
    with tab5:
        interface_comparacao_temporal()
    
    with tab6:
        interface_configuracoes_agro()

def interface_comparacao_temporal():
    """Interface para comparação temporal de análises"""
    try:
        from logic.business_types.agro.comparador_temporal import ComparadorTemporalAgro
    except ImportError:
        st.error("❌ Módulo de comparação temporal não disponível")
        return
    
    st.title("📈 Comparação Temporal - Evolução da Propriedade")
    st.caption("💾 Compare análises salvas ao longo do tempo para acompanhar a evolução")
    
    comparador = ComparadorTemporalAgro()
    
    # Verificar se existem análises salvas
    historico = comparador.listar_analises_disponiveis()
    
    if not historico:
        st.warning("📝 Nenhuma análise salva encontrada!")
        st.info("""
        **Como começar:**
        1. Vá para a aba 'Consultoria Avançada'
        2. Faça uma análise completa
        3. Clique em 'Salvar Esta Análise no Histórico'
        4. Retorne aqui para comparar análises futuras
        """)
        return
    
    st.success(f"📊 **{len(historico)} análises** encontradas no histórico")
    
    # Seção 1: Visualizar histórico
    with st.expander("📋 Ver Histórico de Análises", expanded=True):
        for analise in historico:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            with col1:
                st.write(f"**{analise['metadata']['empresa']}**")
                st.caption(f"Data: {analise['metadata']['data_analise']}")
            with col2:
                receita = analise['dados_dre']['resumo_dre']['total_receitas']
                st.metric("Receita", f"R$ {receita:,.0f}".replace(",", "."))
            with col3:
                resultado = analise['dados_dre']['resumo_dre']['resultado_liquido']
                st.metric("Resultado", f"R$ {resultado:,.0f}".replace(",", "."))
            with col4:
                if st.button("🔍", key=f"ver_{analise['id']}", help="Ver detalhes"):
                    st.session_state[f'detalhes_{analise["id"]}'] = True
            
            # Mostrar detalhes se solicitado
            if st.session_state.get(f'detalhes_{analise["id"]}', False):
                st.markdown("---")
                st.write("**Questionário da época:**")
                for pergunta, resposta in analise['respostas_questionario'].items():
                    st.write(f"• {pergunta}: {resposta}")
                st.markdown("---")
    
    # Seção 2: Comparar duas análises
    st.markdown("## 🔄 Comparação Entre Períodos")
    
    col1, col2 = st.columns(2)
    with col1:
        opcoes_periodo1 = [f"{a['metadata']['data_analise']} - {a['metadata']['empresa']}" for a in historico]
        periodo1 = st.selectbox("📅 Selecione o primeiro período:", opcoes_periodo1, key="periodo1")
    
    with col2:
        opcoes_periodo2 = [f"{a['metadata']['data_analise']} - {a['metadata']['empresa']}" for a in historico]
        periodo2 = st.selectbox("📅 Selecione o segundo período:", opcoes_periodo2, key="periodo2")
    
    if periodo1 and periodo2 and periodo1 != periodo2:
        if st.button("🔍 Gerar Comparação Detalhada", type="primary"):
            with st.spinner("📊 Analisando evolução..."):
                # Encontrar as análises correspondentes
                analise1 = next(a for a in historico if f"{a['metadata']['data_analise']} - {a['metadata']['empresa']}" == periodo1)
                analise2 = next(a for a in historico if f"{a['metadata']['data_analise']} - {a['metadata']['empresa']}" == periodo2)
                
                # Gerar comparação (passando os objetos completos)
                resultado_comparacao = comparador.comparar_analises(analise1, analise2)
                
                if resultado_comparacao:
                    st.markdown("---")
                    st.subheader("📈 **RELATÓRIO DE EVOLUÇÃO**")
                    
                    # Métricas de evolução
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        score = resultado_comparacao['score_evolucao']
                        cor = "🟢" if score > 0 else "🔴" if score < 0 else "🟡"
                        st.metric(
                            "Score de Evolução",
                            f"{score:+.1f}",
                            delta=f"{cor} {'Melhoria' if score > 0 else 'Piora' if score < 0 else 'Estável'}"
                        )
                    
                    with col2:
                        delta_receita = resultado_comparacao['deltas']['total_receitas']
                        st.metric(
                            "Evolução Receita",
                            f"R$ {delta_receita:,.0f}".replace(",", "."),
                            delta=f"{(delta_receita/analise1['dados_dre']['resumo_dre']['total_receitas'])*100:+.1f}%"
                        )
                    
                    with col3:
                        delta_resultado = resultado_comparacao['deltas']['resultado_liquido']
                        st.metric(
                            "Evolução Resultado",
                            f"R$ {delta_resultado:,.0f}".replace(",", "."),
                            delta=f"{(delta_resultado/abs(analise1['dados_dre']['resumo_dre']['resultado_liquido']) if analise1['dados_dre']['resumo_dre']['resultado_liquido'] != 0 else 1)*100:+.1f}%"
                        )
                    
                    # Parecer de evolução
                    st.markdown("### 📋 Parecer de Evolução")
                    st.markdown(resultado_comparacao['parecer_evolucao'])
                    
                    # Principais mudanças
                    st.markdown("### 🔍 Principais Mudanças Identificadas")
                    for categoria, mudancas in resultado_comparacao['principais_mudancas'].items():
                        if mudancas:
                            st.write(f"**{categoria.title()}:**")
                            for mudanca in mudancas:
                                st.write(f"• {mudanca}")

def interface_configuracoes_agro():
    """Interface para configurações do sistema agro"""
    st.title("⚙️ Configurações do Sistema Agro")
    
    st.markdown("### 🔧 Cache e Performance")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Limpar Cache de Análises", help="Remove todas as análises salvas"):
            try:
                from logic.business_types.agro.comparador_temporal import ComparadorTemporalAgro
                comparador = ComparadorTemporalAgro()
                if comparador.limpar_historico():
                    st.success("✅ Cache de análises limpo com sucesso!")
                else:
                    st.error("❌ Erro ao limpar cache")
            except ImportError:
                st.error("❌ Módulo de comparação temporal não disponível")
    
    with col2:
        if st.button("📊 Estatísticas do Sistema"):
            try:
                from logic.business_types.agro.comparador_temporal import ComparadorTemporalAgro
                comparador = ComparadorTemporalAgro()
                historico = comparador.listar_analises_disponiveis()
                
                st.metric("Análises Salvas", len(historico))
                if historico:
                    empresas_unicas = len(set(a['metadata']['empresa'] for a in historico))
                    st.metric("Empresas Analisadas", empresas_unicas)
            except ImportError:
                st.error("❌ Módulo de comparação temporal não disponível")
    
    st.markdown("### 📋 Sobre o Sistema")
    st.info("""
    **Sistema de Gestão Agro v2.0**
    
    ✅ Análise por hectares com rateio proporcional
    ✅ Consultoria avançada com questionário estratégico  
    ✅ Comparação temporal para tracking de evolução
    ✅ Cache otimizado com indicadores visuais de fonte
    ✅ Interface profissional com métricas executivas
    """)

if __name__ == "__main__":
    main()