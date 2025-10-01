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
    """
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
        return df_fluxo.loc[df_fluxo.index.isin(categorias)].sum()
    
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
        linha("RECEITA EXTRA OPERACIONAL", soma_por_categoria_local(df_fluxo, "Outros Recebimentos")),
    ])
    
    dre.loc["RESULTADO"] = dre.loc["LUCRO LIQUIDO"] - dre.loc["RETIRADAS SÓCIOS"] + dre.loc["RECEITA EXTRA OPERACIONAL"]
    
    # Criar linha de estoque com dados JSON
    estoque_serie = pd.Series(index=meses, dtype=float)
    for mes in meses:
        estoque_serie[mes] = dados_estoque.get(mes, 0.0)
    
    # Bloco 5: Saldo e Resultado Final
    dre = pd.concat([
        dre,
        linha("ESTOQUE", estoque_serie),
        linha("SALDO", pd.Series([0.0] * len(meses), index=meses)),  # Placeholder para saldo
    ])
    
    dre.loc["RESULTADO GERENCIAL"] = dre.loc["RESULTADO"]
    
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

def exibir_fluxo_caixa_vyco(df_transacoes, licenca_nome):
    """
    Gera e exibe o fluxo de caixa específico para Vyco usando dados JSON
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
                valor_numerico = float(input_valor.replace(".", "").replace(",", ".").strip())
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
                valor_numerico = float(input_valor.replace(".", "").replace(",", ".").strip())
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

# Sidebar para configurações
st.sidebar.header("⚙️ Configurações de Conexão")

# Verificar status das credenciais
env_user = os.getenv("DB_USER", "")
env_password = os.getenv("DB_PASSWORD", "")

if env_user and env_password and env_user != "seu_usuario_aqui" and env_password != "sua_senha_aqui":
    st.sidebar.success("✅ Credenciais configuradas no arquivo .env")
    st.sidebar.info(f"📋 Usuário: {env_user}")
    st.sidebar.info(f"🔗 Host: {os.getenv('DB_HOST', 'N/A')}")
    st.sidebar.info(f"🗄️ Database: {os.getenv('DB_NAME', 'N/A')}")
else:
    st.sidebar.error("❌ Credenciais não configuradas no .env")
    st.sidebar.warning("📝 **Para configurar:**")
    st.sidebar.code("""1. Edite o arquivo .env na raiz do projeto
2. Substitua:
   DB_USER=seu_usuario_aqui
   DB_PASSWORD=sua_senha_aqui
3. Pelas suas credenciais reais""")
    
    # Fallback: Input manual para credenciais temporárias
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🔧 Temporário (esta sessão):**")
    db_user = st.sidebar.text_input("Usuário do Banco:", type="default")
    db_password = st.sidebar.text_input("Senha do Banco:", type="password")
    
    if db_user and db_password:
        if "secrets" not in st.session_state:
            st.session_state.secrets = {}
        st.session_state.secrets["DB_USER"] = db_user
        st.session_state.secrets["DB_PASSWORD"] = db_password

# Input para ID da licença
st.sidebar.header("🏢 Configuração da Empresa")

# Lista de licenças conhecidas (você pode expandir isso)
licencas_conhecidas = {
    "Amor Saude Caxias Centro": "ec48a041-3554-41e9-8ea7-afcc60f0a868",
    "Amor Saude Bento": "5f1c3fc7-5a15-4cb6-b0f8-335e2317a3e1",
    "Arani": "2fab261a-42ff-4ac1-8ee3-3088395e4b7c"
}

opcao_licenca = st.sidebar.selectbox(
    "Selecione a Licença:",
    [""] + list(licencas_conhecidas.keys()) + ["Inserir manualmente"]
)

if opcao_licenca == "Inserir manualmente":
    licenca_id = st.sidebar.text_input(
        "ID da Licença (UUID):",
        placeholder="00000000-0000-0000-0000-000000000000"
    )
elif opcao_licenca and opcao_licenca != "":
    licenca_id = licencas_conhecidas[opcao_licenca]
    # ID ocultado para o usuário
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
                    st.session_state.licenca_atual = opcao_licenca if opcao_licenca != "Inserir manualmente" else licenca_id
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💰 Categorização", 
        "💹 Faturamento e Estoque", 
        "📅 Projeções", 
        "💼 Parecer Diagnóstico", 
        "🤖 Análise GPT"
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
            
            # Verificar se existem dados salvos
            dados_faturamento = carregar_faturamento_json(st.session_state.licenca_atual)
            dados_estoque = carregar_estoque_json(st.session_state.licenca_atual)
            
            col_status1, col_status2 = st.columns(2)
            with col_status1:
                if dados_faturamento:
                    st.success(f"✅ Faturamento: {len(dados_faturamento)} meses salvos")
                else:
                    st.warning("⚠️ Nenhum faturamento salvo")
            
            with col_status2:
                if dados_estoque:
                    st.success(f"✅ Estoque: {len(dados_estoque)} meses salvos")
                else:
                    st.warning("⚠️ Nenhum estoque salvo")
            
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
                - Período: {meses_futuros} meses
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
                    # Gerar dados históricos usando função específica do Vyco
                    resultado_fluxo = exibir_fluxo_caixa_vyco(st.session_state.df_transacoes_total_vyco, st.session_state.licenca_atual)
                    resultado_dre = exibir_dre_vyco(resultado_fluxo, st.session_state.licenca_atual)

                if resultado_dre is not None:
                    st.success("✅ Projeções geradas com sucesso!")

                    # Importar funções necessárias
                    from logic.Analises_DFC_DRE.exibir_dre import formatar_dre, highlight_rows

                    # Função para projetar valores (adaptada do sistema principal)
                    def projetar_valores_vyco(df, inflacao_anual, meses_futuros, percentual_receita=0, percentual_despesa=0):
                        df_projetado = df.copy()
                        colunas_meses = [col for col in df.columns if re.match(r'\d{4}-\d{2}', col)]
                        if not colunas_meses:
                            return df_projetado, []

                        ultimo_mes = pd.to_datetime(colunas_meses[-1], format="%Y-%m").to_period("M")
                        meses_projetados = [ultimo_mes + i for i in range(1, meses_futuros + 1)]
                        meses_projetados = [m.strftime("%Y-%m") for m in meses_projetados]

                        for mes in meses_projetados:
                            df_projetado[mes] = 0
                            for idx in df_projetado.index:
                                tipo = df_projetado.loc[idx, "__tipo__"] if "__tipo__" in df_projetado.columns else ""
                                valor_base = df_projetado.loc[idx, colunas_meses[-1]] if colunas_meses[-1] in df_projetado.columns else 0
                                if isinstance(valor_base, str):
                                    valor_base = converter_para_float(valor_base)

                                inflacao_fator = (1 + inflacao_anual / 100) ** ((meses_projetados.index(mes) + 1) / 12)

                                if "RECEITA" in str(idx).upper() or "FATURAMENTO" in str(idx).upper():
                                    df_projetado.loc[idx, mes] = valor_base * inflacao_fator * (1 + percentual_receita / 100)
                                elif any(desp in str(idx).upper() for desp in ["DESPESA", "CUSTO", "GASTO"]):
                                    df_projetado.loc[idx, mes] = valor_base * inflacao_fator * (1 + percentual_despesa / 100)
                                else:
                                    df_projetado.loc[idx, mes] = valor_base * inflacao_fator

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
                        dre_realista, meses_proj = projetar_valores_vyco(resultado_dre, inflacao_anual, meses_futuros)

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
                        dre_pessimista, _ = projetar_valores_vyco(resultado_dre, inflacao_anual, meses_futuros, pess_receita, pess_despesa)

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
                        dre_otimista, _ = projetar_valores_vyco(resultado_dre, inflacao_anual, meses_futuros, otim_receita, otim_despesa)

                        meses_exibir = [col for col in dre_otimista.columns if col not in ["TOTAL", "%", "__tipo__", "__grupo__", "__ordem__"]]
                        dre_formatado = formatar_dre(dre_otimista, meses_exibir)

                        st.dataframe(
                            dre_formatado.style.apply(highlight_rows, axis=1).hide(axis="index"),
                            use_container_width=True, 
                            hide_index=True,
                            height=650
                        )

                    # Salvar no estado da sessão
                    st.session_state.resultado_fluxo_vyco = resultado_fluxo
                    st.session_state.resultado_dre_vyco = resultado_dre

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
                    
                    # Exibir DRE formatado
                    if resultado_dre is not None:
                        st.markdown("### 📊 DRE - Demonstração do Resultado do Exercício")
                        from logic.Analises_DFC_DRE.exibir_dre import formatar_dre, highlight_rows
                        meses_dre = [col for col in resultado_dre.columns if col not in ["TOTAL", "%", "__tipo__", "__grupo__", "__ordem__"]]
                        dre_formatado = formatar_dre(resultado_dre, meses_dre)
                        st.dataframe(
                            dre_formatado.style.apply(highlight_rows, axis=1).hide(axis="index"),
                            use_container_width=True,
                            height=600
                        )
                    
                    # Gerar parecer automático com dados do fluxo de caixa
                    gerar_parecer_automatico(resultado_fluxo)
    
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
                    
                    # Exibir DRE formatado
                    if resultado_dre is not None:
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
                
                st.success("✅ Parecer gerado com sucesso!")

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
