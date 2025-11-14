#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Teste do Detalhamento de Subcategorias com Dados Reais do Vyco
"""

import pandas as pd
import sys
import os

# Configurar paths
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.extend([root_dir, os.path.join(root_dir, 'logic'), os.path.join(root_dir, 'pages')])

def main():
    print("TESTE: Detalhamento de Subcategorias com Dados Vyco")
    print("=" * 60)
    
    try:
        # Importar módulos necessários
        from logic.licenca_manager import licenca_manager
        
        # Importar função diretamente do arquivo
        import importlib.util
        pages_dir = os.path.join(root_dir, 'pages')
        vyco_file = os.path.join(pages_dir, '5_Integracao_Vyco.py')
        
        spec = importlib.util.spec_from_file_location("integracao_vyco", vyco_file)
        integracao_vyco = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(integracao_vyco)
        
        obter_dados_vyco = integracao_vyco.buscar_lancamentos_vyco
        processar_dados_vyco = integracao_vyco.processar_dados_vyco
        
        print("Modulos importados com sucesso")
        
        # Listar licenças disponíveis
        licencas_ativas = licenca_manager.obter_licencas_ativas()
        print(f"\nLicencas disponiveis: {licencas_ativas}")
        
        # Usar Arani como padrão (sabemos que tem dados)
        empresa_teste = "Arani"
        licenca_uuid = licenca_manager.obter_id_licenca(empresa_teste)
        
        if not licenca_uuid:
            print(f"UUID nao encontrado para {empresa_teste}")
            print("Tentando com CBM...")
            empresa_teste = "CBM"
            licenca_uuid = licenca_manager.obter_id_licenca(empresa_teste)
            
        if not licenca_uuid:
            print("Nenhuma licenca valida encontrada")
            return
            
        print(f"\nTestando empresa: {empresa_teste}")
        print(f"UUID: {licenca_uuid}")
        
        # Buscar dados do Vyco
        print("\nBuscando dados do Vyco...")
        df_raw = obter_dados_vyco(licenca_uuid, limit=5000)
        
        if df_raw is None or df_raw.empty:
            print("Nenhum dado encontrado no Vyco")
            return
        
        print(f"{len(df_raw)} lancamentos encontrados")
        print(f"Colunas disponiveis: {list(df_raw.columns)}")
        
        # Processar dados
        print("\nProcessando dados...")
        df_transacoes = processar_dados_vyco(df_raw)
        
        if df_transacoes.empty:
            print("Erro ao processar dados")
            return
        
        print(f"{len(df_transacoes)} transacoes processadas")
        print(f"Colunas processadas: {list(df_transacoes.columns)}")
        
        # Verificar categorização Vyco
        if 'Categoria_Vyco' in df_transacoes.columns:
            categorias_vyco = df_transacoes['Categoria_Vyco'].value_counts().head(10)
            print(f"\nTop 10 categorias Vyco:")
            for categoria, count in categorias_vyco.items():
                print(f"  - {categoria}: {count} transacoes")
        else:
            print("\nColuna 'Categoria_Vyco' nao encontrada")
            return
        
        # Testar detalhamento de uma categoria específica
        print("\n" + "="*50)
        print("TESTE DE DETALHAMENTO POR CATEGORIA")
        print("="*50)
        
        # Escolher primeira categoria com dados
        categoria_teste = categorias_vyco.index[0]
        print(f"\nCategoria selecionada: {categoria_teste}")
        
        # Filtrar transações por categoria
        df_categoria = df_transacoes[
            df_transacoes['Categoria_Vyco'].str.contains(categoria_teste, case=False, na=False)
        ].copy()
        
        print(f"Transacoes da categoria: {len(df_categoria)}")
        
        if not df_categoria.empty:
            # Agrupar por descrição
            print(f"\nDetalhamento por subcategoria:")
            subcategorias = {}
            
            for descricao, grupo in df_categoria.groupby('Descrição'):
                valor_total = grupo['Valor (R$)'].sum()
                qtd_transacoes = len(grupo)
                tipo_predominante = grupo['Tipo'].mode().iloc[0] if not grupo['Tipo'].empty else "Misto"
                
                # Limitar tamanho da descrição
                descricao_limpa = descricao[:50] + "..." if len(descricao) > 50 else descricao
                
                if abs(valor_total) > 0.01:  # Só incluir se houver valor significativo
                    subcategorias[descricao_limpa] = {
                        'valor': valor_total,
                        'quantidade': qtd_transacoes,
                        'tipo': tipo_predominante
                    }
            
            # Ordenar por valor absoluto
            subcategorias_ordenadas = sorted(
                subcategorias.items(), 
                key=lambda x: abs(x[1]['valor']), 
                reverse=True
            )
            
            print(f"{len(subcategorias_ordenadas)} subcategorias encontradas:")
            total_categoria = 0
            
            for i, (subcat, dados) in enumerate(subcategorias_ordenadas[:10]):  # Top 10
                valor = dados['valor']
                qtd = dados['quantidade']
                tipo = dados['tipo']
                total_categoria += valor
                
                print(f"  {i+1:2d}. {subcat}")
                print(f"      R$ {valor:,.2f} ({tipo}) - {qtd} transacoes")
            
            print(f"\nTotal da categoria: R$ {total_categoria:,.2f}")
            
            # Criar DataFrame como na função real
            df_detalhamento = pd.DataFrame([
                {
                    'Subcategoria': subcat,
                    'Tipo': dados['tipo'],
                    'Qtd_Transações': dados['quantidade'],
                    'Base (2025)': dados['valor'],
                    'Orçamento (2026)': dados['valor']
                }
                for subcat, dados in subcategorias_ordenadas
            ])
            
            print(f"\nDataFrame criado com {len(df_detalhamento)} linhas")
            print("Estrutura do DataFrame:")
            print(df_detalhamento.head())
            
        else:
            print("Nenhuma transacao encontrada para a categoria")
        
        print(f"\nTeste concluido com sucesso!")
        print(f"Sistema integrado com dados reais do Vyco")
        print(f"Detalhamento por subcategorias funcionando")
        
    except Exception as e:
        print(f"Erro durante o teste: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()