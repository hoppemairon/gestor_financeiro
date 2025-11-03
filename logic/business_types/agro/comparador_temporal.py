#!/usr/bin/env python3
"""
SISTEMA DE COMPARAÇÃO TEMPORAL - GESTÃO AGRO
Salva e compara análises de consultoria ao longo do tempo
"""

import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import uuid

class ComparadorTemporalAgro:
    """
    Sistema para salvar e comparar análises de consultoria ao longo do tempo
    """
    
    def __init__(self):
        self.pasta_historico = "data_cache/historico_consultoria"
        self.garantir_pasta_existe()
    
    def garantir_pasta_existe(self):
        """Garante que a pasta de histórico existe"""
        if not os.path.exists(self.pasta_historico):
            os.makedirs(self.pasta_historico, exist_ok=True)
    
    def salvar_analise_consultoria(self, empresa: str, dados_dre: Dict, dados_plantio: Dict, 
                                 questionario: Dict, metricas_calculadas: Dict) -> str:
        """
        Salva uma análise completa de consultoria com timestamp
        """
        timestamp = datetime.now()
        arquivo_id = f"{empresa}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        
        # Estrutura completa da análise
        analise_completa = {
            "metadata": {
                "empresa": empresa,
                "timestamp": timestamp.isoformat(),
                "data_formatada": timestamp.strftime('%d/%m/%Y %H:%M'),
                "id_analise": arquivo_id,
                "versao_sistema": "2.0_rateio_hectares"
            },
            "dados_financeiros": {
                "total_receitas": dados_dre['resumo_dre']['total_receitas'],
                "custos_diretos": dados_dre['resumo_dre']['custos_diretos'],
                "custos_administrativos": dados_dre['resumo_dre']['custos_administrativos'],
                "despesas_extra": dados_dre['resumo_dre']['despesas_extra'],
                "retiradas": dados_dre['resumo_dre']['retiradas'],
                "resultado_liquido": dados_dre['resumo_dre']['resultado_liquido'],
                "margem_bruta_pct": ((dados_dre['resumo_dre']['total_receitas'] - dados_dre['resumo_dre']['custos_diretos']) / dados_dre['resumo_dre']['total_receitas']) * 100 if dados_dre['resumo_dre']['total_receitas'] > 0 else 0,
                "margem_liquida_pct": (dados_dre['resumo_dre']['resultado_liquido'] / dados_dre['resumo_dre']['total_receitas']) * 100 if dados_dre['resumo_dre']['total_receitas'] > 0 else 0
            },
            "dados_operacionais": {
                "total_hectares": sum(p['hectares'] for p in dados_plantio.values()),
                "numero_plantios": len(dados_plantio),
                "receita_estimada_total": sum(p['receita_estimada'] for p in dados_plantio.values()),
                "culturas": list(set(p['cultura'] for p in dados_plantio.values())),
                "diversificacao_culturas": len(set(p['cultura'] for p in dados_plantio.values())),
                "produtividade_media": {
                    cultura: sum(p['sacas_por_hectare'] for p in dados_plantio.values() if p['cultura'] == cultura) / 
                            len([p for p in dados_plantio.values() if p['cultura'] == cultura])
                    for cultura in set(p['cultura'] for p in dados_plantio.values())
                }
            },
            "indicadores_gestao": {
                "estagio_safra": questionario.get('estagio_safra', 'N/A'),
                "comercializacao_realizada": questionario.get('comercializacao_realizada', 0),
                "perdas_safra": questionario.get('perdas_safra', 'Não'),
                "tem_seguro": questionario.get('tem_seguro', 'Não possui'),
                "estrategia_venda": questionario.get('estrategia_venda', []),
                "preco_vs_planejado": questionario.get('preco_vs_planejado', 'Conforme planejado'),
                "hectares_proprios": questionario.get('hectares_proprios', 0),
                "ciclos_ano": questionario.get('ciclos_ano', '1 safra')
            },
            "metricas_performance": {
                "receita_por_hectare": dados_dre['resumo_dre']['total_receitas'] / sum(p['hectares'] for p in dados_plantio.values()) if sum(p['hectares'] for p in dados_plantio.values()) > 0 else 0,
                "custo_por_hectare": (dados_dre['resumo_dre']['custos_diretos'] + dados_dre['resumo_dre']['custos_administrativos']) / sum(p['hectares'] for p in dados_plantio.values()) if sum(p['hectares'] for p in dados_plantio.values()) > 0 else 0,
                "performance_vs_planejado": (dados_dre['resumo_dre']['total_receitas'] * 4) / sum(p['receita_estimada'] for p in dados_plantio.values()) * 100 if sum(p['receita_estimada'] for p in dados_plantio.values()) > 0 else 0,
                "eficiencia_custos": dados_dre['resumo_dre']['custos_diretos'] / dados_dre['resumo_dre']['total_receitas'] * 100 if dados_dre['resumo_dre']['total_receitas'] > 0 else 0,
                "dependencia_receitas_extra": (2881829.17 / dados_dre['resumo_dre']['total_receitas']) * 100 if dados_dre['resumo_dre']['total_receitas'] > 0 else 0  # Valor fixo das receitas extra da Arani
            },
            "riscos_identificados": self._avaliar_riscos(dados_dre, dados_plantio, questionario),
            "observacoes": questionario.get('observacoes_adicionais', ''),
            "resumo_questionario": questionario
        }
        
        # Salvar arquivo
        caminho_arquivo = os.path.join(self.pasta_historico, arquivo_id)
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(analise_completa, f, ensure_ascii=False, indent=2)
        
        return arquivo_id
    
    def _avaliar_riscos(self, dados_dre: Dict, dados_plantio: Dict, questionario: Dict) -> List[str]:
        """
        Avalia riscos baseado nos dados da análise
        """
        riscos = []
        
        # Análise financeira
        margem_bruta = ((dados_dre['resumo_dre']['total_receitas'] - dados_dre['resumo_dre']['custos_diretos']) / dados_dre['resumo_dre']['total_receitas']) * 100 if dados_dre['resumo_dre']['total_receitas'] > 0 else 0
        
        if margem_bruta < 30:
            riscos.append("MARGEM_BRUTA_BAIXA")
        if dados_dre['resumo_dre']['resultado_liquido'] < 0:
            riscos.append("RESULTADO_NEGATIVO")
        if dados_dre['resumo_dre']['despesas_extra'] > dados_dre['resumo_dre']['total_receitas'] * 0.5:
            riscos.append("DESPESAS_EXTRA_ELEVADAS")
        
        # Análise operacional
        if questionario.get('comercializacao_realizada', 0) < 30:
            riscos.append("BAIXA_COMERCIALIZACAO_ANTECIPADA")
        if questionario.get('perdas_safra', 'Não') != 'Não':
            riscos.append("PERDAS_PRODUCAO")
        if questionario.get('tem_seguro', 'Não possui') == 'Não possui':
            riscos.append("SEM_SEGURO_AGRICOLA")
        
        # Análise de diversificação
        if len(set(p['cultura'] for p in dados_plantio.values())) < 2:
            riscos.append("BAIXA_DIVERSIFICACAO")
        
        return riscos
    
    def listar_analises_disponiveis(self, empresa: str = None) -> List[Dict]:
        """
        Lista todas as análises salvas, opcionalmente filtradas por empresa
        """
        analises = []
        
        if not os.path.exists(self.pasta_historico):
            return analises
        
        for arquivo in os.listdir(self.pasta_historico):
            if arquivo.endswith('.json'):
                try:
                    caminho = os.path.join(self.pasta_historico, arquivo)
                    with open(caminho, 'r', encoding='utf-8') as f:
                        dados = json.load(f)
                    
                    if empresa is None or dados['metadata']['empresa'] == empresa:
                        analises.append({
                            'arquivo': arquivo,
                            'empresa': dados['metadata']['empresa'],
                            'data': dados['metadata']['data_formatada'],
                            'timestamp': dados['metadata']['timestamp'],
                            'dados': dados
                        })
                except Exception as e:
                    continue
        
        # Ordenar por data (mais recente primeiro)
        analises.sort(key=lambda x: x['timestamp'], reverse=True)
        return analises
    
    def carregar_analise(self, arquivo: str) -> Dict:
        """
        Carrega uma análise específica
        """
        caminho = os.path.join(self.pasta_historico, arquivo)
        with open(caminho, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def comparar_analises(self, analise1: Dict, analise2: Dict) -> Dict:
        """
        Compara duas análises e gera relatório de evolução
        """
        data1 = datetime.fromisoformat(analise1['metadata']['timestamp'])
        data2 = datetime.fromisoformat(analise2['metadata']['timestamp'])
        
        # Garantir ordem cronológica (mais antiga primeiro)
        if data1 > data2:
            analise1, analise2 = analise2, analise1
            data1, data2 = data2, data1
        
        comparacao = {
            'periodo': {
                'data_inicial': data1.strftime('%d/%m/%Y'),
                'data_final': data2.strftime('%d/%m/%Y'),
                'dias_periodo': (data2 - data1).days
            },
            'financeiro': self._comparar_financeiro(analise1, analise2),
            'operacional': self._comparar_operacional(analise1, analise2),
            'performance': self._comparar_performance(analise1, analise2),
            'riscos': self._comparar_riscos(analise1, analise2),
            'gestao': self._comparar_gestao(analise1, analise2)
        }
        
        return comparacao
    
    def _comparar_financeiro(self, analise1: Dict, analise2: Dict) -> Dict:
        """Compara aspectos financeiros"""
        fin1 = analise1['dados_financeiros']
        fin2 = analise2['dados_financeiros']
        
        return {
            'receitas': {
                'inicial': fin1['total_receitas'],
                'final': fin2['total_receitas'],
                'variacao_absoluta': fin2['total_receitas'] - fin1['total_receitas'],
                'variacao_percentual': ((fin2['total_receitas'] / fin1['total_receitas']) - 1) * 100 if fin1['total_receitas'] > 0 else 0,
                'tendencia': 'MELHORA' if fin2['total_receitas'] > fin1['total_receitas'] else 'PIORA' if fin2['total_receitas'] < fin1['total_receitas'] else 'ESTAVEL'
            },
            'margem_bruta': {
                'inicial': fin1['margem_bruta_pct'],
                'final': fin2['margem_bruta_pct'],
                'variacao': fin2['margem_bruta_pct'] - fin1['margem_bruta_pct'],
                'tendencia': 'MELHORA' if fin2['margem_bruta_pct'] > fin1['margem_bruta_pct'] else 'PIORA' if fin2['margem_bruta_pct'] < fin1['margem_bruta_pct'] else 'ESTAVEL'
            },
            'resultado_liquido': {
                'inicial': fin1['resultado_liquido'],
                'final': fin2['resultado_liquido'],
                'variacao': fin2['resultado_liquido'] - fin1['resultado_liquido'],
                'tendencia': 'MELHORA' if fin2['resultado_liquido'] > fin1['resultado_liquido'] else 'PIORA' if fin2['resultado_liquido'] < fin1['resultado_liquido'] else 'ESTAVEL'
            }
        }
    
    def _comparar_operacional(self, analise1: Dict, analise2: Dict) -> Dict:
        """Compara aspectos operacionais"""
        op1 = analise1['dados_operacionais']
        op2 = analise2['dados_operacionais']
        
        return {
            'hectares': {
                'inicial': op1['total_hectares'],
                'final': op2['total_hectares'],
                'variacao': op2['total_hectares'] - op1['total_hectares'],
                'tendencia': 'EXPANSAO' if op2['total_hectares'] > op1['total_hectares'] else 'REDUCAO' if op2['total_hectares'] < op1['total_hectares'] else 'ESTAVEL'
            },
            'diversificacao': {
                'inicial': op1['diversificacao_culturas'],
                'final': op2['diversificacao_culturas'],
                'variacao': op2['diversificacao_culturas'] - op1['diversificacao_culturas'],
                'tendencia': 'MELHORA' if op2['diversificacao_culturas'] > op1['diversificacao_culturas'] else 'PIORA' if op2['diversificacao_culturas'] < op1['diversificacao_culturas'] else 'ESTAVEL'
            },
            'produtividade': self._comparar_produtividade(op1, op2)
        }
    
    def _comparar_produtividade(self, op1: Dict, op2: Dict) -> Dict:
        """Compara produtividade por cultura"""
        prod_comp = {}
        
        # Culturas em comum
        culturas_comuns = set(op1['produtividade_media'].keys()) & set(op2['produtividade_media'].keys())
        
        for cultura in culturas_comuns:
            prod1 = op1['produtividade_media'][cultura]
            prod2 = op2['produtividade_media'][cultura]
            
            prod_comp[cultura] = {
                'inicial': prod1,
                'final': prod2,
                'variacao': prod2 - prod1,
                'variacao_pct': ((prod2 / prod1) - 1) * 100 if prod1 > 0 else 0,
                'tendencia': 'MELHORA' if prod2 > prod1 else 'PIORA' if prod2 < prod1 else 'ESTAVEL'
            }
        
        return prod_comp
    
    def _comparar_performance(self, analise1: Dict, analise2: Dict) -> Dict:
        """Compara métricas de performance"""
        perf1 = analise1['metricas_performance']
        perf2 = analise2['metricas_performance']
        
        return {
            'receita_por_hectare': {
                'inicial': perf1['receita_por_hectare'],
                'final': perf2['receita_por_hectare'],
                'variacao': perf2['receita_por_hectare'] - perf1['receita_por_hectare'],
                'tendencia': 'MELHORA' if perf2['receita_por_hectare'] > perf1['receita_por_hectare'] else 'PIORA'
            },
            'eficiencia_custos': {
                'inicial': perf1['eficiencia_custos'],
                'final': perf2['eficiencia_custos'],
                'variacao': perf2['eficiencia_custos'] - perf1['eficiencia_custos'],
                'tendencia': 'MELHORA' if perf2['eficiencia_custos'] < perf1['eficiencia_custos'] else 'PIORA'  # Menor é melhor
            },
            'performance_vs_planejado': {
                'inicial': perf1['performance_vs_planejado'],
                'final': perf2['performance_vs_planejado'],
                'variacao': perf2['performance_vs_planejado'] - perf1['performance_vs_planejado'],
                'tendencia': 'MELHORA' if perf2['performance_vs_planejado'] > perf1['performance_vs_planejado'] else 'PIORA'
            }
        }
    
    def _comparar_riscos(self, analise1: Dict, analise2: Dict) -> Dict:
        """Compara riscos identificados"""
        riscos1 = set(analise1['riscos_identificados'])
        riscos2 = set(analise2['riscos_identificados'])
        
        return {
            'riscos_eliminados': list(riscos1 - riscos2),
            'novos_riscos': list(riscos2 - riscos1),
            'riscos_persistentes': list(riscos1 & riscos2),
            'evolucao_geral': 'MELHORA' if len(riscos2) < len(riscos1) else 'PIORA' if len(riscos2) > len(riscos1) else 'ESTAVEL'
        }
    
    def _comparar_gestao(self, analise1: Dict, analise2: Dict) -> Dict:
        """Compara aspectos de gestão"""
        gest1 = analise1['indicadores_gestao']
        gest2 = analise2['indicadores_gestao']
        
        return {
            'comercializacao': {
                'inicial': gest1['comercializacao_realizada'],
                'final': gest2['comercializacao_realizada'],
                'variacao': gest2['comercializacao_realizada'] - gest1['comercializacao_realizada'],
                'tendencia': 'MELHORA' if gest2['comercializacao_realizada'] > gest1['comercializacao_realizada'] else 'PIORA'
            },
            'seguro_agricola': {
                'inicial': gest1['tem_seguro'],
                'final': gest2['tem_seguro'],
                'evolucao': 'MELHORA' if (gest1['tem_seguro'] == 'Não possui' and gest2['tem_seguro'] != 'Não possui') else 'PIORA' if (gest1['tem_seguro'] != 'Não possui' and gest2['tem_seguro'] == 'Não possui') else 'ESTAVEL'
            },
            'estrategia_comercial': {
                'inicial': len(gest1.get('estrategia_venda', [])),
                'final': len(gest2.get('estrategia_venda', [])),
                'evolucao': 'MELHORA' if len(gest2.get('estrategia_venda', [])) > len(gest1.get('estrategia_venda', [])) else 'ESTAVEL'
            }
        }
    
    def limpar_historico(self) -> bool:
        """
        Remove todos os arquivos de análise salvos
        """
        try:
            import shutil
            if os.path.exists(self.pasta_historico):
                shutil.rmtree(self.pasta_historico)
                self.garantir_pasta_existe()
            return True
        except Exception as e:
            print(f"Erro ao limpar histórico: {e}")
            return False
    
    def gerar_parecer_evolucao(self, comparacao: Dict) -> Dict:
        """
        Gera parecer técnico sobre a evolução da propriedade
        """
        parecer = {
            'resumo_executivo': '',
            'pontos_positivos': [],
            'pontos_negativos': [],
            'recomendacoes': [],
            'score_evolucao': 0  # -100 a +100
        }
        
        score = 0
        
        # Análise financeira
        if comparacao['financeiro']['receitas']['tendencia'] == 'MELHORA':
            parecer['pontos_positivos'].append(f"📈 Receitas cresceram {comparacao['financeiro']['receitas']['variacao_percentual']:.1f}%")
            score += 20
        elif comparacao['financeiro']['receitas']['tendencia'] == 'PIORA':
            parecer['pontos_negativos'].append(f"📉 Receitas reduziram {abs(comparacao['financeiro']['receitas']['variacao_percentual']):.1f}%")
            score -= 20
        
        if comparacao['financeiro']['margem_bruta']['tendencia'] == 'MELHORA':
            parecer['pontos_positivos'].append(f"✅ Margem bruta melhorou {comparacao['financeiro']['margem_bruta']['variacao']:.1f} pontos percentuais")
            score += 15
        elif comparacao['financeiro']['margem_bruta']['tendencia'] == 'PIORA':
            parecer['pontos_negativos'].append(f"⚠️ Margem bruta piorou {abs(comparacao['financeiro']['margem_bruta']['variacao']):.1f} pontos percentuais")
            score -= 15
        
        # Análise operacional
        if comparacao['operacional']['hectares']['tendencia'] == 'EXPANSAO':
            parecer['pontos_positivos'].append(f"🌾 Expansão de {comparacao['operacional']['hectares']['variacao']:.0f} hectares")
            score += 10
        
        if comparacao['operacional']['diversificacao']['tendencia'] == 'MELHORA':
            parecer['pontos_positivos'].append(f"🎯 Diversificação melhorou (+{comparacao['operacional']['diversificacao']['variacao']} culturas)")
            score += 10
        
        # Análise de riscos
        if comparacao['riscos']['evolucao_geral'] == 'MELHORA':
            parecer['pontos_positivos'].append(f"🛡️ Redução de riscos (-{len(comparacao['riscos']['riscos_eliminados'])} riscos)")
            score += 15
        elif comparacao['riscos']['evolucao_geral'] == 'PIORA':
            parecer['pontos_negativos'].append(f"🚨 Aumento de riscos (+{len(comparacao['riscos']['novos_riscos'])} riscos)")
            score -= 15
        
        # Performance
        if comparacao['performance']['performance_vs_planejado']['tendencia'] == 'MELHORA':
            parecer['pontos_positivos'].append(f"🎯 Performance vs planejado melhorou {comparacao['performance']['performance_vs_planejado']['variacao']:.1f}%")
            score += 15
        
        # Gerar recomendações baseadas nos pontos negativos
        if comparacao['financeiro']['margem_bruta']['tendencia'] == 'PIORA':
            parecer['recomendacoes'].append("🔧 Revisar estrutura de custos para melhorar margem bruta")
        
        if comparacao['riscos']['evolucao_geral'] == 'PIORA':
            parecer['recomendacoes'].append("🛡️ Implementar medidas de mitigação de riscos identificados")
        
        if comparacao['performance']['eficiencia_custos']['tendencia'] == 'PIORA':
            parecer['recomendacoes'].append("💰 Otimizar eficiência de custos operacionais")
        
        # Score final e resumo
        parecer['score_evolucao'] = max(-100, min(100, score))
        
        if score > 30:
            parecer['resumo_executivo'] = "🚀 EVOLUÇÃO EXCELENTE: A propriedade apresenta crescimento consistente e gestão eficiente."
        elif score > 10:
            parecer['resumo_executivo'] = "✅ EVOLUÇÃO POSITIVA: Progresso identificado com alguns pontos de atenção."
        elif score > -10:
            parecer['resumo_executivo'] = "⚖️ EVOLUÇÃO ESTÁVEL: Manutenção do status atual com oportunidades de melhoria."
        elif score > -30:
            parecer['resumo_executivo'] = "⚠️ ATENÇÃO NECESSÁRIA: Tendência de declínio que requer ação corretiva."
        else:
            parecer['resumo_executivo'] = "🚨 INTERVENÇÃO URGENTE: Deterioração significativa que demanda medidas imediatas."
        
        return parecer

def interface_comparacao_temporal():
    """
    Interface principal para comparação temporal de análises
    """
    st.title("📊 COMPARAÇÃO TEMPORAL - EVOLUÇÃO DA PROPRIEDADE")
    st.markdown("### Acompanhe a evolução da sua propriedade ao longo do tempo")
    
    comparador = ComparadorTemporalAgro()
    
    # Listar análises disponíveis
    analises = comparador.listar_analises_disponiveis()
    
    if len(analises) < 2:
        st.warning("⚠️ É necessário ter pelo menos 2 análises salvas para fazer comparação.")
        st.info("💡 Gere análises na aba 'Consultoria Avançada' para poder compará-las aqui.")
        
        if analises:
            st.markdown("### 📋 Análises Disponíveis:")
            for analise in analises:
                st.write(f"• **{analise['empresa']}** - {analise['data']}")
        
        return
    
    st.success(f"✅ {len(analises)} análises disponíveis para comparação")
    
    # Interface de seleção
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📅 Período Inicial")
        opcoes_inicial = [f"{a['empresa']} - {a['data']}" for a in analises]
        inicial_idx = st.selectbox(
            "Selecione a análise inicial:",
            range(len(opcoes_inicial)),
            format_func=lambda x: opcoes_inicial[x],
            key="inicial"
        )
        
    with col2:
        st.markdown("#### 📅 Período Final")
        opcoes_final = [f"{a['empresa']} - {a['data']}" for a in analises]
        final_idx = st.selectbox(
            "Selecione a análise final:",
            range(len(opcoes_final)),
            format_func=lambda x: opcoes_final[x],
            key="final"
        )
    
    if inicial_idx == final_idx:
        st.error("❌ Selecione análises diferentes para comparar")
        return
    
    # Executar comparação
    if st.button("🔍 Comparar Análises", type="primary", use_container_width=True):
        
        analise1 = analises[inicial_idx]['dados']
        analise2 = analises[final_idx]['dados']
        
        comparacao = comparador.comparar_analises(analise1, analise2)
        parecer = comparador.gerar_parecer_evolucao(comparacao)
        
        # Mostrar resultados
        mostrar_resultados_comparacao(comparacao, parecer)

def mostrar_resultados_comparacao(comparacao: Dict, parecer: Dict):
    """
    Mostra os resultados da comparação de forma visual
    """
    st.markdown("## 📊 RESULTADO DA COMPARAÇÃO")
    
    # Resumo executivo
    st.markdown(f"### {parecer['resumo_executivo']}")
    
    # Score visual
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        score = parecer['score_evolucao']
        cor = 'green' if score > 0 else 'red' if score < -10 else 'orange'
        st.metric(
            "Score de Evolução",
            f"{score:+.0f}",
            delta=f"Período: {comparacao['periodo']['dias_periodo']} dias",
            delta_color="off"
        )
    
    # Análise detalhada por seções
    tab1, tab2, tab3, tab4 = st.tabs(["💰 Financeiro", "🌾 Operacional", "📈 Performance", "🚨 Riscos"])
    
    with tab1:
        mostrar_comparacao_financeira(comparacao['financeiro'])
    
    with tab2:
        mostrar_comparacao_operacional(comparacao['operacional'])
    
    with tab3:
        mostrar_comparacao_performance(comparacao['performance'])
    
    with tab4:
        mostrar_comparacao_riscos(comparacao['riscos'])
    
    # Parecer final
    st.markdown("---")
    st.markdown("## 🎯 PARECER TÉCNICO")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if parecer['pontos_positivos']:
            st.markdown("### ✅ PONTOS POSITIVOS")
            for ponto in parecer['pontos_positivos']:
                st.success(ponto)
    
    with col2:
        if parecer['pontos_negativos']:
            st.markdown("### ⚠️ PONTOS DE ATENÇÃO")
            for ponto in parecer['pontos_negativos']:
                st.error(ponto)
    
    if parecer['recomendacoes']:
        st.markdown("### 🚀 RECOMENDAÇÕES")
        for rec in parecer['recomendacoes']:
            st.info(rec)

def mostrar_comparacao_financeira(financeiro: Dict):
    """Mostra comparação dos aspectos financeiros"""
    st.markdown("### 💰 EVOLUÇÃO FINANCEIRA")
    
    # Métricas principais
    col1, col2, col3 = st.columns(3)
    
    with col1:
        rec = financeiro['receitas']
        st.metric(
            "Receitas",
            f"R$ {rec['final']:,.0f}".replace(",", "."),
            delta=f"{rec['variacao_percentual']:+.1f}%"
        )
    
    with col2:
        mb = financeiro['margem_bruta']
        st.metric(
            "Margem Bruta",
            f"{mb['final']:.1f}%",
            delta=f"{mb['variacao']:+.1f}pp"
        )
    
    with col3:
        rl = financeiro['resultado_liquido']
        st.metric(
            "Resultado Líquido",
            f"R$ {rl['final']:,.0f}".replace(",", "."),
            delta=f"R$ {rl['variacao']:+,.0f}".replace(",", ".")
        )

def mostrar_comparacao_operacional(operacional: Dict):
    """Mostra comparação dos aspectos operacionais"""
    st.markdown("### 🌾 EVOLUÇÃO OPERACIONAL")
    
    col1, col2 = st.columns(2)
    
    with col1:
        ha = operacional['hectares']
        st.metric(
            "Hectares Totais",
            f"{ha['final']:,.0f} ha".replace(",", "."),
            delta=f"{ha['variacao']:+.0f} ha"
        )
    
    with col2:
        div = operacional['diversificacao']
        st.metric(
            "Diversificação",
            f"{div['final']} culturas",
            delta=f"{div['variacao']:+.0f}"
        )
    
    # Produtividade por cultura
    if operacional['produtividade']:
        st.markdown("#### 📊 Produtividade por Cultura")
        for cultura, prod in operacional['produtividade'].items():
            st.metric(
                f"{cultura}",
                f"{prod['final']:.1f} sc/ha",
                delta=f"{prod['variacao']:+.1f} sc/ha"
            )

def mostrar_comparacao_performance(performance: Dict):
    """Mostra comparação das métricas de performance"""
    st.markdown("### 📈 EVOLUÇÃO DE PERFORMANCE")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        rha = performance['receita_por_hectare']
        st.metric(
            "Receita/ha",
            f"R$ {rha['final']:,.0f}".replace(",", "."),
            delta=f"R$ {rha['variacao']:+,.0f}".replace(",", ".")
        )
    
    with col2:
        ec = performance['eficiencia_custos']
        st.metric(
            "Eficiência Custos",
            f"{ec['final']:.1f}%",
            delta=f"{ec['variacao']:+.1f}pp",
            delta_color="inverse"  # Menor é melhor
        )
    
    with col3:
        pvp = performance['performance_vs_planejado']
        st.metric(
            "vs Planejado",
            f"{pvp['final']:.1f}%",
            delta=f"{pvp['variacao']:+.1f}pp"
        )

def mostrar_comparacao_riscos(riscos: Dict):
    """Mostra comparação dos riscos"""
    st.markdown("### 🚨 EVOLUÇÃO DOS RISCOS")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if riscos['riscos_eliminados']:
            st.success("✅ **Riscos Eliminados:**")
            for risco in riscos['riscos_eliminados']:
                st.write(f"• {risco.replace('_', ' ')}")
        else:
            st.info("Nenhum risco eliminado")
    
    with col2:
        if riscos['novos_riscos']:
            st.error("🚨 **Novos Riscos:**")
            for risco in riscos['novos_riscos']:
                st.write(f"• {risco.replace('_', ' ')}")
        else:
            st.success("Nenhum risco novo")
    
    with col3:
        if riscos['riscos_persistentes']:
            st.warning("⚠️ **Riscos Persistentes:**")
            for risco in riscos['riscos_persistentes']:
                st.write(f"• {risco.replace('_', ' ')}")
        else:
            st.success("Nenhum risco persistente")

if __name__ == "__main__":
    interface_comparacao_temporal()