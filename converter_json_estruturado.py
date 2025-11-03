#!/usr/bin/env python3
"""
Script para converter JSONs existentes para o novo formato estruturado
"""

import sys
import os
import pandas as pd

# Adicionar o diretório do projeto ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logic.data_cache_manager import cache_manager


def converter_json_empresa(empresa_nome):
    """Converte JSONs de uma empresa para nova estrutura"""
    print(f"\n🔄 Convertendo dados da empresa: {empresa_nome}")
    
    # Carregar dados atuais
    dados_dre = cache_manager.carregar_dre(empresa_nome)
    dados_fluxo = cache_manager.carregar_fluxo_caixa(empresa_nome)
    
    if not dados_dre and not dados_fluxo:
        print(f"❌ Nenhum dado encontrado para {empresa_nome}")
        return False
    
    conversoes_realizadas = 0
    
    # Converter DRE se necessário
    if dados_dre:
        if dados_dre.get("formato") == "estruturado":
            print("✅ DRE já está no formato estruturado")
        else:
            print("🔄 Convertendo DRE para formato estruturado...")
            
            # Reconstruir DataFrame do DRE
            if "dados_indexados" in dados_dre:
                df_dre = pd.DataFrame.from_dict(dados_dre["dados_indexados"], orient='index')
            elif "dados" in dados_dre and dados_dre["dados"]:
                df_dre = pd.DataFrame(dados_dre["dados"])
                df_dre = df_dre.set_index(df_dre.columns[0])  # Primeira coluna como índice
            else:
                print("❌ Formato de dados DRE não reconhecido")
                df_dre = None
            
            if df_dre is not None:
                # Salvar com nova estrutura
                metadata = dados_dre.get("metadata", {})
                metadata["conversao"] = "formato_antigo_para_estruturado"
                
                resultado = cache_manager.salvar_dre(df_dre, empresa_nome, metadata)
                if resultado:
                    print("✅ DRE convertido com sucesso!")
                    conversoes_realizadas += 1
                else:
                    print("❌ Erro ao converter DRE")
    
    # Converter Fluxo de Caixa se necessário
    if dados_fluxo:
        if dados_fluxo.get("formato") == "estruturado":
            print("✅ Fluxo de Caixa já está no formato estruturado")
        else:
            print("🔄 Convertendo Fluxo de Caixa para formato estruturado...")
            
            # Reconstruir DataFrame do Fluxo
            if "dados_indexados" in dados_fluxo:
                df_fluxo = pd.DataFrame.from_dict(dados_fluxo["dados_indexados"], orient='index')
            elif "dados" in dados_fluxo and dados_fluxo["dados"]:
                df_fluxo = pd.DataFrame(dados_fluxo["dados"])
                if not df_fluxo.empty and len(df_fluxo.columns) > 1:
                    df_fluxo = df_fluxo.set_index(df_fluxo.columns[0])  # Primeira coluna como índice
            else:
                print("❌ Formato de dados Fluxo não reconhecido")
                df_fluxo = None
            
            if df_fluxo is not None:
                # Salvar com nova estrutura
                metadata = dados_fluxo.get("metadata", {})
                metadata["conversao"] = "formato_antigo_para_estruturado"
                
                resultado = cache_manager.salvar_fluxo_caixa(df_fluxo, empresa_nome, metadata)
                if resultado:
                    print("✅ Fluxo de Caixa convertido com sucesso!")
                    conversoes_realizadas += 1
                else:
                    print("❌ Erro ao converter Fluxo de Caixa")
    
    print(f"📊 Total de conversões realizadas: {conversoes_realizadas}")
    return conversoes_realizadas > 0


def main():
    """Função principal"""
    print("🚀 Iniciando conversão para formato estruturado...")
    
    # Listar empresas disponíveis
    empresas = cache_manager.listar_empresas_disponiveis()
    
    if not empresas:
        print("❌ Nenhuma empresa encontrada no cache")
        return
    
    print(f"📋 Empresas encontradas: {len(empresas)}")
    for empresa in empresas:
        print(f"  • {empresa['nome']}")
    
    print("\n" + "="*50)
    
    # Converter cada empresa
    total_conversoes = 0
    for empresa in empresas:
        resultado = converter_json_empresa(empresa['nome'])
        if resultado:
            total_conversoes += 1
    
    print("\n" + "="*50)
    print(f"🎉 Conversão concluída!")
    print(f"📊 {total_conversoes} de {len(empresas)} empresas foram convertidas")
    
    # Verificar resultados
    print("\n🔍 Verificando resultados...")
    for empresa in empresas:
        dados_dre = cache_manager.carregar_dre(empresa['nome'])
        dados_fluxo = cache_manager.carregar_fluxo_caixa(empresa['nome'])
        
        dre_estruturado = dados_dre and dados_dre.get("formato") == "estruturado"
        fluxo_estruturado = dados_fluxo and dados_fluxo.get("formato") == "estruturado"
        
        status_dre = "✅" if dre_estruturado else "❌"
        status_fluxo = "✅" if fluxo_estruturado else "❌"
        
        print(f"  • {empresa['nome']}: DRE {status_dre} | Fluxo {status_fluxo}")


if __name__ == "__main__":
    main()