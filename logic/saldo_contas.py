"""
Módulo para gerenciar cálculo de saldos bancários
Integra com Vyco para obter saldos atuais e calcula progressão mensal
"""

import pandas as pd
import streamlit as st
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import logging
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Imports opcionais para PostgreSQL
try:
    import psycopg2
    from sqlalchemy import create_engine, text
    from urllib.parse import quote_plus
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False


class SaldoContasManager:
    """Gerenciador de saldos bancários com integração Vyco"""
    
    def __init__(self):
        self.saldos_cache = {}
        
    def conectar_banco_vyco(self):
        """Conecta com o banco Vyco usando as mesmas credenciais da integração"""
        if not POSTGRES_AVAILABLE:
            st.error("❌ Bibliotecas PostgreSQL não disponíveis")
            return None
            
        try:
            # Usar as mesmas configurações da integração Vyco
            host = os.getenv("DB_HOST", "prod-server-db1.postgres.database.azure.com")
            database = os.getenv("DB_NAME", "mr-backoffice-prod-db")
            port = "5432"
            
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
                return None
            
            # Criar string de conexão
            connection_string = f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{database}"
            
            # Criar engine SQLAlchemy
            engine = create_engine(connection_string, pool_pre_ping=True, pool_recycle=300)
            
            return engine
            
        except Exception as e:
            st.error(f"❌ Erro ao conectar com banco Vyco: {str(e)}")
            logging.error(f"Erro conexão Vyco: {e}")
            return None

    def buscar_saldo_atual_vyco(self, licenca_id: str) -> float:
        """
        Busca o saldo atual total de todas as contas de uma licença
        
        Args:
            licenca_id: UUID da licença no Vyco
            
        Returns:
            Saldo total atual (soma de todas as contas)
        """
        try:
            engine = self.conectar_banco_vyco()
            if engine is None:
                return 0.0
                
            # Query baseada na consulta do Power BI
            query = f"""
            SELECT * 
            FROM analytics.fn_contas_por_licencas(
                ARRAY['{licenca_id}']::uuid[], 
                -1, 
                0
            );
            """
            
            # Executar query
            df_contas = pd.read_sql(query, engine)
            engine.dispose()
            
            if df_contas.empty:
                st.warning(f"⚠️ Nenhuma conta encontrada para licença {licenca_id}")
                return 0.0
                
            # Armazenar dados das contas para exibição
            self.dados_contas_debug = df_contas.copy()
                
            # Somar TODOS os saldos atuais (coluna saldoatual)
            if 'saldoatual' in df_contas.columns:
                # Somar apenas contas ativas (sem data de encerramento)
                contas_ativas = df_contas[pd.isna(df_contas.get('dataencerramento', []))]
                saldo_total = contas_ativas['saldoatual'].sum()
                contas_count = len(contas_ativas)
            else:
                saldo_total = 0.0
                contas_count = 0
                    
            return float(saldo_total)
            
        except Exception as e:
            st.error(f"❌ Erro ao buscar saldo atual: {e}")
            return 0.0
    
    def exibir_dados_contas_debug(self) -> pd.DataFrame:
        """
        Retorna DataFrame com dados das contas para debug
        
        Returns:
            DataFrame formatado para exibição
        """
        if not hasattr(self, 'dados_contas_debug') or self.dados_contas_debug.empty:
            return pd.DataFrame()
            
        df_debug = self.dados_contas_debug.copy()
        
        # Selecionar e formatar colunas principais
        df_display = pd.DataFrame()
        
        # Verificar se existe campo de nome da conta
        campos_nome_conta = ['nomeconta', 'nome_conta', 'contanome', 'conta_nome', 'descricao', 'description']
        campo_nome_encontrado = None
        
        for campo in campos_nome_conta:
            if campo in df_debug.columns:
                campo_nome_encontrado = campo
                df_display['Nome da Conta'] = df_debug[campo]
                break
        
        # Se não encontrou nome, mostrar nome da conta diretamente
        if not campo_nome_encontrado and 'nome' in df_debug.columns:
            df_display['Nome da Conta'] = df_debug['nome'].astype(str)
        
        # Outras informações importantes
        if 'valorinicial' in df_debug.columns:
            df_display['Saldo Inicial'] = df_debug['valorinicial'].apply(lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else "R$ 0,00")
        
        if 'datainicial' in df_debug.columns:
            df_display['Data Inicial'] = pd.to_datetime(df_debug['datainicial']).dt.strftime('%d/%m/%Y')
        
        if 'saldoatual' in df_debug.columns:
            df_display['Saldo Atual'] = df_debug['saldoatual'].apply(lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else "R$ 0,00")
        
        if 'dataencerramento' in df_debug.columns:
            df_display['Status'] = df_debug['dataencerramento'].apply(lambda x: "Encerrada" if pd.notna(x) else "Ativa")

        
        return df_display
    
    def calcular_movimentacao_liquida_mes(self, dados_mes: Dict) -> float:
        """
        Calcula a movimentação líquida de um mês (entradas - saídas)
        
        Args:
            dados_mes: Dicionário com valores por categoria do mês
            
        Returns:
            Valor líquido (positivo = entrada, negativo = saída)
        """
        # Categorias que representam ENTRADAS (aumentam saldo)
        categorias_entrada = [
            "FATURAMENTO", "RECEITA", "RECEITA EXTRA OPERACIONAL"
        ]
        
        # Categorias que representam SAÍDAS (diminuem saldo)  
        categorias_saida = [
            "IMPOSTOS", "DESPESA OPERACIONAL", "DESPESAS COM PESSOAL",
            "DESPESA ADMINISTRATIVA", "INVESTIMENTOS", "DESPESA EXTRA OPERACIONAL",
            "RETIRADAS SÓCIOS"
        ]
        
        entradas = 0.0
        saidas = 0.0
        
        for categoria, valor in dados_mes.items():
            valor_num = float(valor) if valor else 0.0
            
            if categoria in categorias_entrada:
                entradas += valor_num
            elif categoria in categorias_saida:
                saidas += abs(valor_num)  # Garantir que saídas sejam positivas
                
        return entradas - saidas
    
    def calcular_saldos_mensais(self, dados_dre: Dict, licenca_id: str, 
                               mes_atual: str = None) -> Dict[str, float]:
        """
        Calcula saldos mensais com lógica automática:
        - Anos ≤ 2025: RETROATIVA (baseada no saldo atual - soma resultados)
        - Anos ≥ 2026: PROGRESSIVA (baseada no saldo atual + resultados mês a mês)
        
        Args:
            dados_dre: Dados do DRE por mês
            licenca_id: ID da licença para buscar saldo atual
            mes_atual: Mês de referência (formato YYYY-MM)
            
        Returns:
            Dicionário com saldos por mês (calculados conforme o ano)
        """
        # Buscar saldo atual real do Vyco (ponto de partida)
        saldo_atual_real = self.buscar_saldo_atual_vyco(licenca_id)
        
        if saldo_atual_real == 0:
            # Se não conseguir obter saldo real, usar lógica antiga
            return self._calcular_saldos_progressivos_antigo(dados_dre, saldo_atual_real)
        
        # Organizar meses em ordem cronológica
        meses_ordenados = sorted(dados_dre.keys())
        
        if not meses_ordenados:
            return {}
        
        # Detectar o ano dos dados para escolher a lógica
        primeiro_mes = meses_ordenados[0]
        ano_dados = int(primeiro_mes.split('-')[0])
        
        # LÓGICA DUAL: Retroativa vs Progressiva
        if ano_dados <= 2025:
            # LÓGICA RETROATIVA para anos históricos (≤ 2025)
            return self._calcular_saldos_retroativos(dados_dre, saldo_atual_real, meses_ordenados)
        else:
            # LÓGICA PROGRESSIVA para orçamentos futuros (≥ 2026)
            return self._calcular_saldos_progressivos(dados_dre, saldo_atual_real, meses_ordenados)
    
    def _calcular_saldos_retroativos(self, dados_dre: Dict, saldo_atual_real: float, meses_ordenados: List) -> Dict[str, float]:
        """
        Lógica RETROATIVA: calcula saldo inicial e progride mês a mês (para dados históricos)
        """
        # ETAPA 1: Coletar todos os RESULTADOS históricos
        resultados_por_mes = {}
        for mes in meses_ordenados:
            resultado_mes = dados_dre[mes].get('RESULTADO', 0.0)
            resultado_mes = float(resultado_mes) if resultado_mes else 0.0
            resultados_por_mes[mes] = resultado_mes
        
        # ETAPA 2: Calcular saldo inicial retroativo
        # Fórmula validada: saldo_inicial = saldo_atual - soma_resultados
        soma_resultados_total = sum(resultados_por_mes.values())
        saldo_inicial_calculado = saldo_atual_real - soma_resultados_total
        
        # ETAPA 3: Calcular progressão mês a mês desde o saldo inicial
        saldos_mensais = {}
        saldo_corrente = saldo_inicial_calculado
        
        for mes in meses_ordenados:
            resultado_mes = resultados_por_mes[mes]
            # Aplicar resultado ao saldo corrente
            saldo_corrente += resultado_mes
            saldos_mensais[mes] = saldo_corrente
            
        return saldos_mensais
    
    def _calcular_saldos_progressivos(self, dados_dre: Dict, saldo_atual_real: float, meses_ordenados: List) -> Dict[str, float]:
        """
        Lógica PROGRESSIVA: começa do saldo atual e projeta para frente (para orçamentos futuros)
        """
        saldos_mensais = {}
        saldo_corrente = saldo_atual_real  # Começar do saldo atual real
        
        for mes in meses_ordenados:
            # Buscar o RESULTADO orçado do mês
            resultado_mes = dados_dre[mes].get('RESULTADO', 0.0)
            resultado_mes = float(resultado_mes) if resultado_mes else 0.0
            
            # Projeção progressiva: saldo_futuro = saldo_atual + resultado_orçado
            saldo_corrente += resultado_mes
            saldos_mensais[mes] = saldo_corrente
            
        return saldos_mensais
    
    def _calcular_saldos_progressivos_antigo(self, dados_dre: Dict, saldo_base: float) -> Dict[str, float]:
        """
        Método auxiliar com lógica progressiva antiga (fallback)
        """
        meses_ordenados = sorted(dados_dre.keys())
        saldos_mensais = {}
        saldo_corrente = saldo_base
        
        for mes in meses_ordenados:
            resultado_mes = dados_dre[mes].get('RESULTADO', 0.0)
            resultado_mes = float(resultado_mes) if resultado_mes else 0.0
            saldo_corrente = saldo_corrente + resultado_mes
            saldos_mensais[mes] = saldo_corrente
            
        return saldos_mensais
    
    def aplicar_saldos_no_dataframe(self, df_dre: pd.DataFrame, saldos_mensais: Dict) -> pd.DataFrame:
        """
        Aplica os saldos calculados no DataFrame do DRE
        
        Args:
            df_dre: DataFrame do DRE
            saldos_mensais: Dicionário com saldos por mês
            
        Returns:
            DataFrame atualizado com saldos
        """
        if "SALDO" in df_dre.index:
            for mes, saldo in saldos_mensais.items():
                if mes in df_dre.columns:
                    df_dre.loc["SALDO", mes] = saldo
                    
        return df_dre
    
    def validar_consistencia(self, saldos_calculados: Dict, saldo_real: float, 
                           mes_referencia: str) -> Tuple[bool, str]:
        """
        Valida se o saldo calculado bate com o saldo real
        
        Returns:
            (is_valid, message)
        """
        if mes_referencia not in saldos_calculados:
            return False, f"Mês {mes_referencia} não encontrado nos cálculos"
            
        saldo_calculado = saldos_calculados[mes_referencia]
        diferenca = abs(saldo_calculado - saldo_real)
        tolerancia = 0.01  # R$ 0,01 de tolerância
        
        if diferenca <= tolerancia:
            return True, f"✅ Saldos consistentes (diferença: R$ {diferenca:.2f})"
        else:
            return False, f"❌ Inconsistência detectada (diferença: R$ {diferenca:.2f})"


# Instância global
saldo_manager = SaldoContasManager()