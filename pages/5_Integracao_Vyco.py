import streamlit as st

# Configuração da página (DEVE ser o primeiro comando Streamlit)
st.set_page_config(
    page_title="Integração Vyco - Análise de Dados", 
    layout="wide",
    initial_sidebar_state="expanded"
)

import pandas as pd
import io
import os
import json
from datetime import datetime
import numpy as np
from dateutil.relativedelta import relativedelta
import re
import requests
import logging
import uuid
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Imports opcionais para PostgreSQL
try:
    import psycopg2
    from sqlalchemy import create_engine, text
    from urllib.parse import quote_plus
    import requests  # Para obter IP público
    POSTGRES_AVAILABLE = True
except ImportError as e:
    POSTGRES_AVAILABLE = False
    st.error(f"❌ Bibliotecas PostgreSQL não instaladas: {e}")
    st.info("Execute: pip install psycopg2-binary sqlalchemy requests")

# Módulos do projeto
from logic.Analises_DFC_DRE.deduplicator import remover_duplicatas
from logic.Analises_DFC_DRE.categorizador import categorizar_transacoes
from logic.Analises_DFC_DRE.fluxo_caixa import exibir_fluxo_caixa  # Função original para compatibilidade
from logic.Analises_DFC_DRE.faturamento import coletar_faturamentos
from logic.Analises_DFC_DRE.estoque import coletar_estoques
from logic.Analises_DFC_DRE.gerador_parecer import gerar_parecer_automatico
from logic.Analises_DFC_DRE.exibir_dre import exibir_dre
from logic.Analises_DFC_DRE.analise_gpt import analisar_dfs_com_gpt
from logic.Analises_DFC_DRE.exibir_dre import highlight_rows

# Novos módulos para tipos de negócio
from logic.business_types.business_manager import (
    carregar_tipos_negocio,
    carregar_template_negocio,
    aplicar_template_agro,
    ativar_modo_agro,
    obter_centros_custo,
    obter_palavras_chave_especificas
)

# Importar gerenciador de cache
from logic.data_cache_manager import cache_manager

# Importar gerenciador de licenças
from logic.licenca_manager import licenca_manager

# Configuração da página removida daqui (movida para o topo)

# Configuração do logging
logging.basicConfig(level=logging.INFO)

# Funções auxiliares

def formatar_valor_br(valor):
    """Formata um valor numérico para o formato brasileiro (R$)"""
    if pd.isna(valor):
        return ""  # Deixa vazio ao invés de mostrar "nan"
    if isinstance(valor, (int, float)):
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(valor, str):
        try:
            valor_num = float(valor.replace(".", "").replace(",", ".").replace("R$", "").replace("R\\$", "").strip())
            return f"R$ {valor_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return valor
    return valor

def converter_para_float(valor_str):
    """Converte uma string de valor BR para float"""
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    try:
        # Tratar tanto R$ quanto R\$ (escapado)
        return float(str(valor_str).replace("R$", "").replace("R\\$", "").replace(".", "").replace(",", ".").strip())
    except:
        return 0.0

# ===== FUNÇÕES DE GERENCIAMENTO DE CACHE =====

def verificar_status_cache(empresa_nome: str) -> dict:
    """
    Verifica status de todos os arquivos de cache de uma empresa
    
    Returns:
        Dict com status de cada tipo de arquivo (dre, fluxo, transacoes, orcamento)
    """
    from logic.orcamento_manager import orcamento_manager
    
    status = {
        'dre': {'existe': False},
        'fluxo': {'existe': False},
        'transacoes': {'existe': False},
        'orcamento': {'existe': False}
    }
    
    # Verificar DRE
    dados_dre = cache_manager.carregar_dre(empresa_nome)
    if dados_dre:
        status['dre'] = {
            'existe': True,
            'timestamp': dados_dre.get('timestamp', 'Desconhecido'),
            'periodo': extrair_periodo_dados(dados_dre.get('dre_estruturado', {})),
            'categorias': contar_categorias_dre(dados_dre.get('dre_estruturado', {})),
            'tem_detalhamento': verificar_tem_detalhamento(dados_dre.get('dre_estruturado', {})),
            'tamanho': obter_tamanho_arquivo(f"{empresa_nome}_dre.json", 'dre')
        }
    
    # Verificar Fluxo
    dados_fluxo = cache_manager.carregar_fluxo_caixa(empresa_nome)
    if dados_fluxo:
        status['fluxo'] = {
            'existe': True,
            'timestamp': dados_fluxo.get('timestamp', 'Desconhecido'),
            'periodo': extrair_periodo_dados(dados_fluxo.get('fluxo_estruturado', {})),
            'grupos': contar_grupos_fluxo(dados_fluxo.get('fluxo_estruturado', {})),
            'tamanho': obter_tamanho_arquivo(f"{empresa_nome}_fluxo.json", 'fluxo_caixa')
        }
    
    # Verificar Transações
    dados_transacoes = cache_manager.carregar_transacoes(empresa_nome)
    if dados_transacoes is not None and not dados_transacoes.empty:
        periodo_trans = extrair_periodo_transacoes(dados_transacoes)
        status['transacoes'] = {
            'existe': True,
            'timestamp': datetime.now().isoformat(),  # Pegar do JSON depois
            'total': len(dados_transacoes),
            'periodo': periodo_trans,
            'tamanho': obter_tamanho_arquivo(f"{empresa_nome}_transacoes.json", 'dre')
        }
    
    # Verificar Orçamento
    orcamentos = orcamento_manager.listar_orcamentos_disponiveis()
    orcamento_empresa = [orc for orc in orcamentos if orc['empresa'] == empresa_nome]
    if orcamento_empresa:
        orc = orcamento_empresa[0]
        status['orcamento'] = {
            'existe': True,
            'timestamp': orc.get('timestamp', 'Desconhecido'),
            'ano_orcamento': orc.get('ano_orcamento', ''),
            'ano_base': orc.get('ano_base', ''),
            'tem_realizado': orc.get('tem_realizado', False)
        }
    
    return status

def extrair_periodo_dados(dados_estruturados: dict) -> str:
    """Extrai período dos dados estruturados (formato YYYY-MM)"""
    if not dados_estruturados:
        return "N/A"
    
    meses = set()
    for secao_data in dados_estruturados.values():
        if isinstance(secao_data, dict):
            itens = secao_data.get('itens', {}) if 'itens' in secao_data else secao_data.get('categorias', {})
            for item_data in itens.values():
                if isinstance(item_data, dict):
                    valores = item_data.get('valores', {}) if 'valores' in item_data else item_data.get('valores_mensais', {})
                    for mes in valores.keys():
                        if isinstance(mes, str) and '-' in mes and mes not in ['TOTAL', '%']:
                            meses.add(mes)
    
    if meses:
        meses_sorted = sorted(list(meses))
        return f"{meses_sorted[0]} até {meses_sorted[-1]}"
    return "N/A"

def extrair_periodo_transacoes(df: pd.DataFrame) -> str:
    """Extrai período das transações"""
    if 'Data' not in df.columns or df.empty:
        return "N/A"
    
    df['Data'] = pd.to_datetime(df['Data'])
    data_min = df['Data'].min().strftime('%m/%Y')
    data_max = df['Data'].max().strftime('%m/%Y')
    return f"{data_min} até {data_max}"

def contar_categorias_dre(dre_estruturado: dict) -> int:
    """Conta total de categorias no DRE"""
    total = 0
    for secao_data in dre_estruturado.values():
        if isinstance(secao_data, dict) and 'itens' in secao_data:
            total += len(secao_data['itens'])
    return total

def contar_grupos_fluxo(fluxo_estruturado: dict) -> int:
    """Conta total de grupos no Fluxo"""
    return len(fluxo_estruturado)

def verificar_tem_detalhamento(dre_estruturado: dict) -> bool:
    """Verifica se DRE tem detalhamento salvo"""
    for secao_data in dre_estruturado.values():
        if isinstance(secao_data, dict) and 'itens' in secao_data:
            for item_data in secao_data['itens'].values():
                if isinstance(item_data, dict) and 'detalhamento' in item_data:
                    return True
    return False

def obter_tamanho_arquivo(filename: str, tipo: str) -> str:
    """Obtém tamanho do arquivo em formato legível"""
    try:
        if tipo == 'dre' or tipo == 'transacoes':
            filepath = os.path.join("./data_cache/dre", filename)
        else:
            filepath = os.path.join("./data_cache/fluxo_caixa", filename)
        
        if os.path.exists(filepath):
            tamanho_bytes = os.path.getsize(filepath)
            if tamanho_bytes < 1024:
                return f"{tamanho_bytes} B"
            elif tamanho_bytes < 1024 * 1024:
                return f"{tamanho_bytes / 1024:.1f} KB"
            else:
                return f"{tamanho_bytes / (1024 * 1024):.1f} MB"
        return "N/A"
    except:
        return "N/A"

def exibir_card_status(tipo: str, info: dict):
    """Exibe card visual do status de um arquivo de cache"""
    if info['existe']:
        st.success(f"✅ **{tipo}**")
        
        # Formatar timestamp
        try:
            if 'timestamp' in info and info['timestamp'] != 'Desconhecido':
                dt = datetime.fromisoformat(info['timestamp'].replace('Z', '+00:00'))
                timestamp_formatado = dt.strftime('%d/%m/%Y %H:%M')
            else:
                timestamp_formatado = "N/A"
        except:
            timestamp_formatado = "N/A"
        
        st.caption(f"📅 {timestamp_formatado}")
        
        # Informações específicas por tipo
        if tipo == "DRE":
            st.caption(f"📊 {info.get('categorias', 0)} categorias")
            st.caption(f"📆 {info.get('periodo', 'N/A')}")
            st.caption(f"💾 {info.get('tamanho', 'N/A')}")
            if info.get('tem_detalhamento'):
                st.caption("✨ Com detalhamento")
        
        elif tipo == "Fluxo":
            st.caption(f"📊 {info.get('grupos', 0)} grupos")
            st.caption(f"📆 {info.get('periodo', 'N/A')}")
            st.caption(f"💾 {info.get('tamanho', 'N/A')}")
        
        elif tipo == "Transações":
            st.caption(f"📊 {info.get('total', 0):,} transações".replace(",", "."))
            st.caption(f"📆 {info.get('periodo', 'N/A')}")
            st.caption(f"💾 {info.get('tamanho', 'N/A')}")
        
        elif tipo == "Orçamento":
            st.caption(f"📅 {info.get('ano_orcamento', 'N/A')}")
            st.caption(f"📊 Base: {info.get('ano_base', 'N/A')}")
            if info.get('tem_realizado'):
                st.caption("✨ Com realizado")
    else:
        st.error(f"❌ **{tipo}**")
        st.caption("Não encontrado")

def atualizar_cache_completo(empresa_nome: str):
    """
    Atualiza todos os arquivos de cache usando dados da session_state
    Nota: Esta função requer que os dados já tenham sido processados nas outras abas
    """
    if 'df_transacoes_total_vyco' not in st.session_state or st.session_state.df_transacoes_total_vyco.empty:
        st.error("❌ Nenhuma transação carregada. Carregue os dados do Vyco primeiro na aba 'Categorização'.")
        st.info("💡 **Como atualizar o cache:**\n1. Vá na aba 'Categorização'\n2. Categorize as transações\n3. Volte aqui e clique novamente")
        return
    
    # Verificar se já tem DRE/Fluxo processados
    if 'ultimo_dre_vyco' not in st.session_state or 'ultimo_fluxo_vyco' not in st.session_state:
        st.warning("⚠️ DRE/Fluxo não foram gerados ainda.")
        st.info("💡 **Como atualizar o cache:**\n1. Vá em 'Projeções' ou 'Parecer Diagnóstico'\n2. Gere os relatórios\n3. Os dados serão salvos automaticamente no cache")
        return
    
    with st.spinner("Atualizando cache completo..."):
        try:
            # Usar dados já processados da session_state
            resultado_fluxo = st.session_state.get('ultimo_fluxo_vyco')
            resultado_dre = st.session_state.get('ultimo_dre_vyco')
            df_transacoes = st.session_state.df_transacoes_total_vyco
            
            # Preparar metadata
            metadata = {
                'licenca': empresa_nome,
                'total_transacoes': len(df_transacoes),
                'gerado_em': datetime.now().isoformat(),
                'origem': 'cache_manual_update'
            }
            
            # Salvar tudo
            sucesso = True
            
            # Fluxo
            if resultado_fluxo is not None and not resultado_fluxo.empty:
                arquivo_fluxo = cache_manager.salvar_fluxo_caixa(resultado_fluxo, empresa_nome, metadata)
                if arquivo_fluxo:
                    st.success(f"✅ Fluxo de caixa atualizado")
                else:
                    sucesso = False
            
            # DRE
            if resultado_dre is not None:
                arquivo_dre = cache_manager.salvar_dre(
                    resultado_dre,
                    empresa_nome,
                    metadata,
                    df_transacoes=df_transacoes
                )
                if arquivo_dre:
                    st.success(f"✅ DRE atualizado")
                else:
                    sucesso = False
            
            # Transações
            if not df_transacoes.empty:
                arquivo_transacoes = cache_manager.salvar_transacoes(
                    df_transacoes,
                    empresa_nome,
                    metadata
                )
                if arquivo_transacoes:
                    st.success(f"✅ Transações salvas")
                else:
                    sucesso = False
            
            if sucesso:
                st.balloons()
                st.success("🎉 Cache atualizado com sucesso!")
            else:
                st.warning("⚠️ Alguns arquivos não foram salvos corretamente")
                
        except Exception as e:
            st.error(f"❌ Erro ao atualizar cache: {e}")

def obter_arquivo_categorias_licenca(licenca_nome, tipo_lancamento=""):
    """
    Obtém o caminho do arquivo JSON específico para uma licença
    """
    # Criar diretório para arquivos de licenças se não existir
    dir_licencas = "./logic/CSVs/licencas"
    if not os.path.exists(dir_licencas):
        os.makedirs(dir_licencas)
    
    # Nome do arquivo baseado na licença, limpo para sistema de arquivos
    nome_limpo = "".join(c for c in licenca_nome if c.isalnum() or c in (' ', '-', '_')).rstrip()
    nome_limpo = nome_limpo.replace(' ', '_').lower()
    
    arquivo_json = f"{dir_licencas}/categorias_{nome_limpo}.json"
    return arquivo_json

def carregar_categorias_licenca(arquivo_json):
    """
    Carrega as categorias salvas do arquivo JSON da licença como dicionário
    """
    if os.path.exists(arquivo_json):
        try:
            with open(arquivo_json, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                # Retornar dicionário diretamente
                return dados if dados else {}
        except Exception as e:
            st.warning(f"⚠️ Erro ao carregar categorias da licença: {e}")
            return {}
    else:
        return {}

def salvar_categorias_licenca(arquivo_json, categorias_dict):
    """
    Salva as categorias no arquivo JSON da licença
    """
    try:
        with open(arquivo_json, 'w', encoding='utf-8') as f:
            # Salvar dicionário diretamente
            json.dump(categorias_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"❌ Erro ao salvar categorias da licença: {e}")
        return False

def salvar_faturamento_json(licenca_nome, dados_faturamento):
    """
    Salva os dados de faturamento em arquivo JSON específico da licença
    """
    try:
        # Criar diretório para dados de licenças se não existir
        dir_licencas = "./logic/CSVs/licencas"
        if not os.path.exists(dir_licencas):
            os.makedirs(dir_licencas)
        
        # Nome do arquivo baseado na licença
        nome_limpo = "".join(c for c in licenca_nome if c.isalnum() or c in (' ', '-', '_')).rstrip()
        nome_limpo = nome_limpo.replace(' ', '_').lower()
        arquivo_json = f"{dir_licencas}/{nome_limpo}_faturamento.json"
        
        with open(arquivo_json, 'w', encoding='utf-8') as f:
            json.dump(dados_faturamento, f, ensure_ascii=False, indent=2)
        
        st.success(f"✅ Faturamento salvo em: {arquivo_json}")
        return True
    except Exception as e:
        st.error(f"❌ Erro ao salvar faturamento: {e}")
        return False

def carregar_faturamento_json(licenca_nome):
    """
    Carrega os dados de faturamento do arquivo JSON da licença
    """
    try:
        dir_licencas = "./logic/CSVs/licencas"
        nome_limpo = "".join(c for c in licenca_nome if c.isalnum() or c in (' ', '-', '_')).rstrip()
        nome_limpo = nome_limpo.replace(' ', '_').lower()
        arquivo_json = f"{dir_licencas}/{nome_limpo}_faturamento.json"
        
        if os.path.exists(arquivo_json):
            with open(arquivo_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        st.error(f"❌ Erro ao carregar faturamento: {e}")
        return {}

def salvar_estoque_json(licenca_nome, dados_estoque):
    """
    Salva os dados de estoque em arquivo JSON específico da licença
    """
    try:
        # Criar diretório para dados de licenças se não existir
        dir_licencas = "./logic/CSVs/licencas"
        if not os.path.exists(dir_licencas):
            os.makedirs(dir_licencas)
        
        # Nome do arquivo baseado na licença
        nome_limpo = "".join(c for c in licenca_nome if c.isalnum() or c in (' ', '-', '_')).rstrip()
        nome_limpo = nome_limpo.replace(' ', '_').lower()
        arquivo_json = f"{dir_licencas}/{nome_limpo}_estoque.json"
        
        with open(arquivo_json, 'w', encoding='utf-8') as f:
            json.dump(dados_estoque, f, ensure_ascii=False, indent=2)
        
        st.success(f"✅ Estoque salvo em: {arquivo_json}")
        return True
    except Exception as e:
        st.error(f"❌ Erro ao salvar estoque: {e}")
        return False

def carregar_estoque_json(licenca_nome):
    """
    Carrega os dados de estoque do arquivo JSON da licença
    """
    try:
        dir_licencas = "./logic/CSVs/licencas"
        nome_limpo = "".join(c for c in licenca_nome if c.isalnum() or c in (' ', '-', '_')).rstrip()
        nome_limpo = nome_limpo.replace(' ', '_').lower()
        arquivo_json = f"{dir_licencas}/{nome_limpo}_estoque.json"
        
        if os.path.exists(arquivo_json):
            with open(arquivo_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        st.error(f"❌ Erro ao carregar estoque: {e}")
        return {}

# ==================== FUNÇÕES DE PARECER GPT ====================

def salvar_parecer_gpt(licenca_nome, parecer_texto, descricao_empresa, periodo_analise=""):
    """
    Salva o parecer GPT em arquivo JSON com timestamp
    
    Args:
        licenca_nome: Nome da licença/empresa
        parecer_texto: Texto completo do parecer gerado pelo GPT
        descricao_empresa: Descrição da empresa fornecida pelo usuário
        periodo_analise: Período analisado (ex: "2024-01 a 2024-12")
    
    Returns:
        str: Caminho do arquivo salvo ou None se houver erro
    """
    try:
        # Criar pasta se não existir
        pasta_pareceres = "./data_cache/pareceres_gpt"
        os.makedirs(pasta_pareceres, exist_ok=True)
        
        # Limpar nome da licença para usar no arquivo
        nome_limpo = "".join(c for c in licenca_nome if c.isalnum() or c in (' ', '-', '_')).rstrip()
        nome_limpo = nome_limpo.replace(' ', '_').lower()
        
        # Gerar timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Nome do arquivo: Empresa_YYYYMMDD_HHMMSS.json
        arquivo_json = os.path.join(pasta_pareceres, f"{nome_limpo}_{timestamp}.json")
        
        # Preparar dados
        dados_parecer = {
            "licenca": licenca_nome,
            "data_geracao": datetime.now().isoformat(),
            "timestamp": timestamp,
            "parecer_texto": parecer_texto,
            "metadata": {
                "descricao_empresa": descricao_empresa,
                "periodo_analise": periodo_analise,
                "total_caracteres": len(parecer_texto)
            }
        }
        
        # Salvar arquivo
        with open(arquivo_json, 'w', encoding='utf-8') as f:
            json.dump(dados_parecer, f, indent=2, ensure_ascii=False)
        
        return arquivo_json
    
    except Exception as e:
        st.error(f"Erro ao salvar parecer GPT: {e}")
        return None

def carregar_ultimo_parecer_gpt(licenca_nome):
    """
    Carrega o último parecer GPT salvo para a licença
    
    Args:
        licenca_nome: Nome da licença/empresa
    
    Returns:
        dict: Dados do parecer ou None se não encontrado
    """
    try:
        pasta_pareceres = "./data_cache/pareceres_gpt"
        
        if not os.path.exists(pasta_pareceres):
            return None
        
        # Limpar nome da licença
        nome_limpo = "".join(c for c in licenca_nome if c.isalnum() or c in (' ', '-', '_')).rstrip()
        nome_limpo = nome_limpo.replace(' ', '_').lower()
        
        # Listar arquivos da licença
        arquivos = [f for f in os.listdir(pasta_pareceres) if f.startswith(nome_limpo) and f.endswith('.json')]
        
        if not arquivos:
            return None
        
        # Ordenar por data (mais recente primeiro)
        arquivos.sort(reverse=True)
        
        # Carregar o mais recente
        arquivo_json = os.path.join(pasta_pareceres, arquivos[0])
        
        with open(arquivo_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    except Exception as e:
        st.error(f"Erro ao carregar último parecer: {e}")
        return None

def listar_pareceres_gpt(licenca_nome):
    """
    Lista todos os pareceres GPT salvos para a licença
    
    Args:
        licenca_nome: Nome da licença/empresa
    
    Returns:
        list: Lista de dicionários com informações dos pareceres
    """
    try:
        pasta_pareceres = "./data_cache/pareceres_gpt"
        
        if not os.path.exists(pasta_pareceres):
            return []
        
        # Limpar nome da licença
        nome_limpo = "".join(c for c in licenca_nome if c.isalnum() or c in (' ', '-', '_')).rstrip()
        nome_limpo = nome_limpo.replace(' ', '_').lower()
        
        # Listar arquivos da licença
        arquivos = [f for f in os.listdir(pasta_pareceres) if f.startswith(nome_limpo) and f.endswith('.json')]
        
        pareceres = []
        for arquivo in arquivos:
            try:
                arquivo_path = os.path.join(pasta_pareceres, arquivo)
                with open(arquivo_path, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                    
                    # Extrair data do timestamp
                    data_geracao = dados.get('data_geracao', '')
                    try:
                        data_obj = datetime.fromisoformat(data_geracao)
                        data_formatada = data_obj.strftime("%d/%m/%Y %H:%M")
                    except:
                        data_formatada = data_geracao
                    
                    pareceres.append({
                        'arquivo': arquivo,
                        'data_geracao': data_geracao,
                        'data_formatada': data_formatada,
                        'periodo': dados.get('metadata', {}).get('periodo_analise', 'N/A'),
                        'caracteres': dados.get('metadata', {}).get('total_caracteres', 0)
                    })
            except:
                continue
        
        # Ordenar por data (mais recente primeiro)
        pareceres.sort(key=lambda x: x['data_geracao'], reverse=True)
        
        return pareceres
    
    except Exception as e:
        st.error(f"Erro ao listar pareceres: {e}")
        return []

def carregar_parecer_especifico(licenca_nome, arquivo_nome):
    """
    Carrega um parecer GPT específico
    
    Args:
        licenca_nome: Nome da licença/empresa
        arquivo_nome: Nome do arquivo do parecer
    
    Returns:
        dict: Dados do parecer ou None se não encontrado
    """
    try:
        pasta_pareceres = "./data_cache/pareceres_gpt"
        arquivo_path = os.path.join(pasta_pareceres, arquivo_nome)
        
        if os.path.exists(arquivo_path):
            with open(arquivo_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    except Exception as e:
        st.error(f"Erro ao carregar parecer: {e}")
        return None

def categorizar_transacoes_vyco(
    df_transacoes,
    plano_path="./logic/CSVs/plano_de_contas.csv",
    categorias_salvas_path="./logic/CSVs/categorias_salvas.csv",
    prefixo_key="cat",
    tipo_lancamento="",
    licenca_nome=""
):
    """
    Versão customizada da categorização especificamente para dados do Vyco
    Usa 'Categoria_Vyco' como parâmetro principal de categorização quando disponível
    Suporte para arquivos específicos por licença
    Inclui aplicação de templates específicos por tipo de negócio
    """
    
    # Aplicar template específico do tipo de negócio
    tipo_negocio = st.session_state.get('tipo_negocio_selecionado', None)
    
    if tipo_negocio == "agronegocio" and not df_transacoes.empty:
        # Aplicar template específico do agronegócio
        try:
            df_transacoes = aplicar_template_agro(df_transacoes, licenca_nome)
            st.info("🌾 Template de agronegócio aplicado às transações")
        except Exception as e:
            st.warning(f"⚠️ Erro ao aplicar template agro: {e}")
    
    # Se uma licença foi informada, usar arquivo específico
    if licenca_nome and licenca_nome.strip():
        arquivo_licenca = obter_arquivo_categorias_licenca(licenca_nome, tipo_lancamento)
        df_categorias = carregar_categorias_licenca(arquivo_licenca)
    else:
        # Fallback para arquivo CSV tradicional
        if os.path.exists(categorias_salvas_path):
            df_categorias = pd.read_csv(categorias_salvas_path)
        else:
            df_categorias = pd.DataFrame(columns=["Descricao", "Tipo", "Categoria"])

    # Verificar se temos dados de categoria do Vyco
    usar_categoria_vyco = 'Categoria_Vyco' in df_transacoes.columns and not df_transacoes['Categoria_Vyco'].isna().all()
    

    
    if usar_categoria_vyco:
        # Usar "Categoria nome" do Vyco como parâmetro de categorização
        try:
            df_desc = (
                df_transacoes
                .groupby("Categoria_Vyco", as_index=False)
                .agg(Quantidade=("Valor (R$)", "count"), Total=("Valor (R$)", "sum"))
            )
            # Pré-categorizar com base no JSON se disponível
            df_desc["Categoria"] = ""
            if licenca_nome and licenca_nome.strip() and isinstance(df_categorias, dict):
                for idx, row in df_desc.iterrows():
                    categoria_vyco = row["Categoria_Vyco"]
                    if categoria_vyco in df_categorias:
                        df_desc.at[idx, "Categoria"] = df_categorias[categoria_vyco]

            st.success("✅ Agrupamento por Categoria Vyco realizado com sucesso!")
        except Exception as e:
            st.error(f"❌ Erro no agrupamento Vyco: {e}")
            # Fallback para modo tradicional
            df_desc = (
                df_transacoes
                .groupby("Descrição", as_index=False)
                .agg(Quantidade=("Valor (R$)", "count"), Total=("Valor (R$)", "sum"))
            )
            # Pré-categorizar com base no JSON se disponível (modo fallback)
            df_desc["Categoria"] = ""
            if licenca_nome and licenca_nome.strip() and isinstance(df_categorias, dict):
                for idx, row in df_desc.iterrows():
                    descricao = row["Descrição"]
                    if descricao in df_categorias:
                        df_desc.at[idx, "Categoria"] = df_categorias[descricao]
            usar_categoria_vyco = False
    else:
        # Usar apenas a descrição (método tradicional)
        df_desc = (
            df_transacoes
            .groupby("Descrição", as_index=False)
            .agg(Quantidade=("Valor (R$)", "count"), Total=("Valor (R$)", "sum"))
        )
        # Pré-categorizar com base no JSON se disponível (modo tradicional)
        df_desc["Categoria"] = ""
        if licenca_nome and licenca_nome.strip() and isinstance(df_categorias, dict):
            for idx, row in df_desc.iterrows():
                descricao = row["Descrição"]
                if descricao in df_categorias:
                    df_desc.at[idx, "Categoria"] = df_categorias[descricao]

    # Verificar se o plano de contas existe
    try:
        df_plano = pd.read_csv(plano_path)
        if df_plano.empty:
            st.error("⚠️ Arquivo plano_de_contas.csv está vazio.")
            return df_transacoes, pd.DataFrame()
    except FileNotFoundError:
        st.error("⚠️ Arquivo plano_de_contas.csv não encontrado.")
        return df_transacoes, pd.DataFrame()
    except Exception as e:
        st.error(f"⚠️ Erro ao ler o arquivo plano_de_contas.csv: {e}")
        return df_transacoes, pd.DataFrame()

    # Mapear o tipo de lançamento para o formato do plano de contas
    tipo_mapeado = tipo_lancamento
    if tipo_lancamento == "Despesa":
        tipo_mapeado = "Débito"
    elif tipo_lancamento == "Receita":
        tipo_mapeado = "Crédito"

    # Filtrar plano pelo tipo de lançamento
    if tipo_mapeado:
        df_plano_filtrado = df_plano[df_plano["Tipo"] == tipo_mapeado].copy()
        if df_plano_filtrado.empty:
            st.warning(f"Nenhuma categoria encontrada para o tipo '{tipo_mapeado}'. Usando todas as categorias.")
            df_plano_filtrado = df_plano.copy()
    else:
        df_plano_filtrado = df_plano.copy()

    # Verificar se há categorias após a filtragem
    if df_plano_filtrado.empty:
        st.error("⚠️ Plano de contas vazio após filtragem.")
        return df_transacoes, df_desc

    # Criar opções de categorias
    df_plano_filtrado["Opcao"] = df_plano_filtrado["Grupo"] + " :: " + df_plano_filtrado["Categoria"]
    opcoes_categorias = df_plano_filtrado["Opcao"].tolist()
    mapa_opcao_categoria = dict(zip(df_plano_filtrado["Opcao"], df_plano_filtrado["Categoria"]))

    # Carregar palavras-chave
    try:
        df_palavras = pd.read_csv("./logic/CSVs/palavras_chave.csv")
    except:
        df_palavras = pd.DataFrame(columns=["PalavraChave", "Tipo", "Categoria"])

    if usar_categoria_vyco:
        st.markdown("### 🧠 Categorize as Descrições (baseado em Categoria Vyco)")
        st.info("🔄 **Modo Vyco:** As categorias do sistema Vyco são usadas como base, mas você pode ajustá-las conforme o plano de contas.")
    else:
        st.markdown("### 🧠 Categorize as Descrições")
        st.info("Para cada descrição, selecione uma categoria do plano de contas.")

    with st.expander("📘 Visualizar Plano de Contas"):
        st.dataframe(df_plano_filtrado[["Grupo", "Categoria"]], use_container_width=True)

    if usar_categoria_vyco:
        with st.expander("📊 Visualizar Categorias do Vyco"):
            vyco_cats = df_transacoes[df_transacoes['Categoria_Vyco'].notna()]['Categoria_Vyco'].value_counts()
            st.dataframe(vyco_cats.reset_index(), use_container_width=True)

    # MOVIDO PARA CIMA: Categorização em Lote
    st.markdown("### 🧩 Categorização em Lote")
    coluna1, coluna2 = st.columns([3, 2])
    with coluna1:
        palavras_chave = st.text_input("🔍 Procurar categorias por palavra:", key=f"busca_palavra_{prefixo_key}")
        if usar_categoria_vyco:
            # Para modo Vyco, usar apenas Categoria_Vyco
            categorias_disponiveis = df_desc[df_desc["Categoria"].isnull() | (df_desc["Categoria"] == "")]["Categoria_Vyco"].tolist()
            categorias_texto = [f"Vyco: {cat}" for cat in categorias_disponiveis]
        else:
            # Para modo tradicional, usar Descrição
            descricoes_disponiveis = df_desc[df_desc["Categoria"].isnull() | (df_desc["Categoria"] == "")]["Descrição"].tolist()
            categorias_texto = descricoes_disponiveis
            
        if palavras_chave:
            categorias_filtradas = [d for d in categorias_texto if palavras_chave.lower() in d.lower()]
        else:
            categorias_filtradas = categorias_texto

        selecionadas = st.multiselect("✅ Categorias para categorizar:", categorias_filtradas, key=f"multi_{prefixo_key}")

    with coluna2:
        opcao_lote = st.selectbox("📂 Categoria para aplicar:", [""] + opcoes_categorias, key=f"lote_{prefixo_key}")
        if st.button("📌 Aplicar Categoria em Lote", key=f"btn_lote_{prefixo_key}"):
            if opcao_lote and selecionadas:
                categoria_escolhida = mapa_opcao_categoria.get(opcao_lote, "")
                if usar_categoria_vyco:
                    # Extrair categorias Vyco (remover "Vyco: ")
                    vyco_selecionadas = [s.replace("Vyco: ", "") for s in selecionadas]
                    df_desc.loc[df_desc["Categoria_Vyco"].isin(vyco_selecionadas), "Categoria"] = categoria_escolhida
                else:
                    df_desc.loc[df_desc["Descrição"].isin(selecionadas), "Categoria"] = categoria_escolhida
                st.success(f"✅ Categoria '{categoria_escolhida}' aplicada em {len(selecionadas)} itens.")

    # Preparar registros para categorização manual individual
    st.markdown("### 📝 Categorização Manual Individual")
    
    if usar_categoria_vyco:
        st.info("💡 **Dica:** As transações abaixo mostram a categoria original do Vyco. Você pode mantê-la ou escolher uma categoria do plano de contas.")
    
    for idx, row in df_desc.iterrows():
        if usar_categoria_vyco:
            # No modo Vyco, agrupamos por categoria
            categoria_vyco = row["Categoria_Vyco"]
            desc = f"Categoria: {categoria_vyco}"  # Label para exibição
        else:
            # No modo tradicional, agrupamos por descrição
            desc = row["Descrição"]
            categoria_vyco = ""
        
        # Se já tem categoria definida, pular
        if pd.notnull(row["Categoria"]) and row["Categoria"] != "":
            continue

        # Buscar categoria salva (usar categoria Vyco como chave se disponível)
        chave_busca = categoria_vyco if usar_categoria_vyco else desc
        categoria_padrao = ""
        
        # Se usando sistema de licenças (dados JSON), buscar diretamente no dicionário
        if licenca_nome and licenca_nome.strip() and isinstance(df_categorias, dict):
            categoria_padrao = df_categorias.get(chave_busca, "")
        elif isinstance(df_categorias, pd.DataFrame):
            # Fallback para sistema CSV tradicional
            categoria_salva = df_categorias[
                (df_categorias["Descricao"] == chave_busca) &
                (df_categorias["Tipo"] == tipo_lancamento)
            ]["Categoria"].values
            
            if len(categoria_salva) > 0:
                categoria_padrao = categoria_salva[0]
        else:
            categoria_padrao = ""
        
        # Se não encontrou categoria salva, tentar outras estratégias
        if not categoria_padrao:
            if usar_categoria_vyco and categoria_vyco:
                # Tentar mapear categoria do Vyco para o plano de contas
                categoria_vyco_escaped = re.escape(categoria_vyco)
                categoria_match = df_plano_filtrado[df_plano_filtrado["Categoria"].str.contains(categoria_vyco_escaped, case=False, na=False)]
                if not categoria_match.empty:
                    categoria_padrao = categoria_match.iloc[0]["Opcao"]
            else:
                # Usar palavras-chave
                for _, row_palavra in df_palavras.iterrows():
                    if row_palavra["Tipo"] == tipo_lancamento and row_palavra["PalavraChave"].lower() in desc.lower():
                        categoria_padrao = row_palavra["Categoria"]
                        break

        # Buscar valores baseado no agrupamento
        if usar_categoria_vyco:
            valores = df_transacoes[df_transacoes["Categoria_Vyco"] == categoria_vyco]["Valor (R$)"].tolist()
        else:
            valores = df_transacoes[df_transacoes["Descrição"] == desc]["Valor (R$)"].tolist()
        
        # Formatar valores para exibição
        valores_formatados = []
        for v in valores:
            if isinstance(v, (int, float)):
                valores_formatados.append(f"R\\$ {abs(v):.2f}".replace(".", ","))
            else:
                valores_formatados.append(str(v))
        
        valores_texto = " - ".join(valores_formatados[:5])  # Mostrar apenas os primeiros 5 valores
        if len(valores) > 5:
            valores_texto += "..."
        
        if usar_categoria_vyco and categoria_vyco:
            total_formatado = formatar_valor_br(row['Total'])
            # Determinar se é entrada ou saída baseado no total
            tipo_icon = "🔵 ENTRADA" if row['Total'] > 0 else "🔴 SAÍDA"
            label = f"📌 **{categoria_vyco}** — {tipo_icon} — {row['Quantidade']}x transações — Total: {total_formatado}"
        else:
            label = f"📌 {desc} — {row['Quantidade']}x — Total: {valores_texto}"

        # Chave única para o selectbox
        chave_selectbox = f"{prefixo_key}_{categoria_vyco if usar_categoria_vyco else desc}_{idx}"
        
        categoria_escolhida = st.selectbox(
            label,
            options=[""] + opcoes_categorias,
            index=0 if not categoria_padrao else (opcoes_categorias.index(categoria_padrao) + 1 if categoria_padrao in opcoes_categorias else 0),
            key=chave_selectbox
        )

        if categoria_escolhida:
            categoria_final = mapa_opcao_categoria.get(categoria_escolhida, categoria_escolhida)
            # Aplicar categoria ao df_desc
            if usar_categoria_vyco:
                df_desc.loc[df_desc["Categoria_Vyco"] == categoria_vyco, "Categoria"] = categoria_final
            else:
                df_desc.loc[df_desc["Descrição"] == desc, "Categoria"] = categoria_final

    # Aplicar categorização de volta ao DataFrame original
    df_resultado = df_transacoes.copy()
    
    # Aplicar automaticamente as categorias do JSON ao DataFrame original
    if licenca_nome and licenca_nome.strip() and isinstance(df_categorias, dict):
        for chave_json, categoria_json in df_categorias.items():
            if usar_categoria_vyco:
                # Aplicar baseado na categoria Vyco
                mascara = df_resultado["Categoria_Vyco"] == chave_json
            else:
                # Aplicar baseado na descrição
                mascara = df_resultado["Descrição"] == chave_json
            
            if mascara.sum() > 0:
                df_resultado.loc[mascara, "Categoria"] = categoria_json
        

    
    for idx, row in df_desc.iterrows():
        if row["Categoria"]:
            if usar_categoria_vyco:
                # Aplicar categoria baseada na categoria Vyco
                mascara = df_resultado["Categoria_Vyco"] == row["Categoria_Vyco"]
            else:
                # Aplicar categoria baseada na descrição (modo tradicional)
                if "Descrição" in row:
                    mascara = df_resultado["Descrição"] == row["Descrição"]
                else:
                    # Fallback caso não tenha Descrição
                    continue
            df_resultado.loc[mascara, "Categoria"] = row["Categoria"]

    # Salvar categorias
    if st.button(f"💾 Salvar Categorias {tipo_lancamento}", key=f"salvar_{prefixo_key}"):
        # Se uma licença foi informada, salvar no arquivo JSON específico
        if licenca_nome and licenca_nome.strip():
            # Carregar categorias existentes do arquivo da licença
            arquivo_licenca = obter_arquivo_categorias_licenca(licenca_nome, tipo_lancamento)
            categorias_existentes = carregar_categorias_licenca(arquivo_licenca)
            
            # Converter DataFrame de categorias para dicionário (apenas categorias não vazias)
            novas_categorias = {}
            categorias_validas = 0
            
            for idx, row in df_desc.iterrows():
                # Verificar se a categoria está definida e não está vazia
                if row["Categoria"] and str(row["Categoria"]).strip():
                    # Usar categoria Vyco como chave se disponível, senão usar descrição
                    if usar_categoria_vyco and "Categoria_Vyco" in row:
                        chave_salvar = row["Categoria_Vyco"]
                    else:
                        chave_salvar = row.get("Descrição", "")
                    
                    # Só salvar se a chave também não estiver vazia
                    if chave_salvar and str(chave_salvar).strip():
                        novas_categorias[chave_salvar] = str(row["Categoria"]).strip()
                        categorias_validas += 1
            
            # Verificar se há categorias válidas para salvar
            if categorias_validas > 0:
                # Mesclar com categorias existentes
                categorias_existentes.update(novas_categorias)
                
                # Salvar no arquivo JSON da licença
                salvar_categorias_licenca(arquivo_licenca, categorias_existentes)
                st.success(f"✅ {categorias_validas} categorias {tipo_lancamento.lower()} salvas para licença {licenca_nome}!")
            else:
                st.warning("⚠️ Nenhuma categoria válida encontrada para salvar. Defina as categorias antes de salvar.")
        else:
            # Fallback para salvamento em CSV tradicional
            categorias_validas_csv = 0
            
            for idx, row in df_desc.iterrows():
                # Verificar se a categoria está definida e não está vazia
                if row["Categoria"] and str(row["Categoria"]).strip():
                    # Usar categoria Vyco como chave se disponível, senão usar descrição
                    if usar_categoria_vyco and "Categoria_Vyco" in row:
                        chave_salvar = row["Categoria_Vyco"]
                    else:
                        chave_salvar = row.get("Descrição", "")
                    
                    # Só salvar se a chave também não estiver vazia
                    if chave_salvar and str(chave_salvar).strip():
                        nova_linha = pd.DataFrame({
                            "Descricao": [str(chave_salvar).strip()],
                            "Tipo": [tipo_lancamento],
                            "Categoria": [str(row["Categoria"]).strip()]
                        })
                        df_categorias = pd.concat([df_categorias, nova_linha], ignore_index=True)
                        categorias_validas_csv += 1
            
            if categorias_validas_csv > 0:
                df_categorias = df_categorias.drop_duplicates(subset=["Descricao", "Tipo"])
                df_categorias.to_csv(categorias_salvas_path, index=False)
                st.success(f"✅ {categorias_validas_csv} categorias {tipo_lancamento.lower()} salvas!")
            else:
                st.warning("⚠️ Nenhuma categoria válida encontrada para salvar. Defina as categorias antes de salvar.")

    return df_resultado, df_desc

def obter_ip_publico():
    """Obtém o IP público do usuário para configuração do firewall"""
    try:
        response = requests.get("https://api.ipify.org?format=text", timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except:
        try:
            response = requests.get("https://httpbin.org/ip", timeout=5)
            if response.status_code == 200:
                return response.json().get("origin", "").split(",")[0].strip()
        except:
            pass
    return None

def conectar_banco():
    """Estabelece conexão com o banco PostgreSQL"""
    if not POSTGRES_AVAILABLE:
        st.error("❌ Bibliotecas PostgreSQL não disponíveis. Execute: pip install psycopg2-binary sqlalchemy")
        return None
        
    try:
        # Configurações de conexão - prioritário do .env
        host = os.getenv("DB_HOST", "prod-server-db1.postgres.database.azure.com")
        database = os.getenv("DB_NAME", "mr-backoffice-prod-db")
        port = os.getenv("DB_PORT", "5432")
        sslmode = os.getenv("DB_SSLMODE", "require")
        
        # Tentar pegar credenciais (prioridade: .env > secrets > session_state)
        user = os.getenv("DB_USER", "")
        password = os.getenv("DB_PASSWORD", "")
        
        # Fallback para secrets.toml se não estiver no .env
        if not user or not password:
            if hasattr(st, 'secrets') and "DB_USER" in st.secrets:
                user = user or st.secrets["DB_USER"]
                password = password or st.secrets["DB_PASSWORD"]
            elif "secrets" in st.session_state:
                user = user or st.session_state.secrets.get("DB_USER", "")
                password = password or st.session_state.secrets.get("DB_PASSWORD", "")
        
        if not user or not password:
            st.error("⚠️ Credenciais do banco não configuradas. Configure DB_USER e DB_PASSWORD no arquivo .env ou no secrets.toml")
            st.info("📝 **Para configurar no .env:**\n1. Edite o arquivo `.env` na raiz do projeto\n2. Substitua `seu_usuario_aqui` e `sua_senha_aqui` pelas credenciais reais")
            return None
            
        # Escapar caracteres especiais na URL
        user_encoded = quote_plus(user)
        password_encoded = quote_plus(password)
        
        # Configurações adicionais do .env
        connect_timeout = os.getenv("DB_CONNECT_TIMEOUT", "30")
        
        # String de conexão com caracteres escapados e configurações do .env
        connection_string = f"postgresql://{user_encoded}:{password_encoded}@{host}:{port}/{database}?sslmode={sslmode}&connect_timeout={connect_timeout}"
        
        # Debug: mostrar a string de conexão (sem a senha) para diagnóstico
        origem_credenciais = "arquivo .env" if os.getenv("DB_USER") else "secrets.toml/session"
        debug_string = f"postgresql://{user_encoded}:***@{host}:{port}/{database}?sslmode={sslmode}"
        #st.success(f"🔗 Conectando com credenciais do {origem_credenciais}: {debug_string}")
        
        # Configurações específicas para Azure PostgreSQL
        engine = create_engine(
            connection_string,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_args={
                "sslmode": "require",
                "connect_timeout": 30
            }
        )
        
        # Testar a conexão
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            
        st.success("✅ Conexão com banco estabelecida com sucesso!")
        return engine
        
    except Exception as e:
        error_msg = str(e)
        st.error(f"❌ Erro ao conectar com o banco de dados: {error_msg}")
        
        # Diagnósticos específicos
        if "could not translate host name" in error_msg:
            st.error("🌐 Problema de DNS/Rede:")
            st.info("• Verifique sua conexão com a internet")
            st.info("• Confirme se o hostname está correto")
            st.info("• Teste pingando: prod-server-db1.postgres.database.azure.com")
        elif "authentication failed" in error_msg or "password authentication failed" in error_msg:
            st.error("🔐 Problema de Autenticação:")
            st.info("• Verifique se usuário e senha estão corretos")
            st.info("• Confirme se o usuário tem permissão no banco")
            st.info("• Para Azure PostgreSQL, use: usuario@servidor (não apenas usuario)")
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            st.error("⏱️ Timeout de Conexão - PROBLEMA COMUM NO AZURE:")
            st.warning("🚨 **SEU IP PROVAVELMENTE NÃO ESTÁ LIBERADO NO FIREWALL DO AZURE**")
            
            # Tentar obter IP público
            ip_publico = obter_ip_publico()
            if ip_publico:
                st.info(f"🌐 **Seu IP público atual: `{ip_publico}`**")
                st.info("� **Use este IP para liberar no firewall do Azure**")
            else:
                st.info("🌐 **Não foi possível detectar seu IP automaticamente**")
                st.info("Acesse: https://whatismyipaddress.com/")
            
            st.info("�📋 **COMO RESOLVER:**")
            st.info("**1. No Portal Azure:**")
            st.info("   • Acesse 'Azure Database for PostgreSQL servers'")
            st.info("   • Selecione seu servidor: prod-server-db1")
            st.info("   • Vá em 'Connection Security' ou 'Networking'")
            st.info("   • Em 'Firewall rules', clique 'Add current client IP'")
            if ip_publico:
                st.info(f"   • Ou adicione manualmente: {ip_publico}")
            st.info("**2. Aguarde 1-2 minutos** para a regra ser aplicada")
            st.info("**3. Teste novamente** a conexão")
            
            with st.expander("🔧 Soluções Avançadas"):
                st.info("• **Rede Corporativa:** Pode precisar liberar range de IPs")
                st.info("• **VPN:** Se estiver usando VPN, libere o IP da VPN")
                st.info("• **Proxy:** Configure proxy se necessário")
                st.info("• **Contate o Admin:** Se não tiver acesso ao Portal Azure")
        elif "ssl" in error_msg.lower():
            st.error("🔒 Problema de SSL:")
            st.info("• O Azure PostgreSQL requer conexão SSL (já configurado automaticamente)")
        elif "does not exist" in error_msg.lower():
            st.error("🏢 Problema de Banco/Schema:")
            st.info("• Verifique se o banco 'mr-backoffice-prod-db' existe")
            st.info("• Confirme se o usuário tem acesso ao schema 'analytics'")
        else:
            st.error("❓ Erro Genérico:")
            st.info("• Tente novamente em alguns minutos")
            st.info("• Verifique se o servidor Azure está funcionando")
            st.info("• Contate o administrador do banco se persistir")
        
        return None

def buscar_lancamentos_vyco(licenca_id, limit=-1, offset=0):
    """Busca lançamentos do banco Vyco usando a função PostgreSQL"""
    if not POSTGRES_AVAILABLE:
        st.error("❌ Bibliotecas PostgreSQL não disponíveis.")
        return None
        
    try:
        engine = conectar_banco()
        if engine is None:
            return None
            
        # Query SQL baseada na consulta do Power BI
        query = f"""
        SELECT * 
        FROM analytics.fn_obter_lancamentos_por_licencas(
            ARRAY['{licenca_id}']::uuid[], 
            {limit}, 
            {offset}
        )
        WHERE previsaostatus = 2;
        """
        
        # Executar query
        df = pd.read_sql(query, engine)
        
        # Fechar conexão
        engine.dispose()
        
        return df
        
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados do Vyco: {str(e)}")
        return None

def processar_dados_vyco(df_raw):
    """Processa os dados brutos do Vyco para o formato padrão do sistema"""
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()
    
    try:

        
        # Mapear colunas do Vyco para o formato padrão
        # Você precisa ajustar os nomes das colunas conforme a estrutura real do seu banco
        df_processado = pd.DataFrame()
        
        # Exemplo de mapeamento - ajuste conforme suas colunas reais
        if 'descricao' in df_raw.columns:
            df_processado['Descrição'] = df_raw['descricao']
        elif 'description' in df_raw.columns:
            df_processado['Descrição'] = df_raw['description']
        else:
            df_processado['Descrição'] = 'Descrição não disponível'
            
        # NOVO: Mapear "Categoria nome" do Vyco como parâmetro de categorização
        # Vamos tentar várias possibilidades de nomes de coluna, priorizando 'categorianome'
        categoria_vyco_encontrada = False
        for col_name in ['categorianome', 'categoria_nome', 'categoria', 'category_name', 'category', 'tipo_categoria', 'nome_categoria']:
            if col_name in df_raw.columns:
                df_processado['Categoria_Vyco'] = df_raw[col_name]
                #st.success(f"✅ Coluna de categoria encontrada: '{col_name}' com {df_raw[col_name].notna().sum()} valores")
                categoria_vyco_encontrada = True
                break
        
        if not categoria_vyco_encontrada:
            df_processado['Categoria_Vyco'] = ''
            st.warning("⚠️ Nenhuma coluna de categoria encontrada no banco Vyco. Usando modo tradicional.")
            
        # Processar valores e determinar tipo baseado em categoriatipo
        if 'valor' in df_raw.columns:
            valores_brutos = df_raw['valor']
        elif 'amount' in df_raw.columns:
            valores_brutos = df_raw['amount']
        else:
            valores_brutos = pd.Series([0.0] * len(df_raw))
        
        # Aplicar lógica de Entrada/Saída baseada em categoriatipo
        if 'categoriatipo' in df_raw.columns:
            
            # Converter valores para positivo e aplicar sinal baseado no tipo
            valores_processados = []
            tipos = []
            
            for idx, row in df_raw.iterrows():
                valor_abs = abs(float(valores_brutos.iloc[idx]) if pd.notna(valores_brutos.iloc[idx]) else 0.0)
                tipo_categoria = int(row['categoriatipo']) if pd.notna(row['categoriatipo']) else -1
                
                if tipo_categoria == 0:
                    # categoriatipo = 0 = Entrada (Crédito) - valor positivo
                    valores_processados.append(valor_abs)
                    tipos.append('Crédito')
                elif tipo_categoria == 1:
                    # categoriatipo = 1 = Saída (Débito) - valor negativo
                    valores_processados.append(-valor_abs)
                    tipos.append('Débito')
                else:
                    # Tipo desconhecido - manter valor original
                    valores_processados.append(float(valores_brutos.iloc[idx]) if pd.notna(valores_brutos.iloc[idx]) else 0.0)
                    tipos.append('Crédito' if valores_processados[-1] > 0 else 'Débito')
            
            df_processado['Valor (R$)'] = valores_processados
            df_processado['Tipo'] = tipos
            
        else:
            st.warning("⚠️ Coluna 'categoriatipo' não encontrada - usando valores originais")
            df_processado['Valor (R$)'] = valores_brutos
            df_processado['Tipo'] = df_processado['Valor (R$)'].apply(
                lambda x: 'Crédito' if x > 0 else 'Débito'
            )
            
        if 'data' in df_raw.columns:
            df_processado['Data'] = pd.to_datetime(df_raw['data'])
        elif 'date' in df_raw.columns:
            df_processado['Data'] = pd.to_datetime(df_raw['date'])
        else:
            df_processado['Data'] = datetime.now()
            
        # Adicionar colunas padrão
        df_processado['Categoria'] = ''
        df_processado['Considerar'] = 'Sim'
        
        return df_processado
        
    except Exception as e:
        st.error(f"❌ Erro ao processar dados do Vyco: {str(e)}")
        return pd.DataFrame()

def resumir_por_ano(df, meses_projetados):
    """Função auxiliar para resumir dados por ano"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    df_copy = df.copy()
    colunas_numericas = df_copy.select_dtypes(include=[np.number]).columns
    
    # Agrupar por ano
    df_anual = pd.DataFrame()
    anos_disponiveis = []
    
    for col in colunas_numericas:
        if col not in df_anual.columns:
            df_anual[col] = 0
            
    return df_anual

def criar_dre_vyco(df_fluxo, plano, licenca_nome):
    """
    Cria o DataFrame do DRE incluindo dados JSON de faturamento e estoque
    """
    # Carregar dados JSON salvos
    dados_faturamento = carregar_faturamento_json(licenca_nome)
    dados_estoque = carregar_estoque_json(licenca_nome)
    
    meses = df_fluxo.columns.tolist()
    
    # Função auxiliar para criar linhas
    def linha(nome, serie):
        return pd.DataFrame([serie], index=[nome])
    
    # Função para somar por grupo
    def soma_por_grupo_local(df_fluxo, plano, grupo):
        cats = plano[plano["Grupo"] == grupo]["Categoria"].tolist()
        valores = df_fluxo.loc[df_fluxo.index.isin(cats)].sum()
        # Se for despesa, inverter o sinal para positivo
        grupos_despesas = ["Despesas", "Investimentos", "Retiradas", "Extra Operacional"]
        if any(desp in grupo for desp in grupos_despesas):
            valores = valores.abs()
        return valores
    
    # Função para somar por categoria
    def soma_por_categoria_local(df_fluxo, *categorias):
        """Soma valores por categorias específicas com busca robusta"""
        # Busca exata primeiro
        categorias_encontradas = [cat for cat in categorias if cat in df_fluxo.index]
        
        # Se não encontrou nenhuma categoria exata, tentar busca parcial
        if not categorias_encontradas:
            for categoria in categorias:
                linhas_parciais = df_fluxo.index[df_fluxo.index.str.contains(categoria, case=False, na=False)]
                if len(linhas_parciais) > 0:
                    categorias_encontradas.extend(linhas_parciais.tolist())
        
        if categorias_encontradas:
            return df_fluxo.loc[df_fluxo.index.isin(categorias_encontradas)].sum()
        else:
            # Retornar série zerada com as colunas do df_fluxo
            return pd.Series(0, index=df_fluxo.columns)
    
    # Construção do DRE por etapas
    dre = pd.DataFrame()
    
    # Criar linha de faturamento com dados JSON
    faturamento_serie = pd.Series(index=meses, dtype=float)
    for mes in meses:
        faturamento_serie[mes] = dados_faturamento.get(mes, 0.0)
    
    # Bloco 1: Faturamento e Margem de Contribuição
    dre = pd.concat([
        linha("FATURAMENTO", faturamento_serie),
        linha("RECEITA", soma_por_categoria_local(df_fluxo, "Receita de Vendas", "Receita de Serviços")),
        linha("IMPOSTOS", soma_por_grupo_local(df_fluxo, plano, "Despesas Impostos")),
        linha("DESPESA OPERACIONAL", soma_por_grupo_local(df_fluxo, plano, "Despesas Operacionais")),
    ])
    
    dre.loc["MARGEM CONTRIBUIÇÃO"] = dre.loc["RECEITA"] - dre.loc["IMPOSTOS"] - dre.loc["DESPESA OPERACIONAL"]
    
    # Bloco 2: Lucro Operacional
    dre = pd.concat([
        dre,
        linha("DESPESAS COM PESSOAL", soma_por_grupo_local(df_fluxo, plano, "Despesas RH")),
        linha("DESPESA ADMINISTRATIVA", soma_por_grupo_local(df_fluxo, plano, "Despesas Administrativas")),
    ])
    
    dre.loc["LUCRO OPERACIONAL"] = dre.loc["MARGEM CONTRIBUIÇÃO"] - dre.loc["DESPESAS COM PESSOAL"] - dre.loc["DESPESA ADMINISTRATIVA"]
    
    # Bloco 3: Lucro Líquido
    dre = pd.concat([
        dre,
        linha("INVESTIMENTOS", soma_por_grupo_local(df_fluxo, plano, "Investimentos / Aplicações")),
        linha("DESPESA EXTRA OPERACIONAL", soma_por_grupo_local(df_fluxo, plano, "Extra Operacional")),
    ])
    
    dre.loc["LUCRO LIQUIDO"] = dre.loc["LUCRO OPERACIONAL"] - dre.loc["INVESTIMENTOS"] - dre.loc["DESPESA EXTRA OPERACIONAL"]
    
    # Bloco 4: Resultado Final
    dre = pd.concat([
        dre,
        linha("RETIRADAS SÓCIOS", soma_por_grupo_local(df_fluxo, plano, "Retiradas")),
        linha("RECEITA EXTRA OPERACIONAL", soma_por_categoria_local(df_fluxo, "Receita Extra Operacional", "Outros Recebimentos")),
    ])
    
    dre.loc["RESULTADO"] = dre.loc["LUCRO LIQUIDO"] - dre.loc["RETIRADAS SÓCIOS"] + dre.loc["RECEITA EXTRA OPERACIONAL"]
    
    # Criar linha de estoque com dados JSON
    estoque_serie = pd.Series(index=meses, dtype=float)
    for mes in meses:
        estoque_serie[mes] = dados_estoque.get(mes, 0.0)
    
    # Bloco 5: Estoque e Resultado Final
    dre = pd.concat([
        dre,
        linha("ESTOQUE", estoque_serie),
    ])
    
    # RESULTADO GERENCIAL = RESULTADO + ESTOQUE
    dre.loc["RESULTADO GERENCIAL"] = dre.loc["RESULTADO"] + dre.loc["ESTOQUE"]
    
    # Adicionar coluna TOTAL (soma de todos os meses)
    dre["TOTAL"] = dre[meses].sum(axis=1)
    
    # Adicionar coluna % (percentual em relação ao faturamento)
    dre["%"] = pd.Series([0.0] * len(dre), index=dre.index)
    faturamento_total = dre.loc["FATURAMENTO", "TOTAL"]
    if faturamento_total != 0:
        for idx in dre.index:
            dre.loc[idx, "%"] = (dre.loc[idx, "TOTAL"] / faturamento_total) * 100
    
    return dre

def exibir_dre_vyco(df_fluxo, licenca_nome, path_plano="./logic/CSVs/plano_de_contas.csv"):
    """
    Função para exibir DRE com dados JSON do Vyco
    """
    try:
        plano = pd.read_csv(path_plano)
        return criar_dre_vyco(df_fluxo, plano, licenca_nome)
    except Exception as e:
        st.error(f"Erro ao criar DRE: {e}")
        return None

def exibir_fluxo_caixa_vyco(df_transacoes, licenca_nome, meses_historicos=None):
    """
    Gera e exibe o fluxo de caixa específico para Vyco usando dados JSON
    
    Parâmetros:
    - df_transacoes: DataFrame com as transações
    - licenca_nome: Nome da licença
    - meses_historicos: Número de meses históricos a exibir (None = todos)
    """
    st.markdown("## 📊 Fluxo de Caixa (por Categoria e Mês) - Vyco")

    # Verificar se o DataFrame está vazio
    if df_transacoes.empty:
        st.warning("⚠️ Não há transações para gerar o fluxo de caixa.")
        return pd.DataFrame()

    # Verificar se as colunas necessárias existem
    colunas_necessarias = ["Considerar", "Valor (R$)", "Data", "Categoria"]
    colunas_faltantes = [col for col in colunas_necessarias if col not in df_transacoes.columns]

    if colunas_faltantes:
        st.error(f"❌ Colunas necessárias ausentes: {', '.join(colunas_faltantes)}")
        return pd.DataFrame()

    # Criar cópia para não modificar o original
    df_filtrado = df_transacoes.copy()

    # Filtrar apenas transações a considerar
    if "Considerar" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["Considerar"].astype(str).str.lower() == "sim"].copy()

    # Converter valores para numérico
    df_filtrado["Valor (R$)"] = pd.to_numeric(df_filtrado["Valor (R$)"], errors="coerce").fillna(0)

    # Converter Data para datetime
    df_filtrado["Data"] = pd.to_datetime(df_filtrado["Data"], errors="coerce")
    df_filtrado = df_filtrado.dropna(subset=["Data"])

    # Criar coluna Mês-Ano
    df_filtrado["Mes"] = df_filtrado["Data"].dt.to_period("M").astype(str)

    # Criar pivot table
    df_pivot = df_filtrado.groupby(["Categoria", "Mes"])["Valor (R$)"].sum().unstack(fill_value=0)

    # Obter todos os meses únicos
    meses = sorted(df_pivot.columns)

    # Adicionar informações de tipo (Crédito/Débito)
    df_pivot["__tipo__"] = df_pivot.apply(lambda row: "Crédito" if row.sum() > 0 else "Débito", axis=1)

    # Calcular totais básicos
    receitas = df_pivot[df_pivot["__tipo__"] == "Crédito"][meses].sum()
    despesas = df_pivot[df_pivot["__tipo__"] == "Débito"][meses].sum()
    resultado = receitas + despesas  # Despesas já são negativas

    # Carregar dados JSON de faturamento e estoque
    dados_faturamento = carregar_faturamento_json(licenca_nome)
    dados_estoque = carregar_estoque_json(licenca_nome)

    # Criar linha de faturamento com dados JSON
    faturamento_valores = []
    for mes in meses:
        faturamento_valores.append(dados_faturamento.get(mes, 0.0))
    linha_fat = pd.DataFrame([faturamento_valores], index=["💰 Faturamento Bruto"], columns=meses)

    # Criar linha de estoque com dados JSON
    estoque_valores = []
    for mes in meses:
        estoque_valores.append(dados_estoque.get(mes, 0.0))
    linha_estoque = pd.DataFrame([estoque_valores], index=["📦 Estoque Final"], columns=meses)

    # Separar receitas e despesas
    df_receitas = df_pivot[df_pivot["__tipo__"] == "Crédito"].drop(columns=["__tipo__"])
    df_despesas = df_pivot[df_pivot["__tipo__"] == "Débito"].drop(columns=["__tipo__"])

    # Criar linhas de divisão
    linha_div_receitas = pd.DataFrame([[None]*len(meses)], index=["🟦 Receitas"], columns=meses)
    linha_div_despesas = pd.DataFrame([[None]*len(meses)], index=["🟥 Despesas"], columns=meses)

    # Criar linhas de totais
    linha_total_receitas = pd.DataFrame([receitas], index=["🔷 Total de Receitas"])
    linha_total_despesas = pd.DataFrame([despesas], index=["🔻 Total de Despesas"])
    linha_resultado = pd.DataFrame([resultado], index=["🏦 Resultado do Período"])

    # Concatenar tudo na ordem
    df_final = pd.concat([
        linha_fat,
        linha_div_receitas,
        df_receitas,
        linha_total_receitas,
        linha_div_despesas,
        df_despesas,
        linha_total_despesas,
        linha_resultado,
        linha_estoque
    ])

    # Calcular variações percentuais mês a mês
    if len(meses) > 1:
        df_variacoes = pd.DataFrame(index=df_final.index, columns=[f"Var. {meses[-1]}" if len(meses) == 2 
                                                                  else f"Var. {meses[-2]}/{meses[-1]}"])
        for idx in df_final.index:
            if idx in ["🟦 Receitas", "🟥 Despesas"] or pd.isna(df_final.loc[idx, meses[-1]]) or pd.isna(df_final.loc[idx, meses[-2]]):
                df_variacoes.loc[idx] = None
            else:
                def calcular_variacao_percentual_local(valor_atual, valor_anterior):
                    if valor_anterior == 0:
                        return float('inf') if valor_atual > 0 else float('-inf') if valor_atual < 0 else 0
                    return ((valor_atual - valor_anterior) / abs(valor_anterior)) * 100
                
                variacao = calcular_variacao_percentual_local(df_final.loc[idx, meses[-1]], df_final.loc[idx, meses[-2]])
                df_variacoes.loc[idx] = variacao
        df_variacoes_fmt = df_variacoes.map(lambda x: f"{x:+.1f}%" if pd.notnull(x) else "")
        df_final_com_var = pd.concat([df_final, df_variacoes_fmt], axis=1)
    else:
        df_final_com_var = df_final

    # Aplicar filtro de meses históricos se especificado
    if meses_historicos is not None and len(meses) > meses_historicos:
        meses_filtrados = meses[-meses_historicos:]
        # Manter apenas as colunas dos meses filtrados
        colunas_manter = meses_filtrados
        # Adicionar colunas de variação se existirem
        colunas_variacoes = [col for col in df_final_com_var.columns if col.startswith("Var.")]
        df_final_com_var = df_final_com_var[colunas_manter + colunas_variacoes]
        meses = meses_filtrados  # Atualizar lista de meses para os gráficos
        
        # Recalcular totais baseados nos meses filtrados
        receitas = df_pivot[df_pivot["__tipo__"] == "Crédito"][meses].sum()
        despesas = df_pivot[df_pivot["__tipo__"] == "Débito"][meses].sum()
        resultado = receitas + despesas

    # Formatar valores para exibição
    df_formatado = df_final_com_var.copy()
    for col in meses:
        df_formatado[col] = df_formatado[col].apply(lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(x) and isinstance(x, (int, float)) else "")

    # Exibir tabela formatada
    st.markdown("### 📋 Tabela de Fluxo de Caixa")
    st.dataframe(df_formatado, use_container_width=True)

    # ---------------------- GRÁFICOS EM ABAS ----------------------
    st.markdown("### 📈 Visualização Gráfica")
    abas = st.tabs([
        "Resultado Mensal",
        "Receitas vs Despesas"
    ])

    # 1. Resultado Mensal
    with abas[0]:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=meses,
            y=resultado.values,
            name="Resultado",
            marker_color=['green' if x >= 0 else 'red' for x in resultado.values]
        ))
        fig.update_layout(
            title="Resultado Mensal",
            xaxis_title="Mês",
            yaxis_title="Valor (R$)",
            template="plotly_white",
            height=500
        )
        fig.add_shape(
            type="line",
            x0=meses[0],
            y0=0,
            x1=meses[-1],
            y1=0,
            line=dict(color="black", width=1, dash="dash")
        )
        for i, valor in enumerate(resultado.values):
            fig.add_annotation(
                x=meses[i],
                y=valor,
                text=f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                showarrow=False,
                yshift=10 if valor >= 0 else -20
            )
        st.plotly_chart(fig, use_container_width=True)

    # 2. Receitas vs Despesas
    with abas[1]:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=meses,
            y=receitas.values,
            name="Receitas",
            marker_color="green"
        ))
        fig.add_trace(go.Bar(
            x=meses,
            y=despesas.values,
            name="Despesas",
            marker_color="red"
        ))
        fig.update_layout(
            title="Receitas vs Despesas",
            xaxis_title="Mês",
            yaxis_title="Valor (R$)",
            template="plotly_white",
            height=500,
            barmode='group'
        )
        st.plotly_chart(fig, use_container_width=True)

    return df_final

def coletar_faturamentos_vyco(df_transacoes, licenca_nome):
    """
    Coleta faturamentos com salvamento em JSON por licença
    """
    st.markdown("## 🧾 Cadastro de Faturamento por Mês")
    st.markdown("#### 💵 Preencha o faturamento bruto mensal:")
    
    # Exibir qual arquivo está sendo usado
    nome_limpo = "".join(c for c in licenca_nome if c.isalnum() or c in (' ', '-', '_')).rstrip()
    nome_limpo = nome_limpo.replace(' ', '_').lower()
    arquivo_json = f"./logic/CSVs/licencas/{nome_limpo}_faturamento.json"
    st.caption(f"📁 Arquivo: `{arquivo_json}`")

    # Garante que a data está em datetime
    df_transacoes["Data"] = pd.to_datetime(df_transacoes["Data"], format="%d/%m/%Y", errors="coerce")
    df_transacoes = df_transacoes.dropna(subset=["Data"])

    meses = sorted(df_transacoes["Data"].dt.to_period("M").astype(str).unique())

    # Carregar dados existentes do JSON
    dados_salvos = carregar_faturamento_json(licenca_nome)

    valores_input = {}
    dados_atualizados = {}

    for mes in meses:
        valor_antigo = dados_salvos.get(mes, 0.0)
        valor_formatado = formatar_valor_br(valor_antigo)

        col1, col2 = st.columns([1.5, 3])
        with col1:
            st.markdown(f"**Faturamento para {mes}**")
        with col2:
            input_valor = st.text_input(
                label=f"Valor do faturamento para {mes}",
                value=valor_formatado,
                key=f"faturamento_vyco_{mes}",
                label_visibility="collapsed",
                placeholder="Ex: 50.000,00"
            )
            
            try:
                # Usar função helper que trata corretamente R$ e formatação BR
                valor_numerico = converter_para_float(input_valor)
                valores_input[mes] = valor_numerico
                dados_atualizados[mes] = valor_numerico
            except:
                valores_input[mes] = 0.0
                dados_atualizados[mes] = 0.0

    # Botão para salvar
    if st.button("💾 Salvar Faturamentos", key="salvar_faturamentos_vyco"):
        if salvar_faturamento_json(licenca_nome, dados_atualizados):
            st.success("✅ Faturamentos salvos com sucesso!")
            st.rerun()

    # Exibir tabela dos dados salvos se existirem
    if dados_salvos:
        st.markdown("### 📊 Faturamentos Salvos")
        df_faturamentos = pd.DataFrame([
            {"Mês": mes, "Valor": formatar_valor_br(valor)}
            for mes, valor in dados_salvos.items()
        ])
        st.dataframe(df_faturamentos, use_container_width=True)

def coletar_estoques_vyco(df_transacoes, licenca_nome):
    """
    Coleta estoques com salvamento em JSON por licença
    """
    st.markdown("## 📦 Cadastro de Estoque Final por Mês")
    st.markdown("#### 🧾 Informe o valor do estoque no fim de cada mês:")
    
    # Exibir qual arquivo está sendo usado
    nome_limpo = "".join(c for c in licenca_nome if c.isalnum() or c in (' ', '-', '_')).rstrip()
    nome_limpo = nome_limpo.replace(' ', '_').lower()
    arquivo_json = f"./logic/CSVs/licencas/{nome_limpo}_estoque.json"
    st.caption(f"📁 Arquivo: `{arquivo_json}`")

    # Garante que datas estejam OK
    df_transacoes["Data"] = pd.to_datetime(df_transacoes["Data"], format="%d/%m/%Y", errors="coerce")
    df_transacoes = df_transacoes.dropna(subset=["Data"])
    meses = sorted(df_transacoes["Data"].dt.to_period("M").astype(str).unique())

    # Carregar dados existentes do JSON
    dados_salvos = carregar_estoque_json(licenca_nome)

    valores_input = {}
    dados_atualizados = {}

    for mes in meses:
        valor_antigo = dados_salvos.get(mes, 0.0)
        valor_formatado = formatar_valor_br(valor_antigo)

        col1, col2 = st.columns([1.5, 3])
        with col1:
            st.markdown(f"**Estoque para {mes}**")
        with col2:
            input_valor = st.text_input(
                label=f"Valor do estoque para {mes}",
                value=valor_formatado,
                key=f"estoque_vyco_{mes}",
                label_visibility="collapsed",
                placeholder="Ex: 50.000,00"
            )
            
            try:
                # Usar função helper que trata corretamente R$ e formatação BR
                valor_numerico = converter_para_float(input_valor)
                valores_input[mes] = valor_numerico
                dados_atualizados[mes] = valor_numerico
            except:
                valores_input[mes] = 0.0
                dados_atualizados[mes] = 0.0

    # Botão para salvar
    if st.button("💾 Salvar Estoques", key="salvar_estoques_vyco"):
        if salvar_estoque_json(licenca_nome, dados_atualizados):
            st.success("✅ Estoques salvos com sucesso!")
            st.rerun()

    # Exibir tabela dos dados salvos se existirem
    if dados_salvos:
        st.markdown("### 📊 Estoques Salvos")
        df_estoques = pd.DataFrame([
            {"Mês": mes, "Valor": formatar_valor_br(valor)}
            for mes, valor in dados_salvos.items()
        ])
        st.dataframe(df_estoques, use_container_width=True)

# Título principal
st.title("🔗 Integração Vyco - Análise de Dados Bancários")
st.markdown("### Análise financeira integrada com dados do sistema Vyco")

# Configuração de Tipo de Negócio
st.markdown("---")
st.subheader("🏢 Configuração do Tipo de Negócio")

col_tipo1, col_tipo2 = st.columns([2, 3])

with col_tipo1:
    # Carregar tipos disponíveis
    tipos_negocio = carregar_tipos_negocio()
    opcoes_tipo = [(key, valor["nome"]) for key, valor in tipos_negocio.items()]
    
    tipo_selecionado = st.selectbox(
        "Selecione o tipo de negócio:",
        options=[key for key, _ in opcoes_tipo],
        format_func=lambda x: next((nome for key, nome in opcoes_tipo if key == x), x),
        help="Selecione o tipo de negócio para ativar funcionalidades específicas"
    )
    
    # Salvar no session_state
    if tipo_selecionado:
        st.session_state['tipo_negocio_selecionado'] = tipo_selecionado
        
        # Ativar modo agro se necessário
        if tipo_selecionado == "agronegocio":
            ativar_modo_agro()
            st.success("🌾 Modo Agronegócio ativado!")
        else:
            # Desativar modo agro para outros tipos
            st.session_state['modo_agro'] = False

with col_tipo2:
    if tipo_selecionado and tipo_selecionado in tipos_negocio:
        tipo_info = tipos_negocio[tipo_selecionado]
        st.info(f"**{tipo_info['nome']}**")
        st.write(tipo_info['descricao'])
        
        # Mostrar funcionalidades específicas se for agronegócio
        if tipo_selecionado == "agronegocio":
            template = carregar_template_negocio("agro")
            if template and "funcionalidades_especiais" in template:
                funcionalidades = template["funcionalidades_especiais"]
                st.markdown("**🚀 Funcionalidades Especiais:**")
                for func, ativo in funcionalidades.items():
                    if ativo:
                        st.write(f"✅ {func.replace('_', ' ').title()}")
                
                # Link para página específica
                st.markdown("👉 **Acesse a página [Gestão Agro](/7_Gestao_Agro) para funcionalidades específicas**")

st.markdown("---")

# Sidebar para configurações
#st.sidebar.header("⚙️ Configurações de Conexão")
#
## Verificar status das credenciais
#env_user = os.getenv("DB_USER", "")
#env_password = os.getenv("DB_PASSWORD", "")
#
#if env_user and env_password and env_user != "seu_usuario_aqui" and env_password != "sua_senha_aqui":
#    st.sidebar.success("✅ Credenciais configuradas no arquivo .env")
#    st.sidebar.info(f"📋 Usuário: {env_user}")
#    st.sidebar.info(f"🔗 Host: {os.getenv('DB_HOST', 'N/A')}")
#    st.sidebar.info(f"🗄️ Database: {os.getenv('DB_NAME', 'N/A')}")
#else:
#    st.sidebar.error("❌ Credenciais não configuradas no .env")
#    st.sidebar.warning("📝 **Para configurar:**")
#    st.sidebar.code("""1. Edite o arquivo .env na raiz do projeto
#2. Substitua:
#   DB_USER=seu_usuario_aqui
#   DB_PASSWORD=sua_senha_aqui
#3. Pelas suas credenciais reais""")
#    
#    # Fallback: Input manual para credenciais temporárias
#    st.sidebar.markdown("---")
#    st.sidebar.markdown("**🔧 Temporário (esta sessão):**")
#    db_user = st.sidebar.text_input("Usuário do Banco:", type="default")
#    db_password = st.sidebar.text_input("Senha do Banco:", type="password")
#    
#    if db_user and db_password:
#        if "secrets" not in st.session_state:
#            st.session_state.secrets = {}
#        st.session_state.secrets["DB_USER"] = db_user
#        st.session_state.secrets["DB_PASSWORD"] = db_password

# Input para ID da licença
st.sidebar.header("🏢 Configuração da Empresa")

# Lista de licenças conhecidas (você pode expandir isso)
# Carregar licenças do CSV
licencas_conhecidas = licenca_manager.obter_licencas_dict()
licencas_ativas = licenca_manager.obter_licencas_ativas()

# Status do CSV de licenças
st.sidebar.markdown("### 📋 Licenças Disponíveis")
valido, erros = licenca_manager.validar_csv()
if valido:
    st.sidebar.success(f"✅ {len(licencas_ativas)} licenças ativas")
else:
    st.sidebar.error("❌ Erro no CSV de licenças")
    for erro in erros:
        st.sidebar.error(f"• {erro}")

opcao_licenca = st.sidebar.selectbox(
    "Selecione a Licença:",
    [""] + licencas_ativas + ["Inserir manualmente", "🔧 Gerenciar Licenças"]
)

if opcao_licenca == "🔧 Gerenciar Licenças":
    # Interface de gerenciamento de licenças
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 🔧 Gerenciar Licenças")
    
    with st.sidebar.expander("➕ Adicionar Nova Licença", expanded=False):
        novo_nome = st.text_input("Nome da Licença:", key="novo_nome")
        novo_id = st.text_input("ID da Licença (UUID):", key="novo_id")
        novas_obs = st.text_area("Observações:", key="novas_obs")
        
        if st.button("➕ Adicionar", key="btn_add"):
            if novo_nome and novo_id:
                if licenca_manager.adicionar_licenca(novo_nome, novo_id, True, novas_obs):
                    st.success(f"✅ Licença '{novo_nome}' adicionada!")
                    st.rerun()
            else:
                st.error("Nome e ID são obrigatórios")
    
    with st.sidebar.expander("🗑️ Desativar Licença", expanded=False):
        licenca_desativar = st.selectbox("Licença para desativar:", [""] + licencas_ativas, key="desativar")
        if st.button("🗑️ Desativar", key="btn_desativar"):
            if licenca_desativar:
                if licenca_manager.desativar_licenca(licenca_desativar):
                    st.success(f"✅ Licença '{licenca_desativar}' desativada!")
                    st.rerun()
    
    licenca_id = ""
    
elif opcao_licenca == "Inserir manualmente":
    licenca_id = st.sidebar.text_input(
        "ID da Licença (UUID):",
        placeholder="00000000-0000-0000-0000-000000000000"
    )
elif opcao_licenca and opcao_licenca != "":
    licenca_id = licenca_manager.obter_id_licenca(opcao_licenca)
    if licenca_id:
        st.sidebar.info(f"🔑 ID: {licenca_id[:8]}...{licenca_id[-8:]}")
    else:
        st.sidebar.error("❌ ID não encontrado para esta licença")
        licenca_id = ""
else:
    licenca_id = ""

# Configurações de consulta
st.sidebar.header("📊 Parâmetros da Consulta")
limit_registros = st.sidebar.number_input("Limite de registros (-1 = todos):", value=-1, min_value=-1)
offset_registros = st.sidebar.number_input("Offset (pular registros):", value=0, min_value=0)

# Botão de teste de conexão
st.sidebar.header("🔧 Diagnóstico")

# Botão para verificar IP público
if st.sidebar.button("🌐 Ver Meu IP Público", help="Mostra seu IP atual para configurar no firewall Azure"):
    with st.spinner("Obtendo seu IP público... ⏳"):
        ip_publico = obter_ip_publico()
        if ip_publico:
            st.sidebar.success(f"🌐 Seu IP: `{ip_publico}`")
            st.sidebar.info("👆 Use este IP no firewall do Azure")
        else:
            st.sidebar.error("❌ Não foi possível obter o IP")
            st.sidebar.info("Acesse: https://whatismyipaddress.com/")

if st.sidebar.button("🧪 Testar Conexão", help="Testa apenas a conexão com o banco, sem buscar dados"):
    with st.spinner("Testando conexão com o banco... ⏳"):
        engine = conectar_banco()
        if engine:
            engine.dispose()  # Fechar conexão de teste

# Botão para buscar dados
if st.sidebar.button("🔍 Buscar Dados do Vyco", type="primary"):
    if not licenca_id:
        st.sidebar.error("⚠️ Insira o ID da licença para continuar")
    else:
        with st.spinner("Conectando ao banco Vyco e buscando dados... ⏳"):
            # Buscar dados do banco
            df_raw = buscar_lancamentos_vyco(licenca_id, limit_registros, offset_registros)
            
            if df_raw is not None and not df_raw.empty:
                # Processar dados para o formato padrão
                df_processado = processar_dados_vyco(df_raw)
                
                if not df_processado.empty:
                    # Remover duplicatas
                    df_sem_duplicatas = remover_duplicatas(df_processado)
                    
                    # Armazenar no session_state
                    st.session_state.df_vyco_raw = df_raw
                    st.session_state.df_vyco_processado = df_sem_duplicatas
                    nova_licenca = opcao_licenca if opcao_licenca != "Inserir manualmente" else licenca_id
                    
                    # Limpar cache se mudou de licença
                    if 'licenca_atual' in st.session_state and st.session_state.licenca_atual != nova_licenca:
                        if 'resultado_fluxo' in st.session_state:
                            del st.session_state['resultado_fluxo']
                        if 'resultado_dre' in st.session_state:
                            del st.session_state['resultado_dre']
                        st.info(f"🔄 Trocando de licença: {st.session_state.licenca_atual} → {nova_licenca}")
                    
                    st.session_state.licenca_atual = nova_licenca
                else:
                    st.error("❌ Erro ao processar os dados do banco")
            else:
                st.error("❌ Nenhum dado encontrado ou erro na consulta")

# Interface principal - só mostra se houver dados carregados
if 'df_vyco_processado' in st.session_state:
    df_dados = st.session_state.df_vyco_processado
    
    st.success(f"📊 Dados carregados: {len(df_dados)} transações da licença {st.session_state.licenca_atual}")
    
    # Mostrar preview dos dados brutos
    with st.expander("👁️ Visualizar Dados Brutos do Vyco"):
        st.subheader("Dados Originais do Banco")
        if 'df_vyco_raw' in st.session_state:
            st.dataframe(st.session_state.df_vyco_raw, use_container_width=True)
        
        st.subheader("Dados Processados para Análise")
        st.dataframe(df_dados, use_container_width=True)
    
    # Separar por tipo (mesmo processo da Pré_Analise)
    df_creditos = df_dados[df_dados['Valor (R$)'] > 0].copy() if 'Valor (R$)' in df_dados.columns else pd.DataFrame()
    df_debitos = df_dados[df_dados['Valor (R$)'] <= 0].copy() if 'Valor (R$)' in df_dados.columns else pd.DataFrame()
    
    # Tabs principais
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "💰 Categorização", 
        "💹 Faturamento e Estoque", 
        "📅 Projeções", 
        "💼 Parecer Diagnóstico", 
        "🤖 Análise GPT",
        "💾 Cache de Dados",
        "📊 Relatório Executivo"
    ])
    
    with tab1:
        st.header("💰 Categorização de Transações Vyco")
        
        if not df_dados.empty:
            # Categorizar créditos
            if not df_creditos.empty:
                st.subheader("💚 Categorizar Créditos (Receitas)")
                df_creditos, df_creditos_desc = categorizar_transacoes_vyco(
                    df_creditos, 
                    prefixo_key="credito_vyco",
                    tipo_lancamento="Receita",
                    licenca_nome=st.session_state.get('licenca_atual', '')
                )
                st.session_state.df_creditos_vyco = df_creditos
                
            # Categorizar débitos
            if not df_debitos.empty:
                st.subheader("💸 Categorizar Débitos (Despesas)")
                df_debitos, df_debitos_desc = categorizar_transacoes_vyco(
                    df_debitos, 
                    prefixo_key="debito_vyco",
                    tipo_lancamento="Despesa",
                    licenca_nome=st.session_state.get('licenca_atual', '')
                )
                st.session_state.df_debitos_vyco = df_debitos
            
            # Combinar todas as transações categorizadas
            df_transacoes_total = pd.concat([df_creditos, df_debitos], ignore_index=True)
            
            # Garantir que os valores estão em formato numérico para análise
            if "Valor (R$)" in df_transacoes_total.columns:
                # Converter para numérico se necessário
                df_transacoes_total["Valor (R$)"] = pd.to_numeric(df_transacoes_total["Valor (R$)"], errors='coerce')
                # Criar uma cópia formatada apenas para exibição
                df_transacoes_total["Valor_Formatado"] = df_transacoes_total["Valor (R$)"].apply(formatar_valor_br)
            
            if "Considerar" not in df_transacoes_total.columns:
                df_transacoes_total["Considerar"] = "Sim"
            
            st.session_state.df_transacoes_total_vyco = df_transacoes_total
            
            # Filtros e exibição
            st.subheader("📋 Todas as Transações Categorizadas - Vyco")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                filtro_tipo = st.multiselect(
                    "Filtrar por Tipo:",
                    options=["Crédito", "Débito"],
                    default=["Crédito", "Débito"],
                    key="filtro_tipo_vyco"
                )
            with col2:
                # Verificar se a coluna Categoria existe antes de tentar acessá-la
                if "Categoria" in df_transacoes_total.columns:
                    categorias_disponiveis = sorted(df_transacoes_total["Categoria"].dropna().unique().tolist())
                else:
                    categorias_disponiveis = []
                
                filtro_categoria = st.multiselect(
                    "Filtrar por Categoria:",
                    options=categorias_disponiveis,
                    default=[],
                    key="filtro_categoria_vyco"
                )
            with col3:
                filtro_texto = st.text_input("Buscar na descrição:", "", key="filtro_texto_vyco")
            
            # Aplicar filtros
            df_filtrado = df_transacoes_total.copy()
            
            if filtro_tipo and len(filtro_tipo) < 2:
                if "Crédito" in filtro_tipo:
                    df_filtrado = df_filtrado[df_filtrado["Valor (R$)"] > 0]
                elif "Débito" in filtro_tipo:
                    df_filtrado = df_filtrado[df_filtrado["Valor (R$)"] <= 0]
            
            if filtro_categoria and "Categoria" in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado["Categoria"].isin(filtro_categoria)]
            
            if filtro_texto:
                df_filtrado = df_filtrado[df_filtrado["Descrição"].str.contains(filtro_texto, case=False, na=False)]
            
            # Preparar dados para exibição (com valores formatados)
            df_exibicao = df_filtrado.copy()
            if "Valor_Formatado" in df_exibicao.columns:
                # Trocar a coluna de valor pela formatada para exibição
                df_exibicao["Valor (R$)"] = df_exibicao["Valor_Formatado"]
                df_exibicao = df_exibicao.drop("Valor_Formatado", axis=1)
            
            # Exibir dados filtrados
            st.dataframe(df_exibicao, use_container_width=True)
            st.info(f"Exibindo {len(df_filtrado)} de {len(df_transacoes_total)} transações.")
            
            # Download
            output = io.BytesIO() 
            df_download = df_transacoes_total.copy()
            # Remover coluna de formatação para o Excel (manter apenas valores numéricos)
            if "Valor_Formatado" in df_download.columns:
                df_download = df_download.drop("Valor_Formatado", axis=1)
            df_download.to_excel(output, index=False)
            output.seek(0)
            
            st.download_button(
                label="📥 Baixar transações Vyco categorizadas (.xlsx)",
                data=output,
                file_name=f"transacoes_vyco_{st.session_state.licenca_atual}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with tab2:
        st.header("💹 Faturamento e Estoque - Dados Vyco")
        
        if 'df_transacoes_total_vyco' in st.session_state and 'licenca_atual' in st.session_state:
            # Status dos arquivos JSON
            st.info(f"📄 **Licença atual:** {st.session_state.licenca_atual}")
            
            # Mostrar arquivos sendo usados
            nome_limpo = "".join(c for c in st.session_state.licenca_atual if c.isalnum() or c in (' ', '-', '_')).rstrip()
            nome_limpo = nome_limpo.replace(' ', '_').lower()
            st.caption(f"📂 Dados salvos em: `./logic/CSVs/licencas/{nome_limpo}_[faturamento|estoque].json`")
            
            # Verificar se existem dados salvos
            dados_faturamento = carregar_faturamento_json(st.session_state.licenca_atual)
            dados_estoque = carregar_estoque_json(st.session_state.licenca_atual)
            
            col_status1, col_status2 = st.columns(2)
            with col_status1:
                if dados_faturamento:
                    st.success(f"✅ Faturamento: {len(dados_faturamento)} meses salvos")
                    st.caption(f"Licença: {st.session_state.licenca_atual}")
                else:
                    st.warning(f"⚠️ Nenhum faturamento salvo para **{st.session_state.licenca_atual}**")
            
            with col_status2:
                if dados_estoque:
                    st.success(f"✅ Estoque: {len(dados_estoque)} meses salvos")
                    st.caption(f"Licença: {st.session_state.licenca_atual}")
                else:
                    st.warning(f"⚠️ Nenhum estoque salvo para **{st.session_state.licenca_atual}**")
            
            st.markdown("---")
            
            # Seção de Faturamento
            coletar_faturamentos_vyco(st.session_state.df_transacoes_total_vyco, st.session_state.licenca_atual)
            
            st.markdown("---")
            
            # Seção de Estoque
            coletar_estoques_vyco(st.session_state.df_transacoes_total_vyco, st.session_state.licenca_atual)
        else:
            st.warning("⚠️ Carregue os dados da licença primeiro na aba 'Dados Vyco'")

    with tab3:
        st.header("📅 Projeções Futuras - Vyco")
        
        if 'df_transacoes_total_vyco' in st.session_state:
            # Configuração dos cenários de projeção
            st.markdown("---")
            st.subheader("⚙️ Configuração de Projeções Futuras")
            
            # Layout em colunas organizadas
            col1, col2, col3 = st.columns([2, 2, 3])
            
            with col1:
                st.markdown("##### 🔧 Parâmetros Gerais")
                inflacao_anual = st.number_input("Inflação anual (%):", min_value=0.0, max_value=100.0, value=5.0, step=0.1, key="vyco_inflacao")
                meses_futuros = st.number_input("Meses a projetar:", min_value=1, max_value=36, value=6, step=1, key="vyco_meses")
                meses_historicos = st.number_input("Meses históricos a exibir:", min_value=1, max_value=36, value=12, step=1, key="vyco_meses_hist")
            
            with col2:
                st.markdown("##### 📉 Cenário Pessimista")
                pess_receita = st.number_input("Receitas (%):", min_value=-100.0, max_value=100.0, value=-10.0, step=1.0, key="vyco_pess_rec")
                pess_despesa = st.number_input("Despesas (%):", min_value=-100.0, max_value=100.0, value=10.0, step=1.0, key="vyco_pess_desp")
            
            with col3:
                st.markdown("##### 📈 Cenário Otimista")
                otim_receita = st.number_input("Receitas (%):", min_value=-100.0, max_value=100.0, value=15.0, step=1.0, key="vyco_otim_rec")
                otim_despesa = st.number_input("Despesas (%):", min_value=-100.0, max_value=100.0, value=-5.0, step=1.0, key="vyco_otim_desp")
            
            # Informações explicativas em um expander
            with st.expander("ℹ️ Como funcionam os cenários"):
                st.markdown("""
                **”µ Cenário Realista:** Aplica apenas a inflação configurada aos valores históricos.
                
                **”´ Cenário Pessimista:** Simula uma situação desfavorável com:
                - Redução nas receitas (padrão: -10%)
                - Aumento nas despesas (padrão: +10%)
                
                **🟢 Cenário Otimista:** Simula crescimento e otimização com:
                - Aumento nas receitas (padrão: +15%)
                - Redução nas despesas (padrão: -5%)
                
                💡 *Você pode ajustar os percentuais acima conforme sua estratégia de negócio.*
                """)
            
            # Resumo visual dos cenários
            st.markdown("##### 📊 Resumo dos Cenários Configurados")
            col_res1, col_res2, col_res3 = st.columns(3)
            
            with col_res1:
                st.info(f"""
                **📊 Realista**
                - Inflação: {inflacao_anual}%
                - Projetar: {meses_futuros} meses
                - Histórico: {meses_historicos} meses
                """)
            
            with col_res2:
                st.error(f"""
                **📉 Pessimista**
                - Receitas: {pess_receita:+.0f}%
                - Despesas: {pess_despesa:+.0f}%
                """)
            
            with col_res3:
                st.success(f"""
                **🟢 Otimista**
                - Receitas: {otim_receita:+.0f}%
                - Despesas: {otim_despesa:+.0f}%
                """)
            
            st.markdown("---")
            
            # Botão centralizado
            col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
            with col_btn2:
                btn_projecoes_clicado = st.button("🚀 Gerar Projeções Vyco", key="btn_projecoes_vyco", use_container_width=True)
            
            # Processamento das projeções (fora da estrutura de colunas para usar largura total)
            if btn_projecoes_clicado:
                with st.spinner("Gerando projeções dos dados Vyco... "):
                    # Gerar dados históricos usando função específica do Vyco com filtro de meses
                    resultado_fluxo = exibir_fluxo_caixa_vyco(st.session_state.df_transacoes_total_vyco, st.session_state.licenca_atual, meses_historicos)
                    resultado_dre = exibir_dre_vyco(resultado_fluxo, st.session_state.licenca_atual)
                    
                    # 💾 SALVAR DADOS EM CACHE PARA GESTÃO AGRO
                    empresa_nome = st.session_state.get('licenca_atual', 'Empresa_Desconhecida')
                    metadata = {
                        'licenca': st.session_state.get('licenca_atual'),
                        'total_transacoes': len(st.session_state.df_transacoes_total_vyco),
                        'gerado_em': datetime.now().isoformat(),
                        'origem': 'vyco_integração'
                    }
                    
                    # Salvar fluxo de caixa
                    if not resultado_fluxo.empty:
                        arquivo_fluxo = cache_manager.salvar_fluxo_caixa(resultado_fluxo, empresa_nome, metadata)
                        if arquivo_fluxo:
                            st.info(f"💾 Fluxo de caixa atualizado: {empresa_nome}_fluxo.json")
                    
                    # Salvar DRE com detalhamento
                    if resultado_dre is not None:
                        arquivo_dre = cache_manager.salvar_dre(
                            resultado_dre, 
                            empresa_nome, 
                            metadata,
                            df_transacoes=st.session_state.df_transacoes_total_vyco
                        )
                        if arquivo_dre:
                            st.info(f"💾 DRE atualizado: {empresa_nome}_dre.json")
                    
                    # Salvar transações categorizadas para detalhamento
                    if not st.session_state.df_transacoes_total_vyco.empty:
                        arquivo_transacoes = cache_manager.salvar_transacoes(
                            st.session_state.df_transacoes_total_vyco,
                            empresa_nome,
                            metadata
                        )
                        if arquivo_transacoes:
                            st.info(f"💾 Transações salvas: {empresa_nome}_transacoes.json")

                if resultado_dre is not None:
                    st.success("✅ Projeções geradas com sucesso!")
                    st.success("💾 Dados salvos automaticamente para uso no módulo Gestão Agro!")

                    # Importar funções necessárias
                    from logic.Analises_DFC_DRE.exibir_dre import formatar_dre, highlight_rows

                    # Filtrar apenas os últimos N meses históricos para DRE e Fluxo
                    colunas_meses = [col for col in resultado_dre.columns if re.match(r'\d{4}-\d{2}', col)]
                    if len(colunas_meses) > meses_historicos:
                        colunas_manter = colunas_meses[-meses_historicos:]
                        colunas_fixas_dre = [col for col in resultado_dre.columns if not re.match(r'\d{4}-\d{2}', col)]
                        resultado_dre_filtrado = resultado_dre[colunas_manter + colunas_fixas_dre].copy()
                        
                        # Filtrar também o fluxo de caixa
                        colunas_fixas_fluxo = [col for col in resultado_fluxo.columns if not re.match(r'\d{4}-\d{2}', col)]
                        resultado_fluxo_filtrado = resultado_fluxo[colunas_manter + colunas_fixas_fluxo].copy()
                    else:
                        resultado_dre_filtrado = resultado_dre.copy()
                        resultado_fluxo_filtrado = resultado_fluxo.copy()

                    # Função para projetar valores (adaptada do sistema principal)
                    def projetar_valores_vyco(df, inflacao_anual, meses_futuros, percentual_receita=0, percentual_despesa=0):
                        from datetime import datetime
                        
                        df_projetado = df.copy()
                        colunas_meses = [col for col in df.columns if re.match(r'\d{4}-\d{2}', col)]
                        if not colunas_meses:
                            return df_projetado, []

                        # Identificar o mês atual para excluir do cálculo (mês incompleto)
                        mes_ano_atual = datetime.now().strftime("%Y-%m")

                        ultimo_mes = pd.to_datetime(colunas_meses[-1], format="%Y-%m").to_period("M")
                        meses_projetados = [ultimo_mes + i for i in range(1, meses_futuros + 1)]
                        meses_projetados = [m.strftime("%Y-%m") for m in meses_projetados]

                        # Identificar linhas calculadas (que não devem ser projetadas, mas recalculadas)
                        linhas_calculadas = [
                            "MARGEM CONTRIBUIÇÃO",
                            "MARGEM CONTRIBUICAO",
                            "LUCRO OPERACIONAL",
                            "LUCRO LIQUIDO",
                            "LUCRO LÍQUIDO",
                            "RESULTADO",
                            "RESULTADO GERENCIAL"
                        ]

                        for mes in meses_projetados:
                            df_projetado[mes] = 0
                            for idx in df_projetado.index:
                                # Verificar se é linha calculada (pular projeção)
                                eh_linha_calculada = any(calc.upper() in str(idx).upper() for calc in linhas_calculadas)
                                
                                if eh_linha_calculada:
                                    # NÃO projetar - será recalculada depois com base nas outras linhas
                                    df_projetado.loc[idx, mes] = 0
                                    continue
                                
                                tipo = df_projetado.loc[idx, "__tipo__"] if "__tipo__" in df_projetado.columns else ""
                                
                                # Calcular média dos valores históricos, EXCLUINDO o mês atual (incompleto)
                                valores_historicos = []
                                for col in colunas_meses:
                                    # Pular o mês atual (incompleto)
                                    if col == mes_ano_atual:
                                        continue
                                    
                                    val = df_projetado.loc[idx, col] if col in df_projetado.columns else 0
                                    if isinstance(val, str):
                                        val = converter_para_float(val)
                                    
                                    # INCLUIR ZEROS na média (para sazonalidade e conservadorismo)
                                    valores_historicos.append(val)
                                
                                # Calcular média como valor base
                                if valores_historicos:
                                    valor_base = sum(valores_historicos) / len(valores_historicos)
                                else:
                                    # Fallback: se não tiver nenhum histórico válido, usar 0
                                    valor_base = 0

                                inflacao_fator = (1 + inflacao_anual / 100) ** ((meses_projetados.index(mes) + 1) / 12)

                                # Aplicar projeção com base no tipo de linha e cenário
                                if "RECEITA" in str(idx).upper() or "FATURAMENTO" in str(idx).upper() or "ESTOQUE" in str(idx).upper():
                                    # RECEITAS, FATURAMENTO, ESTOQUE
                                    if percentual_receita != 0:
                                        # Cenário Pessimista ou Otimista: aplica inflação + percentual
                                        df_projetado.loc[idx, mes] = valor_base * inflacao_fator * (1 + percentual_receita / 100)
                                    else:
                                        # Cenário Realista: aplica SOMENTE inflação
                                        df_projetado.loc[idx, mes] = valor_base * inflacao_fator
                                
                                elif any(desp in str(idx).upper() for desp in ["DESPESA", "CUSTO", "GASTO"]):
                                    # DESPESAS
                                    if percentual_despesa != 0:
                                        # Cenário Pessimista ou Otimista: aplica inflação + percentual
                                        df_projetado.loc[idx, mes] = valor_base * inflacao_fator * (1 + percentual_despesa / 100)
                                    else:
                                        # Cenário Realista: aplica SOMENTE inflação
                                        df_projetado.loc[idx, mes] = valor_base * inflacao_fator
                                
                                else:
                                    # OUTRAS LINHAS (INVESTIMENTOS, RETIRADAS, SALDO, etc.)
                                    # Sempre aplica SOMENTE inflação
                                    df_projetado.loc[idx, mes] = valor_base * inflacao_fator
                        
                        # RECALCULAR linhas derivadas após projetar todas as linhas base
                        for mes in meses_projetados:
                            # Helper para pegar valor com segurança
                            def get_val(nome_linha):
                                if nome_linha in df_projetado.index:
                                    val = df_projetado.loc[nome_linha, mes]
                                    return val if pd.notna(val) else 0
                                return 0
                            
                            # MARGEM CONTRIBUIÇÃO = RECEITA - IMPOSTOS - DESPESA OPERACIONAL
                            receita = get_val("RECEITA")
                            impostos = get_val("IMPOSTOS")
                            desp_oper = get_val("DESPESA OPERACIONAL")
                            df_projetado.loc["MARGEM CONTRIBUIÇÃO", mes] = receita - impostos - desp_oper
                            
                            # LUCRO OPERACIONAL = MARGEM CONTRIBUIÇÃO - DESPESAS COM PESSOAL - DESPESA ADMINISTRATIVA
                            margem = get_val("MARGEM CONTRIBUIÇÃO")
                            desp_pessoal = get_val("DESPESAS COM PESSOAL")
                            desp_admin = get_val("DESPESA ADMINISTRATIVA")
                            df_projetado.loc["LUCRO OPERACIONAL", mes] = margem - desp_pessoal - desp_admin
                            
                            # LUCRO LIQUIDO = LUCRO OPERACIONAL - INVESTIMENTOS - DESPESA EXTRA OPERACIONAL
                            lucro_oper = get_val("LUCRO OPERACIONAL")
                            investimentos = get_val("INVESTIMENTOS")
                            desp_extra = get_val("DESPESA EXTRA OPERACIONAL")
                            df_projetado.loc["LUCRO LIQUIDO", mes] = lucro_oper - investimentos - desp_extra
                            
                            # RESULTADO = LUCRO LIQUIDO - RETIRADAS SÓCIOS + RECEITA EXTRA OPERACIONAL
                            lucro_liq = get_val("LUCRO LIQUIDO")
                            retiradas = get_val("RETIRADAS SÓCIOS")
                            receita_extra = get_val("RECEITA EXTRA OPERACIONAL")
                            df_projetado.loc["RESULTADO", mes] = lucro_liq - retiradas + receita_extra
                            
                            # RESULTADO GERENCIAL = RESULTADO + SALDO + ESTOQUE
                            resultado = get_val("RESULTADO")
                            saldo = get_val("SALDO")
                            estoque = get_val("ESTOQUE")
                            df_projetado.loc["RESULTADO GERENCIAL", mes] = resultado + saldo + estoque

                        # Recalcular totais
                        todas_colunas = [col for col in df_projetado.columns if col not in ["TOTAL", "%", "__tipo__", "__grupo__", "__ordem__"]]
                        df_projetado["TOTAL"] = df_projetado[todas_colunas].sum(axis=1)
                        
                        # Recalcular percentuais
                        if "%" in df_projetado.columns:
                            # Encontrar a linha de faturamento para calcular percentuais
                            faturamento_rows = df_projetado.index[df_projetado.index.str.contains("FATURAMENTO", case=False, na=False)]
                            if len(faturamento_rows) > 0:
                                faturamento_total = df_projetado.loc[faturamento_rows[0], "TOTAL"]
                                if faturamento_total != 0:
                                    for idx in df_projetado.index:
                                        df_projetado.loc[idx, "%"] = (df_projetado.loc[idx, "TOTAL"] / faturamento_total) * 100
                                else:
                                    df_projetado["%"] = 0.0
                            else:
                                df_projetado["%"] = 0.0

                        return df_projetado, meses_projetados

                    # Criar abas para cenários
                    abas_cenarios = st.tabs(["📊 Cenário Realista", "📉 Cenário Pessimista", "📈 Cenário Otimista"])

                    # Cenário Realista (apenas inflação)
                    with abas_cenarios[0]:
                        st.subheader("Cenário Realista (apenas inflação)")
                        dre_realista, meses_proj = projetar_valores_vyco(resultado_dre_filtrado, inflacao_anual, meses_futuros)

                        meses_exibir = [col for col in dre_realista.columns if col not in ["TOTAL", "%", "__tipo__", "__grupo__", "__ordem__"]]
                        dre_formatado = formatar_dre(dre_realista, meses_exibir)

                        st.dataframe(
                            dre_formatado.style.apply(highlight_rows, axis=1).hide(axis="index"),
                            use_container_width=True,
                            hide_index=True,
                            height=650
                        )

                    # Cenário Pessimista
                    with abas_cenarios[1]:
                        st.subheader(f"Cenário Pessimista ({pess_receita:+.0f}% receitas, {pess_despesa:+.0f}% despesas)")
                        dre_pessimista, _ = projetar_valores_vyco(resultado_dre_filtrado, inflacao_anual, meses_futuros, pess_receita, pess_despesa)

                        meses_exibir = [col for col in dre_pessimista.columns if col not in ["TOTAL", "%", "__tipo__", "__grupo__", "__ordem__"]]
                        dre_formatado = formatar_dre(dre_pessimista, meses_exibir)

                        st.dataframe(
                            dre_formatado.style.apply(highlight_rows, axis=1).hide(axis="index"),
                            use_container_width=True, 
                            hide_index=True,
                            height=650
                        )

                    # Cenário Otimista
                    with abas_cenarios[2]:
                        st.subheader(f"Cenário Otimista ({otim_receita:+.0f}% receitas, {otim_despesa:+.0f}% despesas)")
                        dre_otimista, _ = projetar_valores_vyco(resultado_dre_filtrado, inflacao_anual, meses_futuros, otim_receita, otim_despesa)

                        meses_exibir = [col for col in dre_otimista.columns if col not in ["TOTAL", "%", "__tipo__", "__grupo__", "__ordem__"]]
                        dre_formatado = formatar_dre(dre_otimista, meses_exibir)

                        st.dataframe(
                            dre_formatado.style.apply(highlight_rows, axis=1).hide(axis="index"),
                            use_container_width=True, 
                            hide_index=True,
                            height=650
                        )

                    # Salvar no estado da sessão (versões filtradas)
                    st.session_state.resultado_fluxo_vyco = resultado_fluxo_filtrado
                    st.session_state.resultado_dre_vyco = resultado_dre_filtrado

                else:
                    st.error("❌ Erro ao gerar DRE")

    with tab4:
        st.header("💼 Análise Sistema - Vyco")
        
        if st.button("🧾 Gerar Parecer Diagnóstico Vyco", key="btn_parecer_vyco"):
            if 'df_transacoes_total_vyco' in st.session_state:
                with st.spinner("Gerando parecer diagnóstico dos dados Vyco... ⏳"):
                    # Gerar fluxo de caixa com dados JSON específicos do Vyco
                    resultado_fluxo = exibir_fluxo_caixa_vyco(st.session_state.df_transacoes_total_vyco, st.session_state.licenca_atual)
                    resultado_dre = exibir_dre_vyco(resultado_fluxo, st.session_state.licenca_atual)
                    
                    # 💾 SALVAR DADOS EM CACHE PARA GESTÃO AGRO
                    empresa_nome = st.session_state.get('licenca_atual', 'Empresa_Desconhecida')
                    metadata = {
                        'licenca': st.session_state.get('licenca_atual'),
                        'total_transacoes': len(st.session_state.df_transacoes_total_vyco),
                        'gerado_em': datetime.now().isoformat(),
                        'origem': 'vyco_parecer_diagnostico'
                    }
                    
                    # Salvar fluxo de caixa
                    if not resultado_fluxo.empty:
                        arquivo_fluxo = cache_manager.salvar_fluxo_caixa(resultado_fluxo, empresa_nome, metadata)
                        if arquivo_fluxo:
                            st.info(f"💾 Fluxo de caixa atualizado: {empresa_nome}_fluxo.json")
                    
                    # Salvar DRE com detalhamento
                    if resultado_dre is not None:
                        arquivo_dre = cache_manager.salvar_dre(
                            resultado_dre, 
                            empresa_nome, 
                            metadata,
                            df_transacoes=st.session_state.df_transacoes_total_vyco
                        )
                        if arquivo_dre:
                            st.info(f"💾 DRE atualizado: {empresa_nome}_dre.json")
                    
                    # Salvar transações categorizadas para detalhamento
                    if not st.session_state.df_transacoes_total_vyco.empty:
                        arquivo_transacoes = cache_manager.salvar_transacoes(
                            st.session_state.df_transacoes_total_vyco,
                            empresa_nome,
                            metadata
                        )
                        if arquivo_transacoes:
                            st.info(f"💾 Transações salvas: {empresa_nome}_transacoes.json")
                    
                    # Exibir DRE formatado
                    if resultado_dre is not None:
                        st.success("💾 Dados salvos automaticamente para uso no módulo Gestão Agro!")
                        st.markdown("### 📊 DRE - Demonstração do Resultado do Exercício")
                        from logic.Analises_DFC_DRE.exibir_dre import formatar_dre, highlight_rows
                        meses_dre = [col for col in resultado_dre.columns if col not in ["TOTAL", "%", "__tipo__", "__grupo__", "__ordem__"]]
                        dre_formatado = formatar_dre(resultado_dre, meses_dre)
                        st.dataframe(
                            dre_formatado.style.apply(highlight_rows, axis=1).hide(axis="index"),
                            use_container_width=True,
                            height=650
                        )
                    
                    # Gerar parecer automático com dados do fluxo de caixa
                    tipo_negocio_atual = st.session_state.get('tipo_negocio_selecionado', None)
                    gerar_parecer_automatico(resultado_fluxo, tipo_negocio=tipo_negocio_atual)
    
    with tab5:
        st.header("🤖 Análise GPT - Parecer Financeiro Inteligente - Vyco")
        
        descricao_empresa = st.text_area(
            "📝 Conte um pouco sobre a empresa (dados Vyco):",
            placeholder="Ex.: área de atuação, tempo de mercado, porte, número de funcionários, etc.",
            help="Estas informações ajudarão a IA a gerar um parecer mais preciso e contextualizado.",
            key="descricao_empresa_vyco"
        )
        
        if st.button("📊 Gerar Parecer com ChatGPT (Vyco)", key="btn_gpt_vyco"):
            if not descricao_empresa.strip():
                st.warning("⚠️ Por favor, preencha a descrição da empresa antes de gerar o parecer.")
            elif 'df_transacoes_total_vyco' in st.session_state:
                with st.spinner("Gerando parecer financeiro com inteligência artificial dos dados Vyco... ⏳"):
                    # Gerar fluxo de caixa com dados JSON específicos do Vyco
                    resultado_fluxo = exibir_fluxo_caixa_vyco(st.session_state.df_transacoes_total_vyco, st.session_state.licenca_atual)
                    resultado_dre = exibir_dre_vyco(resultado_fluxo, st.session_state.licenca_atual)
                    
                    # 💾 SALVAR DADOS EM CACHE PARA GESTÃO AGRO
                    empresa_nome = st.session_state.get('licenca_atual', 'Empresa_Desconhecida')
                    metadata = {
                        'licenca': st.session_state.get('licenca_atual'),
                        'total_transacoes': len(st.session_state.df_transacoes_total_vyco),
                        'gerado_em': datetime.now().isoformat(),
                        'origem': 'vyco_parecer_gpt',
                        'descricao_empresa': descricao_empresa
                    }
                    
                    # Salvar fluxo de caixa
                    if not resultado_fluxo.empty:
                        arquivo_fluxo = cache_manager.salvar_fluxo_caixa(resultado_fluxo, empresa_nome, metadata)
                        if arquivo_fluxo:
                            st.info(f"💾 Fluxo de caixa atualizado: {empresa_nome}_fluxo.json")
                    
                    # Salvar DRE com detalhamento
                    if resultado_dre is not None:
                        arquivo_dre = cache_manager.salvar_dre(
                            resultado_dre, 
                            empresa_nome, 
                            metadata,
                            df_transacoes=st.session_state.df_transacoes_total_vyco
                        )
                        if arquivo_dre:
                            st.info(f"💾 DRE atualizado: {empresa_nome}_dre.json")
                    
                    # Salvar transações categorizadas para detalhamento
                    if not st.session_state.df_transacoes_total_vyco.empty:
                        arquivo_transacoes = cache_manager.salvar_transacoes(
                            st.session_state.df_transacoes_total_vyco,
                            empresa_nome,
                            metadata
                        )
                        if arquivo_transacoes:
                            st.info(f"💾 Transações salvas: {empresa_nome}_transacoes.json")
                    
                    # Exibir DRE formatado
                    if resultado_dre is not None:
                        st.success("💾 Dados salvos automaticamente para uso no módulo Gestão Agro!")
                        st.markdown("### 📊 DRE - Demonstração do Resultado do Exercício")
                        from logic.Analises_DFC_DRE.exibir_dre import formatar_dre, highlight_rows
                        meses_dre = [col for col in resultado_dre.columns if col not in ["TOTAL", "%", "__tipo__", "__grupo__", "__ordem__"]]
                        dre_formatado = formatar_dre(resultado_dre, meses_dre)
                        st.dataframe(
                            dre_formatado.style.apply(highlight_rows, axis=1).hide(axis="index"),
                            use_container_width=True,
                            height=600
                        )
                    
                    # Gerar parecer inteligente com dados completos
                    parecer = analisar_dfs_com_gpt(resultado_dre, resultado_fluxo, descricao_empresa)
                    
                    # 💾 SALVAR PARECER GPT EM ARQUIVO
                    if parecer:
                        # Identificar período analisado
                        colunas_meses_parecer = [col for col in resultado_dre.columns if re.match(r'\d{4}-\d{2}', col)]
                        if colunas_meses_parecer:
                            periodo_analise = f"{colunas_meses_parecer[0]} a {colunas_meses_parecer[-1]}"
                        else:
                            periodo_analise = "Período não especificado"
                        
                        arquivo_salvo = salvar_parecer_gpt(
                            licenca_nome=st.session_state.licenca_atual,
                            parecer_texto=parecer,
                            descricao_empresa=descricao_empresa,
                            periodo_analise=periodo_analise
                        )
                        
                        if arquivo_salvo:
                            st.success(f"✅ Parecer gerado com sucesso!")
                            st.info(f"💾 Parecer salvo: `{os.path.basename(arquivo_salvo)}`")
                            # Salvar no session_state para usar no relatório
                            st.session_state.ultimo_parecer_gpt = parecer
                        else:
                            st.success("✅ Parecer gerado com sucesso!")
                            st.warning("⚠️ Não foi possível salvar o parecer em arquivo")
                    else:
                        st.error("❌ Erro ao gerar parecer")
    
    # ===== TAB 6: CACHE DE DADOS =====
    with tab6:
        st.header("💾 Gerenciamento do Cache de Dados")
        
        st.markdown("""
        Visualize e gerencie todos os dados salvos em cache para análises rápidas e orçamentos.
        """)
        
        # Usar a empresa já selecionada no sidebar
        if opcao_licenca and opcao_licenca not in ["", "Inserir manualmente", "🔧 Gerenciar Licenças"]:
            empresa_cache = opcao_licenca
            st.info(f"📊 **Empresa selecionada:** {empresa_cache}")
        else:
            st.warning("⚠️ Selecione uma licença no menu lateral primeiro")
            empresa_cache = None
        
        # Botão de atualizar status
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
        with col_btn1:
            if st.button("🔄 Atualizar Status", use_container_width=True):
                st.rerun()
        
        if not empresa_cache:
            st.stop()
        
        st.markdown("---")
        
        # Verificar status do cache
        status = verificar_status_cache(empresa_cache)
        
        # Exibir cards de status
        st.subheader("📋 Status dos Arquivos de Cache")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            exibir_card_status("DRE", status['dre'])
        
        with col2:
            exibir_card_status("Fluxo", status['fluxo'])
        
        with col3:
            exibir_card_status("Transações", status['transacoes'])
        
        with col4:
            exibir_card_status("Orçamento", status['orcamento'])
        
        st.markdown("---")
        
        # Botões de ação
        st.subheader("🔧 Ações Rápidas")
        
        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
        
        with col_btn1:
            if st.button("🔄 Atualizar Cache Completo", use_container_width=True, type="primary"):
                atualizar_cache_completo(empresa_cache)
                st.rerun()
        
        with col_btn2:
            if st.button("📥 Download JSON", use_container_width=True):
                st.info("💡 Selecione qual arquivo deseja baixar nos expanders abaixo")
        
        with col_btn3:
            if st.button("📊 Estatísticas", use_container_width=True):
                total_arquivos = sum(1 for s in status.values() if s['existe'])
                st.info(f"📁 {total_arquivos} arquivos salvos no cache")
        
        with col_btn4:
            if st.button("🗑️ Limpar Cache", use_container_width=True):
                if st.checkbox("⚠️ Confirmar limpeza", key="confirm_clear"):
                    st.warning("🚧 Funcionalidade em desenvolvimento")
        
        st.markdown("---")
        
        # Expanders com preview dos dados
        st.subheader("👁️ Visualização dos Dados")
        
        # Preview DRE
        if status['dre']['existe']:
            with st.expander("📊 Preview DRE Estruturado"):
                dados_dre = cache_manager.carregar_dre(empresa_cache)
                if dados_dre and 'dre_estruturado' in dados_dre:
                    st.markdown("**Estrutura do DRE:**")
                    
                    for secao_key, secao_data in dados_dre['dre_estruturado'].items():
                        st.markdown(f"### {secao_data.get('nome_secao', secao_key)}")
                        
                        itens = secao_data.get('itens', {})
                        for item_key, item_data in itens.items():
                            tem_detalhamento = 'detalhamento' in item_data
                            icone = "✨" if tem_detalhamento else "📊"
                            st.markdown(f"{icone} **{item_key}**")
                            
                            # Mostrar total se disponível
                            valores = item_data.get('valores', {})
                            if 'TOTAL' in valores:
                                total = valores['TOTAL']
                                st.caption(f"   Total: R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    
                    # Botão de download
                    json_str = json.dumps(dados_dre, indent=2, ensure_ascii=False, default=str)
                    st.download_button(
                        label="📥 Baixar DRE completo (JSON)",
                        data=json_str,
                        file_name=f"{empresa_cache}_dre.json",
                        mime="application/json"
                    )
        
        # Preview Fluxo
        if status['fluxo']['existe']:
            with st.expander("📊 Preview Fluxo de Caixa"):
                dados_fluxo = cache_manager.carregar_fluxo_caixa(empresa_cache)
                if dados_fluxo and 'fluxo_estruturado' in dados_fluxo:
                    st.markdown("**Estrutura do Fluxo de Caixa:**")
                    
                    for grupo_key, grupo_data in dados_fluxo['fluxo_estruturado'].items():
                        st.markdown(f"### {grupo_data.get('nome_grupo', grupo_key)}")
                        
                        categorias = grupo_data.get('categorias', {})
                        st.caption(f"   {len(categorias)} categorias")
                    
                    # Botão de download
                    json_str = json.dumps(dados_fluxo, indent=2, ensure_ascii=False, default=str)
                    st.download_button(
                        label="📥 Baixar Fluxo completo (JSON)",
                        data=json_str,
                        file_name=f"{empresa_cache}_fluxo.json",
                        mime="application/json"
                    )
        
        # Preview Transações
        if status['transacoes']['existe']:
            with st.expander("📊 Preview Transações Categorizadas"):
                df_transacoes = cache_manager.carregar_transacoes(empresa_cache)
                if df_transacoes is not None and not df_transacoes.empty:
                    st.markdown(f"**Total de transações:** {len(df_transacoes):,}".replace(",", "."))
                    
                    # Mostrar primeiras 100 linhas
                    st.dataframe(
                        df_transacoes.head(100),
                        use_container_width=True,
                        height=400
                    )
                    
                    st.caption("📝 Mostrando primeiras 100 transações")
                    
                    # Estatísticas rápidas
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    
                    with col_stat1:
                        receitas = df_transacoes[df_transacoes['Valor (R$)'] > 0]['Valor (R$)'].sum()
                        st.metric("💚 Receitas", f"R$ {receitas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    
                    with col_stat2:
                        despesas = df_transacoes[df_transacoes['Valor (R$)'] < 0]['Valor (R$)'].sum()
                        st.metric("💸 Despesas", f"R$ {abs(despesas):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    
                    with col_stat3:
                        saldo = receitas + despesas
                        st.metric("💰 Saldo", f"R$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    
                    # Botão de download
                    csv = df_transacoes.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Baixar Transações (CSV)",
                        data=csv,
                        file_name=f"{empresa_cache}_transacoes.csv",
                        mime="text/csv"
                    )
        
        # Preview Orçamento
        if status['orcamento']['existe']:
            with st.expander("📊 Preview Orçamento"):
                from logic.orcamento_manager import orcamento_manager
                orcamento_data = orcamento_manager.carregar_orcamento(
                    empresa_cache,
                    status['orcamento']['ano_orcamento']
                )
                
                if orcamento_data:
                    st.markdown(f"**Ano Orçamento:** {status['orcamento']['ano_orcamento']}")
                    st.markdown(f"**Ano Base:** {status['orcamento']['ano_base']}")
                    
                    # Mostrar resumo
                    orcamento_mensal = orcamento_data.get('orcamento_mensal', {})
                    st.caption(f"📅 {len(orcamento_mensal)} meses orçados")
                    
                    # Botão de download
                    json_str = json.dumps(orcamento_data, indent=2, ensure_ascii=False, default=str)
                    st.download_button(
                        label="📥 Baixar Orçamento (JSON)",
                        data=json_str,
                        file_name=f"{empresa_cache}_orcamento_{status['orcamento']['ano_orcamento']}.json",
                        mime="application/json"
                    )
        
        # Informações adicionais
        st.markdown("---")
        st.info("""
        💡 **Dicas:**
        - Use "🔄 Atualizar Cache Completo" para garantir que os dados estejam atualizados
        - Os dados ficam salvos localmente em `./data_cache/`
        - Arquivos JSON podem ser abertos em qualquer editor de texto
        - O cache é usado pelo módulo de Orçamento para análises rápidas
        """)
    
    # ===== TAB 7: RELATÓRIO EXECUTIVO =====
    with tab7:
        st.header("📊 Relatório Executivo - Visão Consolidada")
        
        st.markdown("""
        Visão executiva consolidada de todas as análises financeiras. Este relatório integra dados de:
        - 💹 Faturamento e Estoque
        - 📅 Projeções (3 cenários)
        - 💼 Parecer Diagnóstico
        - 🤖 Análise GPT
        """)
        
        # Verificar se há dados disponíveis
        tem_transacoes = 'df_transacoes_total_vyco' in st.session_state
        tem_dre = 'resultado_dre_vyco' in st.session_state
        tem_fluxo = 'resultado_fluxo_vyco' in st.session_state
        
        if not tem_transacoes:
            st.warning("⚠️ Carregue os dados da licença e categorize as transações primeiro (Aba 1: Categorização)")
            st.stop()
        
        st.markdown("---")
        
        # ========== CONFIGURAÇÕES DO RELATÓRIO ==========
        st.subheader("⚙️ Configurações do Relatório")
        
        col_config1, col_config2 = st.columns([2, 2])
        
        with col_config1:
            st.markdown("#### 📅 Período de Análise")
            
            # Obter meses disponíveis das transações
            df_transacoes = st.session_state.df_transacoes_total_vyco
            if 'Data' in df_transacoes.columns:
                df_transacoes['Data'] = pd.to_datetime(df_transacoes['Data'], errors='coerce')
                meses_disponiveis = sorted(df_transacoes['Data'].dropna().dt.to_period('M').astype(str).unique())
                anos_disponiveis = sorted(set([m[:4] for m in meses_disponiveis]))
            else:
                meses_disponiveis = []
                anos_disponiveis = []
            
            if meses_disponiveis:
                tipo_filtro = st.radio(
                    "Tipo de filtro:",
                    ["📅 Últimos N meses", "📆 Ano completo", "🗓️ Meses específicos"],
                    key="tipo_filtro_relatorio",
                    horizontal=True
                )
                
                meses_selecionados = []
                
                if tipo_filtro == "📅 Últimos N meses":
                    num_meses = st.slider(
                        "Quantidade de meses:",
                        min_value=1,
                        max_value=len(meses_disponiveis),
                        value=min(6, len(meses_disponiveis)),
                        key="slider_meses_relatorio"
                    )
                    meses_selecionados = meses_disponiveis[-num_meses:]
                    st.caption(f"📊 Período: {meses_selecionados[0]} a {meses_selecionados[-1]}")
                
                elif tipo_filtro == "📆 Ano completo":
                    ano_selecionado = st.selectbox(
                        "Selecione o ano:",
                        anos_disponiveis,
                        index=len(anos_disponiveis)-1 if anos_disponiveis else 0,
                        key="select_ano_relatorio"
                    )
                    meses_selecionados = [m for m in meses_disponiveis if m.startswith(ano_selecionado)]
                    st.caption(f"📊 {len(meses_selecionados)} meses em {ano_selecionado}")
                
                else:  # Meses específicos
                    meses_selecionados = st.multiselect(
                        "Selecione os meses:",
                        meses_disponiveis,
                        default=meses_disponiveis[-6:] if len(meses_disponiveis) >= 6 else meses_disponiveis,
                        key="multiselect_meses_relatorio"
                    )
                    if meses_selecionados:
                        st.caption(f"📊 {len(meses_selecionados)} meses selecionados")
                
                # Salvar no session_state
                st.session_state.meses_relatorio = meses_selecionados
            else:
                st.warning("⚠️ Nenhum mês disponível nos dados")
                meses_selecionados = []
        
        with col_config2:
            st.markdown("#### 🤖 Parecer Inteligente (GPT)")
            
            # Verificar se existem pareceres salvos
            pareceres_disponiveis = listar_pareceres_gpt(st.session_state.licenca_atual)
            
            if pareceres_disponiveis:
                ultimo_parecer_info = pareceres_disponiveis[0]
                st.success(f"✅ Último parecer: {ultimo_parecer_info['data_formatada']}")
                st.caption(f"📊 Período: {ultimo_parecer_info['periodo']}")
                
                opcao_parecer = st.radio(
                    "Incluir parecer no relatório:",
                    ["📄 Usar último parecer", "📂 Escolher parecer anterior", "🤖 Gerar novo (requer GPT)", "❌ Não incluir"],
                    key="radio_parecer_relatorio"
                )
                
                if opcao_parecer == "📄 Usar último parecer":
                    parecer_selecionado = carregar_ultimo_parecer_gpt(st.session_state.licenca_atual)
                    if parecer_selecionado:
                        st.session_state.parecer_relatorio = parecer_selecionado['parecer_texto']
                        st.info(f"✅ Parecer carregado ({len(parecer_selecionado['parecer_texto'])} caracteres)")
                
                elif opcao_parecer == "📂 Escolher parecer anterior":
                    opcoes_parecer = [f"{p['data_formatada']} - {p['periodo']}" for p in pareceres_disponiveis]
                    parecer_escolhido = st.selectbox(
                        "Selecione o parecer:",
                        opcoes_parecer,
                        key="select_parecer_anterior"
                    )
                    idx_escolhido = opcoes_parecer.index(parecer_escolhido)
                    parecer_selecionado = carregar_parecer_especifico(
                        st.session_state.licenca_atual,
                        pareceres_disponiveis[idx_escolhido]['arquivo']
                    )
                    if parecer_selecionado:
                        st.session_state.parecer_relatorio = parecer_selecionado['parecer_texto']
                        st.info(f"✅ Parecer carregado ({len(parecer_selecionado['parecer_texto'])} caracteres)")
                
                elif opcao_parecer == "🤖 Gerar novo (requer GPT)":
                    st.warning("⚠️ Novo parecer será gerado ao clicar no botão abaixo")
                    st.session_state.gerar_novo_parecer = True
                    st.session_state.parecer_relatorio = None
                
                else:  # Não incluir
                    st.session_state.parecer_relatorio = None
                    st.info("ℹ️ Relatório será gerado sem parecer GPT")
            else:
                st.info("ℹ️ Nenhum parecer salvo ainda")
                st.caption("Gere um parecer na aba 'Análise GPT' primeiro")
                st.session_state.parecer_relatorio = None
        
        st.markdown("---")
        
        # Botão para gerar relatório
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            if st.button("📊 Gerar Relatório Executivo Completo", key="btn_relatorio_exec", use_container_width=True, type="primary"):
                with st.spinner("Gerando relatório executivo... ⏳"):
                    # Filtrar transações pelo período selecionado
                    meses_filtro = st.session_state.get('meses_relatorio', [])
                    df_transacoes_filtrado = st.session_state.df_transacoes_total_vyco.copy()
                    
                    if meses_filtro:
                        df_transacoes_filtrado['Data'] = pd.to_datetime(df_transacoes_filtrado['Data'], errors='coerce')
                        df_transacoes_filtrado['Mes_Periodo'] = df_transacoes_filtrado['Data'].dt.to_period('M').astype(str)
                        df_transacoes_filtrado = df_transacoes_filtrado[df_transacoes_filtrado['Mes_Periodo'].isin(meses_filtro)]
                        df_transacoes_filtrado = df_transacoes_filtrado.drop('Mes_Periodo', axis=1)
                    
                    # Gerar dados com período filtrado
                    resultado_fluxo = exibir_fluxo_caixa_vyco(
                        df_transacoes_filtrado, 
                        st.session_state.licenca_atual
                    )
                    resultado_dre = exibir_dre_vyco(
                        resultado_fluxo, 
                        st.session_state.licenca_atual
                    )
                    
                    # Filtrar DRE pelos meses selecionados
                    if meses_filtro and not resultado_dre.empty:
                        colunas_manter = [col for col in resultado_dre.columns if col in meses_filtro or not re.match(r'\d{4}-\d{2}', col)]
                        resultado_dre = resultado_dre[colunas_manter]
                        # Filtrar fluxo apenas com colunas que existem nele
                        if not resultado_fluxo.empty:
                            colunas_manter_fluxo = [col for col in colunas_manter if col in resultado_fluxo.columns]
                            resultado_fluxo = resultado_fluxo[colunas_manter_fluxo]
                    
                    st.session_state.resultado_fluxo_vyco = resultado_fluxo
                    st.session_state.resultado_dre_vyco = resultado_dre
                    st.session_state.df_transacoes_relatorio = df_transacoes_filtrado
                    st.session_state.relatorio_executivo_gerado = True
                    st.success("✅ Relatório executivo gerado com sucesso!")
                    st.rerun()
        
        # Exibir relatório se foi gerado
        if st.session_state.get('relatorio_executivo_gerado', False) and tem_dre and tem_fluxo:
            resultado_dre = st.session_state.resultado_dre_vyco
            resultado_fluxo = st.session_state.resultado_fluxo_vyco
            # Usar transações filtradas se disponível, senão usar todas
            df_transacoes = st.session_state.get('df_transacoes_relatorio', st.session_state.df_transacoes_total_vyco)
            
            # ========== 1. DASHBOARD EXECUTIVO ==========
            st.markdown("## 📊 Dashboard Executivo - Visão Geral de Todos os Meses")
            
            # Calcular métricas principais
            colunas_meses = [col for col in resultado_dre.columns if re.match(r'\d{4}-\d{2}', col)]
            
            # Função auxiliar para extrair valores
            def obter_valor_dre_mes(linha_nome, mes):
                """Extrai valor do DRE para um mês específico"""
                try:
                    if linha_nome in resultado_dre.index:
                        val = resultado_dre.loc[linha_nome, mes]
                        if isinstance(val, str):
                            val = float(val.replace('R$', '').replace('.', '').replace(',', '.').strip())
                        return float(val) if pd.notna(val) else 0
                    return 0
                except:
                    return 0
            
            # CRIAR TABELA COM TODOS OS MESES
            if colunas_meses:
                st.markdown("### 📊 Indicadores Mensais Consolidados")
                
                # Construir DataFrame com métricas de todos os meses
                metricas_todos_meses = []
                
                for mes in colunas_meses:
                    faturamento = obter_valor_dre_mes("FATURAMENTO", mes)
                    receita = obter_valor_dre_mes("RECEITA", mes)
                    impostos = obter_valor_dre_mes("IMPOSTOS", mes)
                    lucro_liquido = obter_valor_dre_mes("RESULTADO", mes)
                    lucro_operacional = obter_valor_dre_mes("LUCRO OPERACIONAL", mes)
                    estoque = obter_valor_dre_mes("ESTOQUE", mes)
                    
                    margem_liquida = (lucro_liquido / faturamento * 100) if faturamento != 0 else 0
                    margem_ebitda = ((lucro_operacional - impostos) / faturamento * 100) if faturamento != 0 else 0
                    
                    metricas_todos_meses.append({
                        'Mês': mes,
                        'Faturamento': f"R$ {abs(faturamento):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        'EBITDA': f"R$ {lucro_operacional-impostos:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        'Margem EBITDA': f"{margem_ebitda:.1f}%",
                        'Lucro Líquido': f"R$ {lucro_liquido:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        'Margem Líquida': f"{margem_liquida:.1f}%",
                        'Estoque': f"R$ {abs(estoque):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    })
                
                df_metricas = pd.DataFrame(metricas_todos_meses)
                st.dataframe(df_metricas, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                
                # CARDS DO ÚLTIMO MÊS
                ultimo_mes = colunas_meses[-1]
                st.markdown(f"### 📅 Destaques do Último Período: {ultimo_mes}")
                
                faturamento = obter_valor_dre_mes("FATURAMENTO", ultimo_mes)
                receita = obter_valor_dre_mes("RECEITA", ultimo_mes)
                impostos = obter_valor_dre_mes("IMPOSTOS", ultimo_mes)
                lucro_liquido = obter_valor_dre_mes("RESULTADO", ultimo_mes)
                resultado = obter_valor_dre_mes("RESULTADO", ultimo_mes)
                estoque = obter_valor_dre_mes("📦 Estoque Final", ultimo_mes)
                
                # Calcular métricas derivadas do último mês
                margem_liquida = (lucro_liquido / faturamento * 100) if faturamento != 0 else 0
                lucro_operacional = obter_valor_dre_mes("LUCRO OPERACIONAL", ultimo_mes)
                ebitda = lucro_operacional-impostos
                margem_ebitda = (ebitda / faturamento * 100) if faturamento != 0 else 0
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "💰 Faturamento",
                        f"R$ {abs(faturamento):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        delta=None,
                        help="Faturamento bruto do período"
                    )
                
                with col2:
                    delta_color = "normal" if lucro_liquido >= 0 else "inverse"
                    st.metric(
                        "💎 Lucro Líquido",
                        f"R$ {lucro_liquido:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        delta=f"{margem_liquida:.1f}% margem",
                        delta_color=delta_color,
                        help="Lucro líquido após todas as deduções"
                    )
                
                with col3:
                    delta_color = "normal" if ebitda >= 0 else "inverse"
                    st.metric(
                        "📈 EBITDA",
                        f"R$ {ebitda:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        delta=f"{margem_ebitda:.1f}% margem",
                        delta_color=delta_color,
                        help="Lucro antes de juros, impostos, depreciação e amortização"
                    )
                
                with col4:
                    st.metric(
                        "📦 Estoque",
                        f"R$ {abs(estoque):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        delta=None,
                        help="Valor do estoque no fim do período"
                    )
                
                st.markdown("---")
                
                # ========== 2. ANÁLISE DE PERFORMANCE ==========
                st.markdown("## 📈 Análise de Performance")
                
                # Gráfico de evolução temporal
                col_graf1, col_graf2 = st.columns(2)
                
                with col_graf1:
                    st.markdown("### 💰 Evolução do Faturamento")
                    
                    faturamentos_meses = []
                    for mes in colunas_meses:
                        try:
                            val = obter_valor_dre_mes("FATURAMENTO", mes)
                            faturamentos_meses.append(abs(val))
                        except:
                            faturamentos_meses.append(0)
                    
                    import plotly.graph_objects as go
                    
                    fig_fat = go.Figure()
                    fig_fat.add_trace(go.Bar(
                        x=colunas_meses,
                        y=faturamentos_meses,
                        name='Faturamento',
                        marker=dict(color='#1f77b4'),
                        text=[f"R$ {v:,.0f}" for v in faturamentos_meses],
                        textposition='outside'
                    ))
                    
                    fig_fat.update_layout(
                        height=300,
                        margin=dict(l=0, r=0, t=30, b=0),
                        xaxis_title="Mês",
                        yaxis_title="Valor (R$)",
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig_fat, use_container_width=True)
                
                with col_graf2:
                    st.markdown("### 💎 Evolução do Lucro Líquido")
                    
                    lucros_meses = []
                    for mes in colunas_meses:
                        try:
                            val = obter_valor_dre_mes("RESULTADO", mes)
                            lucros_meses.append(val)
                        except:
                            lucros_meses.append(0)
                    
                    fig_lucro = go.Figure()
                    fig_lucro.add_trace(go.Bar(
                        x=colunas_meses,
                        y=lucros_meses,
                        name='Lucro Líquido',
                        marker=dict(
                            color=['#e74c3c' if v < 0 else '#2ca02c' for v in lucros_meses]
                        ),
                        text=[f"R$ {v:,.0f}" for v in lucros_meses],
                        textposition='outside'
                    ))
                    
                    fig_lucro.update_layout(
                        height=300,
                        margin=dict(l=0, r=0, t=30, b=0),
                        xaxis_title="Mês",
                        yaxis_title="Valor (R$)",
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig_lucro, use_container_width=True)
                
                st.markdown("---")
                
                # ========== 3. DISTRIBUIÇÃO DE RECEITAS E DESPESAS ==========
                st.markdown("## 🔍 Composição Financeira")
                
                col_comp1, col_comp2 = st.columns(2)
                
                with col_comp1:
                    st.markdown("### 💚 Composição de Receitas")
                    
                    # Extrair receitas por categoria
                    df_receitas = df_transacoes[df_transacoes['Valor (R$)'] > 0].copy()
                    if not df_receitas.empty and 'Categoria' in df_receitas.columns:
                        receitas_cat = df_receitas.groupby('Categoria')['Valor (R$)'].sum().sort_values(ascending=False).head(5)
                        
                        fig_rec = go.Figure(data=[go.Pie(
                            labels=receitas_cat.index,
                            values=receitas_cat.values,
                            hole=0.3,
                            marker=dict(colors=['#2ecc71', '#27ae60', '#16a085', '#1abc9c', '#48c9b0'])
                        )])
                        
                        fig_rec.update_layout(
                            height=300,
                            margin=dict(l=0, r=0, t=30, b=0),
                            showlegend=True
                        )
                        
                        st.plotly_chart(fig_rec, use_container_width=True)
                    else:
                        st.info("Sem dados de receitas categorizadas")
                
                with col_comp2:
                    st.markdown("### 💸 Composição de Despesas")
                    
                    # Extrair despesas por categoria
                    df_despesas = df_transacoes[df_transacoes['Valor (R$)'] < 0].copy()
                    if not df_despesas.empty and 'Categoria' in df_despesas.columns:
                        df_despesas['Valor_Abs'] = df_despesas['Valor (R$)'].abs()
                        despesas_cat = df_despesas.groupby('Categoria')['Valor_Abs'].sum().sort_values(ascending=False).head(5)
                        
                        fig_desp = go.Figure(data=[go.Pie(
                            labels=despesas_cat.index,
                            values=despesas_cat.values,
                            hole=0.3,
                            marker=dict(colors=['#e74c3c', '#c0392b', '#e67e22', '#d35400', '#f39c12'])
                        )])
                        
                        fig_desp.update_layout(
                            height=300,
                            margin=dict(l=0, r=0, t=30, b=0),
                            showlegend=True
                        )
                        
                        st.plotly_chart(fig_desp, use_container_width=True)
                    else:
                        st.info("Sem dados de despesas categorizadas")
                
                st.markdown("---")
                
                # ========== 4. INDICADORES FINANCEIROS ==========
                st.markdown("## 📊 Indicadores Financeiros Chave")
                
                col_ind1, col_ind2, col_ind3 = st.columns(3)

                faturamento = obter_valor_dre_mes("FATURAMENTO", ultimo_mes)
                receita = obter_valor_dre_mes("RECEITA", ultimo_mes)
                impostos = obter_valor_dre_mes("IMPOSTOS", ultimo_mes)
                lucro_operacional = obter_valor_dre_mes("LUCRO OPERACIONAL",ultimo_mes)
                lucro_liquido = obter_valor_dre_mes("RESULTADO", ultimo_mes)
                resultado = obter_valor_dre_mes("RESULTADO", ultimo_mes)
                estoque = obter_valor_dre_mes("📦 Estoque Final", ultimo_mes)
                
                with col_ind1:
                    st.markdown("#### 💹 Rentabilidade")
                    
                    margem_bruta = ((lucro_operacional) / receita * 100) if receita != 0 else 0
                    margem_liquida = (lucro_liquido / receita * 100) if receita != 0 else 0
                    margem_ebitda = ((lucro_operacional - impostos) / receita * 100) if receita != 0 else 0

                    st.metric("Margem Bruta", f"{margem_bruta:.1f}%")
                    st.metric("Margem Líquida", f"{margem_liquida:.1f}%")
                    st.metric("Margem EBITDA", f"{margem_ebitda:.1f}%")
                
                with col_ind2:
                    st.markdown("#### 💰 Liquidez")
                    
                    # Calcular indicadores de liquidez
                    receitas_total = df_transacoes[df_transacoes['Valor (R$)'] > 0]['Valor (R$)'].sum()
                    total_receitas = abs(receitas_total)
                    total_despesas = abs(despesas)
                    
                    indice_liquidez = (total_receitas / total_despesas) if total_despesas != 0 else 0
                    
                    st.metric("Índice de Liquidez", f"{indice_liquidez:.2f}x")
                    st.metric("Total Receitas", f"R$ {total_receitas:,.0f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    st.metric("Total Despesas", f"R$ {total_despesas:,.0f}".replace(",", "X").replace(".", ",").replace("X", "."))
                
                with col_ind3:
                    st.markdown("#### 📈 Crescimento")
                    
                    # Calcular variação vs mês anterior se houver dados
                    if len(colunas_meses) >= 2:
                        mes_anterior = colunas_meses[-2]
                        try:
                            fat_anterior = resultado_dre.loc["FATURAMENTO", mes_anterior] if "FATURAMENTO" in resultado_dre.index else 0
                            if isinstance(fat_anterior, str):
                                fat_anterior = float(fat_anterior.replace('R$', '').replace('.', '').replace(',', '.').strip())
                            fat_anterior = float(fat_anterior) if pd.notna(fat_anterior) else 0
                            
                            variacao_fat = ((faturamento - fat_anterior) / fat_anterior * 100) if fat_anterior != 0 else 0
                            
                            #st.metric("Faturamento (MoM)", f"{faturamento}%")
                            #st.metric("Faturamento (MoM)", f"{fat_anterior}%")
                            st.metric("Variação Faturamento (MoM)", f"{variacao_fat:+.1f}%")
                        except:
                            st.metric("Variação Faturamento (MoM)", "N/A")
                    else:
                        st.metric("Variação Faturamento (MoM)", "N/A")
                    
                    # Calcular ticket médio de transações
                    num_transacoes = len(df_transacoes[df_transacoes['Valor (R$)'] > 0])
                    ticket_medio = (total_receitas / num_transacoes) if num_transacoes > 0 else 0
                    
                    st.metric("Ticket Médio", f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    st.metric("Transações", f"{num_transacoes:,}".replace(",", "."))
                
                st.markdown("---")
                
                # ========== 5. INSIGHTS E ALERTAS ==========
                st.markdown("## 💡 Insights e Recomendações")
                
                insights = []
                alertas = []
                recomendacoes = []
                
                # Análise de rentabilidade
                if margem_liquida < 5:
                    alertas.append("⚠️ **Margem líquida baixa** ({:.1f}%): Empresa opera com rentabilidade reduzida".format(margem_liquida))
                    recomendacoes.append("🎯 Revisar estrutura de custos e precificação para melhorar margens")
                elif margem_liquida > 15:
                    insights.append("✅ **Margem líquida saudável** ({:.1f}%): Empresa demonstra boa rentabilidade".format(margem_liquida))
                
                # Análise de liquidez
                if indice_liquidez < 1.0:
                    alertas.append("🚨 **Liquidez crítica** ({:.2f}x): Despesas superam receitas".format(indice_liquidez))
                    recomendacoes.append("🎯 Urgente: reduzir custos e/ou aumentar receitas para evitar déficit")
                elif indice_liquidez > 1.5:
                    insights.append("✅ **Liquidez confortável** ({:.2f}x): Receitas superam despesas com boa margem".format(indice_liquidez))
                
                # Análise de crescimento
                if len(colunas_meses) >= 2 and variacao_fat < -5:
                    alertas.append("📉 **Queda no faturamento** ({:+.1f}%): Receitas em declínio vs mês anterior".format(variacao_fat))
                    recomendacoes.append("🎯 Investigar causas da queda e implementar ações comerciais")
                elif len(colunas_meses) >= 2 and variacao_fat > 10:
                    insights.append("📈 **Crescimento forte** ({:+.1f}%): Faturamento em expansão".format(variacao_fat))
                
                # Exibir insights
                if insights:
                    st.success("### ✅ Pontos Positivos")
                    for insight in insights:
                        st.markdown(insight)
                
                # Exibir alertas
                if alertas:
                    st.warning("### ⚠️ Pontos de Atenção")
                    for alerta in alertas:
                        st.markdown(alerta)
                
                # Exibir recomendações
                if recomendacoes:
                    st.info("### 🎯 Recomendações")
                    for rec in recomendacoes:
                        st.markdown(rec)
                
                if not insights and not alertas:
                    st.info("💼 Desempenho dentro dos padrões esperados")
                
                st.markdown("---")
                
                # ========== 6. DRE COMPLETO ==========
                st.markdown("## 📊 DRE - Demonstração do Resultado do Exercício")
                
                with st.expander("📄 Ver DRE Completo", expanded=False):
                    from logic.Analises_DFC_DRE.exibir_dre import formatar_dre, highlight_rows
                    
                    # Formatar DRE
                    meses_dre = [col for col in resultado_dre.columns if col not in ["TOTAL", "%", "__tipo__", "__grupo__", "__ordem__"]]
                    dre_formatado = formatar_dre(resultado_dre, meses_dre)
                    
                    st.dataframe(
                        dre_formatado.style.apply(highlight_rows, axis=1).hide(axis="index"),
                        use_container_width=True,
                        height=600
                    )
                    
                    st.caption(f"📅 Período: {meses_dre[0]} a {meses_dre[-1]}" if meses_dre else "Sem dados")
                
                st.markdown("---")
                
                # ========== 7. FLUXO DE CAIXA COMPLETO ==========
                st.markdown("## 💰 Fluxo de Caixa Consolidado")

                with st.expander("📄 Ver Fluxo de Caixa Completo", expanded=False):
                    if not resultado_fluxo.empty:
                        # Formatar os números para o padrão brasileiro
                        resultado_fluxo_formatado = resultado_fluxo.copy()
                        for col in resultado_fluxo_formatado.select_dtypes(include=['float', 'int']).columns:
                            resultado_fluxo_formatado[col] = resultado_fluxo_formatado[col].apply(
                                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else ""
                            )

                        # Aplicar estilo para alinhar os números à direita
                        resultado_fluxo_styled = resultado_fluxo_formatado.style.set_properties(
                            subset=resultado_fluxo_formatado.select_dtypes(include=['float', 'int']).columns,
                            **{'text-align': 'right'}
                        )

                        # Exibir o DataFrame formatado
                        st.dataframe(resultado_fluxo_styled, use_container_width=True, height=600)
                        st.caption(f"📅 {len(resultado_fluxo)} categorias de fluxo")
                    else:
                        st.info("Nenhum dado de fluxo de caixa disponível")

                st.markdown("---")
                
                # ========== 8. PROJEÇÕES FUTURAS ==========
                st.markdown("## 📅 Projeções Futuras - Cenários")
                
                st.info("""
                💡 **Como gerar projeções:**
                1. Vá para a aba **📅 Projeções**
                2. Configure os parâmetros (inflação, meses futuros, cenários)
                3. Clique em **🚀 Gerar Projeções Vyco**
                4. Retorne aqui para ver as projeções no relatório
                """)
                
                # Verificar se há projeções salvas
                if 'resultado_dre_vyco' in st.session_state and not resultado_dre.empty:
                    # Identificar colunas de projeção (meses futuros)
                    meses_historicos = [col for col in resultado_dre.columns if re.match(r'\d{4}-\d{2}', col)]
                    
                    if meses_historicos:
                        with st.expander("📈 Ver Projeções de Cenários", expanded=False):
                            st.markdown("""
                            **Nota:** As projeções são geradas dinamicamente na aba **📅 Projeções**.
                            
                            Para incluir projeções neste relatório:
                            - Cenário Realista (apenas inflação)
                            - Cenário Pessimista (queda receitas + aumento despesas)
                            - Cenário Otimista (crescimento receitas + redução despesas)
                            
                            Configure os cenários na aba de projeções e volte aqui.
                            """)
                else:
                    st.caption("Gere as análises primeiro nas abas anteriores")
                
                st.markdown("---")
                
                # ========== 9. PARECER INTELIGENTE (GPT) ==========
                if st.session_state.get('parecer_relatorio'):
                    st.markdown("## 🤖 Análise Inteligente (GPT)")
                    
                    with st.expander("📄 Ver Parecer Completo", expanded=True):
                        st.markdown(st.session_state.parecer_relatorio)
                    
                    st.caption("💡 Este parecer foi gerado por Inteligência Artificial com base nos dados financeiros")
                else:
                    st.markdown("## 🤖 Análise Inteligente (GPT)")
                    st.info("""
                    ℹ️ **Nenhum parecer GPT selecionado.**
                    
                    Para incluir análise inteligente:
                    1. Configure o parecer nas opções acima (use último, escolha anterior, ou gere novo)
                    2. Clique novamente em **Gerar Relatório Executivo Completo**
                    """)
                
                st.markdown("---")
                
                # ========== 10. EXPORTAÇÃO ==========
                st.markdown("## 📥 Exportação")
                
                col_exp1, col_exp2 = st.columns(2)
                
                with col_exp1:
                    # Preparar dados para CSV
                    dados_exportacao = {
                        'Métrica': [
                            'Faturamento Bruto',
                            'Lucro Líquido',
                            'EBITDA',
                            'Estoque',
                            'Margem Líquida (%)',
                            'Margem EBITDA (%)',
                            'Índice de Liquidez',
                            'Ticket Médio'
                        ],
                        'Valor': [
                            f"R$ {abs(faturamento):,.2f}",
                            f"R$ {lucro_liquido:,.2f}",
                            f"R$ {ebitda:,.2f}",
                            f"R$ {abs(estoque):,.2f}",
                            f"{margem_liquida:.1f}%",
                            f"{margem_ebitda:.1f}%",
                            f"{indice_liquidez:.2f}x",
                            f"R$ {ticket_medio:,.2f}"
                        ]
                    }
                    
                    df_export = pd.DataFrame(dados_exportacao)
                    csv = df_export.to_csv(index=False).encode('utf-8-sig')
                    
                    st.download_button(
                        label="📊 Download Relatório (CSV)",
                        data=csv,
                        file_name=f"relatorio_executivo_{st.session_state.licenca_atual}_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col_exp2:
                    # Preparar dados para Excel
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_export.to_excel(writer, sheet_name='Resumo Executivo', index=False)
                        
                        # Adicionar DRE
                        if not resultado_dre.empty:
                            # Incluir apenas colunas que existem
                            colunas_export = colunas_meses.copy()
                            for col in ['TOTAL', '%']:
                                if col in resultado_dre.columns:
                                    colunas_export.append(col)
                            dre_export = resultado_dre[colunas_export].copy()
                            dre_export.to_excel(writer, sheet_name='DRE')
                        
                        # Adicionar transações
                        df_transacoes_export = df_transacoes[['Data', 'Descrição', 'Categoria', 'Valor (R$)']].copy()
                        df_transacoes_export.head(1000).to_excel(writer, sheet_name='Transações', index=False)
                    
                    output.seek(0)
                    
                    st.download_button(
                        label="📊 Download Relatório Completo (Excel)",
                        data=output,
                        file_name=f"relatorio_executivo_completo_{st.session_state.licenca_atual}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                st.markdown("---")
                st.success("✅ Relatório Executivo gerado com sucesso!")
                
                # Mostrar informações do período
                meses_relatorio = st.session_state.get('meses_relatorio', [])
                if meses_relatorio:
                    periodo_str = f"{meses_relatorio[0]} a {meses_relatorio[-1]}" if len(meses_relatorio) > 1 else meses_relatorio[0]
                    st.info(f"""
                    💡 **Sobre este relatório:**
                    - **Período analisado:** {periodo_str} ({len(meses_relatorio)} meses)
                    - Dados consolidados de todas as análises financeiras
                    - Métricas e KPIs atualizados automaticamente
                    - Insights gerados com base em regras de negócio
                    - {'Parecer GPT incluído' if st.session_state.get('parecer_relatorio') else 'Sem parecer GPT'}
                    - Exportação disponível em CSV e Excel
                    """)
                else:
                    st.info("""
                    💡 **Sobre este relatório:**
                    - Dados consolidados de todas as análises financeiras
                    - Métricas e KPIs atualizados automaticamente
                    - Insights gerados com base em regras de negócio
                    - Exportação disponível em CSV e Excel
                    """)
            
            else:
                st.info("👆 Clique no botão acima para gerar o relatório executivo completo")
        else:
            st.info("👆 Clique no botão acima para gerar o relatório executivo completo")

else:
    # Instruções iniciais quando não há dados carregados
    st.info("👆 Configure as opções na barra lateral e clique em 'Buscar Dados do Vyco' para começar.")
    
    # Alert para problema comum de timeout
    st.warning("⚠️ **Problema de Timeout?** Seu IP pode não estar liberado no firewall do Azure!")    

    st.markdown("""
    ### 🏢 Licenças Disponíveis:
    """)
    
    for nome, uuid_val in licencas_conhecidas.items():
        st.markdown(f"- **{nome}**")
    

# Rodapé
st.markdown("---")
st.caption("© 2025 Sistema de Análise Financeira - Integração Vyco | Versão 1.0")
