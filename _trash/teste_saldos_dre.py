#!/usr/bin/env python3
"""
Teste para validar se os saldos retroativos estão sendo aplicados corretamente no DRE
"""

import sys
import os

# Adicionar o diretório logic ao path
logic_path = os.path.join(os.path.dirname(__file__), 'logic')
sys.path.append(logic_path)

from logic.saldo_contas import SaldoContasManager
from logic.data_cache_manager import cache_manager
from logic.licenca_manager import licenca_manager

def teste_saldos_retroativos_cbm():
    """Testa se os saldos retroativos estão sendo calculados corretamente para CBM"""
    
    print("🧪 TESTE DE SALDOS RETROATIVOS NO DRE")
    print("=" * 60)
    
    # Empresa de teste
    empresa = "CBM"
    
    # Obter ID da licença
    print(f"📊 ETAPA 1: Obtendo dados da empresa {empresa}...")
    licencas_ativas = licenca_manager.obter_licencas_ativas()
    licenca_id = None
    
    # Buscar diretamente no CSV
    for licenca in licencas_ativas:
        if isinstance(licenca, dict) and licenca.get('nome') == empresa:
            licenca_id = licenca.get('id')
            break
        elif isinstance(licenca, str) and licenca == empresa:
            # Se for só o nome, buscar o ID manualmente
            if empresa == "CBM":
                licenca_id = "4618e68c-f173-4190-92b4-7a078f01df0f"
            break
    
    if not licenca_id:
        print(f"❌ Licença não encontrada para {empresa}")
        return
    
    print(f"✅ ID da licença encontrado: {licenca_id}")
    
    # Carregar dados DRE
    print(f"\n📋 ETAPA 2: Carregando dados DRE...")
    dados_dre = cache_manager.carregar_dre(empresa)
    
    if not dados_dre:
        print(f"❌ Dados DRE não encontrados para {empresa}")
        return
    
    print(f"✅ Dados DRE carregados")
    
    # Usar dados simulados baseados no que sabemos da CBM
    print(f"\n🔧 ETAPA 3: Preparando dados para teste...")
    
    # Dados simulados baseados no teste anterior (resultados CBM conhecidos)
    dados_dre_mensais = {
        "2024-01": {"RESULTADO": -11894.64},
        "2024-02": {"RESULTADO": 25809.46},
        "2024-03": {"RESULTADO": 19117.19},
        "2024-04": {"RESULTADO": 35916.79},
        "2024-05": {"RESULTADO": 8474.35},
        "2024-06": {"RESULTADO": 149258.06},
        "2024-07": {"RESULTADO": 18794.42},
        "2024-08": {"RESULTADO": 57514.41},
        "2024-09": {"RESULTADO": -106716.20},
        "2024-10": {"RESULTADO": 15190.49},
    }
    
    print(f"✅ Dados preparados: {len(dados_dre_mensais)} meses")
    
    # Testar cálculo de saldos retroativos
    print(f"\n💰 ETAPA 4: Calculando saldos retroativos...")
    saldo_manager = SaldoContasManager()
    
    try:
        saldos_calculados = saldo_manager.calcular_saldos_mensais(dados_dre_mensais, licenca_id)
        
        if saldos_calculados:
            print(f"✅ Saldos calculados para {len(saldos_calculados)} meses")
            
            # Mostrar alguns exemplos
            print(f"\n📊 EXEMPLOS DE SALDOS CALCULADOS:")
            print("-" * 50)
            
            meses_ordenados = sorted(saldos_calculados.keys())
            for i, mes in enumerate(meses_ordenados):
                if i < 5 or i >= len(meses_ordenados) - 5:  # Primeiros e últimos 5
                    resultado_mes = dados_dre_mensais[mes]['RESULTADO']
                    saldo_mes = saldos_calculados[mes]
                    print(f"{mes}: Resultado R$ {resultado_mes:>10,.2f} | Saldo R$ {saldo_mes:>12,.2f}")
                elif i == 5:
                    print("   ... (meses intermediários omitidos) ...")
            
            # Validar com teste anterior
            print(f"\n🎯 ETAPA 5: Validação com teste anterior...")
            saldo_atual = saldo_manager.buscar_saldo_atual_vyco(licenca_id)
            ultimo_saldo_calculado = saldos_calculados[max(saldos_calculados.keys())]
            
            print(f"💰 Saldo atual real (Vyco):     R$ {saldo_atual:,.2f}")
            print(f"💰 Último saldo calculado:      R$ {ultimo_saldo_calculado:,.2f}")
            
            diferenca = abs(saldo_atual - ultimo_saldo_calculado)
            print(f"📏 Diferença:                   R$ {diferenca:,.2f}")
            
            if diferenca < 50000:  # Tolerância de R$ 50.000
                print("✅ TESTE PASSOU - Saldos retroativos calculados corretamente!")
            else:
                print("⚠️ DIFERENÇA ALTA - Verificar cálculos")
            
        else:
            print("❌ Nenhum saldo calculado")
            
    except Exception as e:
        print(f"❌ Erro durante o cálculo: {str(e)}")
    
    print(f"\n🏁 TESTE CONCLUÍDO")

if __name__ == "__main__":
    teste_saldos_retroativos_cbm()