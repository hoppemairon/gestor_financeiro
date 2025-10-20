import pandas as pd
from extractors.utils import normalizar_descricao

def converter_para_float(valor_str):
    """Converte uma string de valor BR para float"""
    if isinstance(valor_str, (int, float)):
        return float(valor_str)
    try:
        # Tratar tanto R$ quanto R\$ (escapado)
        return float(str(valor_str).replace("R$", "").replace("R\\$", "").replace(".", "").replace(",", ".").strip())
    except (ValueError, AttributeError, TypeError):
        return 0.0

def remover_duplicatas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove linhas duplicadas com base em Data, Descrição e Valor (R$), se essas colunas existirem.
    """
    colunas_necessarias = {"Data", "Descrição", "Valor (R$)"}
    if not colunas_necessarias.issubset(set(df.columns)):
        return df  # Retorna sem modificar se não tiver colunas esperadas

    df["__desc"] = df["Descrição"].apply(normalizar_descricao)
    # Usar converter_para_float em vez de astype(float) para tratar valores formatados
    df["__valor"] = df["Valor (R$)"].apply(converter_para_float).round(2)
    df["__chave"] = (
        df["Data"].astype(str).str.strip() +
        df["__desc"] +
        df["__valor"].astype(str)
    )

    df_final = df.drop_duplicates(subset="__chave").drop(columns=["__chave", "__desc", "__valor"])
    return df_final