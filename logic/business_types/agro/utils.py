"""
Utilidades para o módulo agronegócio
"""

def formatar_valor_br(valor):
    """
    Formatar valor monetário no padrão brasileiro
    Ex: 1234567.89 -> R$ 1.234.567,89
    """
    try:
        valor_num = float(valor) if not isinstance(valor, (int, float)) else valor
        # Formato americano primeiro, depois troca separadores
        return f"R$ {valor_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"

def formatar_valor_simples_br(valor):
    """
    Formatar valor sem símbolo R$ no padrão brasileiro  
    Ex: 1234567.89 -> 1.234.567,89
    """
    try:
        valor_num = float(valor) if not isinstance(valor, (int, float)) else valor
        # Formato americano primeiro, depois troca separadores
        return f"{valor_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"

def formatar_percentual_br(valor):
    """
    Formatar percentual no padrão brasileiro
    Ex: 0.6543 -> 65,43%
    """
    try:
        valor_num = float(valor) if not isinstance(valor, (int, float)) else valor
        return f"{valor_num*100:.2f}%".replace(".", ",")
    except (ValueError, TypeError):
        return "0,00%"

def formatar_hectares_br(valor):
    """
    Formatar hectares no padrão brasileiro
    Ex: 1234.5 -> 1.234,50 ha
    """
    try:
        valor_num = float(valor) if not isinstance(valor, (int, float)) else valor
        # Formato americano primeiro, depois troca separadores
        return f"{valor_num:,.2f} ha".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00 ha"

def formatar_produtividade_br(valor):
    """
    Formatar produtividade (sacas/ha) no padrão brasileiro
    Ex: 1234.5 -> 1.234,50 sacas/ha
    """
    try:
        valor_num = float(valor) if not isinstance(valor, (int, float)) else valor
        # Formato americano primeiro, depois troca separadores
        return f"{valor_num:,.2f} sacas/ha".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00 sacas/ha"