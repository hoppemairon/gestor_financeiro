import streamlit as st
import pandas as pd
import uuid
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

def inicializar_dados_plantio():
    """
    Inicializa os dados de plantio no session_state
    """
    if 'plantios_agro' not in st.session_state:
        st.session_state['plantios_agro'] = {}
    
    if 'receitas_agro' not in st.session_state:
        st.session_state['receitas_agro'] = {}

def adicionar_plantio(ano: int, cultura: str, hectares: float, 
                     sacas_por_hectare: float, preco_saca: float) -> str:
    """
    Adiciona um novo plantio ao sistema
    """
    plantio_id = str(uuid.uuid4())[:8]
    
    st.session_state['plantios_agro'][plantio_id] = {
        'id': plantio_id,
        'ano': ano,
        'cultura': cultura,
        'hectares': hectares,
        'sacas_por_hectare': sacas_por_hectare,
        'preco_saca': preco_saca,
        'receita_estimada': hectares * sacas_por_hectare * preco_saca,
        'data_cadastro': datetime.now().isoformat(),
        'ativo': True
    }
    
    return plantio_id

def atualizar_plantio(plantio_id: str, hectares: float, cultura: str, 
                     sacas_por_hectare: float, preco_saca: float) -> bool:
    """
    Atualiza dados de um plantio existente
    """
    if plantio_id not in st.session_state['plantios_agro']:
        return False
    
    plantio = st.session_state['plantios_agro'][plantio_id]
    plantio.update({
        'hectares': hectares,
        'cultura': cultura,
        'sacas_por_hectare': sacas_por_hectare,
        'preco_saca': preco_saca,
        'receita_estimada': hectares * sacas_por_hectare * preco_saca,
        'data_atualizacao': datetime.now().isoformat()
    })
    
    return True

def excluir_plantio(plantio_id: str) -> bool:
    """
    Exclui um plantio (marca como inativo)
    """
    if plantio_id not in st.session_state['plantios_agro']:
        return False
    
    st.session_state['plantios_agro'][plantio_id]['ativo'] = False
    return True

def obter_plantios_ativos() -> Dict:
    """
    Retorna apenas os plantios ativos
    """
    plantios_ativos = {}
    
    for pid, plantio in st.session_state.get('plantios_agro', {}).items():
        if plantio.get('ativo', True):
            plantios_ativos[pid] = plantio
    
    return plantios_ativos

def calcular_totais_plantio() -> Dict:
    """
    Calcula totais agregados dos plantios
    """
    plantios = obter_plantios_ativos()
    
    totais = {
        'total_hectares': 0,
        'total_sacas': 0,
        'receita_total_estimada': 0,
        'hectares_por_cultura': {},
        'receita_por_cultura': {},
        'numero_plantios': len(plantios)
    }
    
    for plantio in plantios.values():
        hectares = plantio.get('hectares', 0)
        sacas_ha = plantio.get('sacas_por_hectare', 0)
        preco = plantio.get('preco_saca', 0)
        cultura = plantio.get('cultura', 'Outros')
        
        # Totais gerais
        totais['total_hectares'] += hectares
        totais['total_sacas'] += hectares * sacas_ha
        totais['receita_total_estimada'] += hectares * sacas_ha * preco
        
        # Por cultura
        if cultura not in totais['hectares_por_cultura']:
            totais['hectares_por_cultura'][cultura] = 0
            totais['receita_por_cultura'][cultura] = 0
        
        totais['hectares_por_cultura'][cultura] += hectares
        totais['receita_por_cultura'][cultura] += hectares * sacas_ha * preco
    
    return totais

def obter_culturas_disponiveis() -> List[str]:
    """
    Retorna lista de culturas disponíveis
    """
    from ..business_manager import carregar_template_negocio
    
    template = carregar_template_negocio("agro")
    if template and "metricas_producao" in template:
        culturas_template = list(template["metricas_producao"]["produtividade_media"].keys())
        return [c.title() for c in culturas_template] + ["Outros"]
    
    return ["Soja", "Milho", "Arroz", "Trigo", "Outros"]

def obter_metricas_cultura(cultura: str) -> Dict:
    """
    Obtém métricas de referência para uma cultura
    """
    from ..business_manager import carregar_template_negocio
    
    template = carregar_template_negocio("agro")
    if not template:
        return {}
    
    cultura_lower = cultura.lower()
    metricas = template.get("metricas_producao", {})
    
    resultado = {
        'produtividade': metricas.get("produtividade_media", {}).get(cultura_lower, {}),
        'preco_referencia': metricas.get("preco_referencia", {}).get(cultura_lower, {})
    }
    
    return resultado

def interface_cadastro_plantio():
    """
    Interface Streamlit para cadastro de plantios
    """
    st.subheader("🌱 Cadastro de Plantios")
    
    inicializar_dados_plantio()
    
    # Formulário de cadastro
    with st.form("form_plantio_agro"):
        col1, col2 = st.columns(2)
        
        with col1:
            ano = st.number_input(
                "Ano do plantio", 
                min_value=2020, 
                max_value=2030, 
                value=2025,
                step=1
            )
            
            cultura = st.selectbox(
                "Cultura", 
                obter_culturas_disponiveis(),
                help="Selecione o tipo de cultura plantada"
            )
            
            hectares = st.number_input(
                "Área plantada (hectares)", 
                min_value=0.1, 
                step=0.1, 
                value=100.0,
                help="Área total plantada desta cultura"
            )
        
        with col2:
            # Obter métricas de referência
            metricas = obter_metricas_cultura(cultura)
            produtividade_ref = metricas.get('produtividade', {})
            preco_ref = metricas.get('preco_referencia', {})
            
            # Valores sugeridos baseados na cultura
            prod_padrao = produtividade_ref.get('media', 50)
            preco_padrao = preco_ref.get('medio', 100)
            
            sacas_por_hectare = st.number_input(
                f"Produtividade (sacas/ha)", 
                min_value=1.0, 
                step=1.0, 
                value=float(prod_padrao),
                help=f"Produtividade esperada. Referência para {cultura}: {produtividade_ref}"
            )
            
            preco_saca = st.number_input(
                "Preço da saca (R$)", 
                min_value=0.5, 
                step=0.5, 
                value=float(preco_padrao),
                help=f"Preço de venda esperado. Referência para {cultura}: {preco_ref}"
            )
            
            # Mostrar receita estimada
            receita_estimada = hectares * sacas_por_hectare * preco_saca
            st.metric(
                "Receita Estimada", 
                f"R$ {receita_estimada:,.2f}",
                help="Receita bruta estimada para este plantio"
            )
        
        submitted = st.form_submit_button("🌱 Cadastrar Plantio")
        
        if submitted:
            if hectares > 0 and sacas_por_hectare > 0 and preco_saca > 0:
                plantio_id = adicionar_plantio(ano, cultura, hectares, sacas_por_hectare, preco_saca)
                st.success(f"✅ Plantio cadastrado com sucesso! ID: {plantio_id}")
                st.rerun()
            else:
                st.error("❌ Todos os valores devem ser maiores que zero")

def interface_lista_plantios():
    """
    Interface para listar e editar plantios
    """
    plantios = obter_plantios_ativos()
    
    if not plantios:
        st.info("📋 Nenhum plantio cadastrado ainda.")
        return
    
    st.subheader("📋 Plantios Cadastrados")
    
    # Mostrar totais
    totais = calcular_totais_plantio()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Hectares", f"{totais['total_hectares']:,.1f} ha")
    with col2:
        st.metric("Total Sacas", f"{totais['total_sacas']:,.0f}")
    with col3:
        st.metric("Receita Estimada", f"R$ {totais['receita_total_estimada']:,.2f}")
    with col4:
        st.metric("Nº Plantios", totais['numero_plantios'])
    
    # Lista de plantios
    for pid, plantio in plantios.items():
        with st.expander(f"🌾 {plantio['cultura']} - {plantio['ano']} ({plantio['hectares']:.1f} ha)"):
            col1, col2 = st.columns(2)
            
            with col1:
                novo_hectares = st.number_input(
                    "Hectares", 
                    value=plantio['hectares'], 
                    key=f"ha_{pid}",
                    min_value=0.1,
                    step=0.1
                )
                
                nova_cultura = st.selectbox(
                    "Cultura",
                    obter_culturas_disponiveis(),
                    index=obter_culturas_disponiveis().index(plantio['cultura']) if plantio['cultura'] in obter_culturas_disponiveis() else 0,
                    key=f"cult_{pid}"
                )
            
            with col2:
                nova_sacas = st.number_input(
                    "Sacas/ha", 
                    value=plantio['sacas_por_hectare'], 
                    key=f"sph_{pid}",
                    min_value=1.0,
                    step=1.0
                )
                
                novo_preco = st.number_input(
                    "Preço saca (R$)", 
                    value=plantio['preco_saca'], 
                    key=f"ps_{pid}",
                    min_value=0.5,
                    step=0.5
                )
            
            # Botões de ação
            col_save, col_delete = st.columns([1, 1])
            
            with col_save:
                if st.button("💾 Salvar", key=f"save_{pid}"):
                    if atualizar_plantio(pid, novo_hectares, nova_cultura, nova_sacas, novo_preco):
                        st.success("✅ Plantio atualizado!")
                        st.rerun()
                    else:
                        st.error("❌ Erro ao atualizar plantio")
            
            with col_delete:
                if st.button("🗑️ Excluir", key=f"delete_{pid}"):
                    if excluir_plantio(pid):
                        st.success("✅ Plantio excluído!")
                        st.rerun()
                    else:
                        st.error("❌ Erro ao excluir plantio")

def interface_resumo_por_cultura():
    """
    Interface para mostrar resumo por cultura
    """
    totais = calcular_totais_plantio()
    
    if totais['numero_plantios'] == 0:
        return
    
    st.subheader("📊 Resumo por Cultura")
    
    # Criar DataFrame para exibição
    dados_cultura = []
    
    for cultura in totais['hectares_por_cultura'].keys():
        hectares = totais['hectares_por_cultura'][cultura]
        receita = totais['receita_por_cultura'][cultura]
        percentual_area = (hectares / totais['total_hectares']) * 100
        receita_por_ha = receita / hectares if hectares > 0 else 0
        
        dados_cultura.append({
            'Cultura': cultura,
            'Hectares': hectares,
            '% Área': f"{percentual_area:.1f}%",
            'Receita Estimada': f"R$ {receita:,.2f}",
            'Receita/ha': f"R$ {receita_por_ha:,.2f}"
        })
    
    if dados_cultura:
        df_cultura = pd.DataFrame(dados_cultura)
        st.dataframe(df_cultura, use_container_width=True)

def salvar_dados_plantio(licenca_nome: str) -> bool:
    """
    Salva dados de plantio em arquivo JSON da licença
    """
    try:
        from ..business_manager import obter_configuracao_licenca_agro, salvar_configuracao_licenca_agro
        
        config = obter_configuracao_licenca_agro(licenca_nome)
        config['dados_plantio'] = st.session_state.get('plantios_agro', {})
        config['ultima_atualizacao'] = datetime.now().isoformat()
        
        return salvar_configuracao_licenca_agro(licenca_nome, config)
    
    except Exception as e:
        st.error(f"Erro ao salvar dados de plantio: {e}")
        return False

def carregar_dados_plantio(licenca_nome: str) -> bool:
    """
    Carrega dados de plantio do arquivo JSON da licença
    """
    try:
        from ..business_manager import obter_configuracao_licenca_agro
        
        config = obter_configuracao_licenca_agro(licenca_nome)
        dados_plantio = config.get('dados_plantio', {})
        
        if dados_plantio:
            st.session_state['plantios_agro'] = dados_plantio
            return True
        
        return False
    
    except Exception as e:
        st.error(f"Erro ao carregar dados de plantio: {e}")
        return False