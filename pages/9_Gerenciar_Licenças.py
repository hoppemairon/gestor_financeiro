import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Gerenciador de Licenças", 
    layout="wide",
    initial_sidebar_state="expanded"
)

import pandas as pd
from datetime import datetime

# Módulos do projeto
from logic.licenca_manager import licenca_manager

# Título da página
st.title("🔧 Gerenciador de Licenças Vyco")
st.markdown("""
### Sistema centralizado de gerenciamento de licenças
🔄 **INTEGRAÇÃO:** Licenças gerenciadas via CSV para uso em Vyco e Orçamento
""")

# Sidebar - Status do sistema
st.sidebar.header("📊 Status do Sistema")

# Validar CSV
valido, erros = licenca_manager.validar_csv()
if valido:
    st.sidebar.success("✅ CSV válido")
else:
    st.sidebar.error("❌ Problemas no CSV")
    with st.sidebar.expander("Ver erros", expanded=True):
        for erro in erros:
            st.sidebar.error(f"• {erro}")

# Estatísticas
df_todas = licenca_manager.carregar_licencas(apenas_ativas=False)
df_ativas = licenca_manager.carregar_licencas(apenas_ativas=True)

col1, col2 = st.sidebar.columns(2)
with col1:
    st.metric("Total", len(df_todas))
with col2:
    st.metric("Ativas", len(df_ativas))

if len(df_todas) > 0:
    inativas = len(df_todas) - len(df_ativas)
    st.sidebar.metric("Inativas", inativas)

st.sidebar.markdown("---")

# Backup
st.sidebar.markdown("### 💾 Backup")
if st.sidebar.button("📤 Criar Backup"):
    if licenca_manager.exportar_backup():
        st.sidebar.success("✅ Backup criado!")
    else:
        st.sidebar.error("❌ Erro no backup")

# Abas principais
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Visualizar Licenças", 
    "➕ Adicionar Licença", 
    "✏️ Editar Licenças", 
    "📊 Relatórios"
])

with tab1:
    st.markdown("## 📋 Licenças Cadastradas")
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        mostrar_inativas = st.checkbox("🔍 Mostrar licenças inativas", value=False)
    with col2:
        buscar_texto = st.text_input("🔎 Buscar licença", placeholder="Digite nome ou ID...")
    
    # Carregar dados
    df_exibir = licenca_manager.carregar_licencas(apenas_ativas=not mostrar_inativas)
    
    # Aplicar filtro de busca
    if buscar_texto:
        mask = (
            df_exibir['nome_licenca'].str.contains(buscar_texto, case=False, na=False) |
            df_exibir['id_licenca'].str.contains(buscar_texto, case=False, na=False) |
            df_exibir['observacoes'].str.contains(buscar_texto, case=False, na=False)
        )
        df_exibir = df_exibir[mask]
    
    # Mostrar tabela
    if not df_exibir.empty:
        # Formatar tabela para exibição
        df_display = df_exibir.copy()
        df_display['Status'] = df_display['ativo'].apply(lambda x: "✅ Ativa" if x else "❌ Inativa")
        df_display['ID (Resumo)'] = df_display['id_licenca'].apply(
            lambda x: f"{x[:8]}...{x[-8:]}" if len(x) >= 16 else x
        )
        
        # Reorganizar colunas
        colunas_exibir = ['nome_licenca', 'ID (Resumo)', 'Status', 'observacoes']
        df_display = df_display[colunas_exibir]
        df_display.columns = ['Nome da Licença', 'ID (Resumo)', 'Status', 'Observações']
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Detalhes expandidos
        with st.expander("🔍 Ver IDs completos"):
            for _, row in df_exibir.iterrows():
                status_icon = "✅" if row['ativo'] else "❌"
                st.text(f"{status_icon} {row['nome_licenca']}")
                st.code(row['id_licenca'])
                if pd.notna(row['observacoes']) and row['observacoes']:
                    st.caption(f"📝 {row['observacoes']}")
                st.markdown("---")
    else:
        st.info("ℹ️ Nenhuma licença encontrada com os filtros aplicados.")

with tab2:
    st.markdown("## ➕ Adicionar Nova Licença")
    
    with st.form("form_adicionar"):
        col1, col2 = st.columns(2)
        
        with col1:
            novo_nome = st.text_input(
                "📝 Nome da Licença *",
                placeholder="Ex: Cliente ABC",
                help="Nome identificador da licença"
            )
            
            novo_id = st.text_input(
                "🔑 ID da Licença (UUID) *",
                placeholder="00000000-0000-0000-0000-000000000000",
                help="UUID fornecido pelo sistema Vyco"
            )
        
        with col2:
            ativo_inicialmente = st.checkbox(
                "✅ Ativar imediatamente",
                value=True,
                help="Se marcado, a licença ficará ativa desde o cadastro"
            )
            
            observacoes = st.text_area(
                "📋 Observações",
                placeholder="Ex: Cliente do setor X, configurações especiais...",
                help="Informações adicionais sobre a licença"
            )
        
        # Validação visual do UUID
        if novo_id:
            import re
            uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
            if re.match(uuid_pattern, novo_id):
                st.success("✅ Formato de UUID válido")
            else:
                st.error("❌ Formato de UUID inválido")
        
        submitted = st.form_submit_button("➕ Adicionar Licença", type="primary")
        
        if submitted:
            if not novo_nome or not novo_id:
                st.error("❌ Nome e ID são obrigatórios")
            else:
                # Verificar se UUID tem formato válido
                import re
                uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
                if not re.match(uuid_pattern, novo_id):
                    st.error("❌ ID deve ser um UUID válido")
                else:
                    if licenca_manager.adicionar_licenca(novo_nome, novo_id, ativo_inicialmente, observacoes):
                        st.success(f"✅ Licença '{novo_nome}' adicionada com sucesso!")
                        st.rerun()

with tab3:
    st.markdown("## ✏️ Editar Licenças Existentes")
    
    # Selecionar licença para editar
    df_todas_edit = licenca_manager.carregar_licencas(apenas_ativas=False)
    
    if not df_todas_edit.empty:
        licenca_editar = st.selectbox(
            "📋 Selecione a licença para editar:",
            [""] + df_todas_edit['nome_licenca'].tolist()
        )
        
        if licenca_editar:
            # Carregar dados atuais
            linha_atual = df_todas_edit[df_todas_edit['nome_licenca'] == licenca_editar].iloc[0]
            
            st.markdown(f"### Editando: **{licenca_editar}**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📊 Dados Atuais")
                st.text(f"Nome: {linha_atual['nome_licenca']}")
                st.code(linha_atual['id_licenca'])
                st.text(f"Status: {'Ativa' if linha_atual['ativo'] else 'Inativa'}")
                if pd.notna(linha_atual['observacoes']):
                    st.text(f"Observações: {linha_atual['observacoes']}")
            
            with col2:
                st.markdown("#### ✏️ Novos Dados")
                
                with st.form("form_editar"):
                    novo_nome_edit = st.text_input(
                        "Novo nome:", 
                        value=linha_atual['nome_licenca']
                    )
                    novo_id_edit = st.text_input(
                        "Novo ID:", 
                        value=linha_atual['id_licenca']
                    )
                    novas_obs_edit = st.text_area(
                        "Novas observações:", 
                        value=linha_atual['observacoes'] if pd.notna(linha_atual['observacoes']) else ""
                    )
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        salvar_edit = st.form_submit_button("💾 Salvar Alterações", type="primary")
                    
                    with col_btn2:
                        if linha_atual['ativo']:
                            desativar = st.form_submit_button("🔒 Desativar", type="secondary")
                        else:
                            ativar = st.form_submit_button("🔓 Ativar", type="secondary")
                    
                    if salvar_edit:
                        if licenca_manager.atualizar_licenca(
                            licenca_editar, 
                            novo_nome_edit if novo_nome_edit != linha_atual['nome_licenca'] else None,
                            novo_id_edit if novo_id_edit != linha_atual['id_licenca'] else None,
                            novas_obs_edit
                        ):
                            st.success("✅ Licença atualizada!")
                            st.rerun()
                    
                    if 'desativar' in locals() and desativar:
                        if licenca_manager.desativar_licenca(licenca_editar):
                            st.success("🔒 Licença desativada!")
                            st.rerun()
                    
                    if 'ativar' in locals() and ativar:
                        # Reativar licença
                        df_reativar = licenca_manager.carregar_licencas(apenas_ativas=False)
                        df_reativar.loc[df_reativar['nome_licenca'] == licenca_editar, 'ativo'] = True
                        df_reativar.to_csv(licenca_manager.csv_path, index=False, encoding='utf-8')
                        st.success("🔓 Licença reativada!")
                        st.rerun()
    else:
        st.info("ℹ️ Nenhuma licença disponível para edição.")

with tab4:
    st.markdown("## 📊 Relatórios e Estatísticas")
    
    if not df_todas.empty:
        # Métricas gerais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📋 Total de Licenças", len(df_todas))
        
        with col2:
            licencas_ativas_count = len(df_ativas)
            st.metric("✅ Licenças Ativas", licencas_ativas_count)
        
        with col3:
            licencas_inativas = len(df_todas) - licencas_ativas_count
            st.metric("❌ Licenças Inativas", licencas_inativas)
        
        with col4:
            if len(df_todas) > 0:
                percentual_ativo = (licencas_ativas_count / len(df_todas)) * 100
                st.metric("📊 % Ativas", f"{percentual_ativo:.1f}%")
        
        st.markdown("---")
        
        # Tabela resumo
        st.markdown("### 📋 Resumo Detalhado")
        
        df_relatorio = df_todas.copy()
        df_relatorio['Status'] = df_relatorio['ativo'].apply(lambda x: "Ativa" if x else "Inativa")
        df_relatorio['Tem_Observacoes'] = df_relatorio['observacoes'].apply(
            lambda x: "Sim" if pd.notna(x) and x.strip() != "" else "Não"
        )
        
        # Estatísticas por status
        stats_status = df_relatorio['Status'].value_counts()
        st.markdown("#### Por Status:")
        for status, count in stats_status.items():
            st.text(f"• {status}: {count} licenças")
        
        # Licenças com observações
        with_obs = df_relatorio[df_relatorio['Tem_Observacoes'] == 'Sim']
        st.markdown(f"#### Licenças com Observações: {len(with_obs)}")
        
        if not with_obs.empty:
            for _, row in with_obs.iterrows():
                with st.expander(f"📝 {row['nome_licenca']}"):
                    st.text(row['observacoes'])
        
        # Verificação de integridade
        st.markdown("---")
        st.markdown("### 🔍 Verificação de Integridade")
        
        valido, erros = licenca_manager.validar_csv()
        if valido:
            st.success("✅ Todos os dados estão íntegros")
        else:
            st.error("❌ Problemas encontrados:")
            for erro in erros:
                st.error(f"• {erro}")
    
    else:
        st.info("ℹ️ Nenhuma licença cadastrada para gerar relatórios.")

# Footer
st.markdown("---")
st.markdown("""
💡 **Dicas de Uso:**
- **IDs devem ser UUIDs válidos** fornecidos pelo sistema Vyco
- **Licenças inativas** não aparecem nos sistemas Vyco e Orçamento
- **Backup automático** é recomendado antes de grandes alterações
- **CSV localizado em:** `logic/CSVs/licencas_vyco.csv`
""")