#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script utilitário para limpeza de arquivos temporários do projeto.
Uso: python cleanup_utils.py
"""

import shutil
from pathlib import Path

def clean_temp_files():
    """Remove todos os arquivos temporários do projeto"""
    
    project_root = Path(__file__).parent
    temp_dir = project_root / "temp"
    
    print("🧹 Iniciando limpeza de arquivos temporários...")
    
    # Limpar pasta temp
    if temp_dir.exists():
        temp_files = list(temp_dir.glob("*"))
        temp_files = [f for f in temp_files if f.name != "README.md"]
        
        if temp_files:
            print(f"📁 Removendo {len(temp_files)} arquivos da pasta temp/")
            for file in temp_files:
                if file.is_file():
                    file.unlink()
                    print(f"  ✅ Removido: {file.name}")
                elif file.is_dir():
                    shutil.rmtree(file)
                    print(f"  ✅ Removido diretório: {file.name}")
        else:
            print("📁 Pasta temp/ já está limpa")
    
    # Limpar arquivos temporários do projeto (padrões comuns)
    patterns = [
        "*_temp.*",
        "*_backup.*", 
        "fix_*.py",  # Mas não este arquivo
        "temp_*.py",
        "*.tmp",
        "*.bak"
    ]
    
    removed_count = 0
    for pattern in patterns:
        files = list(project_root.glob(pattern))
        # Excluir este próprio arquivo
        files = [f for f in files if f.name != "cleanup_utils.py"]
        
        for file in files:
            if file.is_file():
                file.unlink()
                print(f"  ✅ Removido: {file.name}")
                removed_count += 1
    
    if removed_count > 0:
        print(f"🗑️  Removidos {removed_count} arquivos temporários do projeto")
    else:
        print("✨ Projeto já está limpo!")
    
    print("🎉 Limpeza concluída!")

if __name__ == "__main__":
    clean_temp_files()