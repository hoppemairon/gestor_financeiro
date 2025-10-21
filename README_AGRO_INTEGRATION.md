# 🌾 Sistema de Tipos de Negócio - Integração Agronegócio

## 📋 Resumo das Implementações

Esta branch (`feature/integracao-agro`) implementa um sistema modular de tipos de negócio no Sistema Bancário MR, com foco inicial na integração de funcionalidades específicas do **agronegócio**.

## 🚀 Principais Funcionalidades Adicionadas

### 1. **Sistema Modular de Tipos de Negócio**
- Estrutura flexível para suportar diferentes tipos de negócio
- Templates específicos por setor (Agro, Medicina, Odontologia)
- Configurações personalizáveis por licença

### 2. **Módulo Agronegócio Completo**
```
logic/business_types/agro/
├── plantio_manager.py      # Gestão de plantios e culturas
├── culturas_financeiro.py  # Análise financeira por cultura
└── rateio_manager.py       # Rateio administrativo baseado em área
```

### 3. **Nova Página: Gestão Agro**
- **Dashboard operacional** com métricas principais
- **Cadastro de plantios** por cultura com dados de produtividade
- **Análise financeira por cultura** com receitas, custos e margens
- **Cenários agro** (pessimista, realista, otimista)
- **Indicadores específicos** do agronegócio

### 4. **Integração com Sistema Vyco**
- Seleção de tipo de negócio na interface principal
- Aplicação automática de templates específicos
- Categorização inteligente com palavras-chave do agro
- Rateio manual para transações sem categoria

## 📊 Indicadores Específicos do Agronegócio

| Indicador | Fórmula | Interpretação |
|-----------|---------|---------------|
| **Receita por Hectare** | `receita_total / hectares_total` | Produtividade financeira por área |
| **Custo por Hectare** | `custo_total / hectares_total` | Custo de produção por área |
| **Custo por Saca** | `custo_total / sacas_total` | Custo unitário de produção |
| **Break-Even Yield** | `custo_total / (preço_saca * hectares)` | Produtividade mínima para cobrir custos |
| **Margem por Cultura** | `(receita - custo) / receita * 100` | Rentabilidade por tipo de cultura |

## 🏗️ Arquitetura da Solução

### Estrutura de Arquivos Criada:
```
logic/business_types/
├── __init__.py
├── business_manager.py           # Gerenciador central
├── agro/
│   ├── __init__.py
│   ├── plantio_manager.py        # CRUD de plantios
│   ├── culturas_financeiro.py    # Análises por cultura
│   └── rateio_manager.py         # Sistema de rateio
└── templates/
    ├── agro_template.json        # Configurações agronegócio
    ├── medicina_template.json    # Configurações medicina
    └── odonto_template.json      # Configurações odontologia

pages/
└── 7_Gestao_Agro.py             # Interface principal agro
```

## 🎯 Template Agronegócio

### Plano de Contas Específico:
- **Receitas:** Venda de grãos (soja, milho, arroz), arrendamentos
- **Custos:** Sementes, fertilizantes, defensivos, combustível, mão de obra
- **Centros de Custo:** Por cultura + administrativo

### Palavras-Chave Inteligentes:
```json
{
  "sementes": "Custo Produção",
  "fertilizante": "Custo Produção", 
  "venda soja": "Venda Soja",
  "diesel": "Combustível Agrícola",
  "arrendamento": "Arrendamento"
}
```

### Cenários Pré-Configurados:
- **Pessimista:** -20% produtividade, -15% preço, +10% custo
- **Realista:** Valores base sem ajustes
- **Otimista:** +15% produtividade, +10% preço, -5% custo

## 🔄 Fluxo de Uso - Agronegócio

1. **Configuração Inicial:**
   - Usuário seleciona "Agronegócio" na página Integração Vyco
   - Sistema ativa automaticamente o modo agro
   - Template específico é carregado

2. **Cadastro de Dados:**
   - Página "Gestão Agro" → Cadastro de plantios
   - Definir: cultura, hectares, produtividade, preço

3. **Importação Financeira:**
   - Dados do Vyco são importados normalmente
   - Aplicação automática de palavras-chave agro
   - Rateio manual para transações sem categoria

4. **Análises Específicas:**
   - DRE tradicional + DRE por cultura
   - Fluxo de caixa com detalhamento por cultura
   - Indicadores específicos do agronegócio
   - Cenários baseados em produtividade

## 🧪 Como Testar

### 1. Ativar a Branch:
```bash
git checkout feature/integracao-agro
```

### 2. Executar o Sistema:
```bash
streamlit run Home.py
```

### 3. Fluxo de Teste:
1. Ir para **"Integração Vyco"**
2. Selecionar **"Agronegócio"** como tipo de negócio
3. Ir para **"Gestão Agro"** (nova página)
4. Cadastrar alguns plantios de teste
5. Importar dados bancários na Integração Vyco
6. Verificar categorização automática e rateio

## 🎯 Benefícios da Implementação

### ✅ **Para o Sistema Atual:**
- **Zero impacto** nos usuários existentes
- **Compatibilidade total** mantida
- **Funcionalidades ativadas** apenas quando necessário

### ✅ **Para Agronegócio:**
- **Análise específica** por cultura
- **Rateio inteligente** baseado em área plantada
- **Indicadores relevantes** para tomada de decisão
- **Cenários agrícolas** para planejamento

### ✅ **Para Expansão:**
- **Base sólida** para outros setores
- **Templates reutilizáveis** para medicina/odonto
- **Arquitetura escalável** para novos tipos

## 🔮 Próximos Passos

### Fase 2 - Melhorias:
- [ ] Interface de rateio manual mais intuitiva
- [ ] Relatórios específicos por cultura
- [ ] Integração com APIs de cotação de commodities
- [ ] Dashboard executivo para agronegócio

### Fase 3 - Expansão:
- [ ] Ativação completa dos templates medicina/odonto
- [ ] Novos tipos de negócio (indústria, varejo)
- [ ] Análises comparativas entre setores

## 🤝 Integração com Projeto Gestor de Plantio

A implementação criou uma **base sólida** para integração futura com o projeto `gestor_plantio` existente, permitindo:

- **Importação** de dados de plantio do sistema externo
- **Sincronização** de dados entre sistemas
- **Análise unificada** financeira + operacional
- **Dashboards integrados** com dados completos

---

## 📞 Suporte e Documentação

Esta implementação mantém a **filosofia do sistema original**:
- **Foco na análise financeira**
- **Interface intuitiva**
- **Relatórios profissionais**
- **Escalabilidade técnica**

Para dúvidas ou sugestões sobre esta implementação, consulte o código nos arquivos criados ou abra uma issue no repositório.

---
*Implementação realizada em outubro de 2025 - Branch: `feature/integracao-agro`*