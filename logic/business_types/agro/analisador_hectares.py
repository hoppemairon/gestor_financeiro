#!/usr/bin/env python3
"""
SISTEMA DE ANÁLISE AGRO - RATEIO POR HECTARES
Implementa lógica de rateio proporcional por área cultivada
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
import json
import os

class AnalisadorAgroHectares:
    """
    Sistema de análise agro baseado em rateio por hectares
    """
    
    def __init__(self):
        self.dados_cache = None
        self.dados_plantio = None
        self.empresa_selecionada = None
    
    def carregar_dados(self, empresa_nome: str):
        """
        Carrega dados DRE e plantios da empresa
        """
        try:
            # Carregar dados DRE do cache
            from logic.data_cache_manager import DataCacheManager
            cache_manager = DataCacheManager()
            self.dados_cache = cache_manager.carregar_dre(empresa_nome)
            
            # Carregar dados de plantio
            arquivo_plantio = f"logic/CSVs/licencas/{empresa_nome}_agro_config.json"
            if os.path.exists(arquivo_plantio):
                with open(arquivo_plantio, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.dados_plantio = config.get("dados_plantio", {})
            
            self.empresa_selecionada = empresa_nome
            return True
            
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return False
    
    def calcular_rateio_por_hectares(self) -> Dict:
        """
        Calcula o rateio de custos proporcionalmente aos hectares
        """
        if not self.dados_cache or not self.dados_plantio:
            return {}
        
        resumo_dre = self.dados_cache['resumo_dre']
        
        # 1. Calcular total de hectares e proporções
        total_hectares = sum(plantio['hectares'] for plantio in self.dados_plantio.values())
        
        if total_hectares == 0:
            st.error("Nenhum hectare cadastrado nos plantios")
            return {}
        
        # 2. Agrupar plantios por cultura
        culturas = {}
        for plantio in self.dados_plantio.values():
            cultura = plantio['cultura']
            if cultura not in culturas:
                culturas[cultura] = {
                    'hectares': 0,
                    'receita_estimada': 0,
                    'plantios': []
                }
            culturas[cultura]['hectares'] += plantio['hectares']
            culturas[cultura]['receita_estimada'] += plantio['receita_estimada']
            culturas[cultura]['plantios'].append(plantio)
        
        # 3. Calcular rateio para cada cultura
        resultado_rateio = {}
        
        for cultura, dados_cultura in culturas.items():
            hectares_cultura = dados_cultura['hectares']
            proporcao = hectares_cultura / total_hectares
            
            # Rateio proporcional dos custos
            custos_diretos_rateados = resumo_dre['custos_diretos'] * proporcao
            despesas_admin_rateadas = resumo_dre['custos_administrativos'] * proporcao
            despesas_extra_rateadas = resumo_dre['despesas_extra'] * proporcao
            retiradas_rateadas = resumo_dre['retiradas'] * proporcao
            
            custo_total_cultura = (custos_diretos_rateados + despesas_admin_rateadas + 
                                 despesas_extra_rateadas + retiradas_rateadas)
            
            resultado_rateio[cultura] = {
                'hectares': hectares_cultura,
                'proporcao_hectares': proporcao,
                'receita_estimada': dados_cultura['receita_estimada'],
                'custos_diretos': custos_diretos_rateados,
                'despesas_administrativas': despesas_admin_rateadas,
                'despesas_extra_operacionais': despesas_extra_rateadas,
                'retiradas': retiradas_rateadas,
                'custo_total': custo_total_cultura,
                'custo_por_hectare': custo_total_cultura / hectares_cultura,
                'receita_por_hectare': dados_cultura['receita_estimada'] / hectares_cultura,
                'margem_estimada': dados_cultura['receita_estimada'] - custo_total_cultura,
                'margem_por_hectare': (dados_cultura['receita_estimada'] - custo_total_cultura) / hectares_cultura,
                'margem_percentual': ((dados_cultura['receita_estimada'] - custo_total_cultura) / dados_cultura['receita_estimada']) * 100 if dados_cultura['receita_estimada'] > 0 else 0,
                'plantios': dados_cultura['plantios']
            }
        
        return resultado_rateio
    
    def interface_selecao_empresa(self):
        """
        Interface para seleção da empresa
        """
        from logic.data_cache_manager import DataCacheManager
        cache_manager = DataCacheManager()
        empresas_disponiveis = cache_manager.listar_empresas_disponiveis()
        
        if not empresas_disponiveis:
            st.error("⚠️ Nenhuma empresa com dados DRE encontrada no cache.")
            st.info("Importe dados DRE de alguma empresa primeiro.")
            return None
        
        # Verificar quais empresas têm dados de plantio
        empresas_com_plantio = []
        for empresa in empresas_disponiveis:
            arquivo_plantio = f"logic/CSVs/licencas/{empresa['nome']}_agro_config.json"
            if os.path.exists(arquivo_plantio):
                empresas_com_plantio.append(empresa['nome'])
        
        if not empresas_com_plantio:
            st.error("⚠️ Nenhuma empresa com dados de plantio encontrada.")
            st.info("Cadastre plantios primeiro na empresa desejada.")
            return None
        
        if len(empresas_com_plantio) == 1:
            empresa_nome = empresas_com_plantio[0]
            st.info(f"📊 Analisando: **{empresa_nome}**")
        else:
            empresa_nome = st.selectbox(
                "📊 Selecione a empresa para análise:",
                empresas_com_plantio,
                help="Empresas com dados DRE e plantios cadastrados"
            )
        
        return empresa_nome
    
    def interface_resumo_executivo(self, rateio: Dict):
        """
        Mostra resumo executivo da análise
        """
        st.markdown("## 🎯 RESUMO EXECUTIVO - ANÁLISE POR CULTURA")
        
        # Indicador de fonte dos dados
        st.info(f"📊 **Fonte dos Dados:** JSON Cache gerado a partir do DRE da empresa **{self.empresa_selecionada}**")
        st.caption("🔄 Os custos reais abaixo foram extraídos do sistema DRE e salvos em cache para análise por cultura")
        
        if not rateio:
            st.warning("Nenhum dado para análise")
            return
        
        resumo_dre = self.dados_cache['resumo_dre']
        
        # Métricas principais
        total_hectares = sum(dados['hectares'] for dados in rateio.values())
        receita_total_estimada = sum(dados['receita_estimada'] for dados in rateio.values())
        custo_total_rateado = sum(dados['custo_total'] for dados in rateio.values())
        margem_total_estimada = receita_total_estimada - custo_total_rateado
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Hectares",
                f"{total_hectares:,.0f} ha".replace(",", "."),
                help="Área total em produção"
            )
        
        with col2:
            st.metric(
                "Receita Estimada",
                f"R$ {receita_total_estimada:,.0f}".replace(",", "."),
                help="Receita estimada total dos plantios"
            )
        
        with col3:
            st.metric(
                "Custo Real (DRE)",
                f"R$ {custo_total_rateado:,.0f}".replace(",", "."),
                help="Custos reais rateados proporcionalmente"
            )
        
        with col4:
            margem_pct = (margem_total_estimada / receita_total_estimada) * 100 if receita_total_estimada > 0 else 0
            st.metric(
                "Margem Estimada",
                f"R$ {margem_total_estimada:,.0f}".replace(",", "."),
                delta=f"{margem_pct:.1f}%",
                help="Margem bruta estimada"
            )
        
        # Alerta sobre performance
        receita_real_dre = resumo_dre['total_receitas']
        if receita_real_dre < receita_total_estimada * 0.3:  # Considerando 3 meses de dados
            st.error("🚨 **ALERTA:** Receita real do DRE muito abaixo da estimativa dos plantios")
        elif receita_real_dre > receita_total_estimada * 0.4:
            st.success("✅ **BOM:** Receita real do DRE alinhada com estimativas")
        else:
            st.warning("⚠️ **ATENÇÃO:** Monitorar performance das vendas")
        
        # Mostrar origem dos dados DRE
        with st.expander("📋 Detalhes da Fonte dos Dados", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📊 Dados do Cache DRE:**")
                st.write(f"• Receitas Totais: R$ {resumo_dre['total_receitas']:,.2f}".replace(",", "."))
                st.write(f"• Custos Diretos: R$ {resumo_dre['custos_diretos']:,.2f}".replace(",", "."))
                st.write(f"• Desp. Administrativas: R$ {resumo_dre['custos_administrativos']:,.2f}".replace(",", "."))
                st.write(f"• Desp. Extra Operacionais: R$ {resumo_dre['despesas_extra']:,.2f}".replace(",", "."))
                st.write(f"• Retiradas Sócios: R$ {resumo_dre['retiradas']:,.2f}".replace(",", "."))
            
            with col2:
                st.markdown("**🔄 Origem dos Dados:**")
                st.write("• ✅ Extraído do sistema DRE")
                st.write("• ✅ Salvo automaticamente em cache JSON")
                st.write("• ✅ Rateado proporcionalmente por hectares")
                st.write("• ✅ Atualizado em tempo real")
                
                if 'timestamp' in self.dados_cache:
                    from datetime import datetime
                    try:
                        timestamp = datetime.fromisoformat(self.dados_cache['timestamp'].replace('Z', '+00:00'))
                        st.write(f"• 📅 Última atualização: {timestamp.strftime('%d/%m/%Y %H:%M')}")
                    except:
                        st.write(f"• 📅 Timestamp: {self.dados_cache.get('timestamp', 'N/A')[:16]}")
    
    def interface_analise_por_cultura(self, rateio: Dict):
        """
        Interface principal de análise por cultura
        """
        st.markdown("## 🌾 ANÁLISE DETALHADA POR CULTURA")
        st.markdown("### 📊 Baseada em custos reais do DRE rateados proporcionalmente por hectares")
        
        if not rateio:
            return
        
        # Criar DataFrame para tabela resumo
        dados_tabela = []
        for cultura, dados in rateio.items():
            dados_tabela.append({
                'Cultura': cultura,
                'Hectares': f"{dados['hectares']:,.0f}".replace(",", "."),
                'Participação': f"{dados['proporcao_hectares']*100:.1f}%",
                'Receita Estimada': f"R$ {dados['receita_estimada']:,.0f}".replace(",", "."),
                'Custo Total': f"R$ {dados['custo_total']:,.0f}".replace(",", "."),
                'Margem Estimada': f"R$ {dados['margem_estimada']:,.0f}".replace(",", "."),
                'Margem %': f"{dados['margem_percentual']:.1f}%",
                'Receita/ha': f"R$ {dados['receita_por_hectare']:,.0f}".replace(",", "."),
                'Custo/ha': f"R$ {dados['custo_por_hectare']:,.0f}".replace(",", "."),
                'Margem/ha': f"R$ {dados['margem_por_hectare']:,.0f}".replace(",", ".")
            })
        
        df_resumo = pd.DataFrame(dados_tabela)
        
        # Mostrar tabela
        st.markdown("### 📊 Resumo Comparativo")
        st.dataframe(df_resumo, use_container_width=True)
        
        # Gráficos
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de distribuição de hectares
            fig_hectares = px.pie(
                values=[dados['hectares'] for dados in rateio.values()],
                names=list(rateio.keys()),
                title="Distribuição de Hectares por Cultura"
            )
            st.plotly_chart(fig_hectares, use_container_width=True)
        
        with col2:
            # Gráfico de margem por hectare
            culturas = list(rateio.keys())
            margens_ha = [dados['margem_por_hectare'] for dados in rateio.values()]
            
            fig_margem = go.Figure(data=[
                go.Bar(x=culturas, y=margens_ha, name='Margem por Hectare')
            ])
            fig_margem.update_layout(
                title="Margem Estimada por Hectare",
                yaxis_title="R$ por hectare"
            )
            st.plotly_chart(fig_margem, use_container_width=True)
        
        # Análise detalhada por cultura
        st.markdown("### 🔍 Análise Detalhada")
        
        for cultura, dados in rateio.items():
            with st.expander(f"🌱 {cultura} - {dados['hectares']:,.0f} hectares".replace(",", ".")):
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("**💰 Receita Estimada**")
                    st.metric("Total", f"R$ {dados['receita_estimada']:,.0f}".replace(",", "."))
                    st.metric("Por Hectare", f"R$ {dados['receita_por_hectare']:,.0f}".replace(",", "."))
                
                with col2:
                    st.markdown("**💸 Custos Rateados (DRE)**")
                    st.caption("🔄 Valores extraídos do cache DRE e rateados por hectare")
                    st.metric("Custos Diretos", f"R$ {dados['custos_diretos']:,.0f}".replace(",", "."))
                    st.metric("Desp. Administrativas", f"R$ {dados['despesas_administrativas']:,.0f}".replace(",", "."))
                    st.metric("Desp. Extra Operacionais", f"R$ {dados['despesas_extra_operacionais']:,.0f}".replace(",", "."))
                    st.metric("Retiradas Sócios", f"R$ {dados['retiradas']:,.0f}".replace(",", "."))
                
                with col3:
                    st.markdown("**📈 Resultado Estimado**")
                    st.metric("Margem Total", f"R$ {dados['margem_estimada']:,.0f}".replace(",", "."))
                    st.metric("Margem por Hectare", f"R$ {dados['margem_por_hectare']:,.0f}".replace(",", "."))
                    st.metric("Margem %", f"{dados['margem_percentual']:.1f}%")
                
                # Mostrar plantios desta cultura
                st.markdown("**🌾 Plantios Cadastrados:**")
                for plantio in dados['plantios']:
                    st.write(f"• {plantio['hectares']:,.0f} ha - {plantio['sacas_por_hectare']:.0f} sc/ha - R$ {plantio['preco_saca']:.2f}/sc".replace(",", "."))
    
    def interface_comparacao_dre(self, rateio: Dict):
        """
        Compara os dados estimados com o DRE real
        """
        st.markdown("## ⚖️ COMPARAÇÃO: ESTIMATIVAS vs DRE REAL")
        
        if not rateio:
            return
        
        resumo_dre = self.dados_cache['resumo_dre']
        
        # Totais estimados vs reais
        receita_estimada_total = sum(dados['receita_estimada'] for dados in rateio.values())
        custo_estimado_total = sum(dados['custo_total'] for dados in rateio.values())
        margem_estimada_total = receita_estimada_total - custo_estimado_total
        
        # Dados reais do DRE
        receita_real = resumo_dre['total_receitas']
        custo_real = resumo_dre['custos_diretos'] + resumo_dre['custos_administrativos'] + resumo_dre['despesas_extra'] + resumo_dre['retiradas']
        margem_real = receita_real - custo_real
        
        # Criar gráfico comparativo
        fig_comp = go.Figure(data=[
            go.Bar(name='Estimado (Plantios)', x=['Receita', 'Custos', 'Margem'], 
                   y=[receita_estimada_total, custo_estimado_total, margem_estimada_total]),
            go.Bar(name='Real (DRE 3 meses)', x=['Receita', 'Custos', 'Margem'], 
                   y=[receita_real, custo_real, margem_real])
        ])
        
        fig_comp.update_layout(
            title="Comparação: Estimativas vs Realidade",
            barmode='group'
        )
        st.plotly_chart(fig_comp, use_container_width=True)
        
        # Análise de performance
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Performance Atual")
            
            # Assumindo que o DRE representa 3 meses (1/4 do ano)
            projecao_anual_receita = receita_real * 4
            performance_receita = (projecao_anual_receita / receita_estimada_total) * 100
            
            st.metric(
                "Performance Receita",
                f"{performance_receita:.1f}%",
                delta=f"Projeção: R$ {projecao_anual_receita:,.0f}".replace(",", "."),
                help="Baseado em projeção anual dos dados de 3 meses"
            )
            
            if performance_receita < 70:
                st.error("🚨 Performance muito abaixo do esperado")
            elif performance_receita < 90:
                st.warning("⚠️ Performance abaixo do esperado")
            else:
                st.success("✅ Performance dentro do esperado")
        
        with col2:
            st.markdown("### 🎯 Recomendações")
            
            if performance_receita < 80:
                st.write("**Ações Urgentes:**")
                st.write("• Revisar estratégia de comercialização")
                st.write("• Acelerar vendas da produção")
                st.write("• Analisar preços praticados")
            elif performance_receita > 120:
                st.write("**Oportunidades:**")
                st.write("• Performance acima do esperado")
                st.write("• Considerar expansão")
                st.write("• Reinvestir em produtividade")
            else:
                st.write("**Manutenção:**")
                st.write("• Manter estratégia atual")
                st.write("• Monitorar indicadores")
                st.write("• Otimizar custos")

def interface_principal_agro():
    """
    Interface principal do sistema de análise agro
    """
    st.title("🌾 GESTÃO AGRO - ANÁLISE POR RATEIO DE HECTARES")
    st.markdown("### 📊 Sistema de análise financeira baseado em dados reais do DRE distribuídos por área cultivada")
    
    # Badge indicativo da fonte
    st.success("🔄 **FONTE:** Dados extraídos automaticamente do DRE e salvos em cache JSON")
    
    analisador = AnalisadorAgroHectares()
    
    # Seleção da empresa
    empresa_nome = analisador.interface_selecao_empresa()
    
    if not empresa_nome:
        return
    
    # Carregar dados
    if not analisador.carregar_dados(empresa_nome):
        st.error("Erro ao carregar dados da empresa")
        return
    
    # Calcular rateio
    with st.spinner("Calculando rateio por hectares..."):
        rateio = analisador.calcular_rateio_por_hectares()
    
    if not rateio:
        st.error("Não foi possível calcular o rateio")
        return
    
    # Mostrar análises
    analisador.interface_resumo_executivo(rateio)
    st.markdown("---")
    analisador.interface_analise_por_cultura(rateio)
    st.markdown("---")
    analisador.interface_comparacao_dre(rateio)

if __name__ == "__main__":
    interface_principal_agro()