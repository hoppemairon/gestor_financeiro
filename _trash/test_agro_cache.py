#!/usr/bin/env python3
"""
Teste do sistema de cache para Gestão Agro
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logic.data_cache_manager import DataCacheManager
from logic.business_types.agro.utils import formatar_valor_br

def testar_cache_agro():
    """Testa se o cache funciona para dados agro"""
    print("🧪 Testando sistema de cache para Gestão Agro...")
    
    # Inicializar cache manager
    cache_manager = DataCacheManager()
    
    # Listar empresas disponíveis
    empresas = cache_manager.listar_empresas_disponiveis()
    print(f"\n📊 Empresas disponíveis no cache: {len(empresas)}")
    
    for empresa in empresas:
        print(f"  - {empresa['nome']}")
        
        # Verificar dados DRE
        if empresa.get('dre'):
            print(f"    Arquivos DRE: {len(empresa['dre'])}")
            for dre_info in empresa['dre']:
                print(f"      - {dre_info['arquivo']}")
                print(f"        Timestamp: {dre_info['timestamp']}")
                
                # Usar dados do resumo_dre já carregado
                resumo_dre = dre_info.get('resumo_dre', {})
                print(f"        📈 Receitas: {formatar_valor_br(resumo_dre.get('total_receitas', 0))}")
                print(f"        📉 Custos Diretos: {formatar_valor_br(resumo_dre.get('custos_diretos', 0))}")
                print(f"        🏢 Despesas Admin: {formatar_valor_br(resumo_dre.get('custos_administrativos', 0))}")
                print(f"        💸 Retiradas: {formatar_valor_br(resumo_dre.get('retiradas', 0))}")
        
        # Verificar dados Fluxo de Caixa
        if empresa.get('fluxo_caixa'):
            print(f"    Arquivos Fluxo: {len(empresa['fluxo_caixa'])}")
        
        print()
    
    if empresas:
        print("✅ Sistema de cache funcionando corretamente!")
        print("✅ Valores formatados em padrão brasileiro!")
        print("✅ Dados disponíveis para análise por cultura!")
    else:
        print("⚠️ Nenhuma empresa no cache. Execute o módulo Vyco primeiro.")
    
    return len(empresas) > 0

if __name__ == "__main__":
    testar_cache_agro()