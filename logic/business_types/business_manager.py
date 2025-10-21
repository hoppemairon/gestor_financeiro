import json
import os
import pandas as pd
import streamlit as st
from typing import Dict, List, Optional, Tuple

def carregar_tipos_negocio() -> Dict:
    """
    Carrega os tipos de negócio disponíveis
    """
    tipos = {
        "clinica_medicina": {
            "nome": "Clínica Médica",
            "template": "medicina_template.json",
            "descricao": "Clínicas médicas e consultórios"
        },
        "clinica_odonto": {
            "nome": "Clínica Odontológica", 
            "template": "odonto_template.json",
            "descricao": "Clínicas odontológicas"
        },
        "agro": {
            "nome": "Agronegócio",
            "template": "agro_template.json",
            "descricao": "Empresas do setor agrícola"
        }
    }
    return tipos

def carregar_template_negocio(tipo_negocio: str) -> Optional[Dict]:
    """
    Carrega o template específico de um tipo de negócio
    """
    tipos = carregar_tipos_negocio()
    
    if tipo_negocio not in tipos:
        return None
    
    template_file = tipos[tipo_negocio].get("template")
    if not template_file:
        return None
    
    template_path = os.path.join(
        os.path.dirname(__file__), 
        "templates", 
        template_file
    )
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Template não encontrado: {template_path}")
        return None
    except json.JSONDecodeError:
        st.error(f"Erro ao ler template: {template_path}")
        return None

def obter_centros_custo(tipo_negocio: str) -> List[str]:
    """
    Obtém os centros de custo padrão para um tipo de negócio
    """
    template = carregar_template_negocio(tipo_negocio)
    
    if template and "centros_custo_padrao" in template:
        return template["centros_custo_padrao"]
    
    # Centros padrão para clínicas
    return ["Administrativo", "Operacional"]

def obter_palavras_chave_especificas(tipo_negocio: str) -> Dict[str, str]:
    """
    Obtém palavras-chave específicas para categorização automática
    """
    template = carregar_template_negocio(tipo_negocio)
    
    if template and "palavras_chave_agro" in template:
        return template["palavras_chave_agro"]
    
    return {}

def aplicar_template_agro(df_transacoes: pd.DataFrame, licenca_nome: str) -> pd.DataFrame:
    """
    Aplica configurações específicas do agronegócio às transações
    """
    if df_transacoes.empty:
        return df_transacoes
    
    # Carregar template do agro
    template = carregar_template_negocio("agro")
    if not template:
        return df_transacoes
    
    # Aplicar palavras-chave específicas do agro
    palavras_chave = template.get("palavras_chave_agro", {})
    
    # Adicionar coluna de centro de custo se não existir
    if 'centro_custo' not in df_transacoes.columns:
        df_transacoes['centro_custo'] = None
    
    # Aplicar categorização baseada em palavras-chave
    for idx, row in df_transacoes.iterrows():
        if pd.isna(row.get('centro_custo')) or row.get('centro_custo') == '':
            descricao = str(row.get('descricao', '')).lower()
            
            for palavra, categoria in palavras_chave.items():
                if palavra.lower() in descricao:
                    df_transacoes.at[idx, 'centro_custo'] = categoria
                    break
    
    return df_transacoes

def calcular_rateio_administrativo_agro(df_transacoes: pd.DataFrame, dados_plantio: Dict) -> pd.DataFrame:
    """
    Calcula rateio administrativo baseado em hectares por cultura
    """
    if df_transacoes.empty or not dados_plantio:
        return df_transacoes
    
    # Calcular total de hectares por cultura
    hectares_por_cultura = {}
    total_hectares = 0
    
    for plantio in dados_plantio.values():
        cultura = plantio.get('cultura', 'Outros')
        hectares = plantio.get('hectares', 0)
        
        if cultura not in hectares_por_cultura:
            hectares_por_cultura[cultura] = 0
        hectares_por_cultura[cultura] += hectares
        total_hectares += hectares
    
    if total_hectares == 0:
        return df_transacoes
    
    # Calcular percentuais de rateio
    percentuais_rateio = {}
    for cultura, hectares in hectares_por_cultura.items():
        percentuais_rateio[cultura] = hectares / total_hectares
    
    # Aplicar rateio nas transações administrativas
    df_rateado = df_transacoes.copy()
    transacoes_admin = df_rateado[
        (df_rateado['centro_custo'] == 'Administrativo') | 
        (df_rateado['centro_custo'].isna())
    ]
    
    # Criar novas linhas para cada cultura
    novas_transacoes = []
    indices_para_remover = []
    
    for idx, transacao in transacoes_admin.iterrows():
        valor_original = transacao.get('valor', 0)
        
        for cultura, percentual in percentuais_rateio.items():
            nova_transacao = transacao.copy()
            nova_transacao['Valor (R$)'] = valor_original * percentual
            nova_transacao['centro_custo'] = cultura
            nova_transacao['descricao'] = f"{transacao.get('descricao', '')} (Rateio {cultura})"
            nova_transacao['rateio_original'] = True
            novas_transacoes.append(nova_transacao)
        
        indices_para_remover.append(idx)
    
    # Remover transações originais e adicionar as rateadas
    df_rateado = df_rateado.drop(indices_para_remover)
    
    if novas_transacoes:
        df_novas = pd.DataFrame(novas_transacoes)
        df_rateado = pd.concat([df_rateado, df_novas], ignore_index=True)
    
    return df_rateado

def obter_indicadores_agro() -> List[Dict]:
    """
    Obtém a lista de indicadores específicos do agronegócio
    """
    template = carregar_template_negocio("agro")
    
    if template and "indicadores_especificos" in template:
        return template["indicadores_especificos"]
    
    return []

def calcular_indicadores_agro(df_transacoes: pd.DataFrame, dados_plantio: Dict) -> Dict:
    """
    Calcula indicadores específicos do agronegócio
    """
    if df_transacoes.empty or not dados_plantio:
        return {}
    
    # Calcular totais
    total_hectares = sum(p.get('hectares', 0) for p in dados_plantio.values())
    total_sacas = sum(
        p.get('hectares', 0) * p.get('sacas_por_hectare', 0) 
        for p in dados_plantio.values()
    )
    
    receita_total = df_transacoes[df_transacoes['Valor (R$)'] > 0]['Valor (R$)'].sum()
    custo_total = abs(df_transacoes[df_transacoes['Valor (R$)'] < 0]['Valor (R$)'].sum())
    
    indicadores = {}
    
    if total_hectares > 0:
        indicadores['Receita por Hectare'] = receita_total / total_hectares
        indicadores['Custo por Hectare'] = custo_total / total_hectares
        indicadores['Margem por Hectare'] = (receita_total - custo_total) / total_hectares
    
    if total_sacas > 0:
        indicadores['Custo por Saca'] = custo_total / total_sacas
    
    if receita_total > 0:
        indicadores['Margem Percentual'] = ((receita_total - custo_total) / receita_total) * 100
    
    return indicadores

def obter_configuracao_licenca_agro(licenca_nome: str) -> Dict:
    """
    Obtém configuração específica de uma licença do agronegócio
    """
    config_path = f"./logic/CSVs/licencas/{licenca_nome}_agro_config.json"
    
    config_padrao = {
        "licenca": licenca_nome,
        "tipo_negocio": "agro",
        "dados_plantio": {},
        "configuracoes_especificas": {
            "usa_rateio_automatico": True,
            "mostra_indicadores_agro": True,
            "cenarios_habilitados": ["realista", "pessimista", "otimista"]
        }
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Mesclar com configuração padrão
                config_padrao.update(config)
    except Exception as e:
        st.warning(f"Erro ao carregar configuração da licença: {e}")
    
    return config_padrao

def salvar_configuracao_licenca_agro(licenca_nome: str, config: Dict) -> bool:
    """
    Salva configuração específica de uma licença do agronegócio
    """
    config_path = f"./logic/CSVs/licencas/{licenca_nome}_agro_config.json"
    
    try:
        # Criar diretório se não existir
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar configuração: {e}")
        return False

def verificar_modo_agro() -> bool:
    """
    Verifica se o sistema está operando no modo agronegócio
    """
    return st.session_state.get('modo_agro', False)

def ativar_modo_agro(licenca_nome: str = None):
    """
    Ativa o modo agronegócio no sistema
    """
    st.session_state['modo_agro'] = True
    st.session_state['tipo_negocio_atual'] = 'agro'
    
    if licenca_nome:
        st.session_state['licenca_agro_atual'] = licenca_nome