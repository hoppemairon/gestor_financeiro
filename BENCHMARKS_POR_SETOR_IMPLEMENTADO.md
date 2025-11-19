# 📊 Sistema de Benchmarks por Setor - Implementado

## 🎯 Objetivo
Tornar os **benchmarks financeiros dinâmicos** de acordo com o tipo de negócio selecionado pelo usuário, proporcionando comparações mais realistas e pareceres financeiros mais precisos.

## 🔧 Mudanças Implementadas

### 1. ✅ Arquivo de Benchmarks por Setor
**Arquivo criado:** `logic/business_types/benchmarks_setores.json`

Contém benchmarks específicos para cada tipo de negócio:
- **Comércio/Varejo**: Margens típicas de 8-12% líquida, giro de estoque alto
- **Indústria**: Margens maiores (10-20%), giro de estoque mais lento
- **Serviços**: Margens altas (15-30%), sem giro de estoque
- **Agronegócio**: Margens variáveis (10-25%), indicadores específicos por cultura

Cada setor inclui:
- Valores de referência (margem média, bruta, operacional, giro de estoque)
- Interpretações detalhadas
- Indicadores complementares específicos do setor

### 2. ✅ Modificações no `gerador_parecer.py`

#### Função `carregar_benchmarks(tipo_negocio)`
Nova função que carrega benchmarks dinâmicos do JSON baseado no tipo de negócio.

```python
def carregar_benchmarks(tipo_negocio: str = None) -> Dict:
    """Carrega benchmarks específicos do setor/tipo de negócio."""
    # Lê o JSON e retorna benchmarks do setor apropriado
```

#### Função `calcular_indicadores()` - Atualizada
Agora aceita parâmetro `tipo_negocio`:
```python
def calcular_indicadores(metricas: Dict[str, pd.Series], tipo_negocio: str = None) -> Dict[str, float]:
```

Carrega benchmarks específicos:
```python
benchmarks_setor = carregar_benchmarks(tipo_negocio)
indicadores["benchmarks"] = {
    "nome_setor": benchmarks_setor.get("nome", "Geral"),
    "margem_media": benchmarks_setor.get("margem_media", 15),
    ...
}
```

#### Função `exibir_metricas_principais()` - Atualizada
Exibe o nome correto do setor (não mais "varejo" fixo):
```python
nome_setor = indicadores['benchmarks'].get('nome_setor', 'Geral')
st.markdown(f"##### Benchmarks do setor ({nome_setor}):")
```

Trata `giro_estoque = None` para setores de serviço:
```python
if giro_bench is not None:
    st.markdown(f"- Giro de estoque esperado: {giro_bench:.2f}")
else:
    st.markdown("- Giro de estoque: N/A (não aplicável para este setor)")
```

#### Função `gerar_parecer_automatico()` - Atualizada
Aceita parâmetro `tipo_negocio` e repassa para `calcular_indicadores()`:
```python
def gerar_parecer_automatico(..., tipo_negocio=None):
    indicadores = calcular_indicadores(metricas, tipo_negocio)
```

### 3. ✅ Integração Vyco (`5_Integracao_Vyco.py`)

O usuário **já seleciona** o tipo de negócio na interface (linhas 1610-1640).

**Modificação feita:**
```python
# Gerar parecer automático com dados do fluxo de caixa
tipo_negocio_atual = st.session_state.get('tipo_negocio_selecionado', None)
gerar_parecer_automatico(resultado_fluxo, tipo_negocio=tipo_negocio_atual)
```

### 4. ✅ Pré-Análise (`1_Pré_Analise.py`)

**Adicionado:**
- Import do `business_manager`
- Seletor de tipo de negócio logo após a seleção de empresa
- Salvamento no `session_state['tipo_negocio_pre_analise']`
- Passagem do tipo para `gerar_parecer_automatico()`

**Interface adicionada:**
```python
st.markdown("## 🏭 Tipo de Negócio")
tipo_selecionado = st.selectbox(
    "Selecione o tipo de negócio:",
    options=[key for key, _ in opcoes_tipo],
    ...
)
```

**Chamada atualizada:**
```python
gerar_parecer_automatico(resultado_fluxo, tipo_negocio=st.session_state.get('tipo_negocio_pre_analise'))
```

## 📈 Benchmarks por Setor

### 🏪 Comércio / Varejo
- **Margem Líquida:** 12% (faixa: 8-15%)
- **Margem Bruta:** 30% (faixa: 25-35%)
- **Margem Operacional:** 10% (faixa: 8-12%)
- **Giro de Estoque:** 8x/ano (faixa: 6-12x)
- **Indicadores complementares:** CMV/Receita, Ticket Médio

### 🏭 Indústria / Manufatura
- **Margem Líquida:** 15% (faixa: 10-20%)
- **Margem Bruta:** 38% (faixa: 30-45%)
- **Margem Operacional:** 15% (faixa: 12-18%)
- **Giro de Estoque:** 6x/ano (faixa: 4-8x)
- **Indicadores complementares:** Produtividade, OEE, Ponto de Equilíbrio

### 💼 Serviços
- **Margem Líquida:** 20% (faixa: 15-30%)
- **Margem Bruta:** 50% (faixa: 40-60%)
- **Margem Operacional:** 25% (faixa: 20-35%)
- **Giro de Estoque:** N/A (não aplicável)
- **Indicadores complementares:** Faturamento/Colaborador, Taxa de Utilização

### 🌾 Agronegócio
- **Margem Líquida:** 18% (faixa: 10-25%)
- **Margem Bruta:** 42% (faixa: 35-50%)
- **Margem Operacional:** 22% (faixa: 15-30%)
- **Giro de Estoque:** 1.5x/ano (faixa: 1-2x devido ao ciclo de safra)
- **Indicadores específicos:** Receita/ha, Custo/ha, Custo/saca, Produtividade (sacas/ha)
- **Benchmarks por cultura:** Soja, Milho, Café com valores específicos

## 🎯 Benefícios

✅ **Comparações Realistas:** Benchmarks adequados ao setor da empresa  
✅ **Pareceres Precisos:** Análises mais contextualizadas e profissionais  
✅ **Flexibilidade:** Fácil adicionar novos setores editando o JSON  
✅ **Reutilização:** Integrado com sistema de tipos de negócio existente  
✅ **Indicadores Específicos:** Cada setor tem métricas relevantes  

## 🚀 Como Usar

### Na Integração Vyco:
1. Selecionar o tipo de negócio no dropdown
2. Processar os dados normalmente
3. O parecer exibirá benchmarks do setor selecionado

### Na Pré-Análise:
1. Selecionar ou criar uma empresa
2. **Novo:** Selecionar o tipo de negócio
3. Fazer upload e processar documentos
4. O parecer exibirá benchmarks do setor selecionado

## 📂 Arquivos Modificados

1. `logic/business_types/benchmarks_setores.json` ← **CRIADO**
2. `logic/Analises_DFC_DRE/gerador_parecer.py` ← **MODIFICADO**
3. `pages/5_Integracao_Vyco.py` ← **MODIFICADO**
4. `pages/1_Pré_Analise.py` ← **MODIFICADO**

## 🔍 Exemplo de Saída

**Antes:**
```
Benchmarks do setor (varejo):
- Margem média esperada: 15%
- Margem bruta esperada: 35%
```

**Depois (Serviços):**
```
Benchmarks do setor (Serviços):
- Margem média esperada: 20%
- Margem bruta esperada: 50%
- Giro de estoque: N/A (não aplicável para este setor)
```

**Depois (Agronegócio):**
```
Benchmarks do setor (Agronegócio):
- Margem média esperada: 18%
- Margem bruta esperada: 42%
- Giro de estoque esperado: 1.50
```

## 🔮 Próximos Passos (Sugestões)

- [ ] Adicionar mais setores (Construção Civil, Tecnologia, Saúde)
- [ ] Permitir customização de benchmarks por empresa
- [ ] Exibir interpretações dos benchmarks na interface
- [ ] Criar gráficos comparativos: empresa vs. benchmark do setor
- [ ] Alertas automáticos quando indicadores fogem muito dos benchmarks

---

**Data de Implementação:** 18/11/2025  
**Status:** ✅ Implementado e Funcional
