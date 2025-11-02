#!/usr/bin/env python3
"""
Script to find potentially unused functions, classes, and files in the codebase.
"""

import ast
from collections import defaultdict
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple


class CodeAnalyzer(ast.NodeVisitor):
    """Analyze Python code to find definitions and usages."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.definitions: Dict[str, List[int]] = defaultdict(
            list
        )  # name -> line numbers
        self.imports: Set[str] = set()
        self.calls: Set[str] = set()
        self.attribute_accesses: Set[str] = set()
        self.names_used: Set[str] = set()

    def visit_FunctionDef(self, node):
        """Track function definitions."""
        self.definitions[node.name].append(node.lineno)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        """Track async function definitions."""
        self.definitions[node.name].append(node.lineno)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Track class definitions."""
        self.definitions[node.name].append(node.lineno)
        self.generic_visit(node)

    def visit_Import(self, node):
        """Track imports."""
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imports.add(name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Track from imports."""
        for alias in node.names:
            if alias.name == "*":
                continue
            name = alias.asname if alias.asname else alias.name
            self.imports.add(name)
        self.generic_visit(node)

    def visit_Call(self, node):
        """Track function calls."""
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
            self.names_used.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.attribute_accesses.add(node.func.attr)
        self.generic_visit(node)

    def visit_Name(self, node):
        """Track name usage."""
        if isinstance(node.ctx, (ast.Load, ast.Del)):
            self.names_used.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        """Track attribute access."""
        self.attribute_accesses.add(node.attr)
        self.generic_visit(node)


def analyze_file(filepath: Path) -> Tuple[Dict, Set, Set, Set]:
    """Analyze a Python file and return definitions and usages."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(filepath))
        analyzer = CodeAnalyzer(str(filepath))
        analyzer.visit(tree)

        return (
            analyzer.definitions,
            analyzer.imports,
            analyzer.calls | analyzer.names_used,
            analyzer.attribute_accesses,
        )
    except SyntaxError as e:
        print(f"⚠️  Syntax error in {filepath}: {e}")
        return {}, set(), set(), set()
    except Exception as e:
        print(f"⚠️  Error analyzing {filepath}: {e}")
        return {}, set(), set(), set()


def find_python_files(root_dir: Path, exclude_dirs: Set[str]) -> List[Path]:
    """Find all Python files in the project, excluding certain directories."""
    python_files = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Remove excluded directories from the walk
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        for filename in filenames:
            if filename.endswith(".py"):
                python_files.append(Path(dirpath) / filename)

    return python_files


def check_if_imported_as_module(
    filepath: Path, root_dir: Path, all_imports: Set[str]
) -> bool:
    """Check if a file is imported as a module in other files."""
    relative_path = filepath.relative_to(root_dir)

    # Convert file path to potential module names
    module_path = str(relative_path.with_suffix(""))
    module_variations = [
        module_path.replace("/", "."),
        module_path.replace("/", ".").replace(".__init__", ""),
        filepath.stem,
    ]

    for variation in module_variations:
        if variation in all_imports:
            return True

    return False


def analyze_codebase(root_dir: Path):
    """Analyze the entire codebase for unused code."""
    exclude_dirs = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        "baml_client",
    }

    print("🔍 Scanning for Python files...\n")
    python_files = find_python_files(root_dir, exclude_dirs)
    print(f"Found {len(python_files)} Python files\n")

    # Collect all definitions and usages
    all_definitions: Dict[str, List[Tuple[Path, int]]] = defaultdict(list)
    all_usages: Set[str] = set()
    all_imports: Set[str] = set()
    all_attribute_accesses: Set[str] = set()
    file_definitions: Dict[Path, Dict[str, List[int]]] = {}

    print("📊 Analyzing files...\n")
    for filepath in python_files:
        definitions, imports, usages, attributes = analyze_file(filepath)

        file_definitions[filepath] = definitions

        for name, lines in definitions.items():
            for line in lines:
                all_definitions[name].append((filepath, line))

        all_usages.update(usages)
        all_imports.update(imports)
        all_attribute_accesses.update(attributes)

    # Find potentially unused definitions
    print("=" * 80)
    print("🔎 POTENTIALLY UNUSED FUNCTIONS AND CLASSES")
    print("=" * 80)
    print()

    unused_by_file: Dict[Path, List[Tuple[str, int]]] = defaultdict(list)

    # Special patterns that indicate a function/class is used
    special_patterns = {
        "__init__",
        "__main__",
        "__str__",
        "__repr__",
        "__enter__",
        "__exit__",
        "__call__",
        "__getitem__",
        "__setitem__",
        "__len__",
        "__iter__",
        "__next__",
        "__contains__",
        "__eq__",
        "__hash__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__ne__",
        "__bool__",
        "__aenter__",
        "__aexit__",
        "setUp",
        "tearDown",
        "setUpClass",
        "tearDownClass",  # test methods
        "test_",  # test functions
        "main",  # entry points
    }

    for name, locations in all_definitions.items():
        # Skip special methods and private functions (might be used via reflection)
        if any(pattern in name for pattern in special_patterns):
            continue

        # Skip if name is used elsewhere
        if name in all_usages or name in all_imports or name in all_attribute_accesses:
            continue

        # If defined multiple times, might be overrides or used polymorphically
        if len(locations) > 1:
            continue

        for filepath, lineno in locations:
            unused_by_file[filepath].append((name, lineno))

    # Print results organized by file
    total_unused = 0
    for filepath in sorted(unused_by_file.keys()):
        unused_items = sorted(unused_by_file[filepath], key=lambda x: x[1])
        if unused_items:
            rel_path = filepath.relative_to(root_dir)
            print(f"📄 {rel_path}")
            for name, lineno in unused_items:
                print(f"   Line {lineno:4d}: {name}")
                total_unused += 1
            print()

    if total_unused == 0:
        print("✅ No obviously unused functions or classes found!\n")
    else:
        print(f"Found {total_unused} potentially unused definitions\n")

    # Find potentially unused files
    print("=" * 80)
    print("🔎 POTENTIALLY UNUSED FILES")
    print("=" * 80)
    print()

    unused_files = []
    for filepath in python_files:
        # Skip __init__.py files
        if filepath.name == "__init__.py":
            continue

        # Skip test files
        if "test" in filepath.name or "tests" in str(filepath):
            continue

        # Skip main entry points
        if filepath.name in ["main.py", "app.py", "manage.py", "setup.py"]:
            continue

        # Check if file is imported
        if not check_if_imported_as_module(filepath, root_dir, all_imports):
            # Check if any of its definitions are used
            definitions = file_definitions.get(filepath, {})
            if definitions:
                used = any(
                    name in all_usages or name in all_attribute_accesses
                    for name in definitions.keys()
                )
                if not used:
                    unused_files.append(filepath)
            else:
                # Empty or definition-less file
                unused_files.append(filepath)

    if unused_files:
        for filepath in sorted(unused_files):
            rel_path = filepath.relative_to(root_dir)
            print(f"📄 {rel_path}")
        print(f"\nFound {len(unused_files)} potentially unused files\n")
    else:
        print("✅ No obviously unused files found!\n")

    print("=" * 80)
    print("⚠️  NOTE: These are suggestions only!")
    print("   - Functions may be used via decorators, metaclasses, or dynamic imports")
    print("   - Entry points (main.py, CLI commands) may appear unused")
    print("   - Test fixtures and utilities may appear unused")
    print("   - Review each item carefully before removing")
    print("=" * 80)


if __name__ == "__main__":
    root_dir = Path(__file__).parent.parent
    analyze_codebase(root_dir)
