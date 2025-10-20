"""
Extrator específico para arquivos Excel com sistema DE/PARA inteligente
Suporta múltiplos formatos de planilhas e mapeamento automático de colunas
"""

import pandas as pd
import streamlit as st
import json
import os
import re
from datetime import datetime
import numpy as np

class ExcelExtractor:
    """
    Classe para extrair e padronizar dados de arquivos Excel
    com sistema de mapeamento DE/PARA configurável
    """
    
    def __init__(self):
        self.templates_dir = "./extractors/excel_templates"
        self.mappings_dir = "./logic/CSVs/excel_mappings"
        self._criar_diretorios()
        self.formatos_conhecidos = self._carregar_formatos_conhecidos()
    
    def _criar_diretorios(self):
        """Cria diretórios necessários se não existirem"""
        for dir_path in [self.templates_dir, self.mappings_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
    
    def _carregar_formatos_conhecidos(self):
        """Carrega formatos pré-definidos de bancos e sistemas conhecidos"""
        return {
            "bradesco": {
                "nome": "Bradesco",
                "colunas": {
                    "data": ["Data", "DATA", "Dt"],
                    "descricao": ["Descrição", "Historico", "Histórico"],
                    "valor": ["Valor", "VALOR", "Vlr"]
                },
                "formato_data": "dd/mm/yyyy",
                "separador_decimal": ",",
                "linha_cabecalho": 1
            },
            "itau": {
                "nome": "Itaú",
                "colunas": {
                    "data": ["Data", "DATA"],
                    "descricao": ["Descrição", "Lançamento"],
                    "valor": ["Valor", "VALOR"],
                    "tipo": ["Tipo", "D/C", "Débito/Crédito", "Operação"]
                },
                "formato_data": "dd/mm/yyyy",
                "separador_decimal": ",",
                "linha_cabecalho": 1
            },
            "bb": {
                "nome": "Banco do Brasil",
                "colunas": {
                    "data": ["Data", "DATA"],
                    "descricao": ["Histórico", "Descrição"],
                    "valor": ["Valor", "VALOR"],
                    "tipo": ["Tipo", "D/C", "Débito/Crédito", "Operação"]
                },
                "formato_data": "dd/mm/yyyy",
                "separador_decimal": ",",
                "linha_cabecalho": 2
            },
            "generico": {
                "nome": "Formato Genérico",
                "colunas": {
                    "data": ["Data", "DATE", "Dt", "data"],
                    "descricao": ["Descrição", "Description", "Histórico", "Historico", "Desc"],
                    "valor": ["Valor", "Value", "Amount", "Vlr", "valor"],
                    "tipo": ["Tipo", "Type", "D/C", "Débito/Crédito", "Debit/Credit", "Operação", "Operation"]
                },
                "formato_data": "dd/mm/yyyy",
                "separador_decimal": ",",
                "linha_cabecalho": 1
            }
        }
    
    def analisar_excel(self, file):
        """
        Analisa o arquivo Excel e detecta automaticamente o formato
        """
        try:
            # Ler múltiplas linhas para detectar cabeçalho
            df_sample = pd.read_excel(file, header=None, nrows=10)
            
            # Resetar posição do arquivo
            file.seek(0)
            
            # Detectar linha do cabeçalho
            linha_cabecalho = self._detectar_linha_cabecalho(df_sample)
            
            # Ler com cabeçalho correto
            df = pd.read_excel(file, header=linha_cabecalho)
            
            # Detectar mapeamento de colunas
            mapeamento = self._detectar_mapeamento_colunas(df.columns.tolist())
            
            # Detectar formato de data e valor
            formato_data = self._detectar_formato_data(df, mapeamento)
            separador_decimal = self._detectar_separador_decimal(df, mapeamento)
            
            return {
                "status": "sucesso",
                "dataframe": df,
                "mapeamento": mapeamento,
                "linha_cabecalho": linha_cabecalho,
                "formato_data": formato_data,
                "separador_decimal": separador_decimal,
                "colunas_detectadas": df.columns.tolist(),
                "preview": df.head(5)
            }
            
        except Exception as e:
            return {
                "status": "erro",
                "mensagem": f"Erro ao analisar Excel: {str(e)}"
            }
    
    def _detectar_linha_cabecalho(self, df_sample):
        """Detecta em qual linha estão os cabeçalhos"""
        for i in range(len(df_sample)):
            linha = df_sample.iloc[i]
            # Verifica se a linha contém texto que parece cabeçalho
            texto_count = sum(1 for x in linha if isinstance(x, str) and len(str(x)) > 2)
            if texto_count >= 2:  # Pelo menos 2 colunas com texto
                return i
        return 0  # Default para primeira linha
    
    def _detectar_mapeamento_colunas(self, colunas):
        """Detecta automaticamente o mapeamento das colunas"""
        mapeamento = {"data": None, "descricao": None, "valor": None, "tipo": None}
        
        colunas_lower = [str(col).lower() for col in colunas]
        
        # Detectar coluna de data
        for i, col in enumerate(colunas_lower):
            if any(palavra in col for palavra in ["data", "date", "dt"]):
                mapeamento["data"] = i
                break
        
        # Detectar coluna de descrição
        for i, col in enumerate(colunas_lower):
            if any(palavra in col for palavra in ["desc", "histórico", "historico", "lançamento", "lancamento"]):
                mapeamento["descricao"] = i
                break
        
        # Detectar coluna de valor
        for i, col in enumerate(colunas_lower):
            if any(palavra in col for palavra in ["valor", "value", "amount", "vlr"]):
                mapeamento["valor"] = i
                break
        
        # Detectar coluna de tipo (débito/crédito)
        for i, col in enumerate(colunas_lower):
            if any(palavra in col for palavra in ["tipo", "type", "d/c", "debito", "credito", "debit", "credit", "operação", "operation"]):
                mapeamento["tipo"] = i
                break
        
        return mapeamento
    
    def _detectar_formato_data(self, df, mapeamento):
        """Detecta o formato de data usado no arquivo"""
        if mapeamento["data"] is None:
            return "dd/mm/yyyy"
        
        col_data = df.iloc[:, mapeamento["data"]]
        
        # Pegar uma amostra de datas válidas
        for valor in col_data.dropna():
            if isinstance(valor, str):
                # Tentar detectar padrão dd/mm/yyyy ou mm/dd/yyyy
                if re.match(r'\d{1,2}/\d{1,2}/\d{4}', str(valor)):
                    return "dd/mm/yyyy"
                elif re.match(r'\d{4}-\d{2}-\d{2}', str(valor)):
                    return "yyyy-mm-dd"
        
        return "dd/mm/yyyy"  # Default
    
    def _detectar_separador_decimal(self, df, mapeamento):
        """Detecta se usa vírgula ou ponto como separador decimal"""
        if mapeamento["valor"] is None:
            return ","
        
        col_valor = df.iloc[:, mapeamento["valor"]]
        
        # Verificar alguns valores para detectar padrão
        for valor in col_valor.dropna().head(10):
            if isinstance(valor, str):
                if "," in str(valor) and "." in str(valor):
                    # Formato brasileiro: 1.234,56
                    return ","
                elif "," in str(valor):
                    return ","
        
        return ","  # Default brasileiro
    
    def padronizar_dados(self, df, mapeamento, formato_data="dd/mm/yyyy", separador_decimal=",", arquivo_nome=""):
        """
        Padroniza os dados para o formato padrão do sistema
        """
        try:
            df_padrao = pd.DataFrame()
            
            # Mapear Data
            if mapeamento["data"] is not None:
                col_data = df.iloc[:, mapeamento["data"]]
                df_padrao["Data"] = self._padronizar_datas(col_data, formato_data)
            else:
                df_padrao["Data"] = datetime.now().strftime("%d/%m/%Y")
            
            # Mapear Descrição
            if mapeamento["descricao"] is not None:
                df_padrao["Descrição"] = df.iloc[:, mapeamento["descricao"]].astype(str)
            else:
                df_padrao["Descrição"] = "Lançamento importado"
            
            # Mapear Valor
            if mapeamento["valor"] is not None:
                col_valor = df.iloc[:, mapeamento["valor"]]
                df_padrao["Valor (R$)"] = self._padronizar_valores(col_valor, separador_decimal)
            else:
                df_padrao["Valor (R$)"] = 0.0
            
            # Mapear Tipo de Transação (Débito/Crédito)
            if mapeamento["tipo"] is not None:
                col_tipo = df.iloc[:, mapeamento["tipo"]]
                df_padrao["Tipo Transação"] = self._padronizar_tipo_transacao(col_tipo)
            else:
                # Se não há coluna de tipo, determinar pelo valor (como antes)
                df_padrao["Tipo Transação"] = df_padrao["Valor (R$)"].apply(
                    lambda x: "Crédito" if float(str(x).replace("R$", "").replace(".", "").replace(",", ".").strip() or 0) > 0 else "Débito"
                )
            
            # Adicionar metadados
            df_padrao["Arquivo"] = arquivo_nome
            df_padrao["Tipo"] = "Excel"
            
            # Adicionar colunas de categorização (necessárias para o fluxo de análise)
            df_padrao["Considerar"] = "Sim"  # Por padrão, todas as transações são consideradas
            df_padrao["Categoria"] = "Não Categorizado"  # Categoria padrão para posterior categorização
            
            # Remover linhas com dados inválidos
            df_padrao = df_padrao.dropna(subset=["Data", "Descrição"])
            df_padrao = df_padrao[df_padrao["Descrição"] != "nan"]
            
            return {
                "status": "sucesso",
                "dataframe": df_padrao,
                "mensagem": f"✅ Excel padronizado: {len(df_padrao)} transações válidas"
            }
            
        except Exception as e:
            return {
                "status": "erro",
                "mensagem": f"Erro ao padronizar dados: {str(e)}"
            }
    
    def _padronizar_datas(self, col_data, formato_data):
        """Padroniza coluna de datas"""
        datas_padrao = []
        
        for valor in col_data:
            try:
                if pd.isna(valor):
                    datas_padrao.append(None)
                    continue
                
                # Se já é datetime
                if isinstance(valor, pd.Timestamp):
                    datas_padrao.append(valor.strftime("%d/%m/%Y"))
                    continue
                
                # Converter string para datetime
                valor_str = str(valor).strip()
                
                if formato_data == "dd/mm/yyyy":
                    # Tentar formatos comuns
                    for fmt in ["%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"]:
                        try:
                            dt = datetime.strptime(valor_str, fmt)
                            datas_padrao.append(dt.strftime("%d/%m/%Y"))
                            break
                        except:
                            continue
                    else:
                        datas_padrao.append(None)
                
                elif formato_data == "yyyy-mm-dd":
                    dt = datetime.strptime(valor_str, "%Y-%m-%d")
                    datas_padrao.append(dt.strftime("%d/%m/%Y"))
                
                else:
                    datas_padrao.append(None)
                    
            except:
                datas_padrao.append(None)
        
        return datas_padrao
    
    def _padronizar_valores(self, col_valor, separador_decimal):
        """Padroniza coluna de valores monetários"""
        valores_padrao = []
        
        for valor in col_valor:
            try:
                if pd.isna(valor):
                    valores_padrao.append(0.0)
                    continue
                
                # Se já é numérico
                if isinstance(valor, (int, float)):
                    valores_padrao.append(float(valor))
                    continue
                
                # Limpar string
                valor_str = str(valor).strip()
                valor_str = re.sub(r'[R$\s]', '', valor_str)  # Remove R$ e espaços
                
                if separador_decimal == ",":
                    # Formato brasileiro: 1.234,56
                    valor_str = valor_str.replace(".", "")  # Remove milhares
                    valor_str = valor_str.replace(",", ".")  # Troca vírgula por ponto
                
                # Converter para float
                valor_num = float(valor_str)
                valores_padrao.append(valor_num)
                
            except:
                valores_padrao.append(0.0)
        
        return valores_padrao
    
    def _padronizar_tipo_transacao(self, col_tipo):
        """Padroniza os tipos de transação para Débito/Crédito"""
        tipos_padronizados = []
        
        for valor in col_tipo:
            if pd.isna(valor):
                tipos_padronizados.append("Débito")  # Default
                continue
            
            valor_str = str(valor).lower().strip()
            
            # Mapear diferentes formatos para Débito/Crédito
            # IMPORTANTE: Verificar palavras completas primeiro para evitar conflitos
            if any(palavra in valor_str for palavra in ["crédito", "credito", "credit", "entrada", "recebimento"]):
                tipos_padronizados.append("Crédito")
            elif any(palavra in valor_str for palavra in ["débito", "debito", "debit", "saída", "saida", "pagamento"]):
                tipos_padronizados.append("Débito")
            elif valor_str in ["c", "+", "entrada"]:  # Verificar caracteres únicos apenas depois
                tipos_padronizados.append("Crédito")
            elif valor_str in ["d", "-", "saida"]:
                tipos_padronizados.append("Débito")
            else:
                # Se não conseguir identificar, tentar pelo valor numérico se disponível
                if valor_str.replace(".", "").replace(",", "").replace("-", "").replace("+", "").isdigit():
                    if "-" in valor_str or valor_str.startswith("("):
                        tipos_padronizados.append("Débito")
                    else:
                        tipos_padronizados.append("Crédito")
                else:
                    tipos_padronizados.append("Débito")  # Default
        
        return tipos_padronizados
    
    def salvar_template(self, nome_template, mapeamento, configuracoes):
        """Salva um template de mapeamento para reutilização"""
        template = {
            "nome": nome_template,
            "mapeamento": mapeamento,
            "configuracoes": configuracoes,
            "criado_em": datetime.now().isoformat()
        }
        
        arquivo_template = os.path.join(self.templates_dir, f"{nome_template}.json")
        
        try:
            with open(arquivo_template, 'w', encoding='utf-8') as f:
                json.dump(template, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            st.error(f"Erro ao salvar template: {e}")
            return False
    
    def carregar_templates(self):
        """Carrega todos os templates salvos"""
        templates = {}
        
        if os.path.exists(self.templates_dir):
            for arquivo in os.listdir(self.templates_dir):
                if arquivo.endswith('.json'):
                    try:
                        with open(os.path.join(self.templates_dir, arquivo), 'r', encoding='utf-8') as f:
                            template = json.load(f)
                            nome = os.path.splitext(arquivo)[0]
                            templates[nome] = template
                    except Exception as e:
                        st.warning(f"Erro ao carregar template {arquivo}: {e}")
        
        return templates

# Função principal para integração
def extrair_lancamentos_excel_inteligente(file, nome_arquivo):
    """
    Função principal para extrair lançamentos de Excel com sistema inteligente
    """
    extractor = ExcelExtractor()
    
    # Analisar arquivo
    analise = extractor.analisar_excel(file)
    
    if analise["status"] == "erro":
        return analise
    
    # Para agora, usar mapeamento automático detectado
    # (mais tarde será integrado com interface visual)
    resultado_padronizacao = extractor.padronizar_dados(
        analise["dataframe"],
        analise["mapeamento"],
        analise["formato_data"],
        analise["separador_decimal"],
        nome_arquivo
    )
    
    if resultado_padronizacao["status"] == "sucesso":
        df_final = resultado_padronizacao["dataframe"]
        
        return {
            "status": "sucesso",
            "transacoes": df_final,
            "mensagem": f"📊 {nome_arquivo} → Excel Inteligente → {len(df_final)} transações",
            "tipo": "excel_inteligente",
            "detalhes": {
                "mapeamento_detectado": analise["mapeamento"],
                "formato_data": analise["formato_data"],
                "separador_decimal": analise["separador_decimal"],
                "colunas_originais": analise["colunas_detectadas"]
            }
        }
    else:
        return resultado_padronizacao