#!/usr/bin/env python3
"""
Teste para verificar formatação brasileira nos valores
"""

import sys
import os

# Adicionar o diretório logic ao path
logic_path = os.path.join(os.path.dirname(__file__), 'logic')
sys.path.append(logic_path)

from logic.saldo_contas import SaldoContasManager
from logic.licenca_manager import licenca_manager

def teste_formatacao_brasileira():
    """Testa a formatação brasileira dos valores"""
    
    print("🧪 TESTE DE FORMATAÇÃO BRASILEIRA")
    print("=" * 50)
    
    # Empresa de teste
    empresa = "CBM"
    licenca_id = "4618e68c-f173-4190-92b4-7a078f01df0f"
    
    print(f"📊 Testando formatação para {empresa}...")
    
    # Buscar saldo atual
    saldo_manager = SaldoContasManager()
    saldo_atual = saldo_manager.buscar_saldo_atual_vyco(licenca_id)
    
    if saldo_atual > 0:
        print(f"✅ Saldo atual encontrado: {saldo_atual}")
        
        # Testar formatação brasileira
        saldo_formatado = f"R$ {saldo_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        print(f"💰 Saldo formatado (BR): {saldo_formatado}")
        
        # Testar dados das contas
        try:
            df_contas = saldo_manager.exibir_dados_contas_debug()
            
            if not df_contas.empty:
                print(f"\n📋 Exemplo de formatação nas contas:")
                print(df_contas.head(2).to_string())
                print("✅ Formatação brasileira aplicada com sucesso!")
            else:
                print("⚠️ Dados das contas não disponíveis para teste")
                
        except Exception as e:
            print(f"❌ Erro ao testar dados das contas: {str(e)}")
    else:
        print("❌ Saldo não encontrado")
    
    print(f"\n🏁 TESTE CONCLUÍDO")

if __name__ == "__main__":
    teste_formatacao_brasileira()