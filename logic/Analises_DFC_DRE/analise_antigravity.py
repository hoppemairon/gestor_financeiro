import pandas as pd
import numpy as np
import openai
import os
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Cliente OpenAI
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def formatar_brl(valor):
    if pd.isna(valor):
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_tendencia(serie_temporal, meses=None):
    """
    Calcula a tendência linear (inclinação da reta) de uma série temporal.
    Se 'meses' for int, considera apenas os últimos N meses.
    """
    if serie_temporal is None or len(serie_temporal) < 2:
        return 0.0
    
    y = serie_temporal.values
    if meses and len(y) > meses:
        y = y[-meses:]
        
    x = np.arange(len(y))
    
    # Remove NaNs
    mask = np.isfinite(y)
    if not mask.any() or len(y[mask]) < 2:
        return 0.0
        
    try:
        slope = np.polyfit(x[mask], y[mask], 1)[0]
        return slope
    except:
        return 0.0

def calcular_indicadores_avancados(df_fluxo, df_dre):
    """
    Calcula indicadores financeiros avançados para o Parecer Antigravity.
    """
    indicadores = {}
    
    # Séries principais
    receita = df_fluxo.loc["🔷 Total de Receitas"] if "🔷 Total de Receitas" in df_fluxo.index else pd.Series(0, index=df_fluxo.columns)
    despesa = df_fluxo.loc["🔻 Total de Despesas"] if "🔻 Total de Despesas" in df_fluxo.index else pd.Series(0, index=df_fluxo.columns)
    resultado = df_fluxo.loc["🏦 Resultado do Período"] if "🏦 Resultado do Período" in df_fluxo.index else pd.Series(0, index=df_fluxo.columns)
    
    # 1. Análise de Tendência (Curto vs Longo Prazo)
    indicadores["tendencia_resultado_12m"] = calcular_tendencia(resultado)
    indicadores["tendencia_resultado_3m"] = calcular_tendencia(resultado, meses=3)
    
    indicadores["sinal_recuperacao"] = (
        indicadores["tendencia_resultado_12m"] < 0 and 
        indicadores["tendencia_resultado_3m"] > 0
    )
    
    indicadores["sinal_deterioracao"] = (
        indicadores["tendencia_resultado_12m"] > 0 and 
        indicadores["tendencia_resultado_3m"] < 0
    )

    # 2. Margens Médias
    receita_media = receita.mean()
    indicadores["receita_media"] = receita_media
    indicadores["resultado_medio"] = resultado.mean()
    
    if receita_media != 0:
        indicadores["margem_liq_media"] = (indicadores["resultado_medio"] / receita_media) * 100
    else:
        indicadores["margem_liq_media"] = 0.0

    # 3. EBITDA (Aproximado se DRE disponível)
    if df_dre is not None and not df_dre.empty:
        # Tenta encontrar linhas de Juros/Impostos/Depreciação se existirem, senão usa Operacional
        # Ajuste conforme estrutura real do seu DRE
        try:
            lucro_operacional = df_dre.loc["LUCRO OPERACIONAL"] if "LUCRO OPERACIONAL" in df_dre.index else (
                df_dre.loc["Lucro Operacional"] if "Lucro Operacional" in df_dre.index else None
            )
            
            if lucro_operacional is not None:
                indicadores["ebitda_medio"] = lucro_operacional.mean() # Simplificação: EBIT ~ EBITDA se não tiver DA
                if receita_media != 0:
                    indicadores["margem_ebitda_media"] = (indicadores["ebitda_medio"] / receita_media) * 100
            else:
                indicadores["ebitda_medio"] = None
        except:
            indicadores["ebitda_medio"] = None
    else:
        indicadores["ebitda_medio"] = None

    # 4. Volatilidade (Risco)
    desvio_padrao = resultado.std()
    indicadores["volatilidade_valor"] = desvio_padrao
    if indicadores["resultado_medio"] != 0:
        indicadores["cv_resultado"] = abs(desvio_padrao / indicadores["resultado_medio"]) # Coeficiente de Variação
    else:
        indicadores["cv_resultado"] = 0.0

    return indicadores

def gerar_prompt_enriquecido(indicadores, df_fluxo, df_dre, descricao_empresa):
    """
    Gera um prompt rico com contexto pré-calculado.
    """
    
    # Preparar texto dos indicadores
    texto_indicadores = f"""
    - Receita Média Mensal: {formatar_brl(indicadores.get('receita_media', 0))}
    - Resultado Médio Mensal: {formatar_brl(indicadores.get('resultado_medio', 0))}
    - Margem Líquida Média: {indicadores.get('margem_liq_media', 0):.1f}%
    
    - Tendência Linear (12 meses): {formatar_brl(indicadores.get('tendencia_resultado_12m', 0))}/mês
    - Tendência Recente (3 meses): {formatar_brl(indicadores.get('tendencia_resultado_3m', 0))}/mês
    """
    
    if indicadores.get("sinal_recuperacao"):
        texto_indicadores += "\n    - ALERTA: Sinais de RECUPERAÇÃO recente (curto prazo positivo vs histórico negativo)."
    if indicadores.get("sinal_deterioracao"):
        texto_indicadores += "\n    - ALERTA: Sinais de DETERIORAÇÃO recente (curto prazo negativo vs histórico positivo)."
        
    if indicadores.get("ebitda_medio"):
        texto_indicadores += f"\n    - Estimativa EBITDA Médio: {formatar_brl(indicadores['ebitda_medio'])}"
        
    texto_indicadores += f"\n    - Volatilidade (Desvio Padrão): {formatar_brl(indicadores.get('volatilidade_valor', 0))}"

    # Preparar tabelas (truncadas se necessário, mas focando nos ultimos meses que importam mais)
    texto_fluxo = df_fluxo.iloc[:, -12:].to_markdown() if df_fluxo is not None else "N/A" # Últimos 12 meses
    texto_dre = df_dre.iloc[:, -12:].to_markdown() if df_dre is not None else "N/A"

    prompt = f"""
    Atue como um Analista Financeiro Sênior 'Antigravity' (focado, direto, crítico e estratégico).
    
    **CONTEXTO DA EMPRESA:**
    {descricao_empresa}
    
    **INDICADORES PRÉ-CALCULADOS (CONFIE NESTES DADOS MATEMÁTICOS):**
    {texto_indicadores}
    
    **DADOS FINANCEIROS (FLUXO DE CAIXA - Últimos 12 meses):**
    {texto_fluxo}
    
    **DRE (Demonstrativo de Resultado):**
    {texto_dre}
    
    ---
    
    **SUA MISSÃO:**
    Gerar um parecer financeiro estruturado que vá direto ao ponto. Não descreva apenas o que subiu ou desceu, explique o PORQUÊ (hipóteses baseadas nas linhas de despesa/receita) e O QUE FAZER.
    
    **ESTRUTURA OBRIGATÓRIA DE SAÍDA:**
    
    ### 1. Diagnóstico Executivo de Precisão 🎯
    (Resumo em 3-4 frases sobre a saúde real da empresa. Use números. Seja taxativo: a empresa está saudável, em risco ou estável?)
    
    ### 2. Análise de Causa Raiz (Hipóteses) 🔍
    (Liste 3 pontos críticos. Para cada um, levante uma hipótese da causa baseada nos dados. Ex: "Aumento de custo fixo não acompanhado por receita sugere ineficiência operacional recente".)
    
    ### 3. Plano de Ação Tático (Próximos 30-60 dias) 🚀
    (3 a 5 ações concretas e imediatas. Comece com verbo no imperativo. Ex: "Renegociar contratos de fornecedores X", "Cortar despesas Y em 10%").
    
    ### 4. Análise de Estrutura de Capital e Risco ⚖️
    (Comente sobre a volatilidade, dependência de capital de terceiros se visível, e sustentabilidade das margens).
    
    """
    return prompt

def analisar_antigravity_gpt(df_dre, df_fluxo, descricao_empresa, modelo="gpt-4-turbo"):
    """
    Função principal para orquestrar a análise Antigravity.
    """
    if df_fluxo is None or df_fluxo.empty:
        return "Erro: Dados insuficientes para análise."

    # 1. Calcular indicadores matemáticos
    indicadores = calcular_indicadores_avancados(df_fluxo, df_dre)
    
    # 2. Gerar prompt enriquecido
    prompt = gerar_prompt_enriquecido(indicadores, df_fluxo, df_dre, descricao_empresa)
    
    # 3. Chamar GPT
    with st.spinner("🚀 Gerando Análise Antigravity (Processando indicadores avançados + IA)..."):
        placeholder = st.empty()
        full_response = ""
        try:
            stream = client.chat.completions.create(
                model=modelo,
                messages=[
                    {"role": "system", "content": "Você é um expert em finanças corporativas, crítico e focado em reestruturação e crescimento."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3, # Menor temperatura para mais precisão
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    placeholder.markdown(full_response)
                    
        except Exception as e:
            st.error(f"Erro na análise Antigravity: {e}")
            return None
            
    return full_response
