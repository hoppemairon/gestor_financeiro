#!/usr/bin/env python3
"""
Script para otimizar JSONs do cache DRE
Remove dados desnecessários identificados na análise
"""

import json
import os
from typing import Dict, Any

def otimizar_json_dre(caminho_arquivo: str) -> bool:
    """
    Remove seções desnecessárias do JSON DRE
    """
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        # Lista de campos a remover (identificados como desnecessários)
        campos_remover = [
            'dados',  # Array duplicado de dados (linhas 228-400)
        ]
        
        # Remover campos desnecessários
        for campo in campos_remover:
            if campo in dados:
                del dados[campo]
                print(f"✅ Removido campo: {campo}")
        
        # Otimizar seções do DRE estruturado
        if 'dre_estruturado' in dados:
            dre = dados['dre_estruturado']
            
            # Remover seções sempre vazias
            secoes_vazias = []
            for secao_nome, secao_dados in dre.items():
                if isinstance(secao_dados, dict) and 'itens' in secao_dados:
                    # Verificar se todos os valores são zero
                    todos_zero = True
                    for item in secao_dados['itens'].values():
                        if isinstance(item, dict) and 'valores' in item:
                            valores = item['valores']
                            if any(v != 0 for k, v in valores.items() if k != '%'):
                                todos_zero = False
                                break
                    
                    if todos_zero and secao_nome in ['patrimonial']:  # Apenas seções específicas
                        secoes_vazias.append(secao_nome)
            
            # Remover seções vazias identificadas
            for secao in secoes_vazias:
                del dre[secao]
                print(f"✅ Removida seção vazia: {secao}")
        
        # Salvar arquivo otimizado
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Arquivo otimizado: {caminho_arquivo}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao otimizar {caminho_arquivo}: {e}")
        return False

def otimizar_todos_dres():
    """
    Otimiza todos os arquivos DRE no cache
    """
    pasta_dre = "data_cache/dre"
    
    if not os.path.exists(pasta_dre):
        print(f"❌ Pasta não encontrada: {pasta_dre}")
        return
    
    arquivos_processados = 0
    
    for arquivo in os.listdir(pasta_dre):
        if arquivo.endswith('_dre.json'):
            caminho_completo = os.path.join(pasta_dre, arquivo)
            print(f"\n🔧 Otimizando: {arquivo}")
            
            if otimizar_json_dre(caminho_completo):
                arquivos_processados += 1
    
    print(f"\n✅ Otimização concluída: {arquivos_processados} arquivos processados")

def mostrar_estatisticas_antes_depois():
    """
    Mostra estatísticas do arquivo antes e depois da otimização
    """
    pasta_dre = "data_cache/dre"
    
    for arquivo in os.listdir(pasta_dre):
        if arquivo.endswith('_dre.json'):
            caminho = os.path.join(pasta_dre, arquivo)
            
            # Tamanho do arquivo
            tamanho_kb = os.path.getsize(caminho) / 1024
            
            # Contar campos
            with open(caminho, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            
            total_campos = contar_campos_recursivo(dados)
            
            print(f"📊 {arquivo}:")
            print(f"   • Tamanho: {tamanho_kb:.1f} KB")
            print(f"   • Total de campos: {total_campos}")

def contar_campos_recursivo(obj: Any) -> int:
    """
    Conta o número total de campos em um objeto JSON recursivamente
    """
    if isinstance(obj, dict):
        return len(obj) + sum(contar_campos_recursivo(v) for v in obj.values())
    elif isinstance(obj, list):
        return sum(contar_campos_recursivo(item) for item in obj)
    else:
        return 0

if __name__ == "__main__":
    print("🔧 OTIMIZAÇÃO DE CACHE DRE")
    print("=" * 50)
    
    print("\n📊 Estatísticas ANTES da otimização:")
    mostrar_estatisticas_antes_depois()
    
    print("\n🚀 Iniciando otimização...")
    otimizar_todos_dres()
    
    print("\n📊 Estatísticas DEPOIS da otimização:")
    mostrar_estatisticas_antes_depois()