"""
Módulo para gerenciar cache de dados do DRE e Fluxo de Caixa
Salva os dados em JSON para uso posterior no módulo de Gestão Agro
"""

import json
import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import streamlit as st


class DataCacheManager:
    """Gerenciador de cache para dados de DRE e Fluxo de Caixa"""
    
    def __init__(self, base_path: str = "./data_cache"):
        self.base_path = base_path
        self.fluxo_path = os.path.join(base_path, "fluxo_caixa")
        self.dre_path = os.path.join(base_path, "dre")
        
        # Criar diretórios se não existirem
        os.makedirs(self.fluxo_path, exist_ok=True)
        os.makedirs(self.dre_path, exist_ok=True)
    
    def _sanitize_filename(self, name: str) -> str:
        """Remove caracteres especiais do nome do arquivo"""
        import re
        return re.sub(r'[<>:"/\\|?*]', '_', name).strip()
    
    def salvar_fluxo_caixa(self, df_fluxo: pd.DataFrame, empresa_nome: str, metadata: Dict = None) -> str:
        """
        Salva dados do fluxo de caixa em JSON com estrutura organizada (substitui arquivo existente)
        
        Args:
            df_fluxo: DataFrame com dados do fluxo de caixa
            empresa_nome: Nome da empresa
            metadata: Informações adicionais (licença, período, etc.)
        
        Returns:
            Caminho do arquivo salvo
        """
        try:
            filename = f"{self._sanitize_filename(empresa_nome)}_fluxo.json"
            filepath = os.path.join(self.fluxo_path, filename)
            
            # Estruturar dados do fluxo de caixa por categoria
            fluxo_estruturado = {}
            
            if not df_fluxo.empty:
                # Processar DataFrame do fluxo (geralmente tem categorias como índice e meses como colunas)
                for categoria in df_fluxo.index:
                    linha_dados = df_fluxo.loc[categoria].to_dict()
                    
                    # Determinar grupo da categoria baseado no nome
                    grupo = "Outras"
                    categoria_lower = str(categoria).lower()
                    
                    if any(term in categoria_lower for term in ["receita", "faturamento", "vendas", "serviços"]):
                        grupo = "Receitas"
                    elif any(term in categoria_lower for term in ["imposto", "taxa", "tributo"]):
                        grupo = "Impostos e Taxas"
                    elif any(term in categoria_lower for term in ["custo", "direto", "operacional"]):
                        grupo = "Custos Diretos"
                    elif any(term in categoria_lower for term in ["pessoal", "salário", "funcionário", "rh"]):
                        grupo = "Despesas com Pessoal"
                    elif any(term in categoria_lower for term in ["administrativ", "escritório", "aluguel", "telefone"]):
                        grupo = "Despesas Administrativas"
                    elif any(term in categoria_lower for term in ["investimento", "aplicação", "ativo"]):
                        grupo = "Investimentos"
                    elif any(term in categoria_lower for term in ["retirada", "sócio", "distribuição"]):
                        grupo = "Retiradas e Distribuições"
                    elif any(term in categoria_lower for term in ["estoque", "inventário"]):
                        grupo = "Estoque"
                    
                    if grupo not in fluxo_estruturado:
                        fluxo_estruturado[grupo] = {
                            "nome_grupo": grupo,
                            "categorias": {}
                        }
                    
                    fluxo_estruturado[grupo]["categorias"][categoria] = {
                        "nome_categoria": categoria,
                        "valores_mensais": linha_dados
                    }
            
            # Preparar dados para salvamento
            data = {
                "empresa": empresa_nome,
                "timestamp": datetime.now().isoformat(),
                "tipo": "fluxo_caixa_estruturado",
                "metadata": metadata or {},
                "estrutura": "grupos_organizados",
                "fluxo_estruturado": fluxo_estruturado,
                # Manter dados brutos para compatibilidade
                "dados": df_fluxo.to_dict('records') if not df_fluxo.empty else [],
                "dados_indexados": df_fluxo.to_dict('index') if not df_fluxo.empty else {}
            }
            
            # Calcular totais por grupo
            if fluxo_estruturado:
                grupos_totais = {}
                for grupo_key, grupo_data in fluxo_estruturado.items():
                    total_grupo = {}
                    for categoria, categoria_data in grupo_data["categorias"].items():
                        for mes, valor in categoria_data["valores_mensais"].items():
                            if mes not in total_grupo:
                                total_grupo[mes] = 0
                            try:
                                total_grupo[mes] += float(valor) if valor and str(valor) != 'nan' else 0
                            except (ValueError, TypeError):
                                pass
                    grupos_totais[grupo_key] = {
                        "nome": grupo_data["nome_grupo"],
                        "totais_mensais": total_grupo
                    }
                
                data["resumo_fluxo"] = {
                    "totais_por_grupo": grupos_totais
                }
            
            # Salvar em JSON (sobrescreve se já existir)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            return filepath
            
        except Exception as e:
            st.error(f"Erro ao salvar fluxo de caixa estruturado: {e}")
            return None
    
    def salvar_dre(self, df_dre: pd.DataFrame, empresa_nome: str, metadata: Dict = None) -> str:
        """
        Salva dados do DRE em JSON com estrutura organizada por seções (substitui arquivo existente)
        
        Args:
            df_dre: DataFrame com dados do DRE
            empresa_nome: Nome da empresa
            metadata: Informações adicionais (licença, período, etc.)
        
        Returns:
            Caminho do arquivo salvo
        """
        try:
            filename = f"{self._sanitize_filename(empresa_nome)}_dre.json"
            filepath = os.path.join(self.dre_path, filename)
            
            # Definir estrutura de seções do DRE
            secoes_dre = {
                "receitas": {
                    "nome": "RECEITAS",
                    "linhas": ["FATURAMENTO", "RECEITA", "RECEITA EXTRA OPERACIONAL"]
                },
                "custos_diretos": {
                    "nome": "CUSTOS E DESPESAS DIRETAS", 
                    "linhas": ["IMPOSTOS", "DESPESA OPERACIONAL"]
                },
                "margem_contribuicao": {
                    "nome": "MARGEM DE CONTRIBUIÇÃO",
                    "linhas": ["MARGEM CONTRIBUIÇÃO"]
                },
                "despesas_operacionais": {
                    "nome": "DESPESAS OPERACIONAIS",
                    "linhas": ["DESPESAS COM PESSOAL", "DESPESA ADMINISTRATIVA"]
                },
                "resultado_operacional": {
                    "nome": "RESULTADO OPERACIONAL", 
                    "linhas": ["LUCRO OPERACIONAL"]
                },
                "outras_despesas": {
                    "nome": "OUTRAS DESPESAS E INVESTIMENTOS",
                    "linhas": ["INVESTIMENTOS", "DESPESA EXTRA OPERACIONAL", "RETIRADAS SÓCIOS"]
                },
                "resultado_liquido": {
                    "nome": "RESULTADO LÍQUIDO",
                    "linhas": ["LUCRO LIQUIDO", "RESULTADO"]
                },
                "patrimonial": {
                    "nome": "INFORMAÇÕES PATRIMONIAIS",
                    "linhas": ["ESTOQUE", "SALDO"]
                },
                "resultado_gerencial": {
                    "nome": "RESULTADO GERENCIAL FINAL",
                    "linhas": ["RESULTADO GERENCIAL"]
                }
            }
            
            # Converter DataFrame para estrutura organizada
            dre_estruturado = {}
            
            # Processar cada seção
            for secao_key, secao_info in secoes_dre.items():
                dre_estruturado[secao_key] = {
                    "nome_secao": secao_info["nome"],
                    "itens": {}
                }
                
                # Processar cada linha da seção
                for linha in secao_info["linhas"]:
                    if linha in df_dre.index:
                        # Converter a série do pandas para dicionário
                        linha_dados = df_dre.loc[linha].to_dict()
                        dre_estruturado[secao_key]["itens"][linha] = {
                            "nome_linha": linha,
                            "valores": linha_dados
                        }
            
            # Preparar dados para salvamento
            data = {
                "empresa": empresa_nome,
                "timestamp": datetime.now().isoformat(),
                "tipo": "dre_estruturado",
                "metadata": metadata or {},
                "estrutura": "secoes_organizadas",
                "dre_estruturado": dre_estruturado,
                # Manter dados brutos para compatibilidade (formato antigo)
                "dados": df_dre.to_dict('records') if not df_dre.empty else [],
                "dados_indexados": df_dre.to_dict('index') if not df_dre.empty else {}
            }
            
            # Extrair informações específicas do DRE se disponíveis
            if not df_dre.empty:
                # Calcular totais por seção
                secoes_totais = {}
                for secao_key, secao_data in dre_estruturado.items():
                    total_secao = 0
                    for item_key, item_data in secao_data["itens"].items():
                        if "TOTAL" in item_data["valores"]:
                            total_secao += float(item_data["valores"]["TOTAL"]) if item_data["valores"]["TOTAL"] else 0
                    secoes_totais[secao_key] = {
                        "nome": secao_data["nome_secao"],
                        "total": total_secao
                    }
                
                # Adicionar resumo aos metadata
                # Calcular retiradas específicas da seção outras_despesas
                retiradas_total = 0
                outras_despesas_sem_retiradas = 0
                if "outras_despesas" in dre_estruturado:
                    for item_key, item_data in dre_estruturado["outras_despesas"]["itens"].items():
                        if "TOTAL" in item_data["valores"]:
                            valor_total = float(item_data["valores"]["TOTAL"]) if item_data["valores"]["TOTAL"] else 0
                            # Identificar retiradas pelo nome da linha
                            if any(termo in item_key.upper() for termo in ["RETIRADA", "SÓCIO", "DISTRIBUIÇÃO"]):
                                retiradas_total += abs(valor_total)
                            else:
                                outras_despesas_sem_retiradas += abs(valor_total)
                
                data["resumo_dre"] = {
                    "totais_por_secao": secoes_totais,
                    "total_receitas": secoes_totais.get("receitas", {}).get("total", 0),
                    "total_custos_diretos": secoes_totais.get("custos_diretos", {}).get("total", 0),
                    "total_despesas_operacionais": secoes_totais.get("despesas_operacionais", {}).get("total", 0),
                    "resultado_liquido": secoes_totais.get("resultado_liquido", {}).get("total", 0),
                    # Compatibilidade com análise de culturas (chaves esperadas)
                    "custos_diretos": abs(secoes_totais.get("custos_diretos", {}).get("total", 0)),
                    "custos_administrativos": abs(secoes_totais.get("despesas_operacionais", {}).get("total", 0)),
                    "despesas_extra": outras_despesas_sem_retiradas,
                    "retiradas": retiradas_total
                }
            
            # Salvar em JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            return filepath
            
        except Exception as e:
            st.error(f"Erro ao salvar DRE estruturado: {e}")
            return None
    
    def listar_empresas_disponiveis(self) -> List[Dict]:
        """
        Lista todas as empresas com dados salvos
        
        Returns:
            Lista de dicionários com informações das empresas
        """
        empresas = {}
        
        # Verificar arquivos de fluxo de caixa
        for filename in os.listdir(self.fluxo_path):
            if filename.endswith('_fluxo.json'):
                try:
                    filepath = os.path.join(self.fluxo_path, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    empresa = data.get('empresa', 'Desconhecida')
                    timestamp = data.get('timestamp', '')
                    
                    if empresa not in empresas:
                        empresas[empresa] = {
                            'nome': empresa,
                            'fluxo_caixa': [],
                            'dre': []
                        }
                    
                    empresas[empresa]['fluxo_caixa'].append({
                        'arquivo': filename,
                        'timestamp': timestamp,
                        'caminho': filepath
                    })
                    
                except Exception:
                    continue
        
        # Verificar arquivos de DRE
        for filename in os.listdir(self.dre_path):
            if filename.endswith('_dre.json'):
                try:
                    filepath = os.path.join(self.dre_path, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    empresa = data.get('empresa', 'Desconhecida')
                    timestamp = data.get('timestamp', '')
                    
                    if empresa not in empresas:
                        empresas[empresa] = {
                            'nome': empresa,
                            'fluxo_caixa': [],
                            'dre': []
                        }
                    
                    empresas[empresa]['dre'].append({
                        'arquivo': filename,
                        'timestamp': timestamp,
                        'caminho': filepath,
                        'resumo_dre': data.get('resumo_dre', {})
                    })
                    
                except Exception:
                    continue
        
        return list(empresas.values())
    
    def carregar_dre(self, empresa_nome: str, arquivo: str = None) -> Optional[Dict]:
        """
        Carrega dados do DRE de uma empresa (compatível com formato antigo e novo)
        
        Args:
            empresa_nome: Nome da empresa
            arquivo: Nome específico do arquivo (opcional, usa o arquivo padrão da empresa)
        
        Returns:
            Dados do DRE ou None se não encontrado
        """
        try:
            if arquivo:
                filepath = os.path.join(self.dre_path, arquivo)
            else:
                # Usar nome padrão da empresa
                filename = f"{self._sanitize_filename(empresa_nome)}_dre.json"
                filepath = os.path.join(self.dre_path, filename)
            
            if not os.path.exists(filepath):
                return None
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Verificar se é formato novo ou antigo
            if data.get("estrutura") == "secoes_organizadas" and "dre_estruturado" in data:
                # Formato novo - criar informações adicionais para facilitar uso
                data["formato"] = "estruturado"
                
                # Criar índice rápido de linhas por seção
                data["indice_linhas"] = {}
                if "dre_estruturado" in data:
                    for secao_key, secao_data in data["dre_estruturado"].items():
                        for linha_key, linha_data in secao_data["itens"].items():
                            data["indice_linhas"][linha_key] = {
                                "secao": secao_key,
                                "nome_secao": secao_data["nome_secao"],
                                "valores": linha_data["valores"]
                            }
                
            else:
                # Formato antigo - manter compatibilidade
                data["formato"] = "antigo"
                data["indice_linhas"] = {}
                
            return data
                
        except Exception as e:
            st.error(f"Erro ao carregar DRE: {e}")
            return None
    
    def carregar_fluxo_caixa(self, empresa_nome: str, arquivo: str = None) -> Optional[Dict]:
        """
        Carrega dados do fluxo de caixa de uma empresa (compatível com formato antigo e novo)
        
        Args:
            empresa_nome: Nome da empresa
            arquivo: Nome específico do arquivo (opcional, usa o arquivo padrão da empresa)
        
        Returns:
            Dados do fluxo de caixa ou None se não encontrado
        """
        try:
            if arquivo:
                filepath = os.path.join(self.fluxo_path, arquivo)
            else:
                # Usar nome padrão da empresa
                filename = f"{self._sanitize_filename(empresa_nome)}_fluxo.json"
                filepath = os.path.join(self.fluxo_path, filename)
            
            if not os.path.exists(filepath):
                return None
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Verificar se é formato novo ou antigo
            if data.get("estrutura") == "grupos_organizados" and "fluxo_estruturado" in data:
                # Formato novo - criar informações adicionais para facilitar uso
                data["formato"] = "estruturado"
                
                # Criar índice rápido de categorias por grupo
                data["indice_categorias"] = {}
                if "fluxo_estruturado" in data:
                    for grupo_key, grupo_data in data["fluxo_estruturado"].items():
                        for categoria_key, categoria_data in grupo_data["categorias"].items():
                            data["indice_categorias"][categoria_key] = {
                                "grupo": grupo_key,
                                "nome_grupo": grupo_data["nome_grupo"],
                                "valores": categoria_data["valores_mensais"]
                            }
                
            else:
                # Formato antigo - manter compatibilidade
                data["formato"] = "antigo"
                data["indice_categorias"] = {}
                
            return data
                
        except Exception as e:
            st.error(f"Erro ao carregar fluxo de caixa: {e}")
            return None


# Instância global do gerenciador
cache_manager = DataCacheManager()