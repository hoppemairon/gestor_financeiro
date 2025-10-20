import streamlit as st
import pandas as pd
import json
import os
import io
from datetime import datetime
from extractors.excel_extractor import ExcelExtractor

# Configuração da página
st.set_page_config(
    page_title="Configurador Excel - Templates DE/PARA", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚙️ Configurador Excel - Sistema DE/PARA")

st.markdown("""
### 🎯 Configuração Avançada de Templates Excel
Esta página permite criar e gerenciar templates personalizados para diferentes formatos de Excel.

**Funcionalidades:**
- 🔧 **Criar templates** personalizados por cliente/banco
- 📊 **Preview em tempo real** do mapeamento
- 💾 **Salvar configurações** para reutilização
- 🏦 **Templates pré-definidos** para bancos conhecidos
""")

# Inicializar extrator
extractor = ExcelExtractor()

# Sidebar para seleção de ação
st.sidebar.header("🛠️ Ações")
acao = st.sidebar.radio(
    "Escolha uma ação:",
    ["📤 Upload e Configuração", "📋 Gerenciar Templates", "🔍 Testar Template"]
)

if acao == "📤 Upload e Configuração":
    st.header("📤 Configurar Novo Template")
    
    # Upload do arquivo
    uploaded_file = st.file_uploader(
        "Envie um arquivo Excel para configurar:",
        type=["xlsx", "xls"],
        help="Faça upload de um arquivo Excel para criar um template personalizado"
    )
    
    if uploaded_file:
        # Analisar arquivo
        with st.spinner("Analisando arquivo Excel..."):
            analise = extractor.analisar_excel(uploaded_file)
        
        if analise["status"] == "sucesso":
            st.success("✅ Arquivo analisado com sucesso!")
            
            # Mostrar preview dos dados
            st.subheader("👁️ Preview dos Dados")
            st.dataframe(analise["preview"], use_container_width=True)
            
            # Configuração do mapeamento
            st.subheader("🎯 Configuração do Mapeamento")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🔧 Mapeamento Automático Detectado:**")
                mapeamento_detectado = analise["mapeamento"]
                colunas = analise["colunas_detectadas"]
                
                for campo, indice in mapeamento_detectado.items():
                    if indice is not None and indice < len(colunas):
                        emoji = "📅" if campo == "data" else "📝" if campo == "descricao" else "💰" if campo == "valor" else "🔄"
                        st.success(f"✅ **{emoji} {campo.title()}**: {colunas[indice]}")
                    else:
                        emoji = "📅" if campo == "data" else "📝" if campo == "descricao" else "💰" if campo == "valor" else "🔄"
                        st.error(f"❌ **{emoji} {campo.title()}**: Não detectado")
            
            with col2:
                st.markdown("**⚙️ Configuração Manual:**")
                
                # Permitir ajuste manual
                opcoes_colunas = ["Não mapear"] + [f"Coluna {i}: {col}" for i, col in enumerate(colunas)]
                
                data_col = st.selectbox(
                    "📅 Coluna de Data:",
                    options=range(len(opcoes_colunas)),
                    format_func=lambda x: opcoes_colunas[x],
                    index=mapeamento_detectado["data"] + 1 if mapeamento_detectado["data"] is not None else 0
                )
                
                desc_col = st.selectbox(
                    "📝 Coluna de Descrição:",
                    options=range(len(opcoes_colunas)),
                    format_func=lambda x: opcoes_colunas[x],
                    index=mapeamento_detectado["descricao"] + 1 if mapeamento_detectado["descricao"] is not None else 0
                )
                
                valor_col = st.selectbox(
                    "💰 Coluna de Valor:",
                    options=range(len(opcoes_colunas)),
                    format_func=lambda x: opcoes_colunas[x],
                    index=mapeamento_detectado["valor"] + 1 if mapeamento_detectado["valor"] is not None else 0
                )
                
                tipo_col = st.selectbox(
                    "🔄 Coluna de Tipo (Débito/Crédito):",
                    options=range(len(opcoes_colunas)),
                    format_func=lambda x: opcoes_colunas[x],
                    index=mapeamento_detectado["tipo"] + 1 if mapeamento_detectado["tipo"] is not None else 0
                )
            
            # Configurações adicionais
            st.subheader("⚙️ Configurações Adicionais")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                formato_data = st.selectbox(
                    "📅 Formato de Data:",
                    options=["dd/mm/yyyy", "yyyy-mm-dd", "mm/dd/yyyy"],
                    index=0 if analise["formato_data"] == "dd/mm/yyyy" else 1
                )
            
            with col2:
                separador_decimal = st.selectbox(
                    "💰 Separador Decimal:",
                    options=[",", "."],
                    index=0 if analise["separador_decimal"] == "," else 1
                )
            
            with col3:
                linha_cabecalho = st.number_input(
                    "📋 Linha do Cabeçalho:",
                    min_value=0,
                    max_value=10,
                    value=analise["linha_cabecalho"]
                )
            
            # Criar mapeamento final
            mapeamento_final = {
                "data": data_col - 1 if data_col > 0 else None,
                "descricao": desc_col - 1 if desc_col > 0 else None,
                "valor": valor_col - 1 if valor_col > 0 else None,
                "tipo": tipo_col - 1 if tipo_col > 0 else None
            }
            
            # Preview do resultado
            st.subheader("🔍 Preview do Resultado")
            
            if st.button("🔄 Gerar Preview"):
                with st.spinner("Processando com configurações..."):
                    resultado = extractor.padronizar_dados(
                        analise["dataframe"],
                        mapeamento_final,
                        formato_data,
                        separador_decimal,
                        uploaded_file.name
                    )
                
                if resultado["status"] == "sucesso":
                    st.success("✅ Dados processados com sucesso!")
                    st.dataframe(resultado["dataframe"].head(10), use_container_width=True)
                    
                    # Adicionar botão de download
                    st.subheader("📥 Download dos Dados Processados")
                    
                    try:
                        # Preparar arquivo Excel para download
                        with st.spinner("Preparando arquivo para download..."):
                            output = io.BytesIO()
                            
                            # Tentar com openpyxl primeiro, depois xlsxwriter como fallback
                            try:
                                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                    resultado["dataframe"].to_excel(writer, index=False, sheet_name='Dados_Processados')
                                st.success("✅ Arquivo Excel preparado com openpyxl")
                            except ImportError:
                                # Fallback para xlsxwriter se openpyxl não estiver disponível
                                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                    resultado["dataframe"].to_excel(writer, index=False, sheet_name='Dados_Processados')
                                st.info("ℹ️ Arquivo Excel preparado com xlsxwriter (fallback)")
                            
                            excel_data = output.getvalue()
                            
                            if len(excel_data) > 0:
                                st.success(f"✅ Arquivo pronto! Tamanho: {len(excel_data)} bytes")
                                
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    download_filename = f"dados_processados_{uploaded_file.name.split('.')[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                                    
                                    download_button = st.download_button(
                                        label="📊 Download Excel Processado",
                                        data=excel_data,
                                        file_name=download_filename,
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        type="primary",
                                        help="Clique para baixar o arquivo Excel com os dados processados"
                                    )
                                    
                                    if download_button:
                                        st.success("🎉 Download iniciado!")
                                
                                with col2:
                                    st.info(f"📈 Total: {len(resultado['dataframe'])} transações processadas")
                                    st.info(f"📁 Nome do arquivo: {download_filename}")
                            else:
                                st.error("❌ Arquivo Excel está vazio!")
                    
                    except Exception as e:
                        st.error(f"❌ Erro ao preparar download: {e}")
                        st.exception(e)  # Mostra stack trace completo
                        st.info("💡 Tente instalar: pip install openpyxl xlsxwriter")
                    
                    # Salvar template
                    st.subheader("💾 Salvar Template")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        nome_template = st.text_input(
                            "Nome do Template:",
                            placeholder="Ex: Bradesco_Conta_Corrente"
                        )
                    
                    with col2:
                        if st.button("💾 Salvar Template", type="primary"):
                            if nome_template:
                                configuracoes = {
                                    "formato_data": formato_data,
                                    "separador_decimal": separador_decimal,
                                    "linha_cabecalho": linha_cabecalho
                                }
                                
                                sucesso = extractor.salvar_template(nome_template, mapeamento_final, configuracoes)
                                
                                if sucesso:
                                    st.success(f"✅ Template '{nome_template}' salvo com sucesso!")
                                else:
                                    st.error("❌ Erro ao salvar template.")
                            else:
                                st.error("❌ Digite um nome para o template.")
                else:
                    st.error(f"❌ Erro ao processar: {resultado['mensagem']}")
        else:
            st.error(f"❌ Erro ao analisar arquivo: {analise['mensagem']}")

elif acao == "📋 Gerenciar Templates":
    st.header("📋 Gerenciar Templates Salvos")
    
    # Carregar templates
    templates = extractor.carregar_templates()
    
    if templates:
        st.success(f"📁 {len(templates)} templates encontrados:")
        
        for nome, template in templates.items():
            with st.expander(f"📄 {template.get('nome', nome)}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**🎯 Mapeamento:**")
                    mapeamento = template.get('mapeamento', {})
                    for campo, indice in mapeamento.items():
                        status = f"Coluna {indice}" if indice is not None else "Não mapeado"
                        st.markdown(f"• **{campo.title()}**: {status}")
                
                with col2:
                    st.markdown("**⚙️ Configurações:**")
                    config = template.get('configuracoes', {})
                    st.markdown(f"• **Formato Data**: {config.get('formato_data', 'N/A')}")
                    st.markdown(f"• **Separador**: {config.get('separador_decimal', 'N/A')}")
                    st.markdown(f"• **Linha Cabeçalho**: {config.get('linha_cabecalho', 'N/A')}")
                    st.markdown(f"• **Criado em**: {template.get('criado_em', 'N/A')[:10]}")
                
                if st.button(f"🗑️ Excluir {nome}", key=f"delete_{nome}"):
                    arquivo_template = os.path.join(extractor.templates_dir, f"{nome}.json")
                    if os.path.exists(arquivo_template):
                        os.remove(arquivo_template)
                        st.success(f"✅ Template '{nome}' excluído!")
                        st.rerun()
    else:
        st.info("📂 Nenhum template salvo encontrado. Use a aba 'Upload e Configuração' para criar templates.")

elif acao == "🔍 Testar Template":
    st.header("🔍 Testar Template Existente")
    
    # Carregar templates
    templates = extractor.carregar_templates()
    
    if templates:
        # Seleção do template
        template_selecionado = st.selectbox(
            "📄 Escolha um template:",
            options=list(templates.keys()),
            format_func=lambda x: templates[x].get('nome', x)
        )
        
        # Upload para teste
        arquivo_teste = st.file_uploader(
            "📤 Upload arquivo para testar:",
            type=["xlsx", "xls"]
        )
        
        if arquivo_teste and template_selecionado:
            template = templates[template_selecionado]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📋 Template Selecionado:**")
                st.json(template, expanded=False)
            
            with col2:
                if st.button("🧪 Testar Template"):
                    with st.spinner("Testando template..."):
                        try:
                            # Ler arquivo
                            df = pd.read_excel(arquivo_teste, header=template['configuracoes']['linha_cabecalho'])
                            
                            # Aplicar template
                            resultado = extractor.padronizar_dados(
                                df,
                                template['mapeamento'],
                                template['configuracoes']['formato_data'],
                                template['configuracoes']['separador_decimal'],
                                arquivo_teste.name
                            )
                            
                            if resultado["status"] == "sucesso":
                                st.success("✅ Template testado com sucesso!")
                                st.subheader("📊 Resultado:")
                                st.dataframe(resultado["dataframe"].head(10), use_container_width=True)
                                
                                # Adicionar download para teste de template
                                col_info, col_download = st.columns(2)
                                
                                with col_info:
                                    st.info(f"📈 Total de {len(resultado['dataframe'])} transações processadas")
                                
                                with col_download:
                                    try:
                                        # Preparar arquivo Excel para download
                                        output = io.BytesIO()
                                        
                                        # Tentar com openpyxl primeiro, depois xlsxwriter
                                        try:
                                            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                                resultado["dataframe"].to_excel(writer, index=False, sheet_name='Teste_Template')
                                        except ImportError:
                                            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                                resultado["dataframe"].to_excel(writer, index=False, sheet_name='Teste_Template')
                                        
                                        excel_data = output.getvalue()
                                        
                                        st.download_button(
                                            label="📥 Download Teste",
                                            data=excel_data,
                                            file_name=f"teste_template_{template_selecionado}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            type="secondary"
                                        )
                                    except Exception as e:
                                        st.error(f"❌ Erro no download: {e}")
                                        st.info("💡 Instale: pip install openpyxl xlsxwriter")
                            else:
                                st.error(f"❌ Erro no teste: {resultado['mensagem']}")
                        
                        except Exception as e:
                            st.error(f"❌ Erro ao testar template: {str(e)}")
    else:
        st.info("📂 Nenhum template disponível para teste. Crie templates primeiro.")

# Rodapé
st.markdown("---")
st.caption("© 2025 Sistema de Análise Financeira - Configurador Excel DE/PARA | Versão 1.0")