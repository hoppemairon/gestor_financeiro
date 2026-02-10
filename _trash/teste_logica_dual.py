#!/usr/bin/env python3
"""
Teste para validar a lógica dual: retroativa (≤2025) vs progressiva (≥2026)
"""

import sys
import os

# Adicionar o diretório logic ao path
logic_path = os.path.join(os.path.dirname(__file__), 'logic')
sys.path.append(logic_path)

from logic.saldo_contas import SaldoContasManager
from logic.licenca_manager import licenca_manager

def teste_logica_dual():
    """Testa se a lógica dual está funcionando corretamente"""
    
    print("🧪 TESTE DE LÓGICA DUAL - RETROATIVA vs PROGRESSIVA")
    print("=" * 70)
    
    # Empresa de teste
    empresa = "CBM"
    licenca_id = "4618e68c-f173-4190-92b4-7a078f01df0f"
    
    saldo_manager = SaldoContasManager()
    saldo_atual = saldo_manager.buscar_saldo_atual_vyco(licenca_id)
    
    print(f"💰 Saldo atual real (Nov/2025): R$ {saldo_atual:,.2f}")
    print()
    
    # TESTE 1: Dados de 2025 (deve usar lógica RETROATIVA)
    print("📊 TESTE 1: DADOS 2025 (LÓGICA RETROATIVA)")
    print("-" * 50)
    
    dados_2025 = {
        "2025-01": {"RESULTADO": 10000},
        "2025-02": {"RESULTADO": 15000},
        "2025-03": {"RESULTADO": 20000},
    }
    
    saldos_2025 = saldo_manager.calcular_saldos_mensais(dados_2025, licenca_id)
    
    print("Dados de entrada (2025):", dados_2025)
    print("Saldos calculados:")
    for mes, saldo in sorted(saldos_2025.items()):
        print(f"  {mes}: R$ {saldo:,.2f}")
    
    # Verificar se é retroativo (saldo final deve aproximar do saldo atual)
    ultimo_saldo_2025 = saldos_2025[max(saldos_2025.keys())]
    diferenca_2025 = abs(ultimo_saldo_2025 - saldo_atual)
    print(f"Verificação retroativa: Último saldo = R$ {ultimo_saldo_2025:,.2f}")
    print(f"Diferença do saldo atual: R$ {diferenca_2025:,.2f}")
    
    if diferenca_2025 < 100000:  # Tolerância
        print("✅ LÓGICA RETROATIVA funcionando corretamente!")
    else:
        print("❌ Problema na lógica retroativa")
    
    print()
    
    # TESTE 2: Dados de 2026 (deve usar lógica PROGRESSIVA)
    print("📊 TESTE 2: DADOS 2026 (LÓGICA PROGRESSIVA)")
    print("-" * 50)
    
    dados_2026 = {
        "2026-01": {"RESULTADO": 25000},
        "2026-02": {"RESULTADO": 30000},
        "2026-03": {"RESULTADO": 35000},
    }
    
    saldos_2026 = saldo_manager.calcular_saldos_mensais(dados_2026, licenca_id)
    
    print("Dados de entrada (2026):", dados_2026)
    print("Saldos calculados:")
    for mes, saldo in sorted(saldos_2026.items()):
        print(f"  {mes}: R$ {saldo:,.2f}")
    
    # Verificar se é progressivo (primeiro saldo deve começar do saldo atual + primeiro resultado)
    primeiro_saldo_2026 = saldos_2026["2026-01"]
    saldo_esperado_jan = saldo_atual + 25000
    diferenca_progressiva = abs(primeiro_saldo_2026 - saldo_esperado_jan)
    
    print(f"Verificação progressiva:")
    print(f"  Saldo atual + Resultado Jan/2026 = {saldo_atual:,.2f} + 25.000 = {saldo_esperado_jan:,.2f}")
    print(f"  Saldo calculado Jan/2026 = R$ {primeiro_saldo_2026:,.2f}")
    print(f"  Diferença: R$ {diferenca_progressiva:,.2f}")
    
    if diferenca_progressiva < 10:  # Deve ser exato
        print("✅ LÓGICA PROGRESSIVA funcionando corretamente!")
    else:
        print("❌ Problema na lógica progressiva")
    
    print()
    
    # RESUMO FINAL
    print("🎯 RESUMO DO TESTE:")
    print("=" * 30)
    print(f"✅ Lógica Retroativa (2025): {'OK' if diferenca_2025 < 100000 else 'ERRO'}")
    print(f"✅ Lógica Progressiva (2026): {'OK' if diferenca_progressiva < 10 else 'ERRO'}")
    
    if diferenca_2025 < 100000 and diferenca_progressiva < 10:
        print("\n🎉 TESTE PASSOU - Lógica dual funcionando perfeitamente!")
    else:
        print("\n❌ TESTE FALHOU - Verificar implementação")
    
    print(f"\n🏁 TESTE CONCLUÍDO")

if __name__ == "__main__":
    teste_logica_dual()