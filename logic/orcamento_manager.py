"""
Módulo para gerenciar orçamentos anuais
Salva os dados em JSON para comparação entre anos base e projetados
"""

import json
import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Union
import streamlit as st
import copy


class OrcamentoManager:
    """Gerenciador de orçamentos para comparação entre anos"""
    
    def __init__(self, base_path: str = "./data_cache"):
        self.base_path = base_path
        self.orcamento_path = os.path.join(base_path, "orcamento")
        
        # Criar diretório se não existir
        os.makedirs(self.orcamento_path, exist_ok=True)
    
    def _sanitize_filename(self, name: str) -> str:
        """Remove caracteres especiais do nome do arquivo"""
        import re
        return re.sub(r'[<>:"/\\|?*]', '_', name).strip()
    
    def salvar_orcamento(self, empresa_nome: str, ano_orcamento: int, ano_base: int, 
                        dados_orcamento: Dict, dados_realizado: Dict = None, 
                        metadata: Dict = None) -> str:
        """
        Salva dados do orçamento em JSON
        
        Args:
            empresa_nome: Nome da empresa
            ano_orcamento: Ano do orçamento (ex: 2026)
            ano_base: Ano usado como base (ex: 2025)
            dados_orcamento: Dados orçados por mês/categoria
            dados_realizado: Dados realizados (opcional)
            metadata: Informações adicionais
        
        Returns:
            Caminho do arquivo salvo
        """
        try:
            filename = f"{self._sanitize_filename(empresa_nome)}_orcamento_{ano_orcamento}.json"
            filepath = os.path.join(self.orcamento_path, filename)
            
            # Estruturar dados do orçamento
            data = {
                "empresa": empresa_nome,
                "ano_orcamento": ano_orcamento,
                "ano_base": ano_base,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
                "orcamento_mensal": dados_orcamento,
                "realizado_mensal": dados_realizado or {},
                "configuracoes": {
                    "ultima_atualizacao": datetime.now().isoformat(),
                    "versao": "1.0"
                }
            }
            
            # Salvar em JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            return filepath
            
        except Exception as e:
            st.error(f"Erro ao salvar orçamento: {e}")
            return None
    
    def carregar_orcamento(self, empresa_nome: str, ano_orcamento: int) -> Optional[Dict]:
        """
        Carrega dados do orçamento de uma empresa
        
        Args:
            empresa_nome: Nome da empresa
            ano_orcamento: Ano do orçamento
        
        Returns:
            Dados do orçamento ou None se não encontrado
        """
        try:
            filename = f"{self._sanitize_filename(empresa_nome)}_orcamento_{ano_orcamento}.json"
            filepath = os.path.join(self.orcamento_path, filename)
            
            if not os.path.exists(filepath):
                return None
                
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return data
                
        except Exception as e:
            st.error(f"Erro ao carregar orçamento: {e}")
            return None
    
    def atualizar_realizado(self, empresa_nome: str, ano_orcamento: int, 
                           mes: str, dados_reais: Dict) -> bool:
        """
        Atualiza dados realizados de um mês específico
        
        Args:
            empresa_nome: Nome da empresa
            ano_orcamento: Ano do orçamento
            mes: Mês no formato 'YYYY-MM'
            dados_reais: Dados realizados do mês
        
        Returns:
            True se sucesso, False caso contrário
        """
        try:
            # Carregar orçamento existente
            dados_orcamento = self.carregar_orcamento(empresa_nome, ano_orcamento)
            
            if not dados_orcamento:
                st.error("Orçamento não encontrado para atualização")
                return False
            
            # Atualizar dados realizados
            if "realizado_mensal" not in dados_orcamento:
                dados_orcamento["realizado_mensal"] = {}
            
            dados_orcamento["realizado_mensal"][mes] = dados_reais
            dados_orcamento["configuracoes"]["ultima_atualizacao"] = datetime.now().isoformat()
            
            # Salvar novamente
            self.salvar_orcamento(
                empresa_nome, 
                ano_orcamento,
                dados_orcamento["ano_base"],
                dados_orcamento["orcamento_mensal"],
                dados_orcamento["realizado_mensal"],
                dados_orcamento["metadata"]
            )
            
            return True
            
        except Exception as e:
            st.error(f"Erro ao atualizar realizado: {e}")
            return False
    
    def calcular_diferencas(self, orcado: Dict, realizado: Dict) -> Dict:
        """
        Calcula diferenças entre orçado e realizado
        
        Args:
            orcado: Dados orçados
            realizado: Dados realizados
        
        Returns:
            Dicionário com diferenças calculadas
        """
        diferencas = {}
        
        for categoria in orcado.keys():
            valor_orcado = float(orcado.get(categoria, 0))
            valor_realizado = float(realizado.get(categoria, 0))
            
            diferenca_absoluta = valor_realizado - valor_orcado
            diferenca_percentual = 0
            
            if valor_orcado != 0:
                diferenca_percentual = (diferenca_absoluta / valor_orcado) * 100
            
            diferencas[categoria] = {
                "orcado": valor_orcado,
                "realizado": valor_realizado,
                "diferenca_absoluta": diferenca_absoluta,
                "diferenca_percentual": diferenca_percentual
            }
        
        return diferencas
    
    def aplicar_facilitador(self, tipo_facilitador: str, valor: Union[float, str], 
                          dados_base: Dict, categoria: str = None) -> Dict:
        """
        Aplica facilitadores de orçamento
        
        Args:
            tipo_facilitador: 'percentual', 'valor_fixo', 'tendencia', 'copia_mensal'
            valor: Valor do facilitador (% ou valor absoluto)
            dados_base: Dados do ano base
            categoria: Categoria específica (opcional, se None aplica em todas)
        
        Returns:
            Dados modificados
        """
        dados_resultado = copy.deepcopy(dados_base)
        
        try:
            if tipo_facilitador == "percentual":
                # Aplicar percentual de crescimento
                percentual = float(valor) / 100
                
                for mes, dados_mes in dados_resultado.items():
                    if categoria:
                        if categoria in dados_mes:
                            dados_mes[categoria] *= (1 + percentual)
                    else:
                        for cat in dados_mes:
                            dados_mes[cat] *= (1 + percentual)
            
            elif tipo_facilitador == "valor_fixo":
                # Manter valor fixo do primeiro mês
                primeiro_mes = next(iter(dados_resultado.keys()))
                valor_fixo = dados_resultado[primeiro_mes]
                
                for mes in dados_resultado.keys():
                    if categoria:
                        if categoria in valor_fixo:
                            dados_resultado[mes][categoria] = valor_fixo[categoria]
                    else:
                        dados_resultado[mes] = copy.deepcopy(valor_fixo)
            
            elif tipo_facilitador == "tendencia":
                # Crescimento linear mensal
                crescimento_mensal = float(valor) / 100
                
                for i, (mes, dados_mes) in enumerate(dados_resultado.items()):
                    fator_crescimento = (1 + crescimento_mensal) ** i
                    
                    if categoria:
                        if categoria in dados_mes:
                            dados_mes[categoria] *= fator_crescimento
                    else:
                        for cat in dados_mes:
                            dados_mes[cat] *= fator_crescimento
            
            elif tipo_facilitador == "copia_mensal":
                # Copiar dados de um mês específico para todos
                mes_origem = valor
                if mes_origem in dados_resultado:
                    dados_origem = dados_resultado[mes_origem]
                    
                    for mes in dados_resultado.keys():
                        if categoria:
                            if categoria in dados_origem:
                                dados_resultado[mes][categoria] = dados_origem[categoria]
                        else:
                            dados_resultado[mes] = copy.deepcopy(dados_origem)
        
        except Exception as e:
            st.error(f"Erro ao aplicar facilitador: {e}")
        
        return dados_resultado
    
    def listar_orcamentos_disponiveis(self) -> List[Dict]:
        """
        Lista todos os orçamentos salvos
        
        Returns:
            Lista de dicionários com informações dos orçamentos
        """
        orcamentos = []
        
        try:
            for filename in os.listdir(self.orcamento_path):
                if filename.endswith('_orcamento.json') or '_orcamento_' in filename:
                    filepath = os.path.join(self.orcamento_path, filename)
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    orcamentos.append({
                        'arquivo': filename,
                        'empresa': data.get('empresa', 'Desconhecida'),
                        'ano_orcamento': data.get('ano_orcamento', 0),
                        'ano_base': data.get('ano_base', 0),
                        'timestamp': data.get('timestamp', ''),
                        'caminho': filepath,
                        'tem_realizado': bool(data.get('realizado_mensal', {}))
                    })
        
        except Exception as e:
            st.error(f"Erro ao listar orçamentos: {e}")
        
        return orcamentos
    
    def extrair_dados_base_do_cache(self, empresa_nome: str, tipo_dados: str = "dre") -> Dict:
        """
        Extrai dados do ano base do cache existente (DRE ou Fluxo)
        
        Args:
            empresa_nome: Nome da empresa
            tipo_dados: "dre" ou "fluxo_caixa"
        
        Returns:
            Dados estruturados por mês e categoria
        """
        from logic.data_cache_manager import cache_manager
        
        dados_estruturados = {}
        
        try:
            if tipo_dados == "dre":
                dados_cache = cache_manager.carregar_dre(empresa_nome)
                if dados_cache and "dre_estruturado" in dados_cache:
                    # Extrair dados do DRE estruturado
                    for secao_key, secao_data in dados_cache["dre_estruturado"].items():
                        for linha_key, linha_data in secao_data["itens"].items():
                            categoria = linha_data["nome_linha"]
                            valores_mensais = linha_data["valores"]
                            
                            # Organizar por mês
                            for mes, valor in valores_mensais.items():
                                if mes != "TOTAL" and mes != "%":
                                    if mes not in dados_estruturados:
                                        dados_estruturados[mes] = {}
                                    dados_estruturados[mes][categoria] = float(valor) if valor else 0.0
            
            elif tipo_dados == "fluxo_caixa":
                dados_cache = cache_manager.carregar_fluxo_caixa(empresa_nome)
                if dados_cache and "fluxo_estruturado" in dados_cache:
                    # Extrair dados do Fluxo estruturado
                    for grupo_key, grupo_data in dados_cache["fluxo_estruturado"].items():
                        for categoria_key, categoria_data in grupo_data["categorias"].items():
                            categoria = categoria_data["nome_categoria"]
                            valores_mensais = categoria_data["valores_mensais"]
                            
                            # Organizar por mês
                            for mes, valor in valores_mensais.items():
                                if mes not in dados_estruturados:
                                    dados_estruturados[mes] = {}
                                dados_estruturados[mes][categoria] = float(valor) if valor else 0.0
        
        except Exception as e:
            st.error(f"Erro ao extrair dados base: {e}")
        
        return dados_estruturados


# Instância global do gerenciador
orcamento_manager = OrcamentoManager()