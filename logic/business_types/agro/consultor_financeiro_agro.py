#!/usr/bin/env python3
"""
SISTEMA DE ANÁLISE FINANCEIRA AGRO - VERSÃO CONSULTOR
Criado para coletar informações críticas e gerar análise profissional
"""

import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import os

class ConsultorFinanceiroAgro:
    """
    Sistema de consultoria financeira especializada em agronegócio
    """
    
    def __init__(self):
        self.questoes_criticas = {
            'safra': [
                "Em que estágio está a safra atual?",
                "Quando foi/será a colheita de cada cultura?",
                "Houve perdas por clima, pragas ou outros fatores?",
                "Qual % da produção já foi comercializada?"
            ],
            'receitas': [
                "As receitas do DRE incluem vendas de grãos ou outras fontes?",
                "Há contratos futuros ou vendas antecipadas?",
                "Existe receita de arrendamento ou outras atividades?",
                "Qual a origem das 'Receitas Extra Operacionais'?"
            ],
            'custos': [
                "As 'Despesas Extra Operacionais' (R$ 6,4M) se referem a quê?",
                "Há investimentos em máquinas/equipamentos no período?",
                "Os custos incluem sementes, defensivos, fertilizantes?",
                "Como são controlados os custos por cultura?"
            ],
            'operacional': [
                "Quantos hectares estão em produção atualmente?",
                "Há terras arrendadas ou próprias?",
                "Qual o ciclo de produção de cada cultura?",
                "Existe rotação de culturas ou cultivo simultâneo?"
            ],
            'mercado': [
                "Qual a estratégia de comercialização (spot, contratos, CPR)?",
                "Como está o preço atual vs planejado?",
                "Há financiamentos vinculados à produção?",
                "Existe seguro agrícola?"
            ]
        }
        
        self.indicadores_agro = {
            'produtividade': ['Sacas/ha', 'Comparação com média regional', 'Tendência histórica'],
            'rentabilidade': ['Margem por hectare', 'ROI por cultura', 'Ponto de equilíbrio'],
            'eficiencia': ['Custo por saca', 'Giro do ativo', 'Prazo médio de recebimento'],
            'risco': ['Concentração por cultura', 'Exposição cambial', 'Sazonalidade'],
            'sustentabilidade': ['Reinvestimento', 'Capacidade de pagamento', 'Crescimento']
        }

    def interface_questionario_inicial(self):
        """
        Interface para coletar informações críticas sobre a operação
        """
        st.title("🎯 Análise Financeira Agro - Questionário Consultoria")
        st.markdown("### Para uma análise precisa, preciso entender melhor sua operação:")
        
        # Verificar se já há respostas salvas
        if 'questionario_agro' not in st.session_state:
            st.session_state['questionario_agro'] = {}
        
        respostas = st.session_state['questionario_agro']
        
        # Seção 1: Situação da Safra
        with st.expander("🌾 1. SITUAÇÃO ATUAL DA SAFRA", expanded=True):
            st.markdown("**Entender o estágio operacional é crucial para interpretar os números financeiros**")
            
            respostas['estagio_safra'] = st.selectbox(
                "Em que estágio está a safra atual?",
                ["Pré-plantio", "Plantio", "Desenvolvimento", "Pré-colheita", "Colheita", "Pós-colheita", "Entre safras"],
                index=0 if 'estagio_safra' not in respostas else ["Pré-plantio", "Plantio", "Desenvolvimento", "Pré-colheita", "Colheita", "Pós-colheita", "Entre safras"].index(respostas['estagio_safra'])
            )
            
            respostas['comercializacao_realizada'] = st.slider(
                "Qual % da produção esperada já foi comercializada?",
                0, 100, 
                respostas.get('comercializacao_realizada', 0),
                help="Percentual já vendido da safra atual"
            )
            
            respostas['perdas_safra'] = st.selectbox(
                "Houve perdas significativas na safra?",
                ["Não", "Perdas menores (até 10%)", "Perdas moderadas (10-30%)", "Perdas severas (>30%)"],
                index=0 if 'perdas_safra' not in respostas else ["Não", "Perdas menores (até 10%)", "Perdas moderadas (10-30%)", "Perdas severas (>30%)"].index(respostas['perdas_safra'])
            )
        
        # Seção 2: Composição das Receitas
        with st.expander("💰 2. ORIGEM DAS RECEITAS", expanded=True):
            st.markdown("**Suas receitas do DRE (R$ 7.237.988) incluem:**")
            
            col1, col2 = st.columns(2)
            with col1:
                respostas['receita_vendas_graos'] = st.checkbox(
                    "Vendas de grãos/produtos agrícolas",
                    respostas.get('receita_vendas_graos', True)
                )
                respostas['receita_arrendamento'] = st.checkbox(
                    "Receitas de arrendamento",
                    respostas.get('receita_arrendamento', False)
                )
                respostas['receita_servicos'] = st.checkbox(
                    "Prestação de serviços agrícolas",
                    respostas.get('receita_servicos', False)
                )
            
            with col2:
                respostas['receita_cpr'] = st.checkbox(
                    "Adiantamentos (CPR, contratos)",
                    respostas.get('receita_cpr', False)
                )
                respostas['receita_financeira'] = st.checkbox(
                    "Receitas financeiras/aplicações",
                    respostas.get('receita_financeira', False)
                )
                respostas['receita_outras'] = st.checkbox(
                    "Outras receitas",
                    respostas.get('receita_outras', False)
                )
            
            respostas['origem_receita_extra'] = st.text_area(
                "Explique a origem das 'Receitas Extra Operacionais' (R$ 2.881.829):",
                respostas.get('origem_receita_extra', ''),
                help="Esta é uma quantia significativa que precisa ser entendida"
            )
        
        # Seção 3: Natureza dos Custos
        with st.expander("📊 3. NATUREZA DOS CUSTOS", expanded=True):
            st.markdown("**As 'Despesas Extra Operacionais' de R$ 6.477.012 são:**")
            
            respostas['custos_insumos'] = st.slider(
                "% Insumos agrícolas (sementes, defensivos, fertilizantes)",
                0, 100, 
                respostas.get('custos_insumos', 40)
            )
            
            respostas['custos_maquinas'] = st.slider(
                "% Máquinas e equipamentos (compra, manutenção)",
                0, 100,
                respostas.get('custos_maquinas', 20)
            )
            
            respostas['custos_financeiros'] = st.slider(
                "% Custos financeiros (juros, financiamentos)",
                0, 100,
                respostas.get('custos_financeiros', 15)
            )
            
            respostas['custos_outros'] = st.slider(
                "% Outros custos",
                0, 100,
                respostas.get('custos_outros', 25)
            )
            
            # Validação da soma
            total_custos = (respostas['custos_insumos'] + respostas['custos_maquinas'] + 
                          respostas['custos_financeiros'] + respostas['custos_outros'])
            
            if total_custos != 100:
                st.warning(f"⚠️ A soma deve ser 100%. Atual: {total_custos}%")
        
        # Seção 4: Estratégia Comercial
        with st.expander("🎯 4. ESTRATÉGIA COMERCIAL", expanded=True):
            respostas['estrategia_venda'] = st.multiselect(
                "Como comercializa a produção?",
                ["Venda à vista no mercado spot", "Contratos futuros", "CPR (Cédula de Produto Rural)", 
                 "Barter (troca por insumos)", "Vendas antecipadas", "Cooperativa"],
                default=respostas.get('estrategia_venda', [])
            )
            
            respostas['preco_vs_planejado'] = st.selectbox(
                "Preços atuais vs planejamento:",
                ["Muito acima (+20%)", "Acima (+10%)", "Conforme planejado", "Abaixo (-10%)", "Muito abaixo (-20%)"],
                index=2 if 'preco_vs_planejado' not in respostas else ["Muito acima (+20%)", "Acima (+10%)", "Conforme planejado", "Abaixo (-10%)", "Muito abaixo (-20%)"].index(respostas['preco_vs_planejado'])
            )
            
            respostas['tem_seguro'] = st.selectbox(
                "Possui seguro agrícola?",
                ["Sim, cobertura completa", "Sim, cobertura parcial", "Não possui"],
                index=2 if 'tem_seguro' not in respostas else ["Sim, cobertura completa", "Sim, cobertura parcial", "Não possui"].index(respostas['tem_seguro'])
            )
        
        # Seção 5: Estrutura Operacional
        with st.expander("🏗️ 5. ESTRUTURA OPERACIONAL", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                respostas['hectares_total'] = st.number_input(
                    "Total de hectares em operação:",
                    min_value=0.0,
                    value=respostas.get('hectares_total', 4400.0),
                    step=100.0,
                    help="Incluindo arrendados"
                )
                
                respostas['hectares_proprios'] = st.number_input(
                    "Hectares próprios:",
                    min_value=0.0,
                    max_value=respostas['hectares_total'],
                    value=respostas.get('hectares_proprios', 2000.0),
                    step=100.0
                )
            
            with col2:
                respostas['ciclos_ano'] = st.selectbox(
                    "Quantos ciclos produtivos por ano?",
                    ["1 safra", "2 safras (safrinha)", "Produção contínua"],
                    index=0 if 'ciclos_ano' not in respostas else ["1 safra", "2 safras (safrinha)", "Produção contínua"].index(respostas['ciclos_ano'])
                )
                
                respostas['mao_obra'] = st.selectbox(
                    "Tipo de mão de obra predominante:",
                    ["Familiar", "Contratada fixa", "Contratada temporária", "Mista"],
                    index=1 if 'mao_obra' not in respostas else ["Familiar", "Contratada fixa", "Contratada temporária", "Mista"].index(respostas['mao_obra'])
                )
        
        # Botão para salvar e continuar
        if st.button("💾 Salvar Respostas e Gerar Análise", type="primary", use_container_width=True):
            st.session_state['questionario_agro'] = respostas
            st.success("✅ Questionário salvo! Análise será gerada com base nas suas respostas.")
            return True
        
        return False

    def gerar_analise_profissional(self, dados_dre: dict, dados_plantio: dict, questionario: dict):
        """
        Gera análise financeira profissional baseada em todos os dados coletados
        """
        st.title("📈 PARECER TÉCNICO FINANCEIRO - AGRONEGÓCIO")
        
        # Salvar análise automaticamente no histórico
        if st.button("💾 Salvar Esta Análise no Histórico", type="primary"):
            from .comparador_temporal import ComparadorTemporalAgro
            comparador = ComparadorTemporalAgro()
            
            # Calcular métricas para salvar
            metricas = self._calcular_metricas_para_historico(dados_dre, dados_plantio)
            
            # Determinar nome da empresa
            empresa_nome = "Empresa_Padrao"
            if dados_dre and 'empresa' in dados_dre:
                empresa_nome = dados_dre['empresa']
            
            arquivo_id = comparador.salvar_analise_consultoria(
                empresa_nome, dados_dre, dados_plantio, questionario, metricas
            )
            
            st.success(f"✅ Análise salva com sucesso! ID: {arquivo_id}")
            st.info("🔍 Vá para a aba 'Comparação Temporal' para comparar com análises anteriores")
        
        # Header executivo
        self._header_executivo(dados_dre, dados_plantio, questionario)
        
        # Análise detalhada
        self._analise_performance_financeira(dados_dre)
        self._analise_viabilidade_plantios(dados_plantio, dados_dre)
        self._analise_riscos_oportunidades(questionario, dados_dre)
        self._recomendacoes_estrategicas(questionario, dados_dre, dados_plantio)
        
    def _header_executivo(self, dados_dre: dict, dados_plantio: dict, questionario: dict):
        """Resumo executivo da análise"""
        st.markdown("## 🎯 RESUMO EXECUTIVO")
        
        # Indicador de fonte dos dados
        st.info("📊 **Análise baseada em dados reais:** DRE extraído do sistema e salvo em cache JSON + Plantios cadastrados")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Receita Realizada",
                f"R$ {dados_dre['resumo_dre']['total_receitas']:,.0f}".replace(",", "."),
                delta="3 meses",
                help="Receita total do período analisado"
            )
        
        with col2:
            receita_planejada = sum(p['receita_estimada'] for p in dados_plantio.values())
            performance = (dados_dre['resumo_dre']['total_receitas'] / receita_planejada) * 100
            st.metric(
                "Performance vs Planejado",
                f"{performance:.1f}%",
                delta=f"Gap: R$ {receita_planejada - dados_dre['resumo_dre']['total_receitas']:,.0f}".replace(",", "."),
                delta_color="inverse"
            )
        
        with col3:
            margem = dados_dre['resumo_dre']['total_receitas'] - dados_dre['resumo_dre']['custos_diretos']
            st.metric(
                "Margem Contribuição",
                f"R$ {margem:,.0f}".replace(",", "."),
                delta=f"{(margem/dados_dre['resumo_dre']['total_receitas'])*100:.1f}%"
            )
        
        with col4:
            resultado = dados_dre['resumo_dre']['resultado_liquido']
            st.metric(
                "Resultado Período",
                f"R$ {resultado:,.0f}".replace(",", "."),
                delta="❌ Prejuízo" if resultado < 0 else "✅ Lucro",
                delta_color="inverse" if resultado < 0 else "normal"
            )
        
        # Alertas críticos
        if performance < 50:
            st.error("🚨 **ALERTA CRÍTICO:** Performance muito abaixo do planejado indica problemas operacionais ou comerciais sérios.")
        elif resultado < 0:
            st.warning("⚠️ **ATENÇÃO:** Resultado negativo no período requer ação imediata para correção de rota.")

    def _analise_performance_financeira(self, dados_dre: dict):
        """Análise detalhada da performance financeira"""
        st.markdown("## 📊 ANÁLISE DE PERFORMANCE FINANCEIRA")
        st.caption("🔄 Dados extraídos do DRE do sistema e analisados automaticamente")
        
        resumo = dados_dre['resumo_dre']
        
        # Gráfico de composição das receitas
        fig_receitas = go.Figure(data=[
            go.Bar(name='Receitas Operacionais', x=['Receitas'], y=[resumo['total_receitas'] - 2881829.17]),
            go.Bar(name='Receitas Extra Operacionais', x=['Receitas'], y=[2881829.17])
        ])
        fig_receitas.update_layout(
            title="Composição das Receitas",
            barmode='stack'
        )
        st.plotly_chart(fig_receitas, use_container_width=True)
        
        # Análise de custos
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 💸 Estrutura de Custos")
            custos_data = {
                'Custos Diretos': resumo['custos_diretos'],
                'Despesas Administrativas': resumo['custos_administrativos'],
                'Despesas Extra': resumo['despesas_extra'],
                'Retiradas Sócios': resumo['retiradas']
            }
            
            fig_custos = px.pie(
                values=list(custos_data.values()),
                names=list(custos_data.keys()),
                title="Distribuição dos Custos"
            )
            st.plotly_chart(fig_custos, use_container_width=True)
        
        with col2:
            st.markdown("### 📈 Indicadores Chave")
            
            margem_bruta = ((resumo['total_receitas'] - resumo['custos_diretos']) / resumo['total_receitas']) * 100
            margem_liquida = (resumo['resultado_liquido'] / resumo['total_receitas']) * 100
            
            st.metric("Margem Bruta", f"{margem_bruta:.1f}%")
            st.metric("Margem Líquida", f"{margem_liquida:.1f}%")
            
            # Comparação com benchmarks do setor
            st.markdown("**Benchmarks do Setor:**")
            st.write("• Margem Bruta Típica: 35-45%")
            st.write("• Margem Líquida Típica: 8-15%")
            
            if margem_bruta < 35:
                st.error("❌ Margem bruta abaixo do mercado")
            elif margem_bruta > 45:
                st.success("✅ Margem bruta excelente")
            else:
                st.info("📊 Margem bruta dentro da média")

    def _analise_viabilidade_plantios(self, dados_plantio: dict, dados_dre: dict):
        """Análise da viabilidade dos plantios planejados"""
        st.markdown("## 🌾 ANÁLISE DE VIABILIDADE DOS PLANTIOS")
        
        receita_total_planejada = sum(p['receita_estimada'] for p in dados_plantio.values())
        receita_realizada = dados_dre['resumo_dre']['total_receitas']
        
        # Criar DataFrame para análise
        plantios_df = []
        for plantio in dados_plantio.values():
            plantios_df.append({
                'Cultura': plantio['cultura'],
                'Hectares': plantio['hectares'],
                'Produtividade (sc/ha)': plantio['sacas_por_hectare'],
                'Preço Planejado (R$/sc)': plantio['preco_saca'],
                'Receita Estimada': plantio['receita_estimada'],
                'Receita por Hectare': plantio['receita_estimada'] / plantio['hectares']
            })
        
        df_plantios = pd.DataFrame(plantios_df)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📋 Resumo dos Plantios")
            st.dataframe(df_plantios, use_container_width=True)
            
            # Métricas totais
            st.metric("Total Hectares Planejados", f"{df_plantios['Hectares'].sum():,.0f} ha".replace(",", "."))
            st.metric("Receita Total Estimada", f"R$ {receita_total_planejada:,.0f}".replace(",", "."))
        
        with col2:
            st.markdown("### ⚖️ Realidade vs Planejamento")
            
            # Gráfico comparativo
            fig_comp = go.Figure(data=[
                go.Bar(name='Receita Planejada (Anual)', x=['Comparação'], y=[receita_total_planejada]),
                go.Bar(name='Receita Realizada (3 meses)', x=['Comparação'], y=[receita_realizada * 4])  # Projeção anual
            ])
            fig_comp.update_layout(title="Projeção Anual vs Planejamento")
            st.plotly_chart(fig_comp, use_container_width=True)
            
            # Análise de viabilidade
            projecao_anual = receita_realizada * 4
            if projecao_anual < receita_total_planejada * 0.7:
                st.error("🚨 **ALTA PROBABILIDADE DE NÃO ATINGIR AS METAS**")
                st.write("**Ações necessárias:**")
                st.write("• Revisar estratégia de comercialização")
                st.write("• Analisar custos de produção")
                st.write("• Considerar diversificação")
            elif projecao_anual < receita_total_planejada * 0.9:
                st.warning("⚠️ **RISCO MODERADO DE NÃO ATINGIR METAS**")
            else:
                st.success("✅ **PROJEÇÃO ALINHADA COM PLANEJAMENTO**")

    def _analise_riscos_oportunidades(self, questionario: dict, dados_dre: dict):
        """Análise de riscos e oportunidades baseada no questionário"""
        st.markdown("## ⚖️ ANÁLISE DE RISCOS E OPORTUNIDADES")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🚨 PRINCIPAIS RISCOS")
            
            riscos = []
            
            # Análise baseada no questionário
            if questionario.get('comercializacao_realizada', 0) < 30:
                riscos.append("• **ALTO:** Baixa comercialização antecipada - exposição total ao preço spot")
            
            if questionario.get('perdas_safra', 'Não') != 'Não':
                riscos.append("• **ALTO:** Perdas na safra atual comprometem resultado")
            
            if questionario.get('tem_seguro', 'Não possui') == 'Não possui':
                riscos.append("• **MÉDIO:** Sem seguro agrícola - exposição a eventos climáticos")
            
            if dados_dre['resumo_dre']['despesas_extra'] > dados_dre['resumo_dre']['total_receitas'] * 0.5:
                riscos.append("• **ALTO:** Despesas extra operacionais excessivas")
            
            # Análise de concentração
            receitas_extra_pct = (2881829.17 / dados_dre['resumo_dre']['total_receitas']) * 100
            if receitas_extra_pct > 30:
                riscos.append(f"• **MÉDIO:** Alta dependência de receitas extra operacionais ({receitas_extra_pct:.1f}%)")
            
            for risco in riscos:
                st.write(risco)
            
            if not riscos:
                st.success("✅ Nenhum risco crítico identificado")
        
        with col2:
            st.markdown("### 🎯 OPORTUNIDADES")
            
            oportunidades = []
            
            # Análise de margem
            margem_atual = ((dados_dre['resumo_dre']['total_receitas'] - dados_dre['resumo_dre']['custos_diretos']) / dados_dre['resumo_dre']['total_receitas']) * 100
            if margem_atual > 40:
                oportunidades.append("• **Margem operacional excelente** - reinvestir em expansão")
            
            # Análise de comercialização
            if questionario.get('comercializacao_realizada', 0) < 50:
                oportunidades.append("• **Flexibilidade comercial** - aguardar melhores preços")
            
            # Análise de diversificação
            if len(set(p['cultura'] for p in questionario.get('dados_plantio', {}).values() if 'cultura' in p)) < 3:
                oportunidades.append("• **Diversificação** - reduzir risco com mais culturas")
            
            # Análise de eficiência
            if questionario.get('custos_financeiros', 0) > 20:
                oportunidades.append("• **Otimização financeira** - renegociar financiamentos")
            
            for oportunidade in oportunidades:
                st.write(oportunidade)

    def _recomendacoes_estrategicas(self, questionario: dict, dados_dre: dict, dados_plantio: dict):
        """Recomendações estratégicas baseadas na análise completa"""
        st.markdown("## 🎯 RECOMENDAÇÕES ESTRATÉGICAS")
        
        st.markdown("### 🚀 AÇÕES IMEDIATAS (30 dias)")
        
        # Análise de fluxo de caixa
        resultado_mensal = dados_dre['resumo_dre']['resultado_liquido'] / 3
        if resultado_mensal < 0:
            st.error("1. **CRÍTICO:** Revisar fluxo de caixa - resultado negativo mensal")
            st.write("   • Renegociar prazos de pagamento")
            st.write("   • Acelerar vendas da produção")
            st.write("   • Reduzir despesas não essenciais")
        
        # Análise de comercialização
        if questionario.get('comercializacao_realizada', 0) < 50:
            st.warning("2. **Definir estratégia de comercialização:**")
            st.write("   • Analisar cenários de preços futuros")
            st.write("   • Considerar CPR para capital de giro")
            st.write("   • Avaliar contratos de barter")
        
        st.markdown("### 📈 PLANO DE MÉDIO PRAZO (6-12 meses)")
        
        # Análise de custos
        if dados_dre['resumo_dre']['despesas_extra'] > dados_dre['resumo_dre']['total_receitas'] * 0.3:
            st.info("1. **Otimização de custos:**")
            st.write("   • Auditoria detalhada das despesas extra operacionais")
            st.write("   • Implementar centro de custos por cultura")
            st.write("   • Negociar melhores condições com fornecedores")
        
        # Análise de produtividade
        st.info("2. **Melhoria da produtividade:**")
        for plantio in dados_plantio.values():
            cultura = plantio['cultura']
            produtividade = plantio['sacas_por_hectare']
            if cultura == 'Soja' and produtividade < 60:
                st.write(f"   • {cultura}: Atual {produtividade} sc/ha - Meta: 60+ sc/ha")
            elif cultura == 'Arroz' and produtividade < 180:
                st.write(f"   • {cultura}: Atual {produtividade} sc/ha - Meta: 180+ sc/ha")
        
        st.markdown("### 🏗️ ESTRATÉGIA DE LONGO PRAZO (1-3 anos)")
        
        st.success("1. **Sustentabilidade financeira:**")
        st.write("   • Criar reserva de emergência (6 meses de custeio)")
        st.write("   • Diversificar fontes de receita")
        st.write("   • Implementar gestão profissional")
        
        st.success("2. **Crescimento sustentável:**")
        st.write("   • Avaliar aquisição vs arrendamento de terras")
        st.write("   • Investir em tecnologia (agricultura de precisão)")
        st.write("   • Considerar integração vertical")

    def _calcular_metricas_para_historico(self, dados_dre: dict, dados_plantio: dict) -> dict:
        """
        Calcula métricas adicionais para salvar no histórico
        """
        resumo_dre = dados_dre['resumo_dre']
        
        # Calcular métricas
        total_hectares = sum(p['hectares'] for p in dados_plantio.values())
        receita_total_estimada = sum(p['receita_estimada'] for p in dados_plantio.values())
        
        return {
            'margem_bruta_absoluta': resumo_dre['total_receitas'] - resumo_dre['custos_diretos'],
            'margem_liquida_absoluta': resumo_dre['resultado_liquido'],
            'receita_por_hectare_real': resumo_dre['total_receitas'] / total_hectares if total_hectares > 0 else 0,
            'custo_total_por_hectare': (resumo_dre['custos_diretos'] + resumo_dre['custos_administrativos'] + resumo_dre['despesas_extra']) / total_hectares if total_hectares > 0 else 0,
            'eficiencia_operacional': resumo_dre['total_receitas'] / (resumo_dre['custos_diretos'] + resumo_dre['custos_administrativos']) if (resumo_dre['custos_diretos'] + resumo_dre['custos_administrativos']) > 0 else 0,
            'performance_anual_projetada': (resumo_dre['total_receitas'] * 4) / receita_total_estimada * 100 if receita_total_estimada > 0 else 0
        }

def interface_principal():
    """Interface principal do sistema de consultoria"""
    st.title("🎯 Análise Financeira Agro - Questionário Consultoria")
    st.markdown("### 📊 Consultoria especializada baseada em dados reais do seu DRE")
    
    # Badge indicativo
    st.success("🔄 **METODOLOGIA:** Combina dados reais do DRE (via cache JSON) + Informações operacionais coletadas")
    
    consultor = ConsultorFinanceiroAgro()
    
    if consultor.interface_questionario_inicial():
        # Carregar dados existentes
        from logic.data_cache_manager import DataCacheManager
        cache_manager = DataCacheManager()
        
        # Buscar dados da empresa (assumindo Arani como exemplo)
        dados_dre = cache_manager.carregar_dre("Arani")
        
        # Buscar dados de plantio
        import json
        try:
            with open("logic/CSVs/licencas/Arani_agro_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                dados_plantio = config.get("dados_plantio", {})
        except:
            dados_plantio = {}
        
        if dados_dre and dados_plantio:
            consultor.gerar_analise_profissional(
                dados_dre, 
                dados_plantio, 
                st.session_state['questionario_agro']
            )
        else:
            st.error("Erro ao carregar dados para análise")

if __name__ == "__main__":
    interface_principal()