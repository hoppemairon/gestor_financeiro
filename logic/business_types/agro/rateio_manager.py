import streamlit as st
import pandas as pd
from typing import Dict, List, Optional, Tuple

def interface_rateio_manual_agro(df_transacoes: pd.DataFrame, dados_plantio: Dict) -> pd.DataFrame:
    """
    Interface para rateio manual de transações no modo agronegócio
    """
    if df_transacoes.empty:
        return df_transacoes
    
    # Identificar transações sem centro de custo definido
    mask_sem_categoria = (
        df_transacoes['centro_custo'].isna() | 
        (df_transacoes['centro_custo'] == '') |
        (df_transacoes['centro_custo'] == 'Não Categorizada')
    )
    
    transacoes_sem_categoria = df_transacoes[mask_sem_categoria]
    
    if transacoes_sem_categoria.empty:
        st.success("✅ Todas as transações já possuem centro de custo definido!")
        return df_transacoes
    
    st.subheader("🎯 Rateio Manual - Agronegócio")
    st.info(f"📋 Encontradas **{len(transacoes_sem_categoria)}** transações sem centro de custo definido.")
    
    # Obter culturas disponíveis dos plantios
    culturas_disponiveis = obter_culturas_dos_plantios(dados_plantio)
    
    if not culturas_disponiveis:
        st.warning("⚠️ Nenhuma cultura cadastrada. Cadastre plantios primeiro na página Gestão Agro.")
        return df_transacoes
    
    # Opções de centro de custo
    opcoes_centro_custo = ["Administrativo"] + culturas_disponiveis + ["Outros"]
    
    # Interface de rateio
    st.markdown("### 📝 Categorização por Transação")
    
    # Criar cópias para modificação
    df_resultado = df_transacoes.copy()
    transacoes_rateadas = []
    
    with st.form("form_rateio_agro"):
        st.markdown("**👇 Defina o centro de custo para cada transação:**")
        
        for idx, transacao in transacoes_sem_categoria.iterrows():
            col1, col2, col3 = st.columns([3, 2, 2])
            
            with col1:
                st.write(f"**{transacao.get('Descrição', 'Sem descrição')}**")
                valor = transacao.get('Valor (R$)', 0)
                if valor > 0:
                    st.write(f"💰 Receita: {valor:,.2f}")
                else:
                    st.write(f"💸 Despesa: {abs(valor):,.2f}")
                
                # Mostrar data se disponível
                if 'Data' in transacao:
                    st.write(f"📅 {transacao['Data']}")
            
            with col2:
                centro_custo = st.selectbox(
                    "Centro de Custo:",
                    opcoes_centro_custo,
                    key=f"centro_{idx}",
                    help="Selecione o centro de custo apropriado"
                )
            
            with col3:
                if centro_custo == "Administrativo":
                    st.info("🔄 Será rateado por cultura")
                    
                    # Mostrar preview do rateio
                    percentuais_rateio = calcular_percentuais_rateio(dados_plantio)
                    with st.expander("Ver rateio"):
                        for cultura, perc in percentuais_rateio.items():
                            valor_cultura = valor * perc
                            st.write(f"• {cultura}: {perc*100:.1f}% = R$ {valor_cultura:,.2f}")
                else:
                    st.success(f"✅ Direto para {centro_custo}")
            
            # Guardar a seleção
            transacoes_rateadas.append({
                'indice': idx,
                'centro_custo': centro_custo,
                'valor_original': valor
            })
            
            st.markdown("---")
        
        # Botão para aplicar rateio
        aplicar_rateio = st.form_submit_button("🎯 Aplicar Rateio", type="primary")
        
        if aplicar_rateio:
            df_resultado = aplicar_rateio_transacoes(
                df_resultado, 
                transacoes_rateadas, 
                dados_plantio,
                transacoes_sem_categoria
            )
            
            st.success("✅ Rateio aplicado com sucesso!")
            st.session_state['rateio_aplicado'] = True
            
            # Mostrar resumo do rateio
            mostrar_resumo_rateio(df_resultado, dados_plantio)
            
            return df_resultado
    
    return df_transacoes

def obter_culturas_dos_plantios(dados_plantio: Dict) -> List[str]:
    """
    Extrai lista única de culturas dos dados de plantio
    """
    culturas = set()
    
    for plantio in dados_plantio.values():
        if plantio.get('ativo', True):
            cultura = plantio.get('cultura', '')
            if cultura:
                culturas.add(cultura)
    
    return sorted(list(culturas))

def calcular_percentuais_rateio(dados_plantio: Dict) -> Dict[str, float]:
    """
    Calcula percentuais de rateio baseados na área plantada por cultura
    """
    hectares_por_cultura = {}
    total_hectares = 0
    
    # Somar hectares por cultura
    for plantio in dados_plantio.values():
        if not plantio.get('ativo', True):
            continue
            
        cultura = plantio.get('cultura', 'Outros')
        hectares = plantio.get('hectares', 0)
        
        if cultura not in hectares_por_cultura:
            hectares_por_cultura[cultura] = 0
        hectares_por_cultura[cultura] += hectares
        total_hectares += hectares
    
    # Calcular percentuais
    percentuais_rateio = {}
    if total_hectares > 0:
        for cultura, hectares in hectares_por_cultura.items():
            percentuais_rateio[cultura] = hectares / total_hectares
    
    return percentuais_rateio

def aplicar_rateio_transacoes(df_original: pd.DataFrame, 
                            transacoes_rateadas: List[Dict],
                            dados_plantio: Dict,
                            transacoes_sem_categoria: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica o rateio definido pelo usuário às transações
    """
    df_resultado = df_original.copy()
    percentuais_rateio = calcular_percentuais_rateio(dados_plantio)
    
    # Lista para novas transações rateadas
    novas_transacoes = []
    indices_para_remover = []
    
    for item_rateio in transacoes_rateadas:
        idx = item_rateio['indice']
        centro_custo = item_rateio['centro_custo']
        
        if idx not in transacoes_sem_categoria.index:
            continue
            
        transacao_original = transacoes_sem_categoria.loc[idx]
        
        if centro_custo == "Administrativo":
            # Ratear por todas as culturas
            for cultura, percentual in percentuais_rateio.items():
                nova_transacao = transacao_original.copy()
                nova_transacao['Valor (R$)'] = transacao_original['Valor (R$)'] * percentual
                nova_transacao['centro_custo'] = cultura
                nova_transacao['Descrição'] = f"{transacao_original.get('Descrição', '')} (Rateio {cultura})"
                nova_transacao['rateio_origem'] = 'Administrativo'
                nova_transacao['percentual_rateio'] = percentual
                
                novas_transacoes.append(nova_transacao)
        else:
            # Aplicar centro de custo direto
            df_resultado.at[idx, 'centro_custo'] = centro_custo
            df_resultado.at[idx, 'rateio_origem'] = 'Direto'
            continue
        
        # Marcar para remoção (apenas para transações rateadas)
        indices_para_remover.append(idx)
    
    # Remover transações que foram rateadas e adicionar as novas
    if indices_para_remover:
        df_resultado = df_resultado.drop(indices_para_remover)
    
    if novas_transacoes:
        df_novas = pd.DataFrame(novas_transacoes)
        df_resultado = pd.concat([df_resultado, df_novas], ignore_index=True)
    
    return df_resultado

def mostrar_resumo_rateio(df_transacoes: pd.DataFrame, dados_plantio: Dict):
    """
    Mostra resumo do rateio aplicado
    """
    st.subheader("📊 Resumo do Rateio Aplicado")
    
    # Contar transações por centro de custo
    if 'centro_custo' in df_transacoes.columns:
        resumo_centro_custo = df_transacoes.groupby('centro_custo').agg({
            'Valor (R$)': ['count', 'sum']
        }).round(2)
        
        resumo_centro_custo.columns = ['Quantidade', 'Total (R$)']
        resumo_centro_custo = resumo_centro_custo.reset_index()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📈 Transações por Centro de Custo:**")
            st.dataframe(resumo_centro_custo, use_container_width=True)
        
        with col2:
            # Gráfico de distribuição
            if len(resumo_centro_custo) > 0:
                import plotly.express as px
                
                fig = px.pie(
                    resumo_centro_custo,
                    values='Quantidade',
                    names='centro_custo',
                    title="Distribuição de Transações por Centro de Custo"
                )
                st.plotly_chart(fig, use_container_width=True)
    
    # Mostrar transações rateadas administrativamente
    transacoes_rateadas = df_transacoes[
        df_transacoes.get('rateio_origem', '') == 'Administrativo'
    ]
    
    if not transacoes_rateadas.empty:
        st.markdown("**🔄 Transações Rateadas Administrativamente:**")
        with st.expander(f"Ver {len(transacoes_rateadas)} transações rateadas"):
            st.dataframe(
                transacoes_rateadas[['Descrição', 'centro_custo', 'Valor (R$)', 'percentual_rateio']],
                use_container_width=True
            )

def interface_ajuste_rateio_agro(dados_plantio: Dict):
    """
    Interface para ajustar manualmente os percentuais de rateio
    """
    st.subheader("⚙️ Configuração de Rateio Administrativo")
    
    if not dados_plantio:
        st.warning("📋 Cadastre plantios primeiro para configurar o rateio.")
        return
    
    # Calcular rateio atual baseado em hectares
    percentuais_atuais = calcular_percentuais_rateio(dados_plantio)
    
    if not percentuais_atuais:
        st.warning("⚠️ Nenhuma área plantada encontrada.")
        return
    
    st.info("🔄 **Rateio Automático:** Baseado na área plantada por cultura")
    
    # Mostrar rateio atual
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📊 Rateio Atual (por hectares):**")
        
        for cultura, percentual in percentuais_atuais.items():
            hectares = sum(
                p.get('hectares', 0) for p in dados_plantio.values()
                if p.get('cultura') == cultura and p.get('ativo', True)
            )
            st.metric(
                f"{cultura}",
                f"{percentual*100:.1f}%",
                f"{hectares:.1f} ha"
            )
    
    with col2:
        # Opção para rateio manual (futuro)
        st.markdown("**⚙️ Configurações Avançadas:**")
        
        usar_rateio_manual = st.checkbox(
            "Usar rateio manual (sobrescreve cálculo automático)",
            help="Permite definir percentuais personalizados"
        )
        
        if usar_rateio_manual:
            st.info("🚧 **Funcionalidade em desenvolvimento**")
            st.markdown("Por enquanto, o rateio é calculado automaticamente baseado na área plantada.")
        
        # Mostrar total para validação
        total_percentual = sum(percentuais_atuais.values()) * 100
        if abs(total_percentual - 100) < 0.01:
            st.success(f"✅ Total: {total_percentual:.1f}%")
        else:
            st.error(f"❌ Total: {total_percentual:.1f}% (deve ser 100%)")

def salvar_configuracao_rateio(licenca_nome: str, config_rateio: Dict) -> bool:
    """
    Salva configuração de rateio específica da licença
    """
    try:
        from ..business_manager import obter_configuracao_licenca_agro, salvar_configuracao_licenca_agro
        
        config = obter_configuracao_licenca_agro(licenca_nome)
        config['configuracao_rateio'] = config_rateio
        config['ultima_atualizacao_rateio'] = datetime.now().isoformat()
        
        return salvar_configuracao_licenca_agro(licenca_nome, config)
    
    except Exception as e:
        st.error(f"Erro ao salvar configuração de rateio: {e}")
        return False