import streamlit as st
import pandas as pd
import io
from datetime import datetime
from extractors.ofx_extractor import extrair_lancamentos_ofx

st.set_page_config(page_title="Análise OFX vs Excel", layout="wide")
st.title("🔄 Reconciliação Bancária: OFX vs Excel")

st.markdown("""
Esta ferramenta permite comparar transações bancárias (OFX) com sua planilha de controle (Excel).
Identifique rapidamente transações que estão em um sistema mas não no outro.
""")

# =====================================
# Inicialização do Session State
# =====================================
if 'df_ofx' not in st.session_state:
    st.session_state.df_ofx = None
if 'df_excel' not in st.session_state:
    st.session_state.df_excel = None
if 'df_reconciliado' not in st.session_state:
    st.session_state.df_reconciliado = None
if 'col_data_excel' not in st.session_state:
    st.session_state.col_data_excel = None
if 'col_valor_excel' not in st.session_state:
    st.session_state.col_valor_excel = None
if 'tolerancia_valor' not in st.session_state:
    st.session_state.tolerancia_valor = 0.01

# =====================================
# ETAPA 1: Upload de Arquivos OFX
# =====================================
st.header("📤 Etapa 1: Carregar Arquivos OFX (Banco)")

with st.expander("ℹ️ Como funciona o upload de OFX", expanded=False):
    st.markdown("""
    - Faça upload de um ou mais arquivos OFX do seu banco
    - O sistema vai consolidar todas as transações em uma única tabela
    - Campos extraídos: Data, Descrição, Valor, Tipo
    """)

uploaded_ofx = st.file_uploader(
    "📁 Envie os arquivos .OFX aqui",
    type=["ofx"],
    accept_multiple_files=True,
    key="uploader_ofx"
)

if uploaded_ofx:
    if st.button("🔄 Processar Arquivos OFX", key="processar_ofx"):
        todas_transacoes = []
        
        with st.spinner("Processando arquivos OFX..."):
            for file in uploaded_ofx:
                transacoes, encoding = extrair_lancamentos_ofx(file, file.name)
                
                if isinstance(transacoes, str) or not transacoes:
                    st.error(f"❌ Erro ao processar {file.name}: {encoding}")
                    continue
                
                st.success(f"✅ {file.name} processado (codificação: {encoding})")
                todas_transacoes.extend(transacoes)
        
        if todas_transacoes:
            df_ofx = pd.DataFrame(todas_transacoes)
            
            # Garantir que a coluna de data está em formato datetime
            if 'Data' in df_ofx.columns:
                df_ofx['Data'] = pd.to_datetime(df_ofx['Data'], errors='coerce')
            
            # Garantir que valor está em float
            if 'Valor (R$)' in df_ofx.columns:
                # Remover formatação se existir
                if df_ofx['Valor (R$)'].dtype == 'object':
                    df_ofx['Valor_Float'] = df_ofx['Valor (R$)'].apply(lambda x: 
                        float(str(x).replace(".", "").replace(",", ".").replace("R$", "").strip()) 
                        if isinstance(x, str) else float(x)
                    )
                else:
                    df_ofx['Valor_Float'] = df_ofx['Valor (R$)'].astype(float)
            
            st.session_state.df_ofx = df_ofx
            st.success(f"✅ {len(df_ofx)} transações carregadas do OFX")

# Exibir preview do OFX
if st.session_state.df_ofx is not None:
    st.subheader("📊 Preview das Transações OFX")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Transações", len(st.session_state.df_ofx))
    with col2:
        if 'Valor_Float' in st.session_state.df_ofx.columns:
            total = st.session_state.df_ofx['Valor_Float'].sum()
            st.metric("Valor Total", f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    with col3:
        if 'Data' in st.session_state.df_ofx.columns:
            datas = st.session_state.df_ofx['Data'].dropna()
            if len(datas) > 0:
                periodo = f"{datas.min().strftime('%d/%m/%Y')} a {datas.max().strftime('%d/%m/%Y')}"
                st.metric("Período", periodo)
    
    # Mostrar amostra
    st.dataframe(st.session_state.df_ofx.head(10), use_container_width=True)

st.divider()

# =====================================
# ETAPA 2: Upload de Arquivo Excel
# =====================================
st.header("📤 Etapa 2: Carregar Planilha Excel")

with st.expander("ℹ️ Como funciona o upload de Excel", expanded=False):
    st.markdown("""
    - Faça upload do seu arquivo Excel com transações
    - Você escolherá quais colunas representam a Data e o Valor
    - O sistema vai padronizar os dados para comparação
    """)

uploaded_excel = st.file_uploader(
    "📁 Envie o arquivo .XLSX ou .XLS aqui",
    type=["xlsx", "xls"],
    key="uploader_excel"
)

if uploaded_excel:
    try:
        df_excel_raw = pd.read_excel(uploaded_excel)
        
        st.success(f"✅ Arquivo Excel carregado: {len(df_excel_raw)} linhas")
        
        st.subheader("🔧 Configuração das Colunas")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Selecione a coluna de DATA:**")
            col_data = st.selectbox(
                "Qual coluna contém as datas?",
                options=df_excel_raw.columns.tolist(),
                key="select_col_data"
            )
        
        with col2:
            st.markdown("**Selecione a coluna de VALOR:**")
            col_valor = st.selectbox(
                "Qual coluna contém os valores?",
                options=df_excel_raw.columns.tolist(),
                key="select_col_valor"
            )
        
        # Tolerância para comparação de valores
        st.markdown("**Tolerância para comparação de valores:**")
        tolerancia = st.number_input(
            "Diferença máxima aceita (R$)",
            min_value=0.00,
            max_value=10.00,
            value=0.01,
            step=0.01,
            help="Valores que diferem até este montante serão considerados iguais"
        )
        
        if st.button("✅ Confirmar Configuração e Processar Excel", key="processar_excel"):
            with st.spinner("Processando planilha Excel..."):
                df_excel = df_excel_raw.copy()
                
                # Processar coluna de data
                try:
                    df_excel['Data_Excel'] = pd.to_datetime(df_excel[col_data], errors='coerce')
                except:
                    st.error(f"❌ Erro ao converter coluna '{col_data}' para data")
                    st.stop()
                
                # Processar coluna de valor
                try:
                    if df_excel[col_valor].dtype == 'object':
                        # Se for string, tentar converter removendo formatações
                        df_excel['Valor_Excel'] = df_excel[col_valor].apply(lambda x: 
                            float(str(x).replace(".", "").replace(",", ".").replace("R$", "").replace("R\\$", "").strip()) 
                            if pd.notna(x) and str(x).strip() != '' else 0.0
                        )
                    else:
                        df_excel['Valor_Excel'] = df_excel[col_valor].astype(float)
                except:
                    st.error(f"❌ Erro ao converter coluna '{col_valor}' para valor numérico")
                    st.stop()
                
                # Remover linhas com data ou valor inválidos
                df_excel = df_excel.dropna(subset=['Data_Excel', 'Valor_Excel'])
                
                # Salvar no session state
                st.session_state.df_excel = df_excel
                st.session_state.col_data_excel = col_data
                st.session_state.col_valor_excel = col_valor
                st.session_state.tolerancia_valor = tolerancia
                
                st.success(f"✅ {len(df_excel)} transações válidas processadas do Excel")
    
    except Exception as e:
        st.error(f"❌ Erro ao processar arquivo Excel: {e}")

# Exibir preview do Excel
if st.session_state.df_excel is not None:
    st.subheader("📊 Preview das Transações Excel")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Transações", len(st.session_state.df_excel))
    with col2:
        total = st.session_state.df_excel['Valor_Excel'].sum()
        st.metric("Valor Total", f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    with col3:
        datas = st.session_state.df_excel['Data_Excel'].dropna()
        if len(datas) > 0:
            periodo = f"{datas.min().strftime('%d/%m/%Y')} a {datas.max().strftime('%d/%m/%Y')}"
            st.metric("Período", periodo)
    
    # Mostrar amostra com as colunas selecionadas
    cols_mostrar = [st.session_state.col_data_excel, st.session_state.col_valor_excel, 'Data_Excel', 'Valor_Excel']
    cols_mostrar = [c for c in cols_mostrar if c in st.session_state.df_excel.columns]
    st.dataframe(st.session_state.df_excel[cols_mostrar].head(10), use_container_width=True)

st.divider()

# =====================================
# ETAPA 3: Reconciliação
# =====================================
st.header("🔍 Etapa 3: Reconciliação e Comparação")

if st.session_state.df_ofx is not None and st.session_state.df_excel is not None:
    
    if st.button("🎯 Executar Reconciliação", type="primary", key="executar_reconciliacao"):
        with st.spinner("Comparando transações..."):
            
            df_ofx = st.session_state.df_ofx.copy()
            df_excel = st.session_state.df_excel.copy()
            tolerancia = st.session_state.tolerancia_valor
            
            # Preparar DataFrames para matching
            df_ofx['Data_Normalizada'] = df_ofx['Data'].dt.date
            df_ofx['Valor_Abs'] = df_ofx['Valor_Float'].abs()
            df_ofx['Matched'] = False
            df_ofx['Origem'] = 'OFX'
            
            df_excel['Data_Normalizada'] = df_excel['Data_Excel'].dt.date
            df_excel['Valor_Abs'] = df_excel['Valor_Excel'].abs()
            df_excel['Matched'] = False
            df_excel['Origem'] = 'Excel'
            
            # Criar lista de matches
            matches = []
            
            # Para cada transação do OFX, tentar encontrar match no Excel
            for idx_ofx, row_ofx in df_ofx.iterrows():
                if row_ofx['Matched']:
                    continue
                
                data_ofx = row_ofx['Data_Normalizada']
                valor_ofx = row_ofx['Valor_Abs']
                
                # Buscar no Excel transações com mesma data
                candidatos = df_excel[
                    (df_excel['Data_Normalizada'] == data_ofx) & 
                    (~df_excel['Matched'])
                ]
                
                # Verificar valores dentro da tolerância
                for idx_excel, row_excel in candidatos.iterrows():
                    valor_excel = row_excel['Valor_Abs']
                    diferenca = abs(valor_ofx - valor_excel)
                    
                    if diferenca <= tolerancia:
                        # Match encontrado!
                        matches.append({
                            'Data': data_ofx,
                            'Valor_OFX': row_ofx['Valor_Float'],
                            'Valor_Excel': row_excel['Valor_Excel'],
                            'Diferenca': diferenca,
                            'Descricao_OFX': row_ofx.get('Descrição', ''),
                            'Status': '✅ Batido'
                        })
                        
                        df_ofx.loc[idx_ofx, 'Matched'] = True
                        df_excel.loc[idx_excel, 'Matched'] = True
                        break  # Pegar apenas o primeiro match
            
            # Transações apenas no OFX (não encontradas no Excel)
            apenas_ofx = df_ofx[~df_ofx['Matched']].copy()
            apenas_ofx['Status'] = '⚠️ Apenas no OFX'
            
            # Transações apenas no Excel (não encontradas no OFX)
            apenas_excel = df_excel[~df_excel['Matched']].copy()
            apenas_excel['Status'] = '⚠️ Apenas no Excel'
            
            # Criar DataFrame consolidado
            df_matches = pd.DataFrame(matches)
            
            # Salvar resultado
            resultado = {
                'matches': df_matches,
                'apenas_ofx': apenas_ofx,
                'apenas_excel': apenas_excel,
                'total_ofx': len(df_ofx),
                'total_excel': len(df_excel),
                'total_matches': len(df_matches),
                'total_apenas_ofx': len(apenas_ofx),
                'total_apenas_excel': len(apenas_excel)
            }
            
            st.session_state.df_reconciliado = resultado
            st.success("✅ Reconciliação concluída!")
    
    # Exibir resultados da reconciliação
    if st.session_state.df_reconciliado is not None:
        resultado = st.session_state.df_reconciliado
        
        st.subheader("📊 Resultado da Reconciliação")
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "✅ Transações Batidas",
                resultado['total_matches'],
                delta=f"{(resultado['total_matches']/resultado['total_ofx']*100):.1f}%" if resultado['total_ofx'] > 0 else "0%"
            )
        
        with col2:
            st.metric(
                "⚠️ Apenas OFX",
                resultado['total_apenas_ofx']
            )
        
        with col3:
            st.metric(
                "⚠️ Apenas Excel",
                resultado['total_apenas_excel']
            )
        
        with col4:
            total_divergencias = resultado['total_apenas_ofx'] + resultado['total_apenas_excel']
            st.metric(
                "❗ Total Divergências",
                total_divergencias
            )
        
        # Tabs para visualizar cada categoria
        tab1, tab2, tab3 = st.tabs(["✅ Transações Batidas", "⚠️ Apenas no OFX", "⚠️ Apenas no Excel"])
        
        with tab1:
            if not resultado['matches'].empty:
                st.markdown(f"**{len(resultado['matches'])} transações encontradas em ambos os sistemas**")
                
                # Formatar valores para exibição
                df_display = resultado['matches'].copy()
                df_display['Data'] = pd.to_datetime(df_display['Data']).dt.strftime('%d/%m/%Y')
                df_display['Valor_OFX'] = df_display['Valor_OFX'].apply(
                    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                df_display['Valor_Excel'] = df_display['Valor_Excel'].apply(
                    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                df_display['Diferenca'] = df_display['Diferenca'].apply(
                    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                
                st.dataframe(df_display, use_container_width=True)
                
                # Botão de download
                output = io.BytesIO()
                resultado['matches'].to_excel(output, index=False)
                output.seek(0)
                st.download_button(
                    label="📥 Baixar Transações Batidas",
                    data=output,
                    file_name=f"transacoes_batidas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Nenhuma transação batida encontrada.")
        
        with tab2:
            if not resultado['apenas_ofx'].empty:
                st.markdown(f"**{len(resultado['apenas_ofx'])} transações encontradas no banco (OFX) mas não no Excel**")
                st.info("💡 Estas transações podem estar faltando no seu controle Excel")
                
                # Selecionar colunas relevantes
                cols_mostrar = ['Data', 'Descrição', 'Valor_Float', 'Tipo']
                cols_mostrar = [c for c in cols_mostrar if c in resultado['apenas_ofx'].columns]
                
                df_display = resultado['apenas_ofx'][cols_mostrar].copy()
                if 'Data' in df_display.columns:
                    df_display['Data'] = pd.to_datetime(df_display['Data']).dt.strftime('%d/%m/%Y')
                if 'Valor_Float' in df_display.columns:
                    df_display['Valor (R$)'] = df_display['Valor_Float'].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    df_display = df_display.drop('Valor_Float', axis=1)
                
                st.dataframe(df_display, use_container_width=True)
                
                # Botão de download
                output = io.BytesIO()
                resultado['apenas_ofx'].to_excel(output, index=False)
                output.seek(0)
                st.download_button(
                    label="📥 Baixar Transações Apenas OFX",
                    data=output,
                    file_name=f"apenas_ofx_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.success("✅ Todas as transações do OFX estão no Excel!")
        
        with tab3:
            if not resultado['apenas_excel'].empty:
                st.markdown(f"**{len(resultado['apenas_excel'])} transações encontradas no Excel mas não no banco (OFX)**")
                st.info("💡 Estas transações podem não ter sido baixadas do banco ou foram registradas manualmente")
                
                # Selecionar colunas relevantes
                cols_mostrar = ['Data_Excel', 'Valor_Excel']
                # Adicionar coluna original de descrição se existir
                for col in resultado['apenas_excel'].columns:
                    if 'descri' in col.lower() or 'hist' in col.lower():
                        cols_mostrar.append(col)
                        break
                
                cols_mostrar = [c for c in cols_mostrar if c in resultado['apenas_excel'].columns]
                
                df_display = resultado['apenas_excel'][cols_mostrar].copy()
                if 'Data_Excel' in df_display.columns:
                    df_display['Data'] = pd.to_datetime(df_display['Data_Excel']).dt.strftime('%d/%m/%Y')
                    df_display = df_display.drop('Data_Excel', axis=1)
                if 'Valor_Excel' in df_display.columns:
                    df_display['Valor (R$)'] = df_display['Valor_Excel'].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                    df_display = df_display.drop('Valor_Excel', axis=1)
                
                st.dataframe(df_display, use_container_width=True)
                
                # Botão de download
                output = io.BytesIO()
                resultado['apenas_excel'].to_excel(output, index=False)
                output.seek(0)
                st.download_button(
                    label="📥 Baixar Transações Apenas Excel",
                    data=output,
                    file_name=f"apenas_excel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.success("✅ Todas as transações do Excel estão no OFX!")
        
        # Resumo geral
        st.divider()
        st.subheader("📋 Resumo Geral")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Estatísticas")
            st.markdown(f"""
            - **Total OFX:** {resultado['total_ofx']} transações
            - **Total Excel:** {resultado['total_excel']} transações
            - **Taxa de Match:** {(resultado['total_matches']/resultado['total_ofx']*100):.1f}% (OFX)
            - **Taxa de Match:** {(resultado['total_matches']/resultado['total_excel']*100):.1f}% (Excel)
            """)
        
        with col2:
            st.markdown("### 💡 Recomendações")
            if resultado['total_apenas_ofx'] > 0:
                st.warning(f"⚠️ {resultado['total_apenas_ofx']} transações do banco não estão no seu controle")
            if resultado['total_apenas_excel'] > 0:
                st.warning(f"⚠️ {resultado['total_apenas_excel']} transações do Excel não aparecem no banco")
            if resultado['total_apenas_ofx'] == 0 and resultado['total_apenas_excel'] == 0:
                st.success("✅ Reconciliação 100% completa!")

else:
    st.info("👆 Carregue arquivos OFX e Excel nas etapas acima para começar a reconciliação")

# =====================================
# Botão de Limpar Tudo
# =====================================
st.divider()

if st.button("🧹 Limpar Tudo e Reiniciar"):
    st.session_state.df_ofx = None
    st.session_state.df_excel = None
    st.session_state.df_reconciliado = None
    st.session_state.col_data_excel = None
    st.session_state.col_valor_excel = None
    st.rerun()
