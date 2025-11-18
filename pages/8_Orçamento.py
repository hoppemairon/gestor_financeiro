import streamlit as st

# Configuração da página (DEVE ser o primeiro comando Streamlit)
st.set_page_config(
    page_title="Orçamento Empresarial", 
    layout="wide",
    initial_sidebar_state="expanded"
)

import pandas as pd
import json
from datetime import datetime
import numpy as np
from dateutil.relativedelta import relativedelta
import plotly.express as px
import plotly.graph_objects as go

# Módulos do projeto
from logic.orcamento_manager import orcamento_manager
from logic.data_cache_manager import cache_manager
from logic.licenca_manager import licenca_manager
from logic.saldo_contas import saldo_manager, SaldoContasManager

# Constantes para estilo do DRE (igual ao parecer)
ESTILO_LINHAS_DRE = {
    "FATURAMENTO": ("#5d65c8", "white"),
    "RECEITA": ("#152357", "white"), 
    "MARGEM CONTRIBUIÇÃO": ("#39b79c", "black"),
    "LUCRO OPERACIONAL": ("#39b79c", "black"),
    "LUCRO LIQUIDO": ("#39b79c", "black"),
    "RESULTADO": ("#216a5a", "black"),
    "SALDO": ("#b1c95c", "black"),
    "RESULTADO GERENCIAL": ("#216a5a", "white"),
}

# Configuração da página
st.title("📊 Orçamento Empresarial")
st.markdown("""
### Sistema integrado de planejamento orçamentário
🔄 **INTEGRAÇÃO AUTOMÁTICA:** Dados base extraídos do sistema Vyco + Orçamento personalizado por categoria
""")

# Funções auxiliares
def formatar_valor_br(valor):
    """Formata um valor numérico para o formato brasileiro (R$)"""
    if pd.isna(valor) or valor == 0:
        return "R$ 0,00"
    if isinstance(valor, (int, float)):
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(valor)

def converter_para_float(valor_str):
    """Converte uma string de valor BR para float"""
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    try:
        return float(str(valor_str).replace("R$", "").replace(".", "").replace(",", ".").strip())
    except:
        return 0.0

def obter_meses_ano(ano):
    """Retorna lista de meses formatados para um ano"""
    return [f"{ano}-{mes:02d}" for mes in range(1, 13)]

def nome_mes_pt(mes_str):
    """Converte YYYY-MM para nome do mês em português"""
    meses = {
        "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
        "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
        "09": "Set", "10": "Out", "11": "Nov", "12": "Dez"
    }
    try:
        ano, mes = mes_str.split("-")
        return f"{meses[mes]}/{ano}"
    except:
        return mes_str

def highlight_rows_orcamento(row):
    """Aplica estilos às linhas do orçamento (igual ao DRE do parecer)"""
    if "Categoria" in row.index:
        descricao = row["Categoria"]
    else:
        return ["" for _ in row]
    
    bg_color, text_color = ESTILO_LINHAS_DRE.get(descricao, ("", "black"))
    return [f"background-color: {bg_color}; color: {text_color}; font-weight: bold;" if bg_color else "" for _ in row]

def ordenar_categorias_dre(categorias):
    """Ordena categorias na ordem do DRE do parecer"""
    ordem_dre = [
        "FATURAMENTO",
        "RECEITA", 
        "IMPOSTOS",
        "DESPESA OPERACIONAL", 
        "MARGEM CONTRIBUIÇÃO",
        "DESPESAS COM PESSOAL",
        "DESPESA ADMINISTRATIVA",
        "LUCRO OPERACIONAL", 
        "INVESTIMENTOS",
        "DESPESA EXTRA OPERACIONAL",
        "LUCRO LIQUIDO",
        "RETIRADAS SÓCIOS",
        "RECEITA EXTRA OPERACIONAL",
        "RESULTADO",
        "SALDO",
        "ESTOQUE",
        "RESULTADO GERENCIAL"
    ]
    
    # Manter a ordem do DRE quando possível
    categorias_ordenadas = []
    categorias_restantes = list(categorias)
    
    for categoria_dre in ordem_dre:
        if categoria_dre in categorias_restantes:
            categorias_ordenadas.append(categoria_dre)
            categorias_restantes.remove(categoria_dre)
    
    # Adicionar categorias restantes no final
    categorias_ordenadas.extend(sorted(categorias_restantes))
    
    return categorias_ordenadas

def processar_detalhamento_local(df_transacoes: pd.DataFrame, categoria: str, mes: str) -> pd.DataFrame:
    """
    Processa detalhamento de uma categoria/mês usando DF de transações do cache
    SEM importar módulo Vyco - totalmente independente
    
    Args:
        df_transacoes: DataFrame completo de transações categorizadas (do cache)
        categoria: Categoria do DRE (ex: 'DESPESA OPERACIONAL')
        mes: Mês no formato 'YYYY-MM'
    
    Returns:
        DataFrame com: Subcategoria | Tipo | Qtd | Valor | % Categoria
    """
    try:
        if df_transacoes is None or df_transacoes.empty:
            return pd.DataFrame()
        
        # Verificar qual coluna de descrição está presente (encoding pode variar)
        col_descricao = None
        for possivel_col in ['Descrição', 'DescriÃ§Ã£o', 'Descricao', 'descrição']:
            if possivel_col in df_transacoes.columns:
                col_descricao = possivel_col
                break
        
        if not col_descricao:
            # Debug: mostrar colunas disponíveis
            colunas_disponiveis = ', '.join(df_transacoes.columns.tolist())
            st.warning(f"⚠️ Coluna de descrição não encontrada no cache. Colunas disponíveis: {colunas_disponiveis}")
            return pd.DataFrame()
        
        # Debug inicial
        st.write(f"🔍 **Debug:** Procurando categoria '{categoria}' no mês '{mes}'")
        st.write(f"📊 Total de transações no cache: {len(df_transacoes)}")
        
        # Filtrar por categoria
        df_filtrado = df_transacoes[
            df_transacoes['Categoria_Vyco'].str.contains(categoria, case=False, na=False)
        ].copy()
        
        st.write(f"📊 Transações após filtro de categoria: {len(df_filtrado)}")
        
        if df_filtrado.empty:
            st.warning(f"❌ Nenhuma transação encontrada para categoria '{categoria}'")
            return pd.DataFrame()
        
        # Converter Data para datetime se necessário
        if 'Data' in df_filtrado.columns:
            df_filtrado['Data'] = pd.to_datetime(df_filtrado['Data'], errors='coerce')
            
            # Debug: mostrar range de datas
            data_min = df_filtrado['Data'].min()
            data_max = df_filtrado['Data'].max()
            st.write(f"📅 Range de datas: {data_min} até {data_max}")
            
            # Criar coluna de ano-mês para debug
            df_filtrado['Ano_Mes'] = df_filtrado['Data'].dt.strftime('%Y-%m')
            st.write(f"📅 Meses disponíveis: {df_filtrado['Ano_Mes'].unique()[:10]}")
            
            # Filtrar por mês
            df_filtrado = df_filtrado[df_filtrado['Ano_Mes'] == mes]
            st.write(f"📊 Transações após filtro de mês '{mes}': {len(df_filtrado)}")
        
        if df_filtrado.empty:
            st.warning(f"❌ Nenhuma transação encontrada para '{categoria}' em '{mes}'")
            return pd.DataFrame()
        
        # Agrupar por Descrição (subcategoria) usando a coluna correta
        resultado = df_filtrado.groupby(col_descricao).agg({
            'Valor (R$)': 'sum',
            'Tipo': lambda x: x.mode().iloc[0] if not x.empty else 'Misto',
            'Data': 'count'  # Contar transações
        }).reset_index()
        
        # Renomear colunas
        resultado.columns = ['Subcategoria', 'Valor', 'Tipo', 'Qtd']
        
        # Reordenar colunas
        resultado = resultado[['Subcategoria', 'Tipo', 'Qtd', 'Valor']]
        
        # Limitar tamanho da descrição
        resultado['Subcategoria'] = resultado['Subcategoria'].apply(
            lambda x: str(x)[:80] + "..." if len(str(x)) > 80 else str(x)
        )
        
        # Filtrar valores significativos
        resultado = resultado[resultado['Valor'].abs() > 0.01]
        
        # Calcular percentuais
        total = resultado['Valor'].sum()
        if total != 0:
            resultado['% Categoria'] = (resultado['Valor'] / total * 100).round(2)
        else:
            resultado['% Categoria'] = 0.0
        
        # Ordenar por valor absoluto (maior → menor)
        resultado = resultado.sort_values(by='Valor', key=abs, ascending=False)
        
        return resultado.reset_index(drop=True)
        
    except Exception as e:
        st.error(f"Erro ao processar detalhamento: {e}")
        return pd.DataFrame()
    categorias_ordenadas = []
    categorias_restantes = list(categorias)
    
    for categoria_dre in ordem_dre:
        if categoria_dre in categorias_restantes:
            categorias_ordenadas.append(categoria_dre)
            categorias_restantes.remove(categoria_dre)
    
    # Adicionar categorias restantes no final
    categorias_ordenadas.extend(sorted(categorias_restantes))
    
    return categorias_ordenadas

def calcular_resultado_gerencial(dados_orcamento, meses_orcamento):
    """Recalcula o RESULTADO GERENCIAL = RESULTADO + SALDO + ESTOQUE"""
    for mes in meses_orcamento:
        if mes in dados_orcamento:
            resultado = dados_orcamento[mes].get('RESULTADO', 0)
            saldo = dados_orcamento[mes].get('SALDO', 0)
            estoque = dados_orcamento[mes].get('ESTOQUE', 0)
            
            # Aplicar fórmula correta
            dados_orcamento[mes]['RESULTADO GERENCIAL'] = resultado + saldo + estoque
    
    return dados_orcamento

def aplicar_saldos_calculados(dados_orcamento, meses_orcamento, licenca_id):
    """Aplica saldos calculados baseados no Vyco nos dados do orçamento"""
    try:
        # Calcular saldos mensais usando o saldo_manager (NOVA LÓGICA DUAL)
        saldos_mensais = saldo_manager.calcular_saldos_mensais(dados_orcamento, licenca_id)
        
        # Aplicar saldos nos dados do orçamento
        for mes in meses_orcamento:
            if mes in saldos_mensais:
                if mes not in dados_orcamento:
                    dados_orcamento[mes] = {}
                dados_orcamento[mes]['SALDO'] = saldos_mensais[mes]
        
        # Indicar qual lógica foi aplicada
        if saldos_mensais and meses_orcamento:
            primeiro_mes = min(meses_orcamento)
            ano_orcamento = int(primeiro_mes.split('-')[0])
            
            if ano_orcamento <= 2025:
                st.success(f"✅ Saldos calculados RETROATIVAMENTE para {len(saldos_mensais)} meses (ano {ano_orcamento} - dados históricos)")
            else:
                st.success(f"✅ Saldos calculados PROGRESSIVAMENTE para {len(saldos_mensais)} meses (ano {ano_orcamento} - orçamento futuro)")
                
    except Exception as e:
        st.warning(f"⚠️ Erro ao calcular saldos retroativos: {str(e)}")
        # Manter saldos zerados em caso de erro
        for mes in meses_orcamento:
            if mes not in dados_orcamento:
                dados_orcamento[mes] = {}
            dados_orcamento[mes]['SALDO'] = 0
    
    return dados_orcamento

def criar_df_cenario_mensal(dados_orcamento, dados_ano_base, dados_realizado, meses_orcamento, categorias, ano_base, ano_orcamento):
    """Cria DataFrame mensal no formato dos cenários com comparação ano base vs realizado"""
    
    # Ordenar categorias seguindo padrão dos cenários
    categorias_ordenadas = ordenar_categorias_dre(categorias)
    
    # Criar DataFrame mensal
    dados_cenario = []
    
    for categoria in categorias_ordenadas:
        linha = {"Categoria": categoria}
        
        # Adicionar 4 colunas por mês: Base | Orçado | Ano Orçamento | Diferença
        for mes in meses_orcamento:
            # Extrair apenas o nome do mês (ex: "2026-01" -> "Jan")
            mes_numero = mes.split('-')[1]
            mes_nomes = {
                '01': 'Jan', '02': 'Fev', '03': 'Mar', '04': 'Abr', 
                '05': 'Mai', '06': 'Jun', '07': 'Jul', '08': 'Ago',
                '09': 'Set', '10': 'Out', '11': 'Nov', '12': 'Dez'
            }
            mes_nome = mes_nomes.get(mes_numero, mes_numero)
            
            # Valor do ano base (mês correspondente)
            mes_base = mes.replace(str(ano_orcamento), str(ano_base))
            valor_base = dados_ano_base.get(mes_base, {}).get(categoria, 0)
            
            # Valor orçado (planejado)
            valor_orcamento = dados_orcamento.get(mes, {}).get(categoria, 0)
            
            # Valor realizado do ano de orçamento (se existir)
            valor_realizado = dados_realizado.get(mes, {}).get(categoria, 0)
            
            # Diferença entre realizado e base (só calcular se houver dados realizados)
            if valor_realizado != 0:
                diferenca = valor_realizado - valor_base
            else:
                diferenca = 0  # Sem dados realizados ainda
            
            # Adicionar colunas formatadas em sequência
            linha[f"{mes_nome}/{ano_base}"] = formatar_valor_br(valor_base)
            linha[f"Orçado {mes_nome}"] = formatar_valor_br(valor_orcamento)
            linha[f"{mes_nome}/{ano_orcamento}"] = formatar_valor_br(valor_realizado) if valor_realizado != 0 else "-"
            linha[f"Diferença {mes_nome}"] = formatar_valor_br(diferenca) if diferenca != 0 else "-"
        
        dados_cenario.append(linha)
    
    return pd.DataFrame(dados_cenario)

    # Categorias ordenadas seguindo DRE
    categorias_ordenadas = []
    
    # Adicionar categorias na ordem da DRE
    for cat in ordem_dre:
        if cat in categorias:
            categorias_ordenadas.append(cat)
    
    # Adicionar categorias não mapeadas no final
    for cat in sorted(categorias):
        if cat not in categorias_ordenadas:
            categorias_ordenadas.append(cat)
    
    return categorias_ordenadas

def highlight_rows_cenario(row):
    """Aplica cores às linhas seguindo padrão dos cenários"""
    categoria = row["Categoria"].upper() if isinstance(row.iloc[0], str) else row.iloc[0].upper()
    
    # Cores específicas para categorias dos cenários
    cores_cenario = {
        "FATURAMENTO": ("#5d65c8", "white"),
        "RECEITA": ("#152357", "white"),
        "MARGEM CONTRIBUIÇÃO": ("#39b79c", "black"),
        "LUCRO OPERACIONAL": ("#39b79c", "black"),
        "LUCRO LIQUIDO": ("#39b79c", "black"),
        "RESULTADO": ("#216a5a", "white"),
        "RESULTADO GERENCIAL": ("#216a5a", "white"),
    }
    
    # Verificar se categoria corresponde a alguma cor especial
    for key, (bg_color, text_color) in cores_cenario.items():
        if key in categoria:
            return [f'background-color: {bg_color}; color: {text_color}; font-weight: bold'] * len(row)
    
    # Cor padrão para outras categorias (fundo escuro como nos cenários)
    return ['background-color: #2e3137; color: white'] * len(row)



def formatar_df_detalhamento(df):
    """
    Formata DataFrame de detalhamento com estilo brasileiro
    """
    if df.empty:
        return df
        
    df_formatado = df.copy()
    
    # Formatar colunas de valores para o padrão brasileiro
    for coluna in ['Base (2025)', 'Orçamento (2026)']:
        if coluna in df_formatado.columns:
            df_formatado[coluna] = df_formatado[coluna].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) and x != 0 else "R$ 0,00"
            )
    
    return df_formatado

# ===== INÍCIO DA INTERFACE =====
    """
    Obtém detalhamento das subcategorias que compõem uma categoria principal usando dados reais do Vyco
    
    Args:
        empresa_selecionada: Nome da empresa
        categoria_principal: Categoria principal (ex: 'DESPESA OPERACIONAL')
        ano_base: Ano de referência dos dados
        
    Returns:
        DataFrame com subcategorias e valores consolidados
    """
    try:
        # Importar funções do Vyco
        import sys
        import os
        
        # Adicionar o diretório pages ao path se não estiver
        pages_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'pages')
        if pages_dir not in sys.path:
            sys.path.append(pages_dir)
            
        # Importar diretamente do arquivo
        import importlib.util
        vyco_file = os.path.join(pages_dir, '5_Integracao_Vyco.py')
        spec = importlib.util.spec_from_file_location("integracao_vyco", vyco_file)
        integracao_vyco = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(integracao_vyco)
        
        obter_dados_vyco = integracao_vyco.buscar_lancamentos_vyco
        processar_dados_vyco = integracao_vyco.processar_dados_vyco
        from logic.licenca_manager import obter_uuid_por_nome
        
        # Obter UUID da licença
        licenca_uuid = obter_uuid_por_nome(empresa_selecionada)
        if not licenca_uuid:
            st.warning(f"UUID não encontrado para licença: {empresa_selecionada}")
            return pd.DataFrame()
        
        # Buscar dados do Vyco (últimos 10000 lançamentos)
        df_raw = obter_dados_vyco(licenca_uuid, limit=10000)
        if df_raw is None or df_raw.empty:
            st.info("Nenhum lançamento encontrado no Vyco")
            return pd.DataFrame()
        
        # Processar dados
        df_transacoes = processar_dados_vyco(df_raw)
        if df_transacoes.empty:
            return pd.DataFrame()
        
        # Filtrar por categoria selecionada
        if 'Categoria_Vyco' not in df_transacoes.columns:
            st.warning("⚠️ Categorização Vyco não disponível. Usando dados do cache DRE...")
            # Fallback para método original
            dados_dre = cache_manager.carregar_dre(empresa_selecionada)
            if not dados_dre:
                return pd.DataFrame()
            return obter_detalhamento_cache_dre(dados_dre, categoria_principal, ano_base)
        
        # Filtrar transações por categoria
        df_categoria = df_transacoes[
            df_transacoes['Categoria_Vyco'].str.contains(categoria_principal, case=False, na=False)
        ].copy()
        
        if df_categoria.empty:
            st.info(f"Nenhuma transação encontrada para a categoria '{categoria_principal}'")
            return pd.DataFrame()
        
        # Filtrar por ano se houver coluna Data
        if 'Data' in df_categoria.columns:
            df_categoria['Data'] = pd.to_datetime(df_categoria['Data'])
            df_categoria = df_categoria[df_categoria['Data'].dt.year == ano_base]
        
        if df_categoria.empty:
            st.info(f"Nenhuma transação encontrada para a categoria '{categoria_principal}' no ano {ano_base}")
            return pd.DataFrame()
        
        # Agrupar por descrição/subcategoria
        subcategorias_valores = {}
        for descricao, grupo in df_categoria.groupby('Descrição'):
            valor_total = grupo['Valor (R$)'].sum()
            qtd_transacoes = len(grupo)
            
            # Limitar tamanho da descrição
            descricao_limpa = descricao[:50] + "..." if len(descricao) > 50 else descricao
            
            if abs(valor_total) > 0.01:  # Só incluir se houver valor significativo
                subcategorias_valores[descricao_limpa] = {
                    'valor': valor_total,
                    'quantidade': qtd_transacoes,
                    'tipo': grupo['Tipo'].mode().iloc[0] if not grupo['Tipo'].empty else "Misto"
                }
        
        # Criar DataFrame
        if subcategorias_valores:
            df_detalhamento = pd.DataFrame([
                {
                    'Subcategoria': subcat,
                    'Tipo': dados['tipo'],
                    'Qtd_Transações': dados['quantidade'],
                    'Base (2025)': dados['valor'],
                    'Orçamento (2026)': dados['valor']  # Valor inicial igual ao base
                }
                for subcat, dados in subcategorias_valores.items()
            ])
            
            # Ordenar por valor absoluto (maior para menor)
            df_detalhamento = df_detalhamento.sort_values(
                by='Base (2025)', key=abs, ascending=False
            ).reset_index(drop=True)
            
            return df_detalhamento
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.warning(f"⚠️ Erro ao carregar detalhamento: {str(e)}")
        return pd.DataFrame()

def obter_detalhamento_cache_dre(dados_dre, categoria_principal, ano_base):
    """
    Método de fallback usando cache DRE quando dados Vyco não estão disponíveis
    """
    subcategorias_valores = {}
    
    # Buscar na estrutura DRE
    if isinstance(dados_dre, dict) and 'dre_estruturado' in dados_dre:
        estrutura = dados_dre['dre_estruturado']
        
        # Navegar pelas seções do DRE
        for secao_nome, secao_dados in estrutura.items():
            if isinstance(secao_dados, dict) and 'itens' in secao_dados:
                itens = secao_dados['itens']
                
                if categoria_principal in itens:
                    categoria_dados = itens[categoria_principal]
                    
                    # Buscar subcategorias se existirem
                    if isinstance(categoria_dados, dict):
                        if 'subitens' in categoria_dados:
                            # Tem subcategorias detalhadas
                            subitens = categoria_dados['subitens']
                            for subcat_nome, subcat_dados in subitens.items():
                                if isinstance(subcat_dados, dict) and 'valores' in subcat_dados:
                                    valores_mensais = subcat_dados['valores']
                                    valores_ano_base = {mes: valor for mes, valor in valores_mensais.items() 
                                                      if mes.startswith(str(ano_base))}
                                    total_anual = sum(float(v) if v else 0 for v in valores_ano_base.values())
                                    if total_anual != 0:
                                        subcategorias_valores[subcat_nome] = total_anual
                        elif 'valores' in categoria_dados:
                            # Não tem subcategorias, usar o valor total da categoria
                            valores_mensais = categoria_dados['valores']
                            valores_ano_base = {mes: valor for mes, valor in valores_mensais.items() 
                                              if mes.startswith(str(ano_base))}
                            total_anual = sum(float(v) if v else 0 for v in valores_ano_base.values())
                            if total_anual != 0:
                                subcategorias_valores[categoria_principal] = total_anual
    
    # Criar DataFrame
    if subcategorias_valores:
        df_detalhamento = pd.DataFrame([
            {
                'Subcategoria': subcat,
                'Base (2025)': valor,
                'Orçamento (2026)': valor
            }
            for subcat, valor in subcategorias_valores.items()
        ])
        return df_detalhamento
    else:
        return pd.DataFrame()

def formatar_df_detalhamento(df):
    """
    Formata DataFrame de detalhamento com estilo brasileiro
    """
    if df.empty:
        return df
        
    df_formatado = df.copy()
    
    # Formatar colunas de valores para o padrão brasileiro
    for coluna in ['Base (2025)', 'Orçamento (2026)']:
        if coluna in df_formatado.columns:
            df_formatado[coluna] = df_formatado[coluna].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) and x != 0 else "R$ 0,00"
            )
    
    return df_formatado

# Sidebar - Configurações
st.sidebar.header("⚙️ Configurações Orçamento")

# Listar empresas/licenças disponíveis
licencas_ativas = licenca_manager.obter_licencas_ativas()
empresas_disponiveis = cache_manager.listar_empresas_disponiveis()

if not licencas_ativas:
    st.warning("⚠️ Nenhuma licença ativa encontrada no CSV.")
    st.info("🔧 **Para adicionar licenças:**")
    st.info("1. Vá em 'Integração Vyco'")
    st.info("2. Selecione '🔧 Gerenciar Licenças'")
    st.info("3. Adicione novas licenças")
    st.stop()

if not empresas_disponiveis:
    st.warning("⚠️ Nenhuma empresa com dados no cache encontrada.")
    st.info("🔄 **Para usar este módulo:**")
    st.info("1. Importe dados via 'Integração Vyco'")
    st.info("2. Os dados serão salvos automaticamente no cache")
    st.info("3. Retorne a esta página para criar orçamentos")
    st.stop()

# Seleção da licença/empresa
empresa_selecionada = st.sidebar.selectbox(
    "📋 Cliente/Licença",
    licencas_ativas
)

# Verificar se a licença tem dados no cache
if empresa_selecionada not in [emp['nome'] for emp in empresas_disponiveis]:
    st.sidebar.warning(f"⚠️ '{empresa_selecionada}' sem dados no cache")
    st.sidebar.info("🔄 Importe dados via Vyco primeiro")

# Seleção do ano base e ano orçamento
col1, col2 = st.sidebar.columns(2)
with col1:
    ano_base = st.selectbox(
        "📅 Ano Base",
        [2024, 2025],
        index=1  # Padrão 2025
    )

with col2:
    ano_orcamento = st.selectbox(
        "📈 Ano Orçamento",
        [2025, 2026, 2027],
        index=1  # Padrão 2026
    )

# Seleção do tipo de dados
tipo_dados = st.sidebar.radio(
    "📊 Tipo de Análise",
    ["DRE", "Fluxo de Caixa"],
    index=0
)

st.sidebar.markdown("---")

# Status dos dados
st.sidebar.markdown("---")
st.sidebar.markdown("### 📋 Status dos Dados")

# Mostrar ID da licença
id_licenca = licenca_manager.obter_id_licenca(empresa_selecionada)
if id_licenca:
    st.sidebar.success(f"✅ Licença ativa")
    st.sidebar.caption(f"🔑 ID: {id_licenca[:8]}...{id_licenca[-8:]}")
else:
    st.sidebar.error("❌ ID da licença não encontrado")

# Verificar se existem dados base
dados_empresa = next((emp for emp in empresas_disponiveis if emp['nome'] == empresa_selecionada), None)

if dados_empresa:
    if dados_empresa.get('dre'):
        st.sidebar.success("✅ DRE disponível")
    else:
        st.sidebar.error("❌ DRE não encontrado")
    
    if dados_empresa.get('fluxo_caixa'):
        st.sidebar.success("✅ Fluxo de Caixa disponível")
    else:
        st.sidebar.error("❌ Fluxo de Caixa não encontrado")

# Verificar se existe orçamento salvo
orcamento_existente = orcamento_manager.carregar_orcamento(empresa_selecionada, ano_orcamento)
if orcamento_existente:
    st.sidebar.success("💾 Orçamento salvo encontrado")
    ultima_atualizacao = orcamento_existente.get('configuracoes', {}).get('ultima_atualizacao', 'Desconhecida')
    if ultima_atualizacao != 'Desconhecida':
        try:
            dt = datetime.fromisoformat(ultima_atualizacao.replace('Z', '+00:00'))
            st.sidebar.caption(f"📅 Atualizado: {dt.strftime('%d/%m/%Y %H:%M')}")
        except:
            st.sidebar.caption(f"📅 Atualizado: {ultima_atualizacao}")
else:
    st.sidebar.info("📝 Novo orçamento")

# Facilitadores rápidos
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔧 Facilitadores Rápidos")

# Crescimento geral
col1, col2 = st.sidebar.columns([2, 1])
with col1:
    crescimento_geral = st.number_input(
        "Crescimento Geral (%)",
        value=10.0,
        step=1.0,
        format="%.1f"
    )
with col2:
    if st.button("Aplicar", key="crescimento"):
        st.session_state.aplicar_crescimento = crescimento_geral

# Principais abas
tab1, tab2, tab3 = st.tabs(["📊 Comparativo Mensal", "📈 Gráficos", "⚙️ Configurações"])

with tab1:
    # Informações das Contas Bancárias
    st.subheader("🏦 Informações das Contas Bancárias")
    
    if empresa_selecionada and empresa_selecionada != "Selecione uma empresa":
        # Obter dados das contas bancárias
        licenca_id = licenca_manager.obter_id_licenca(empresa_selecionada)
        
        if licenca_id:
            
            # Buscar dados das contas via Vyco
            saldo_manager_temp = SaldoContasManager()
            saldo_atual = saldo_manager_temp.buscar_saldo_atual_vyco(licenca_id)
            
            if saldo_atual > 0:
                # Exibir DataFrame com informações das contas
                df_contas = saldo_manager_temp.exibir_dados_contas_debug()
                
                if not df_contas.empty:
                    st.markdown("**📋 Dados das Contas Bancárias:**")
                    st.dataframe(df_contas, use_container_width=True, hide_index=True)
                    
                    # Mostrar total consolidado
                    saldo_formatado = f"R$ {saldo_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    st.markdown(f"💰 Saldo Total Atual: {saldo_formatado}")
                else:
                    st.info("📊 Dados detalhados das contas não disponíveis")
                    saldo_formatado = f"R$ {saldo_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    st.markdown(f"💰 Saldo Total Atual: {saldo_formatado}")
            else:
                st.warning("⚠️ Não foi possível obter dados das contas bancárias")
        else:
            st.error("❌ Empresa não encontrada")
    else:
        st.info("👆 Selecione uma empresa para ver as informações das contas")
    
    st.markdown("---")
    
    # Carregar dados base
    tipo_cache = "dre" if tipo_dados == "DRE" else "fluxo_caixa"
    dados_base = orcamento_manager.extrair_dados_base_do_cache(empresa_selecionada, tipo_cache)
    
    if not dados_base:
        st.error(f"❌ Não foi possível carregar dados base de {tipo_dados} para {empresa_selecionada}")
        st.stop()
    
    # Filtrar dados do ano base
    dados_ano_base = {mes: dados for mes, dados in dados_base.items() if mes.startswith(str(ano_base))}
    
    if not dados_ano_base:
        st.error(f"❌ Não foram encontrados dados para o ano base {ano_base}")
        st.stop()
    
    # Inicializar dados do orçamento
    meses_orcamento = obter_meses_ano(ano_orcamento)
    
    # Carregar orçamento existente ou criar novo
    if orcamento_existente:
        dados_orcamento = orcamento_existente.get('orcamento_mensal', {})
        dados_realizado = orcamento_existente.get('realizado_mensal', {})
    else:
        # Criar orçamento base copiando dados do ano anterior (mesmo mês)
        dados_orcamento = {}
        dados_realizado = {}
        
        for mes_orc in meses_orcamento:
            # Buscar mês correspondente no ano base
            mes_base = mes_orc.replace(str(ano_orcamento), str(ano_base))
            if mes_base in dados_ano_base:
                dados_orcamento[mes_orc] = dados_ano_base[mes_base].copy()
            else:
                # Se não encontrar, usar primeiro mês disponível como base
                primeiro_mes = next(iter(dados_ano_base.values()), {})
                dados_orcamento[mes_orc] = primeiro_mes.copy() if primeiro_mes else {}
    
    # Aplicar facilitadores se solicitado
    if st.session_state.get('aplicar_crescimento'):
        dados_orcamento = orcamento_manager.aplicar_facilitador(
            'percentual', 
            st.session_state.aplicar_crescimento, 
            dados_orcamento
        )
        # Recalcular RESULTADO GERENCIAL após aplicar facilitadores
        dados_orcamento = calcular_resultado_gerencial(dados_orcamento, meses_orcamento)
        del st.session_state.aplicar_crescimento
    
    # Interface de orçamento mensal (formato cenários)
    st.markdown(f"## 📊 {tipo_dados.upper()} - Cenário Orçamentário {ano_orcamento}")
    
    # Extrair todas as categorias dos dados
    todas_categorias = set()
    for dados_mes in dados_orcamento.values():
        todas_categorias.update(dados_mes.keys())
    for dados_mes in dados_ano_base.values():
        todas_categorias.update(dados_mes.keys())
    
    categorias = list(todas_categorias)
    
    # Aplicar saldos calculados baseados no Vyco
    # Buscar licença da empresa selecionada
    licenca_id = licenca_manager.obter_id_licenca(empresa_selecionada)
    if licenca_id:
        dados_orcamento = aplicar_saldos_calculados(dados_orcamento, meses_orcamento, licenca_id)
    else:
        # Manter saldos zerados se não houver licença
        for mes in meses_orcamento:
            if mes not in dados_orcamento:
                dados_orcamento[mes] = {}
            dados_orcamento[mes]['SALDO'] = 0
    
    # Recalcular RESULTADO GERENCIAL com fórmula correta
    dados_orcamento = calcular_resultado_gerencial(dados_orcamento, meses_orcamento)
    
    # Criar DataFrame mensal igual aos cenários com comparação
    df_cenario_mensal = criar_df_cenario_mensal(dados_orcamento, dados_ano_base, dados_realizado, meses_orcamento, categorias, ano_base, ano_orcamento)
    
    # Exibir tabela mensal com estilo de cenários
    st.dataframe(
        df_cenario_mensal.style.apply(highlight_rows_cenario, axis=1),
        use_container_width=True, 
        hide_index=True,
        height=650
    )
    
    # Opção de download
    csv = df_cenario_mensal.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar Orçamento como CSV",
        data=csv,
        file_name=f"orcamento_{empresa_selecionada}_{ano_orcamento}.csv",
        mime="text/csv",
    )
    
    # 🔍 DETALHAMENTO DE COMPOSIÇÃO (NOVO - VERSÃO LIMPA)
    st.markdown("---")
    with st.expander("🔍 **Detalhamento de Composição (Ano Base)** - Veja o que compõe cada linha do orçamento", expanded=False):
        st.markdown("""
        📊 **Como funciona:** Selecione uma categoria e um mês para ver todas as transações que compõem aquele valor.
        Os dados são carregados diretamente do cache (rápido) e agrupados por subcategoria.
        """)
        
        col_det1, col_det2 = st.columns(2)
        
        with col_det1:
            categoria_detalhamento = st.selectbox(
                "📋 Selecione a categoria",
                ordenar_categorias_dre(categorias),
                key="cat_detalhamento"
            )
        
        with col_det2:
            # Meses do ano base
            meses_base_detalhamento = [mes.replace(str(ano_orcamento), str(ano_base)) for mes in meses_orcamento]
            mes_detalhamento = st.selectbox(
                "📅 Selecione o mês (Ano Base)",
                meses_base_detalhamento,
                format_func=nome_mes_pt,
                key="mes_detalhamento"
            )
        
        # Exibir detalhamento automaticamente ao selecionar
        if categoria_detalhamento and mes_detalhamento:
            with st.spinner("Carregando detalhamento..."):
                # Usar detalhamento salvo no cache DRE (já tem a informação agregada)
                detalhamento_lista = cache_manager.carregar_detalhamento_categoria_mes(
                    empresa_selecionada,
                    categoria_detalhamento,
                    mes_detalhamento
                )
                
                if detalhamento_lista is not None and len(detalhamento_lista) > 0:
                    # Converter lista de dicts para DataFrame
                    df_exibir = pd.DataFrame(detalhamento_lista)
                    
                    # Renomear colunas se necessário
                    if 'subcategoria' in df_exibir.columns:
                        df_exibir = df_exibir.rename(columns={
                            'subcategoria': 'Subcategoria',
                            'valor': 'Valor',
                            'quantidade': 'Qtd',
                            'tipo': 'Tipo'
                        })
                    
                    # Calcular totais e percentuais
                    if 'Valor' in df_exibir.columns:
                        total = df_exibir['Valor'].sum()
                        if total != 0 and '% Categoria' not in df_exibir.columns:
                            df_exibir['% Categoria'] = (df_exibir['Valor'] / total * 100).round(2)
                    
                    # Ordenar por valor
                    if 'Valor' in df_exibir.columns:
                        df_exibir = df_exibir.sort_values(by='Valor', key=abs, ascending=False)
                    
                    # Exibir título
                    st.markdown(f"#### 📊 Composição: {categoria_detalhamento} - {nome_mes_pt(mes_detalhamento)}")
                    
                    # Formatar valores para exibição
                    df_display = df_exibir.copy()
                    if 'Valor' in df_display.columns:
                        df_display['Valor'] = df_display['Valor'].apply(formatar_valor_br)
                    if '% Categoria' in df_display.columns:
                        df_display['% Categoria'] = df_display['% Categoria'].apply(lambda x: f"{x:.2f}%")
                    
                    # Exibir tabela
                    st.dataframe(
                        df_display, 
                        use_container_width=True, 
                        hide_index=True,
                        height=400
                    )
                    
                    # Mostrar resumo
                    total_valor = df_exibir['Valor'].sum() if 'Valor' in df_exibir.columns else 0
                    total_subcategorias = len(df_exibir)
                    total_transacoes = int(df_exibir['Qtd'].sum()) if 'Qtd' in df_exibir.columns else 0
                    
                    st.info(f"💰 **Total:** {formatar_valor_br(total_valor)} | 📝 **{total_subcategorias}** subcategorias | 🔢 **{total_transacoes}** transações")
                    
                    # Botão de download do detalhamento
                    csv_detalhamento = df_display.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Baixar Detalhamento como CSV",
                        data=csv_detalhamento,
                        file_name=f"detalhamento_{categoria_detalhamento}_{mes_detalhamento}.csv",
                        mime="text/csv",
                        key="download_detalhamento"
                    )
                else:
                    st.warning(f"⚠️ **Sem detalhamento para {categoria_detalhamento} em {nome_mes_pt(mes_detalhamento)}**")
                    st.info("💡 **Possíveis causas:**\n- Não há transações neste período\n- DRE precisa ser regenerado na aba **Integração Vyco**")
    
    # Interface de edição detalhada por mês
    st.markdown("---")
    st.markdown("### ✏️ Edição Detalhada por Mês")
    
    col1, col2 = st.columns(2)
    
    with col1:
        mes_edicao = st.selectbox(
            "📅 Selecione o mês para edição",
            meses_orcamento,
            format_func=nome_mes_pt,
            key="mes_edicao"
        )
    
    with col2:
        categoria_edicao = st.selectbox(
            "📋 Categoria para editar",
            ordenar_categorias_dre(todas_categorias := set().union(*[dados_mes.keys() for dados_mes in dados_orcamento.values()])),
            key="categoria_edicao"
        )
    
    if mes_edicao and categoria_edicao:
        col_edit1, col_edit2, col_edit3 = st.columns(3)
        
        with col_edit1:
            st.markdown("#### 📊 Dados Base")
            mes_base_correspondente = mes_edicao.replace(str(ano_orcamento), str(ano_base))
            valor_base = dados_ano_base.get(mes_base_correspondente, {}).get(categoria_edicao, 0)
            st.metric("Ano Base", formatar_valor_br(valor_base))
        
        with col_edit2:
            st.markdown("#### ✏️ Orçamento")
            valor_atual = dados_orcamento.get(mes_edicao, {}).get(categoria_edicao, 0)
            valor_editado = st.number_input(
                f"{categoria_edicao}",
                value=float(valor_atual),
                step=1000.0,
                format="%.2f",
                key=f"edit_{categoria_edicao}_{mes_edicao}"
            )
            
            # Atualizar dados de orçamento
            if mes_edicao not in dados_orcamento:
                dados_orcamento[mes_edicao] = {}
            dados_orcamento[mes_edicao][categoria_edicao] = valor_editado
            
            # Recalcular RESULTADO GERENCIAL após edição
            dados_orcamento = calcular_resultado_gerencial(dados_orcamento, meses_orcamento)
        
        with col_edit3:
            st.markdown("#### 📈 Comparação")
            if valor_base != 0:
                variacao = ((valor_editado - valor_base) / valor_base) * 100
                st.metric(
                    "Variação vs Base", 
                    f"{variacao:+.1f}%",
                    f"{formatar_valor_br(valor_editado - valor_base)}"
                )
with tab2:
    st.markdown("## 📈 Análise Gráfica")
    
    if 'dados_orcamento' in locals() and 'dados_ano_base' in locals():
        # Preparar dados para gráfico
        categorias_graf = st.multiselect(
            "Selecione categorias para visualizar",
            categorias,
            default=categorias[:3] if len(categorias) >= 3 else categorias
        )
        
        if categorias_graf:
            # Criar gráfico comparativo
            fig = go.Figure()
            
            meses_display = [nome_mes_pt(mes) for mes in meses_orcamento]
            
            for categoria in categorias_graf:
                valores_orcados = [dados_orcamento.get(mes, {}).get(categoria, 0) for mes in meses_orcamento]
                
                fig.add_trace(go.Scatter(
                    x=meses_display,
                    y=valores_orcados,
                    mode='lines+markers',
                    name=f"{categoria} (Orçado)",
                    line=dict(width=3)
                ))
            
            fig.update_layout(
                title=f"Evolução {tipo_dados} - {ano_orcamento}",
                xaxis_title="Meses",
                yaxis_title="Valor (R$)",
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.markdown("## ⚙️ Configurações Avançadas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💾 Salvar Orçamento")
        if st.button("💾 Salvar Orçamento Atual", type="primary"):
            if 'dados_orcamento' in locals():
                resultado = orcamento_manager.salvar_orcamento(
                    empresa_selecionada,
                    ano_orcamento,
                    ano_base,
                    dados_orcamento,
                    dados_realizado,
                    {
                        'tipo_dados': tipo_cache,
                        'criado_por': 'usuario',
                        'observacoes': 'Orçamento criado via interface web'
                    }
                )
                
                if resultado:
                    st.success("✅ Orçamento salvo com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Erro ao salvar orçamento")
    
    with col2:
        st.markdown("### 🗑️ Limpar Dados")
        if st.button("🗑️ Resetar Orçamento", type="secondary"):
            if st.session_state.get('confirmar_reset'):
                # Resetar dados
                st.session_state.clear()
                st.success("✅ Dados resetados!")
                st.rerun()
            else:
                st.session_state.confirmar_reset = True
                st.warning("⚠️ Clique novamente para confirmar")