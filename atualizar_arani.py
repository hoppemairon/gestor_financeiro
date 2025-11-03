#!/usr/bin/env python3
"""
Script para forçar atualização do JSON da Arani com nova estrutura
"""

import sys
import os
import json
import pandas as pd

# Adicionar o diretório do projeto ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logic.data_cache_manager import cache_manager


def forcar_atualizacao_arani():
    """Força atualização do JSON da Arani com nova estrutura"""
    print("🔄 Forçando atualização do JSON da Arani...")
    
    # Carregar JSON atual da Arani
    dados_atuais = cache_manager.carregar_dre("Arani")
    
    if not dados_atuais:
        print("❌ Não foi possível carregar dados da Arani")
        return
    
    print(f"✅ JSON carregado: {dados_atuais.get('tipo', 'desconhecido')}")
    
    # Verificar se já tem as chaves de compatibilidade
    resumo_dre = dados_atuais.get('resumo_dre', {})
    
    if 'custos_diretos' in resumo_dre and 'custos_administrativos' in resumo_dre:
        print("✅ JSON já tem chaves de compatibilidade")
        print(f"   • Custos Diretos: R$ {resumo_dre.get('custos_diretos', 0):,.2f}")
        print(f"   • Custos Administrativos: R$ {resumo_dre.get('custos_administrativos', 0):,.2f}")
        print(f"   • Despesas Extra: R$ {resumo_dre.get('despesas_extra', 0):,.2f}")
        print(f"   • Retiradas: R$ {resumo_dre.get('retiradas', 0):,.2f}")
        return
    
    # Reconstruir DataFrame do DRE a partir dos dados indexados
    if "dados_indexados" in dados_atuais:
        df_dre = pd.DataFrame.from_dict(dados_atuais["dados_indexados"], orient='index')
        print(f"✅ DataFrame reconstruído: {df_dre.shape}")
        print(f"   Linhas: {list(df_dre.index[:5])}...")
    else:
        print("❌ Não foi possível reconstruir DataFrame - dados_indexados não encontrado")
        return
    
    # Salvar novamente com a nova estrutura
    metadata = dados_atuais.get("metadata", {})
    metadata["atualizacao_forcada"] = "estrutura_compatibilidade_culturas"
    
    resultado = cache_manager.salvar_dre(df_dre, "Arani", metadata)
    
    if resultado:
        print("✅ JSON atualizado com sucesso!")
        
        # Carregar novamente para verificar
        dados_novos = cache_manager.carregar_dre("Arani")
        resumo_novo = dados_novos.get('resumo_dre', {})
        
        print("📊 Valores atualizados:")
        print(f"   • Custos Diretos: R$ {resumo_novo.get('custos_diretos', 0):,.2f}")
        print(f"   • Custos Administrativos: R$ {resumo_novo.get('custos_administrativos', 0):,.2f}")
        print(f"   • Despesas Extra: R$ {resumo_novo.get('despesas_extra', 0):,.2f}")
        print(f"   • Retiradas: R$ {resumo_novo.get('retiradas', 0):,.2f}")
        
    else:
        print("❌ Erro ao atualizar JSON")


if __name__ == "__main__":
    forcar_atualizacao_arani()