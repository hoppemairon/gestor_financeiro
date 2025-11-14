#!/usr/bin/env python3
"""
Teste para verificar se a funcionalidade de detalhamento de subcategorias está funcionando
"""

import sys
import os
import pandas as pd

# Adicionar o diretório logic ao path
logic_path = os.path.join(os.path.dirname(__file__), 'logic')
sys.path.append(logic_path)

from logic.data_cache_manager import cache_manager

def teste_detalhamento_subcategorias():
    """Testa a funcionalidade de detalhamento de subcategorias"""
    
    print("🧪 TESTE DE DETALHAMENTO DE SUBCATEGORIAS")
    print("=" * 60)
    
    # Empresa de teste
    empresa = "CBM"
    ano_base = 2025
    
    print(f"📊 Testando detalhamento para empresa: {empresa}")
    print(f"📅 Ano base: {ano_base}")
    
    # Carregar dados DRE
    try:
        dados_dre = cache_manager.carregar_dre(empresa)
        
        if not dados_dre:
            print("❌ Dados DRE não encontrados")
            return
        
        print("✅ Dados DRE carregados com sucesso")
        
        # Explorar estrutura
        if isinstance(dados_dre, dict) and 'dre_estruturado' in dados_dre:
            estrutura = dados_dre['dre_estruturado']
            print(f"\n📋 Seções encontradas: {list(estrutura.keys())}")
            
            # Testar diferentes categorias
            categorias_teste = [
                'FATURAMENTO',
                'DESPESA OPERACIONAL', 
                'RECEITA',
                'IMPOSTOS',
                'INVESTIMENTOS'
            ]
            
            for categoria in categorias_teste:
                print(f"\n🔍 TESTANDO CATEGORIA: {categoria}")
                print("-" * 40)
                
                categoria_encontrada = False
                
                # Buscar nas seções
                for secao_nome, secao_dados in estrutura.items():
                    if isinstance(secao_dados, dict) and 'itens' in secao_dados:
                        itens = secao_dados['itens']
                        
                        if categoria in itens:
                            categoria_encontrada = True
                            categoria_dados = itens[categoria]
                            
                            print(f"  ✅ Encontrada na seção: {secao_nome}")
                            print(f"  📊 Tipo de dados: {type(categoria_dados)}")
                            
                            if isinstance(categoria_dados, dict):
                                print(f"  🔑 Chaves disponíveis: {list(categoria_dados.keys())}")
                                
                                # Verificar se tem subcategorias
                                if 'subitens' in categoria_dados:
                                    subitens = categoria_dados['subitens']
                                    print(f"  📁 Subcategorias encontradas: {len(subitens)}")
                                    
                                    for i, (subcat_nome, subcat_dados) in enumerate(subitens.items()):
                                        if i < 3:  # Mostrar apenas as primeiras 3
                                            if isinstance(subcat_dados, dict) and 'valores' in subcat_dados:
                                                valores_mensais = subcat_dados['valores']
                                                valores_2025 = {mes: valor for mes, valor in valores_mensais.items() 
                                                              if mes.startswith('2025')}
                                                total_anual = sum(float(v) if v else 0 for v in valores_2025.values())
                                                print(f"    └─ {subcat_nome}: R$ {total_anual:,.2f}")
                                        elif i == 3:
                                            print(f"    └─ ... e mais {len(subitens) - 3} subcategorias")
                                            break
                                
                                elif 'valores' in categoria_dados:
                                    valores_mensais = categoria_dados['valores']
                                    valores_2025 = {mes: valor for mes, valor in valores_mensais.items() 
                                                  if mes.startswith('2025')}
                                    total_anual = sum(float(v) if v else 0 for v in valores_2025.values())
                                    print(f"  💰 Total da categoria: R$ {total_anual:,.2f}")
                                    print(f"  📝 Observação: Sem subcategorias detalhadas")
                            
                            break
                
                if not categoria_encontrada:
                    print(f"  ❌ Categoria '{categoria}' não encontrada")
        
        else:
            print("❌ Estrutura DRE não encontrada")
            
    except Exception as e:
        print(f"❌ Erro durante o teste: {str(e)}")
    
    print(f"\n🏁 TESTE CONCLUÍDO")

if __name__ == "__main__":
    teste_detalhamento_subcategorias()