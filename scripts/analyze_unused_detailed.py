#!/usr/bin/env python3
"""
More detailed analysis of potentially unused code with better context.
"""

import ast
from pathlib import Path
from typing import List, Tuple


def is_route_handler(node: ast.FunctionDef, decorators_in_file: List[str]) -> bool:
    """Check if a function is a route handler (FastAPI, Flask, etc.)."""
    route_decorators = {
        "get",
        "post",
        "put",
        "delete",
        "patch",
        "route",
        "api_route",
        "websocket",
    }

    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id in route_decorators:
            return True
        if isinstance(decorator, ast.Call) and isinstance(
            decorator.func, ast.Attribute
        ):
            if decorator.func.attr in route_decorators:
                return True
    return False


def is_test_method(name: str) -> bool:
    """Check if a function/method is a test."""
    return name.startswith("test_") or name in [
        "setUp",
        "tearDown",
        "setUpClass",
        "tearDownClass",
    ]


def is_special_method(name: str) -> bool:
    """Check if a method is a special/dunder method."""
    return name.startswith("__") and name.endswith("__")


def is_pydantic_validator(node: ast.FunctionDef) -> bool:
    """Check if function is a Pydantic validator."""
    validator_decorators = {
        "validator",
        "field_validator",
        "model_validator",
        "root_validator",
    }
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id in validator_decorators:
            return True
        if isinstance(decorator, ast.Call):
            if (
                isinstance(decorator.func, ast.Name)
                and decorator.func.id in validator_decorators
            ):
                return True
    return False


def is_property_or_cached(node: ast.FunctionDef) -> bool:
    """Check if function is a property or cached property."""
    property_decorators = {"property", "cached_property", "lru_cache", "cache"}
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id in property_decorators:
            return True
        if isinstance(decorator, ast.Call):
            if (
                isinstance(decorator.func, ast.Name)
                and decorator.func.id in property_decorators
            ):
                return True
    return False


def is_event_handler(node: ast.FunctionDef) -> bool:
    """Check if function is an event handler."""
    event_decorators = {"on_event", "event", "listener", "subscriber", "callback"}
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id in event_decorators:
            return True
        if isinstance(decorator, ast.Call):
            if (
                isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in event_decorators
            ):
                return True
    return False


class DetailedAnalyzer(ast.NodeVisitor):
    """More detailed analyzer with context about usage patterns."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.functions: List[
            Tuple[str, int, bool, str]
        ] = []  # name, line, is_public, reason
        self.classes: List[Tuple[str, int, List[str]]] = []  # name, line, methods
        self.current_class = None

    def visit_ClassDef(self, node):
        """Track classes and their methods."""
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)

        self.classes.append((node.name, node.lineno, methods))

        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node):
        """Track function definitions with context."""
        self._handle_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        """Track async function definitions with context."""
        self._handle_function(node)
        self.generic_visit(node)

    def _handle_function(self, node):
        """Common handler for function/async function definitions."""
        # Determine why this function might be "used"
        reason = None

        if is_special_method(node.name):
            reason = "special_method"
        elif is_test_method(node.name):
            reason = "test_method"
        elif is_route_handler(node, []):
            reason = "route_handler"
        elif is_pydantic_validator(node):
            reason = "validator"
        elif is_property_or_cached(node):
            reason = "property"
        elif is_event_handler(node):
            reason = "event_handler"
        elif node.name.startswith("_") and not node.name.startswith("__"):
            reason = "private"

        is_public = not node.name.startswith("_")

        self.functions.append((node.name, node.lineno, is_public, reason))


def analyze_with_context(root_dir: Path):
    """Analyze codebase with better context."""
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

    python_files = []
    for dirpath, dirnames, filenames in root_dir.walk():
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for filename in filenames:
            if filename.endswith(".py"):
                python_files.append(Path(dirpath) / filename)

    print("=" * 80)
    print("📋 DETAILED ANALYSIS OF POTENTIALLY UNUSED CODE")
    print("=" * 80)
    print()

    # Categorize findings
    truly_unused = []
    route_handlers_unused = []
    private_unused = []

    for filepath in python_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content, filename=str(filepath))
            analyzer = DetailedAnalyzer(str(filepath))
            analyzer.visit(tree)

            # Check for imports of functions from this file
            content.lower()

            for func_name, lineno, is_public, reason in analyzer.functions:
                # Skip if it has a known usage reason
                if reason:
                    continue

                # Basic check: is it imported/called in the same file?
                if content.count(func_name) > 1:
                    continue

                rel_path = filepath.relative_to(root_dir)

                if "router.py" in str(filepath) or "routes.py" in str(filepath):
                    route_handlers_unused.append((rel_path, lineno, func_name))
                elif not is_public:
                    private_unused.append((rel_path, lineno, func_name))
                else:
                    truly_unused.append((rel_path, lineno, func_name))

        except Exception:
            pass

    # Print categorized results
    if truly_unused:
        print("🔴 HIGH CONFIDENCE - Likely Unused Public Functions/Classes")
        print("-" * 80)
        for filepath, lineno, name in sorted(truly_unused):
            print(f"{filepath}:{lineno} - {name}")
        print()

    if route_handlers_unused:
        print(
            "⚠️  REVIEW REQUIRED - Unused Route Handlers (May be legitimate endpoints)"
        )
        print("-" * 80)
        for filepath, lineno, name in sorted(route_handlers_unused):
            print(f"{filepath}:{lineno} - {name}")
        print()

    if private_unused:
        print("🔵 LOW PRIORITY - Unused Private Functions (May be internal helpers)")
        print("-" * 80)
        for filepath, lineno, name in sorted(private_unused)[:20]:  # Limit output
            print(f"{filepath}:{lineno} - {name}")
        if len(private_unused) > 20:
            print(f"... and {len(private_unused) - 20} more")
        print()

    print("=" * 80)
    print("Summary:")
    print(f"  High confidence unused: {len(truly_unused)}")
    print(f"  Route handlers to review: {len(route_handlers_unused)}")
    print(f"  Private functions: {len(private_unused)}")
    print("=" * 80)


if __name__ == "__main__":
    root_dir = Path("/app")
    analyze_with_context(root_dir)
