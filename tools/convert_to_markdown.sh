#!/bin/bash
# Convert Python source files to Markdown format
# This script converts all Python files from the project root to .md files in tools/md/

cd "$(dirname "$0")/.." || exit 1

# Activate virtual environment if it exists
if [ -d "env" ]; then
    source env/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the conversion script
python3 tools/convert_to_markdown.py

