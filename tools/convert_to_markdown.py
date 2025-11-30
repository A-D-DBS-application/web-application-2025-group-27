#!/usr/bin/env python3
"""
Python to Markdown Converter Tool

Converteert alle Python source bestanden naar Markdown documentatie format.
Perfect voor het genereren van code documentatie of voor gebruik in andere projecten.

Educational note: Deze tool is ontworpen om herbruikbaar te zijn in andere projecten.
Pas de CONFIGURATION sectie aan voor je eigen project structuur.

Gebruik:
    python tools/convert_to_markdown.py

Of pas de paden aan in de CONFIGURATION sectie hieronder.
"""

import os
import shutil
from pathlib import Path
from typing import Set, List

# ============================================================================
# CONFIGURATION - Pas deze aan voor je eigen project
# ============================================================================

# Bestanden die automatisch worden uitgesloten van conversie
EXCLUDED_FILES: Set[str] = {
    '__init__.py',
    'convert_to_markdown.py',
    'run.py',  # Entry point, niet nodig in documentatie
    'env.py',  # Alembic environment file
    'script.py.mako',  # Alembic template file
}

# Directories die worden overgeslagen (naast __pycache__)
EXCLUDED_DIRS: Set[str] = {
    'md',  # Voorkom recursie als output dir in tools staat
    '__pycache__',
    '.git',
    'node_modules',
    'env',  # Virtual environment
    'venv',  # Virtual environment (alternatief)
    'migrations',  # Database migrations - niet converteren
    'tools',  # Tools directory - niet converteren
}

# ============================================================================


def convert_py_to_markdown(src_dir: Path, output_dir: Path,
                           excluded_files: Set[str] = None,
                           excluded_dirs: Set[str] = None) -> int:
    """
    Converteer alle Python bestanden naar Markdown format

    Educational note: Deze functie:
    1. Scant recursief door de source directory
    2. Filtert onnodige bestanden (__init__.py, etc.)
    3. Behoudt de directory structuur in de output
    4. Converteert elk .py bestand naar een .md bestand met code syntax highlighting

    Args:
        src_dir: Directory met Python source bestanden
        output_dir: Directory waar markdown bestanden worden opgeslagen
        excluded_files: Set van bestandsnamen om over te slaan
        excluded_dirs: Set van directory namen om over te slaan

    Returns:
        Aantal geconverteerde bestanden
    """
    excluded_files = excluded_files or EXCLUDED_FILES
    excluded_dirs = excluded_dirs or EXCLUDED_DIRS

    # Verwijder bestaande output directory (optioneel - comment uit als je oude bestanden wilt behouden)
    if output_dir.exists():
        shutil.rmtree(output_dir)
        print(f"✓ Cleaned existing directory: {output_dir}")

    # Maak nieuwe output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Vind alle Python bestanden (recursief door directory structuur)
    python_files: List[Path] = []

    for root, dirs, files in os.walk(src_dir):
        # Filter directories - verwijder uit dirs lijst om ze over te slaan
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        for file in files:
            # Alleen Python bestanden, en niet in excluded list
            if file.endswith('.py') and file not in excluded_files:
                file_path = Path(root) / file
                python_files.append(file_path)

    # Sorteer voor consistente output
    python_files.sort()

    print(f"✓ Found {len(python_files)} Python files to convert\n")

    converted_count = 0

    # Converteer elk bestand
    for py_file in python_files:
        try:
            # Lees Python bestand
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"✗ Error reading {py_file}: {e}")
            continue

        # Bereken relatieve pad vanaf source directory
        rel_path = py_file.relative_to(src_dir)

        # Maak output pad (behoud directory structuur)
        # Bijvoorbeeld: services/company_api.py → tools/md/services/company_api.md
        output_subdir = output_dir / rel_path.parent
        output_subdir.mkdir(parents=True, exist_ok=True)
        md_file = output_dir / rel_path.with_suffix('.md')

        # Maak markdown content
        # Bestandsnaam (zonder extensie) wordt de titel
        title = rel_path.stem

        markdown_content = f"""# {title}

```python
{content}
```
"""

        # Schrijf markdown bestand
        try:
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print(f"  ✓ {rel_path} → {md_file.relative_to(output_dir)}")
            converted_count += 1
        except Exception as e:
            print(f"  ✗ Error writing {md_file}: {e}")

    return converted_count


def main():
    """
    Main entry point - configureer hier de paden voor je project

    Educational note: Pas deze functie aan voor je eigen project structuur:
    - Wijzig src_dir als je source code in een andere directory staat
    - Wijzig output_dir als je markdown ergens anders wilt opslaan
    - Voeg command-line argument support toe voor flexibiliteit
    """
    # Get directories (aangepast voor Flask project structuur)
    # Script locatie: tools/convert_to_markdown.py
    tools_dir = Path(__file__).parent

    # PROJECT STRUCTUUR AANPASSEN:
    # Voor dit Flask project staan de Python files direct in de root
    project_root = tools_dir.parent  # Van tools/ → project root
    src_dir = project_root  # Source directory is project root (alle .py files)

    # Output directory (waar markdown bestanden worden opgeslagen)
    output_dir = tools_dir / 'md'  # Output in tools/md/

    # OPTIE: Accepteer paden als command-line argumenten
    # import sys
    # if len(sys.argv) > 1:
    #     src_dir = Path(sys.argv[1])
    # if len(sys.argv) > 2:
    #     output_dir = Path(sys.argv[2])

    print("=" * 60)
    print("Python to Markdown Converter - Rival Project")
    print("=" * 60)
    print(f"Source directory: {src_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Excluded files: {EXCLUDED_FILES}")
    print(f"Excluded directories: {EXCLUDED_DIRS}")
    print("=" * 60)
    print()

    if not src_dir.exists():
        print(f"✗ Error: Source directory does not exist: {src_dir}")
        print("\nTip: Pas de paden aan in de main() functie voor je project structuur")
        return

    # Converteer bestanden
    converted_count = convert_py_to_markdown(
        src_dir,
        output_dir,
        excluded_files=EXCLUDED_FILES,
        excluded_dirs=EXCLUDED_DIRS
    )

    print()
    print("=" * 60)
    print(f"✓ Conversion complete! {converted_count} files converted")
    print(f"  Output location: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()

