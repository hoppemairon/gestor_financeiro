"""
Módulo para gerenciar licenças via arquivo CSV
Centraliza o gerenciamento de licenças para Vyco e Orçamento
"""

import pandas as pd
import os
import streamlit as st
from typing import List, Dict, Optional, Tuple


class LicencaManager:
    """Gerenciador de licenças via CSV"""
    
    def __init__(self, csv_path: str = "./logic/CSVs/licencas_vyco.csv"):
        self.csv_path = csv_path
        self._criar_diretorio_se_necessario()
        self._criar_csv_se_nao_existir()
    
    def _criar_diretorio_se_necessario(self):
        """Cria o diretório do CSV se não existir"""
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
    
    def _criar_csv_se_nao_existir(self):
        """Cria o arquivo CSV com estrutura padrão se não existir"""
        if not os.path.exists(self.csv_path):
            df_inicial = pd.DataFrame({
                'nome_licenca': [
                    'Amor Saude Caxias Centro',
                    'Amor Saude Bento', 
                    'Arani'
                ],
                'id_licenca': [
                    'ec48a041-3554-41e9-8ea7-afcc60f0a868',
                    '5f1c3fc7-5a15-4cb6-b0f8-335e2317a3e1',
                    '2fab261a-42ff-4ac1-8ee3-3088395e4b7c'
                ],
                'ativo': [True, True, True],
                'observacoes': [
                    'Licença principal Amor Saúde',
                    'Unidade Bento Gonçalves',
                    'Agronegócio - Fazenda Arani'
                ]
            })
            df_inicial.to_csv(self.csv_path, index=False, encoding='utf-8')
    
    def carregar_licencas(self, apenas_ativas: bool = True) -> pd.DataFrame:
        """
        Carrega licenças do CSV
        
        Args:
            apenas_ativas: Se True, retorna apenas licenças ativas
        
        Returns:
            DataFrame com as licenças
        """
        try:
            if not os.path.exists(self.csv_path):
                return pd.DataFrame(columns=['nome_licenca', 'id_licenca', 'ativo', 'observacoes'])
            
            df = pd.read_csv(self.csv_path, encoding='utf-8')
            
            # Garantir que a coluna 'ativo' existe
            if 'ativo' not in df.columns:
                df['ativo'] = True
            
            # Converter coluna ativo para boolean
            df['ativo'] = df['ativo'].astype(bool)
            
            if apenas_ativas:
                df = df[df['ativo'] == True]
            
            return df
            
        except Exception as e:
            st.error(f"Erro ao carregar licenças: {e}")
            return pd.DataFrame(columns=['nome_licenca', 'id_licenca', 'ativo', 'observacoes'])
    
    def obter_licencas_ativas(self) -> List[str]:
        """
        Retorna lista dos nomes das licenças ativas
        
        Returns:
            Lista de nomes de licenças ativas
        """
        df = self.carregar_licencas(apenas_ativas=True)
        return df['nome_licenca'].tolist()
    
    def obter_id_licenca(self, nome_licenca: str) -> Optional[str]:
        """
        Retorna o ID de uma licença pelo nome
        
        Args:
            nome_licenca: Nome da licença
            
        Returns:
            ID da licença ou None se não encontrada
        """
        df = self.carregar_licencas(apenas_ativas=True)
        licenca = df[df['nome_licenca'] == nome_licenca]
        
        if not licenca.empty:
            return licenca.iloc[0]['id_licenca']
        return None
    
    def obter_licencas_dict(self) -> Dict[str, str]:
        """
        Retorna dicionário {nome_licenca: id_licenca} para licenças ativas
        
        Returns:
            Dicionário com nomes e IDs das licenças
        """
        df = self.carregar_licencas(apenas_ativas=True)
        return dict(zip(df['nome_licenca'], df['id_licenca']))
    
    def adicionar_licenca(self, nome: str, id_licenca: str, ativo: bool = True, 
                         observacoes: str = "") -> bool:
        """
        Adiciona nova licença ao CSV
        
        Args:
            nome: Nome da licença
            id_licenca: ID/UUID da licença
            ativo: Se a licença está ativa
            observacoes: Observações sobre a licença
            
        Returns:
            True se sucesso, False caso contrário
        """
        try:
            df = self.carregar_licencas(apenas_ativas=False)
            
            # Verificar se já existe
            if nome in df['nome_licenca'].values:
                st.warning(f"⚠️ Licença '{nome}' já existe no CSV")
                return False
            
            # Adicionar nova linha
            nova_linha = {
                'nome_licenca': nome,
                'id_licenca': id_licenca,
                'ativo': ativo,
                'observacoes': observacoes
            }
            
            # Usar pd.concat ao invés de append (deprecated)
            nova_linha_df = pd.DataFrame([nova_linha])
            df = pd.concat([df, nova_linha_df], ignore_index=True)
            
            # Salvar
            df.to_csv(self.csv_path, index=False, encoding='utf-8')
            return True
            
        except Exception as e:
            st.error(f"Erro ao adicionar licença: {e}")
            return False
    
    def desativar_licenca(self, nome: str) -> bool:
        """
        Desativa uma licença (marca como inativa)
        
        Args:
            nome: Nome da licença
            
        Returns:
            True se sucesso, False caso contrário
        """
        try:
            df = self.carregar_licencas(apenas_ativas=False)
            
            if nome not in df['nome_licenca'].values:
                st.warning(f"⚠️ Licença '{nome}' não encontrada")
                return False
            
            # Marcar como inativa
            df.loc[df['nome_licenca'] == nome, 'ativo'] = False
            
            # Salvar
            df.to_csv(self.csv_path, index=False, encoding='utf-8')
            return True
            
        except Exception as e:
            st.error(f"Erro ao desativar licença: {e}")
            return False
    
    def atualizar_licenca(self, nome_atual: str, nome_novo: str = None, 
                         id_novo: str = None, observacoes_novas: str = None) -> bool:
        """
        Atualiza dados de uma licença existente
        
        Args:
            nome_atual: Nome atual da licença
            nome_novo: Novo nome (opcional)
            id_novo: Novo ID (opcional)
            observacoes_novas: Novas observações (opcional)
            
        Returns:
            True se sucesso, False caso contrário
        """
        try:
            df = self.carregar_licencas(apenas_ativas=False)
            
            if nome_atual not in df['nome_licenca'].values:
                st.warning(f"⚠️ Licença '{nome_atual}' não encontrada")
                return False
            
            # Atualizar campos se fornecidos
            idx = df[df['nome_licenca'] == nome_atual].index[0]
            
            if nome_novo:
                df.loc[idx, 'nome_licenca'] = nome_novo
            if id_novo:
                df.loc[idx, 'id_licenca'] = id_novo
            if observacoes_novas is not None:
                df.loc[idx, 'observacoes'] = observacoes_novas
            
            # Salvar
            df.to_csv(self.csv_path, index=False, encoding='utf-8')
            return True
            
        except Exception as e:
            st.error(f"Erro ao atualizar licença: {e}")
            return False
    
    def validar_csv(self) -> Tuple[bool, List[str]]:
        """
        Valida estrutura e dados do CSV
        
        Returns:
            Tuple (válido: bool, erros: List[str])
        """
        erros = []
        
        try:
            if not os.path.exists(self.csv_path):
                erros.append("Arquivo CSV não encontrado")
                return False, erros
            
            df = pd.read_csv(self.csv_path, encoding='utf-8')
            
            # Verificar colunas obrigatórias
            colunas_obrigatorias = ['nome_licenca', 'id_licenca']
            for coluna in colunas_obrigatorias:
                if coluna not in df.columns:
                    erros.append(f"Coluna obrigatória '{coluna}' não encontrada")
            
            # Verificar duplicatas
            duplicatas_nome = df[df.duplicated(subset=['nome_licenca'], keep=False)]
            if not duplicatas_nome.empty:
                nomes_dup = duplicatas_nome['nome_licenca'].tolist()
                erros.append(f"Nomes duplicados encontrados: {nomes_dup}")
            
            duplicatas_id = df[df.duplicated(subset=['id_licenca'], keep=False)]
            if not duplicatas_id.empty:
                ids_dup = duplicatas_id['id_licenca'].tolist()
                erros.append(f"IDs duplicados encontrados: {ids_dup}")
            
            # Verificar IDs vazios
            ids_vazios = df[df['id_licenca'].isnull() | (df['id_licenca'] == '')]
            if not ids_vazios.empty:
                erros.append("Encontrados IDs de licença vazios")
            
            return len(erros) == 0, erros
            
        except Exception as e:
            erros.append(f"Erro ao validar CSV: {e}")
            return False, erros
    
    def exportar_backup(self, caminho_backup: str = None) -> bool:
        """
        Cria backup do arquivo de licenças
        
        Args:
            caminho_backup: Caminho para o backup (opcional)
            
        Returns:
            True se sucesso, False caso contrário
        """
        try:
            if not caminho_backup:
                timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
                caminho_backup = f"./logic/CSVs/licencas_vyco_backup_{timestamp}.csv"
            
            df = self.carregar_licencas(apenas_ativas=False)
            df.to_csv(caminho_backup, index=False, encoding='utf-8')
            
            return True
            
        except Exception as e:
            st.error(f"Erro ao criar backup: {e}")
            return False


# Instância global do gerenciador
licenca_manager = LicencaManager()