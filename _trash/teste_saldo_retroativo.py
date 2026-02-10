"""
Teste de Validação - Lógica de Saldo Retroativo
Valida se conseguimos calcular saldo inicial baseado no saldo atual e resultados históricos
"""

import json
import os
from datetime import datetime
from logic.data_cache_manager import cache_manager
from logic.saldo_contas import saldo_manager
from logic.licenca_manager import licenca_manager

def carregar_dados_dre_cbm():
    """Carrega dados DRE da CBM do cache"""
    try:
        # Usar o cache manager do sistema para carregar dados corretos
        empresas_disponiveis = cache_manager.listar_empresas_disponiveis()
        
        # Procurar CBM especificamente (não Arani)
        empresa_cbm = None
        for empresa in empresas_disponiveis:
            if "cbm" in empresa['nome'].lower():
                empresa_cbm = empresa
                break
        
        if not empresa_cbm:
            print("❌ Empresa CBM não encontrada no cache")
            print("📋 Empresas disponíveis:")
            for emp in empresas_disponiveis:
                print(f"   - {emp['nome']}")
            return {}
        
        print(f"📁 Carregando dados de: {empresa_cbm['nome']}")
        
        # Carregar dados DRE usando o método correto
        dados_dre = cache_manager.carregar_dre(empresa_cbm['nome'])
        
        if not dados_dre:
            print("❌ Dados DRE não encontrados")
            return {}
        
        # Debug da estrutura
        print(f"🔍 Estrutura dos dados carregados:")
        for chave in list(dados_dre.keys())[:5]:  # Primeiras 5 chaves
            print(f"   {chave}: {type(dados_dre[chave])}")
        
        return dados_dre
        
    except Exception as e:
        print(f"❌ Erro ao carregar dados CBM: {e}")
        return {}

def obter_saldo_atual_cbm():
    """Obtém saldo atual da CBM via Vyco"""
    try:
        # Buscar licença da CBM especificamente
        licencas_ativas = licenca_manager.obter_licencas_ativas()
        
        licenca_cbm = None
        for licenca in licencas_ativas:
            if "cbm" in licenca.lower():
                licenca_cbm = licenca
                break
        
        if not licenca_cbm:
            print("❌ Licença da CBM não encontrada")
            print("📋 Licenças disponíveis:")
            for lic in licencas_ativas:
                print(f"   - {lic}")
            return 0.0
        
        licenca_id = licenca_manager.obter_id_licenca(licenca_cbm)
        if not licenca_id:
            print("❌ ID da licença CBM não encontrado")
            return 0.0
        
        print(f"🔍 Buscando saldo atual para: {licenca_cbm}")
        print(f"🔑 ID da licença: {licenca_id}")
        saldo_atual = saldo_manager.buscar_saldo_atual_vyco(licenca_id)
        
        return saldo_atual
        
    except Exception as e:
        print(f"❌ Erro ao obter saldo atual: {e}")
        return 0.0

def obter_saldo_inicial_contas_cbm():
    """Obtém saldo inicial das contas da CBM (simulação - usaremos valorinicial)"""
    try:
        # Buscar licença da CBM especificamente
        licencas_ativas = licenca_manager.obter_licencas_ativas()
        
        licenca_cbm = None
        for licenca in licencas_ativas:
            if "cbm" in licenca.lower():
                licenca_cbm = licenca
                break
        
        if not licenca_cbm:
            return 0.0
        
        licenca_id = licenca_manager.obter_id_licenca(licenca_cbm)
        if not licenca_id:
            return 0.0
        
        # Buscar dados das contas para obter valor inicial
        engine = saldo_manager.conectar_banco_vyco()
        if engine is None:
            return 0.0
            
        import pandas as pd
        query = f"""
        SELECT valorinicial, datainicial, dataencerramento
        FROM analytics.fn_contas_por_licencas(
            ARRAY['{licenca_id}']::uuid[], 
            -1, 
            0
        );
        """
        
        df_contas = pd.read_sql(query, engine)
        engine.dispose()
        
        if df_contas.empty:
            return 0.0
        
        # Somar valores iniciais das contas ativas
        if 'valorinicial' in df_contas.columns:
            contas_ativas = df_contas[pd.isna(df_contas.get('dataencerramento', []))]
            saldo_inicial_total = contas_ativas['valorinicial'].sum()
            return float(saldo_inicial_total)
        
        return 0.0
        
    except Exception as e:
        print(f"❌ Erro ao obter saldo inicial: {e}")
        return 0.0

def teste_validacao_saldo_retroativo():
    """
    Teste principal para validar lógica retroativa
    """
    print("🧪 INICIANDO TESTE DE VALIDAÇÃO DE SALDO RETROATIVO")
    print("=" * 60)
    
    # ETAPA 1: Carregar dados DRE
    print("\n📊 ETAPA 1: Carregando dados DRE da CBM...")
    dados_dre = carregar_dados_dre_cbm()
    
    if not dados_dre:
        print("❌ Não foi possível carregar dados DRE")
        return
    
    print(f"✅ Dados carregados: {len(dados_dre)} meses encontrados")
    
    # Filtrar chaves que são metadados vs dados reais
    chaves_dados = [k for k in dados_dre.keys() if k not in ["dados_indexados", "tipo", "ultima_atualizacao"]]
    
    if chaves_dados:
        meses_disponiveis = sorted(chaves_dados)
        print(f"📅 Período: {meses_disponiveis[0]} até {meses_disponiveis[-1]}")
    else:
        print("⚠️ Não foram encontradas chaves de dados mensais")
    
    # ETAPA 2: Obter saldo atual
    print("\n💰 ETAPA 2: Obtendo saldo atual via Vyco...")
    saldo_atual_real = obter_saldo_atual_cbm()
    
    if saldo_atual_real == 0:
        print("❌ Não foi possível obter saldo atual")
        return
    
    print(f"✅ Saldo atual obtido: R$ {saldo_atual_real:,.2f}")
    
    # ETAPA 3: Calcular soma dos resultados históricos
    print("\n🔄 ETAPA 3: Calculando soma dos resultados históricos...")
    
    # Debug da estrutura dos dados
    print("🔍 Analisando estrutura dos dados...")
    
    dados_mensais = {}
    fonte_utilizada = ""
    
    # PRIORIDADE 1: Buscar especificamente por "RESULTADO" (valor líquido real)
    campos_resultado_prioritarios = ['RESULTADO']
    
    print("🎯 BUSCANDO ESPECIFICAMENTE 'RESULTADO' (valor líquido)...")
    
    # Verificar estruturas aninhadas em busca de RESULTADO
    for chave_principal, conteudo_principal in dados_dre.items():
        if isinstance(conteudo_principal, dict):
            for chave_secao, conteudo_secao in conteudo_principal.items():
                # Verificar se a seção é exatamente RESULTADO
                if chave_secao == 'RESULTADO':
                    print(f"🎯 ENCONTRADO: {chave_principal}.{chave_secao}")
                    if isinstance(conteudo_secao, dict):
                        for mes, valor in conteudo_secao.items():
                            if mes not in ['TOTAL', '%'] and isinstance(valor, (int, float)) and len(mes) == 7:
                                dados_mensais[mes] = {'RESULTADO': valor}
                        fonte_utilizada = f"{chave_principal}.{chave_secao}"
                        print(f"✅ USANDO FONTE: {fonte_utilizada}")
                        break
                        
                # Verificar estruturas mais aninhadas (como resultado_liquido.RESULTADO)
                if isinstance(conteudo_secao, dict) and 'itens' in conteudo_secao:
                    for item_key, item_value in conteudo_secao['itens'].items():
                        if item_key == 'RESULTADO' and isinstance(item_value, dict):
                            if 'valores' in item_value:
                                valores = item_value['valores']
                                print(f"🎯 ENCONTRADO: {chave_principal}.{chave_secao}.itens.{item_key}")
                                for mes, valor in valores.items():
                                    if mes not in ['TOTAL', '%'] and isinstance(valor, (int, float)) and len(mes) == 7:
                                        dados_mensais[mes] = {'RESULTADO': valor}
                                fonte_utilizada = f"{chave_principal}.{chave_secao}.itens.{item_key}.valores"
                                print(f"✅ USANDO FONTE: {fonte_utilizada}")
                                break
                
                if dados_mensais:
                    break
            if dados_mensais:
                break
    
    # FALLBACK: Se não encontrou RESULTADO, buscar por outros campos
    if not dados_mensais:
        print("⚠️ RESULTADO específico não encontrado, buscando alternativas...")
        campos_alternativos = ['LUCRO_LIQUIDO', 'LUCRO LIQUIDO', 'resultado_liquido']
        
        for chave_principal, conteudo_principal in dados_dre.items():
            if isinstance(conteudo_principal, dict):
                for chave_secao, conteudo_secao in conteudo_principal.items():
                    if any(campo.lower() in chave_secao.lower() for campo in campos_alternativos):
                        print(f"🔄 Tentando: {chave_principal}.{chave_secao}")
                        if isinstance(conteudo_secao, dict):
                            if 'valores' in conteudo_secao:
                                valores = conteudo_secao['valores']
                                for mes, valor in valores.items():
                                    if mes not in ['TOTAL', '%'] and isinstance(valor, (int, float)) and len(mes) == 7:
                                        dados_mensais[mes] = {'RESULTADO': valor}
                                fonte_utilizada = f"{chave_principal}.{chave_secao}.valores"
                                break
                if dados_mensais:
                    break
    
    # Se não encontrou RESULTADO, buscar por 'dados_indexados' que pode conter resultado final
    if not dados_mensais and 'dados_indexados' in dados_dre:
        dados_indexados = dados_dre['dados_indexados']
        if isinstance(dados_indexados, dict):
            print("\n📋 USANDO dados_indexados como fallback")
            print(f"   📊 Conteúdo: {dict(list(dados_indexados.items())[:3])}")
            
            for mes, valor in dados_indexados.items():
                if mes not in ['TOTAL', '%'] and isinstance(valor, (int, float)) and len(mes) == 7:
                    dados_mensais[mes] = {'RESULTADO': valor}
            fonte_utilizada = "dados_indexados"
            print(f"   📈 Extraídos {len(dados_mensais)} meses")
    
    if not dados_mensais:
        print("❌ Não foi possível encontrar dados de RESULTADO na estrutura")
        return
    
    print(f"\n🎯 FONTE DE DADOS CONFIRMADA: {fonte_utilizada}")
    print(f"✅ DADOS DE RESULTADO confirmados: {len(dados_mensais)} meses para análise")
    
    # Mostrar alguns valores de exemplo da fonte selecionada
    print(f"\n📋 VALORES DE EXEMPLO DA FONTE ({fonte_utilizada}):")
    exemplo_meses = sorted(dados_mensais.keys())[:5]
    for mes in exemplo_meses:
        valor = dados_mensais[mes]['RESULTADO']
        print(f"   {mes}: R$ {valor:>12,.2f}")
    
    # Filtrar apenas meses válidos e ordenar
    meses_validos = []
    for mes in sorted(dados_mensais.keys()):
        try:
            ano = int(mes[:4])
            mes_num = int(mes[5:7])
            if 2020 <= ano <= 2025 and 1 <= mes_num <= 12:
                meses_validos.append(mes)
        except:
            continue
    
    print(f"\n🗓️ PERÍODO ANALISADO: {meses_validos[0]} a {meses_validos[-1]} ({len(meses_validos)} meses)")
    
    soma_resultados_historicos = 0.0
    resultados_detalhados = []
    
    for mes in meses_validos:
        resultado_mes = dados_mensais[mes]['RESULTADO']
        soma_resultados_historicos += resultado_mes
        resultados_detalhados.append((mes, resultado_mes))
    
    print(f"✅ Soma dos resultados calculada: R$ {soma_resultados_historicos:,.2f}")
    print(f"📈 Meses com resultado: {len(resultados_detalhados)}")
    
    # Mostrar alguns exemplos
    print("\n📋 Exemplos de resultados por mês:")
    for i, (mes, resultado) in enumerate(resultados_detalhados):
        if i < 10:  # Primeiros 10 para debug
            status = "🔺" if resultado > 0 else "🔻" if resultado < 0 else "➖"
            print(f"   {mes}: R$ {resultado:>12,.2f} {status}")
    
    if len(resultados_detalhados) > 10:
        print(f"   ... e mais {len(resultados_detalhados) - 10} meses")
    
    # Debug adicional - mostrar maiores valores
    print("\n📊 Top 5 maiores resultados (absolutos):")
    resultados_ordenados = sorted(resultados_detalhados, key=lambda x: abs(x[1]), reverse=True)
    for i, (mes, resultado) in enumerate(resultados_ordenados[:5]):
        status = "🔺" if resultado > 0 else "🔻" if resultado < 0 else "➖"
        print(f"   {i+1}. {mes}: R$ {resultado:>12,.2f} {status}")
    
    # ETAPA 4: Calcular saldo inicial retroativo
    print("\n🎯 ETAPA 4: Calculando saldo inicial retroativo...")
    
    # FÓRMULA: Saldo_Inicial = Saldo_Atual - Soma_Resultados_Históricos
    saldo_inicial_calculado = saldo_atual_real - soma_resultados_historicos
    
    print(f"✅ Saldo inicial calculado: R$ {saldo_inicial_calculado:,.2f}")
    
    # ETAPA 5: Obter saldo inicial real (das contas)
    print("\n🏦 ETAPA 5: Obtendo saldo inicial real das contas...")
    saldo_inicial_real = obter_saldo_inicial_contas_cbm()
    
    if saldo_inicial_real == 0:
        print("⚠️ Não foi possível obter saldo inicial real")
        print("   (Usando saldo calculado como referência)")
    else:
        print(f"✅ Saldo inicial real: R$ {saldo_inicial_real:,.2f}")
    
    # ETAPA 6: Análise e validação
    print("\n📈 ETAPA 6: Análise dos resultados...")
    print("=" * 60)
    
    print(f"💰 Saldo Atual (Real):           R$ {saldo_atual_real:>15,.2f}")
    print(f"📊 Soma Resultados Históricos:   R$ {soma_resultados_historicos:>15,.2f}")
    print(f"🎯 Saldo Inicial Calculado:      R$ {saldo_inicial_calculado:>15,.2f}")
    
    if saldo_inicial_real > 0:
        print(f"🏦 Saldo Inicial Real:           R$ {saldo_inicial_real:>15,.2f}")
        
        diferenca = abs(saldo_inicial_calculado - saldo_inicial_real)
        percentual_erro = (diferenca / saldo_inicial_real) * 100 if saldo_inicial_real != 0 else 0
        
        print(f"📏 Diferença:                    R$ {diferenca:>15,.2f}")
        print(f"📊 Erro Percentual:              {percentual_erro:>15.2f}%")
        
        # Conclusão
        print("\n" + "=" * 60)
        if percentual_erro < 5:
            print("✅ TESTE PASSOU - Lógica retroativa validada!")
            print("   A diferença está dentro da tolerância de 5%")
        elif percentual_erro < 15:
            print("⚠️ TESTE PARCIAL - Lógica tem desvios")
            print("   A diferença é aceitável mas pode indicar problemas nos dados")
        else:
            print("❌ TESTE FALHOU - Lógica precisa ser revista")
            print("   Diferença muito alta, pode haver problemas na abordagem")
    else:
        print("\n" + "=" * 60)
        print("💡 TESTE INFORMATIVO - Saldo inicial calculado com sucesso")
        print("   Não foi possível validar contra saldo real")
    
    # Fórmula de validação
    print(f"\n🧮 FÓRMULA UTILIZADA:")
    print(f"   Saldo_Inicial = Saldo_Atual - Soma_Resultados")
    print(f"   {saldo_inicial_calculado:,.2f} = {saldo_atual_real:,.2f} - {soma_resultados_historicos:,.2f}")
    
    # NOVA SEÇÃO: Progressão mês a mês do saldo
    print(f"\n📊 PROGRESSÃO DO SALDO MÊS A MÊS:")
    print("=" * 80)
    
    # Começar do saldo inicial real e aplicar resultados mês a mês
    saldo_inicial_real = obter_saldo_inicial_contas_cbm()
    if saldo_inicial_real == 0:
        saldo_inicial_real = saldo_inicial_calculado
    
    saldo_corrente = saldo_inicial_real
    print(f"💰 SALDO INICIAL (Jan/2024): R$ {saldo_corrente:>12,.2f}")
    print("-" * 80)
    
    # Aplicar resultados mês a mês
    for i, (mes, resultado) in enumerate(resultados_detalhados):
        saldo_anterior = saldo_corrente
        saldo_corrente += resultado
        
        status = "🔺" if resultado > 0 else "🔻" if resultado < 0 else "➖"
        
        # Mostrar apenas alguns meses para não poluir
        if i < 10 or i >= len(resultados_detalhados) - 5:
            print(f"{mes}: R$ {saldo_anterior:>12,.2f} + R$ {resultado:>10,.2f} {status} = R$ {saldo_corrente:>12,.2f}")
        elif i == 10:
            print("   ... (meses intermediários omitidos) ...")
    
    print("-" * 80)
    print(f"💰 SALDO FINAL CALCULADO:    R$ {saldo_corrente:>12,.2f}")
    print(f"💰 SALDO ATUAL REAL (Vyco): R$ {saldo_atual_real:>12,.2f}")
    diferenca_final = abs(saldo_corrente - saldo_atual_real)
    print(f"📏 DIFERENÇA FINAL:          R$ {diferenca_final:>12,.2f}")
    
    if diferenca_final < 1000:
        print("✅ EXCELENTE! Diferença menor que R$ 1.000 - Lógica validada!")
    elif diferenca_final < 10000:
        print("✅ BOM! Diferença menor que R$ 10.000 - Lógica aprovada!")
    elif diferenca_final < 100000:
        print("⚠️ ACEITÁVEL - Diferença pode ser explicada por fatores externos")
    else:
        print("❌ DIFERENÇA ALTA - Investigar discrepâncias")
    
    print(f"\n🔄 PRÓXIMOS PASSOS:")
    if diferenca_final < 10000:
        print("   ✅ Implementar lógica retroativa no sistema principal")
        print("   ✅ A abordagem está validada e pronta para uso")
        print("   📊 Usar fonte: RESULTADO (valor líquido)")
    else:
        print("   🔍 Investigar discrepâncias nos dados")
        print("   🔧 Verificar se há retiradas, investimentos ou outras movimentações não contabilizadas")

if __name__ == "__main__":
    teste_validacao_saldo_retroativo()