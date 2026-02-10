#!/usr/bin/env python3
"""
Exemplo de como fica o JSON estruturado
"""

import json
from datetime import datetime

# Exemplo de JSON DRE Estruturado
dre_estruturado_exemplo = {
    "empresa": "Arani",
    "timestamp": datetime.now().isoformat(),
    "tipo": "dre_estruturado",
    "metadata": {
        "licenca": "Arani",
        "origem": "vyco_integração",
        "formato": "estruturado_v2"
    },
    "estrutura": "secoes_organizadas",
    "dre_estruturado": {
        "receitas": {
            "nome_secao": "RECEITAS",
            "itens": {
                "FATURAMENTO": {
                    "nome_linha": "FATURAMENTO",
                    "valores": {
                        "2025-08": 42227.55,
                        "2025-09": 42399.59,
                        "2025-10": 42572.33,
                        "TOTAL": 127199.47,
                        "%": 100.0
                    }
                },
                "RECEITA": {
                    "nome_linha": "RECEITA",
                    "valores": {
                        "2025-08": 1485126.52,
                        "2025-09": 2828976.88,
                        "2025-10": 42056.21,
                        "TOTAL": 4356159.61,
                        "%": 95.2
                    }
                }
            }
        },
        "custos_diretos": {
            "nome_secao": "CUSTOS E DESPESAS DIRETAS",
            "itens": {
                "IMPOSTOS": {
                    "nome_linha": "IMPOSTOS",
                    "valores": {
                        "2025-08": 22257.69,
                        "2025-09": 208984.02,
                        "2025-10": 114.98,
                        "TOTAL": 231356.69,
                        "%": 5.3
                    }
                },
                "DESPESA OPERACIONAL": {
                    "nome_linha": "DESPESA OPERACIONAL",
                    "valores": {
                        "2025-08": 1504064.68,
                        "2025-09": 3039544.51,
                        "2025-10": 230372.75,
                        "TOTAL": 4773981.94,
                        "%": 107.8
                    }
                }
            }
        },
        "margem_contribuicao": {
            "nome_secao": "MARGEM DE CONTRIBUIÇÃO",
            "itens": {
                "MARGEM CONTRIBUIÇÃO": {
                    "nome_linha": "MARGEM CONTRIBUIÇÃO",
                    "valores": {
                        "2025-08": -41195.85,
                        "2025-09": -419551.65,
                        "2025-10": -188431.52,
                        "TOTAL": -649179.02,
                        "%": -14.9
                    }
                }
            }
        },
        "despesas_operacionais": {
            "nome_secao": "DESPESAS OPERACIONAIS",
            "itens": {
                "DESPESAS COM PESSOAL": {
                    "nome_linha": "DESPESAS COM PESSOAL",
                    "valores": {
                        "2025-08": 38004.80,
                        "2025-09": 38159.63,
                        "2025-10": 38315.10,
                        "TOTAL": 114479.53,
                        "%": 2.6
                    }
                },
                "DESPESA ADMINISTRATIVA": {
                    "nome_linha": "DESPESA ADMINISTRATIVA",
                    "valores": {
                        "2025-08": 48561.69,
                        "2025-09": 48759.53,
                        "2025-10": 48958.18,
                        "TOTAL": 146279.40,
                        "%": 3.3
                    }
                }
            }
        }
    },
    "resumo_dre": {
        "totais_por_secao": {
            "receitas": {
                "nome": "RECEITAS",
                "total": 4483359.08
            },
            "custos_diretos": {
                "nome": "CUSTOS E DESPESAS DIRETAS",
                "total": 5005338.63
            },
            "despesas_operacionais": {
                "nome": "DESPESAS OPERACIONAIS",
                "total": 260758.93
            }
        },
        "total_receitas": 4483359.08,
        "total_custos_diretos": 5005338.63,
        "total_despesas_operacionais": 260758.93,
        "resultado_liquido": -782738.48
    }
}

# Exemplo de JSON Fluxo Estruturado
fluxo_estruturado_exemplo = {
    "empresa": "Arani",
    "timestamp": datetime.now().isoformat(),
    "tipo": "fluxo_caixa_estruturado",
    "metadata": {
        "licenca": "Arani",
        "origem": "vyco_integração",
        "formato": "estruturado_v2"
    },
    "estrutura": "grupos_organizados",
    "fluxo_estruturado": {
        "Receitas": {
            "nome_grupo": "Receitas",
            "categorias": {
                "Receita de Vendas": {
                    "nome_categoria": "Receita de Vendas",
                    "valores_mensais": {
                        "2025-08": 1485126.52,
                        "2025-09": 2828976.88,
                        "2025-10": 42056.21,
                        "TOTAL": 4356159.61
                    }
                },
                "Receita de Serviços": {
                    "nome_categoria": "Receita de Serviços",
                    "valores_mensais": {
                        "2025-08": 0.0,
                        "2025-09": 0.0,
                        "2025-10": 0.0,
                        "TOTAL": 0.0
                    }
                }
            }
        },
        "Impostos e Taxas": {
            "nome_grupo": "Impostos e Taxas",
            "categorias": {
                "Impostos e Encargos": {
                    "nome_categoria": "Impostos e Encargos",
                    "valores_mensais": {
                        "2025-08": -22257.69,
                        "2025-09": -208984.02,
                        "2025-10": -114.98,
                        "TOTAL": -231356.69
                    }
                }
            }
        },
        "Custos Diretos": {
            "nome_grupo": "Custos Diretos",
            "categorias": {
                "Despesas com Fornecedores": {
                    "nome_categoria": "Despesas com Fornecedores",
                    "valores_mensais": {
                        "2025-08": -1536971.83,
                        "2025-09": 0.0,
                        "2025-10": 0.0,
                        "TOTAL": -1536971.83
                    }
                },
                "Outras Desp. Operacionais": {
                    "nome_categoria": "Outras Desp. Operacionais",
                    "valores_mensais": {
                        "2025-08": -455818.30,
                        "2025-09": 0.0,
                        "2025-10": 0.0,
                        "TOTAL": -455818.30
                    }
                }
            }
        },
        "Despesas com Pessoal": {
            "nome_grupo": "Despesas com Pessoal",
            "categorias": {
                "Folha de Pagamento": {
                    "nome_categoria": "Folha de Pagamento",
                    "valores_mensais": {
                        "2025-08": -73506.80,
                        "2025-09": 0.0,
                        "2025-10": 0.0,
                        "TOTAL": -73506.80
                    }
                },
                "FGTS": {
                    "nome_categoria": "FGTS",
                    "valores_mensais": {
                        "2025-08": -8053.13,
                        "2025-09": 0.0,
                        "2025-10": 0.0,
                        "TOTAL": -8053.13
                    }
                }
            }
        }
    },
    "resumo_fluxo": {
        "totais_por_grupo": {
            "Receitas": {
                "nome": "Receitas",
                "totais_mensais": {
                    "2025-08": 1485126.52,
                    "2025-09": 2828976.88,
                    "2025-10": 42056.21,
                    "TOTAL": 4356159.61
                }
            },
            "Impostos e Taxas": {
                "nome": "Impostos e Taxas",
                "totais_mensais": {
                    "2025-08": -22257.69,
                    "2025-09": -208984.02,
                    "2025-10": -114.98,
                    "TOTAL": -231356.69
                }
            },
            "Custos Diretos": {
                "nome": "Custos Diretos",
                "totais_mensais": {
                    "2025-08": -1992790.13,
                    "2025-09": 0.0,
                    "2025-10": 0.0,
                    "TOTAL": -1992790.13
                }
            }
        }
    }
}

# Salvar exemplos
print("📝 Criando exemplos de JSON estruturado...")

with open('exemplo_dre_estruturado.json', 'w', encoding='utf-8') as f:
    json.dump(dre_estruturado_exemplo, f, ensure_ascii=False, indent=2, default=str)

with open('exemplo_fluxo_estruturado.json', 'w', encoding='utf-8') as f:
    json.dump(fluxo_estruturado_exemplo, f, ensure_ascii=False, indent=2, default=str)

print("✅ Exemplos criados:")
print("  • exemplo_dre_estruturado.json")
print("  • exemplo_fluxo_estruturado.json")

print("\n📊 Estrutura do DRE:")
print("✅ Seções organizadas com nomes legíveis:")
for secao_key, secao_data in dre_estruturado_exemplo["dre_estruturado"].items():
    print(f"  📋 {secao_data['nome_secao']}")
    for item_key in secao_data["itens"].keys():
        print(f"      • {item_key}")

print("\n📊 Estrutura do Fluxo de Caixa:")
print("✅ Grupos organizados com nomes legíveis:")
for grupo_key, grupo_data in fluxo_estruturado_exemplo["fluxo_estruturado"].items():
    print(f"  📋 {grupo_data['nome_grupo']}")
    for categoria_key in grupo_data["categorias"].keys():
        print(f"      • {categoria_key}")

print("\n🎉 Agora os JSONs têm:")
print("✅ Seções organizadas do DRE (Receitas, Custos Diretos, etc.)")
print("✅ Grupos organizados do Fluxo (Receitas, Impostos, Despesas, etc.)")
print("✅ Nomes legíveis das linhas do DRE")
print("✅ Resumos automáticos por seção")
print("✅ Compatibilidade com formato antigo (dados_indexados)")
print("✅ Metadados estruturados")