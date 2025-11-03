#!/usr/bin/env python3
"""
Script simples para converter JSONs existentes para o novo formato estruturado
"""

import json
import os
import pandas as pd
from datetime import datetime


def converter_json_empresa(empresa_nome):
    """Converte JSONs de uma empresa para nova estrutura"""
    print(f"\n🔄 Convertendo dados da empresa: {empresa_nome}")
    
    # Caminhos dos arquivos
    dre_path = f"./data_cache/dre/{empresa_nome}_dre.json"
    fluxo_path = f"./data_cache/fluxo_caixa/{empresa_nome}_fluxo.json"
    
    conversoes_realizadas = 0
    
    # Converter DRE se existe
    if os.path.exists(dre_path):
        try:
            with open(dre_path, 'r', encoding='utf-8') as f:
                dados_dre = json.load(f)
            
            if dados_dre.get("estrutura") == "secoes_organizadas":
                print("✅ DRE já está no formato estruturado")
            else:
                print("🔄 Convertendo DRE para formato estruturado...")
                
                # Converter DRE 
                if "dados_indexados" in dados_dre:
                    df_dre = pd.DataFrame.from_dict(dados_dre["dados_indexados"], orient='index')
                elif "dados" in dados_dre and isinstance(dados_dre["dados"], list) and dados_dre["dados"]:
                    df_dre = pd.DataFrame(dados_dre["dados"])
                    if not df_dre.empty:
                        df_dre = df_dre.set_index(df_dre.columns[0])
                else:
                    print("❌ Formato de dados DRE não reconhecido")
                    df_dre = None
                
                if df_dre is not None and not df_dre.empty:
                    # Salvar com nova estrutura
                    salvar_dre_estruturado(df_dre, empresa_nome, dados_dre.get("metadata", {}))
                    conversoes_realizadas += 1
                    print("✅ DRE convertido com sucesso!")
                else:
                    print("❌ Erro ao processar DRE")
        except Exception as e:
            print(f"❌ Erro ao converter DRE: {e}")
    
    # Converter Fluxo se existe
    if os.path.exists(fluxo_path):
        try:
            with open(fluxo_path, 'r', encoding='utf-8') as f:
                dados_fluxo = json.load(f)
            
            if dados_fluxo.get("estrutura") == "grupos_organizados":
                print("✅ Fluxo de Caixa já está no formato estruturado")
            else:
                print("🔄 Convertendo Fluxo de Caixa para formato estruturado...")
                
                # Converter Fluxo
                if "dados_indexados" in dados_fluxo:
                    df_fluxo = pd.DataFrame.from_dict(dados_fluxo["dados_indexados"], orient='index')
                elif "dados" in dados_fluxo and isinstance(dados_fluxo["dados"], list) and dados_fluxo["dados"]:
                    df_fluxo = pd.DataFrame(dados_fluxo["dados"])
                    if not df_fluxo.empty:
                        df_fluxo = df_fluxo.set_index(df_fluxo.columns[0])
                else:
                    print("❌ Formato de dados Fluxo não reconhecido")
                    df_fluxo = None
                
                if df_fluxo is not None and not df_fluxo.empty:
                    # Salvar com nova estrutura
                    salvar_fluxo_estruturado(df_fluxo, empresa_nome, dados_fluxo.get("metadata", {}))
                    conversoes_realizadas += 1
                    print("✅ Fluxo de Caixa convertido com sucesso!")
                else:
                    print("❌ Erro ao processar Fluxo de Caixa")
        except Exception as e:
            print(f"❌ Erro ao converter Fluxo: {e}")
    
    print(f"📊 Total de conversões realizadas: {conversoes_realizadas}")
    return conversoes_realizadas > 0


def salvar_dre_estruturado(df_dre, empresa_nome, metadata):
    """Salva DRE em formato estruturado"""
    
    # Definir estrutura de seções do DRE
    secoes_dre = {
        "receitas": {
            "nome": "RECEITAS",
            "linhas": ["FATURAMENTO", "RECEITA", "RECEITA EXTRA OPERACIONAL"]
        },
        "custos_diretos": {
            "nome": "CUSTOS E DESPESAS DIRETAS", 
            "linhas": ["IMPOSTOS", "DESPESA OPERACIONAL"]
        },
        "margem_contribuicao": {
            "nome": "MARGEM DE CONTRIBUIÇÃO",
            "linhas": ["MARGEM CONTRIBUIÇÃO"]
        },
        "despesas_operacionais": {
            "nome": "DESPESAS OPERACIONAIS",
            "linhas": ["DESPESAS COM PESSOAL", "DESPESA ADMINISTRATIVA"]
        },
        "resultado_operacional": {
            "nome": "RESULTADO OPERACIONAL", 
            "linhas": ["LUCRO OPERACIONAL"]
        },
        "outras_despesas": {
            "nome": "OUTRAS DESPESAS E INVESTIMENTOS",
            "linhas": ["INVESTIMENTOS", "DESPESA EXTRA OPERACIONAL", "RETIRADAS SÓCIOS"]
        },
        "resultado_liquido": {
            "nome": "RESULTADO LÍQUIDO",
            "linhas": ["LUCRO LIQUIDO", "RESULTADO"]
        },
        "patrimonial": {
            "nome": "INFORMAÇÕES PATRIMONIAIS",
            "linhas": ["ESTOQUE", "SALDO"]
        },
        "resultado_gerencial": {
            "nome": "RESULTADO GERENCIAL FINAL",
            "linhas": ["RESULTADO GERENCIAL"]
        }
    }
    
    # Converter DataFrame para estrutura organizada
    dre_estruturado = {}
    
    # Processar cada seção
    for secao_key, secao_info in secoes_dre.items():
        dre_estruturado[secao_key] = {
            "nome_secao": secao_info["nome"],
            "itens": {}
        }
        
        # Processar cada linha da seção
        for linha in secao_info["linhas"]:
            if linha in df_dre.index:
                # Converter a série do pandas para dicionário
                linha_dados = df_dre.loc[linha].to_dict()
                dre_estruturado[secao_key]["itens"][linha] = {
                    "nome_linha": linha,
                    "valores": linha_dados
                }
    
    # Preparar dados para salvamento
    data = {
        "empresa": empresa_nome,
        "timestamp": datetime.now().isoformat(),
        "tipo": "dre_estruturado",
        "metadata": metadata,
        "estrutura": "secoes_organizadas",
        "dre_estruturado": dre_estruturado,
        # Manter dados brutos para compatibilidade (formato antigo)
        "dados": df_dre.to_dict('records') if not df_dre.empty else [],
        "dados_indexados": df_dre.to_dict('index') if not df_dre.empty else {}
    }
    
    # Salvar arquivo
    filepath = f"./data_cache/dre/{empresa_nome}_dre.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def salvar_fluxo_estruturado(df_fluxo, empresa_nome, metadata):
    """Salva Fluxo em formato estruturado"""
    
    # Estruturar dados do fluxo de caixa por categoria
    fluxo_estruturado = {}
    
    if not df_fluxo.empty:
        # Processar DataFrame do fluxo (geralmente tem categorias como índice e meses como colunas)
        for categoria in df_fluxo.index:
            linha_dados = df_fluxo.loc[categoria].to_dict()
            
            # Determinar grupo da categoria baseado no nome
            grupo = "Outras"
            categoria_lower = str(categoria).lower()
            
            if any(term in categoria_lower for term in ["receita", "faturamento", "vendas", "serviços"]):
                grupo = "Receitas"
            elif any(term in categoria_lower for term in ["imposto", "taxa", "tributo"]):
                grupo = "Impostos e Taxas"
            elif any(term in categoria_lower for term in ["custo", "direto", "operacional"]):
                grupo = "Custos Diretos"
            elif any(term in categoria_lower for term in ["pessoal", "salário", "funcionário", "rh"]):
                grupo = "Despesas com Pessoal"
            elif any(term in categoria_lower for term in ["administrativ", "escritório", "aluguel", "telefone"]):
                grupo = "Despesas Administrativas"
            elif any(term in categoria_lower for term in ["investimento", "aplicação", "ativo"]):
                grupo = "Investimentos"
            elif any(term in categoria_lower for term in ["retirada", "sócio", "distribuição"]):
                grupo = "Retiradas e Distribuições"
            elif any(term in categoria_lower for term in ["estoque", "inventário"]):
                grupo = "Estoque"
            
            if grupo not in fluxo_estruturado:
                fluxo_estruturado[grupo] = {
                    "nome_grupo": grupo,
                    "categorias": {}
                }
            
            fluxo_estruturado[grupo]["categorias"][categoria] = {
                "nome_categoria": categoria,
                "valores_mensais": linha_dados
            }
    
    # Preparar dados para salvamento
    data = {
        "empresa": empresa_nome,
        "timestamp": datetime.now().isoformat(),
        "tipo": "fluxo_caixa_estruturado",
        "metadata": metadata,
        "estrutura": "grupos_organizados",
        "fluxo_estruturado": fluxo_estruturado,
        # Manter dados brutos para compatibilidade
        "dados": df_fluxo.to_dict('records') if not df_fluxo.empty else [],
        "dados_indexados": df_fluxo.to_dict('index') if not df_fluxo.empty else {}
    }
    
    # Salvar arquivo
    filepath = f"./data_cache/fluxo_caixa/{empresa_nome}_fluxo.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def main():
    """Função principal"""
    print("🚀 Iniciando conversão para formato estruturado...")
    
    # Encontrar empresas nos diretórios
    empresas = set()
    
    dre_dir = "./data_cache/dre"
    fluxo_dir = "./data_cache/fluxo_caixa"
    
    # Verificar arquivos DRE
    if os.path.exists(dre_dir):
        for arquivo in os.listdir(dre_dir):
            if arquivo.endswith('_dre.json'):
                empresa = arquivo.replace('_dre.json', '')
                empresas.add(empresa)
    
    # Verificar arquivos Fluxo
    if os.path.exists(fluxo_dir):
        for arquivo in os.listdir(fluxo_dir):
            if arquivo.endswith('_fluxo.json'):
                empresa = arquivo.replace('_fluxo.json', '')
                empresas.add(empresa)
    
    if not empresas:
        print("❌ Nenhuma empresa encontrada no cache")
        return
    
    print(f"📋 Empresas encontradas: {len(empresas)}")
    for empresa in sorted(empresas):
        print(f"  • {empresa}")
    
    print("\n" + "="*50)
    
    # Converter cada empresa
    total_conversoes = 0
    for empresa in sorted(empresas):
        resultado = converter_json_empresa(empresa)
        if resultado:
            total_conversoes += 1
    
    print("\n" + "="*50)
    print(f"🎉 Conversão concluída!")
    print(f"📊 {total_conversoes} de {len(empresas)} empresas foram convertidas")


if __name__ == "__main__":
    main()