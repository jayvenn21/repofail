"""Light AST scan for Python imports — torch.cuda, GPU usage, etc."""

import ast
from pathlib import Path
from typing import Any


def _is_torch_cuda_import(node: ast.ImportFrom) -> bool:
    """Check if this is 'from torch import cuda' or 'from torch.cuda import ...'."""
    if node.module:
        return "torch.cuda" in node.module or (node.module == "torch" and any(alias.name == "cuda" for alias in node.names))
    return False


def _is_torch_import(node: ast.AST) -> bool:
    """Check if this imports torch."""
    if isinstance(node, ast.Import):
        return any(alias.name == "torch" or alias.name.startswith("torch.") for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return node.module and (node.module == "torch" or node.module.startswith("torch."))
    return False


def _has_cuda_attr_access(node: ast.AST) -> bool:
    """Check for torch.cuda.* usage (attribute access)."""
    if isinstance(node, ast.Attribute):
        return _get_full_attr_name(node) == "torch.cuda"
    return False


def _get_full_attr_name(node: ast.Attribute) -> str:
    """Get full dotted name of attribute chain."""
    parts = []
    n: ast.AST = node
    while isinstance(n, ast.Attribute):
        parts.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        parts.append(n.id)
    parts.reverse()
    return ".".join(parts)


def _has_device_cuda(node: ast.AST) -> bool:
    """Check for device='cuda' or device=\"cuda\" in keyword args."""
    if isinstance(node, ast.Call):
        for kw in node.keywords:
            if kw.arg in ("device", "device_map") and isinstance(kw.value, ast.Constant):
                val = kw.value.value
                if isinstance(val, str) and "cuda" in val.lower():
                    return True
    return False


def _get_device_cuda_kw(node: ast.Call) -> tuple[str | None, int]:
    """Return (kind, lineno) for device='cuda' in call, else (None, 0)."""
    for kw in node.keywords:
        if kw.arg in ("device", "device_map") and isinstance(kw.value, ast.Constant):
            val = kw.value.value
            if isinstance(val, str) and "cuda" in val.lower():
                return f"{kw.arg}=\"{val}\"", node.lineno
    return None, 0


def _has_to_cuda(node: ast.Call) -> tuple[bool, int]:
    """Check for .to(\"cuda\") or .to('cuda') — must be Attribute with attr 'to'."""
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "to":
        return False, 0
    if len(node.args) == 1 and isinstance(node.args[0], ast.Constant):
        val = node.args[0].value
        if isinstance(val, str) and val.lower() == "cuda":
            return True, node.lineno
    return False, 0


class ImportVisitor(ast.NodeVisitor):
    """Collects torch/tensorflow imports and CUDA usage with line numbers."""

    def __init__(self) -> None:
        self.uses_torch = False
        self.uses_tensorflow = False
        self.requires_cuda = False
        self.cuda_in_code = False
        self.cuda_usages: list[tuple[int, str]] = []  # (lineno, kind)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "torch" or alias.name.startswith("torch"):
                self.uses_torch = True
            if "torch.cuda" in alias.name:
                self.requires_cuda = True
                self.cuda_usages.append((node.lineno, "import torch.cuda"))
            if alias.name == "tensorflow" or alias.name.startswith("tensorflow"):
                self.uses_tensorflow = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            if node.module == "torch" or node.module.startswith("torch"):
                self.uses_torch = True
            if _is_torch_cuda_import(node):
                self.requires_cuda = True
                self.cuda_usages.append((node.lineno, "import torch.cuda"))
            if node.module == "tensorflow" or node.module.startswith("tensorflow"):
                self.uses_tensorflow = True
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        name = _get_full_attr_name(node)
        if "torch.cuda" in name or name == "torch.cuda":
            self.cuda_in_code = True
            self.requires_cuda = True
            self.cuda_usages.append((node.lineno, "torch.cuda"))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        kind, lineno = _get_device_cuda_kw(node)
        if kind:
            self.cuda_in_code = True
            self.requires_cuda = True
            self.cuda_usages.append((lineno, kind))
        ok, ln = _has_to_cuda(node)
        if ok:
            self.cuda_in_code = True
            self.requires_cuda = True
            self.cuda_usages.append((ln, ".to(\"cuda\")"))
        self.generic_visit(node)


def _has_cuda_conditional(tree: ast.AST) -> bool:
    """True if code checks torch.cuda.is_available() before using CUDA."""
    found = [False]

    class CudaConditionalVisitor(ast.NodeVisitor):
        def visit_If(self, node: ast.If) -> None:
            # Check if condition is torch.cuda.is_available() or similar
            if isinstance(node.test, ast.Call):
                if isinstance(node.test.func, ast.Attribute):
                    name = _get_full_attr_name(node.test.func)
                    if "cuda" in name.lower() and "is_available" in name:
                        found[0] = True
            self.generic_visit(node)

    CudaConditionalVisitor().visit(tree)
    return found[0]


def scan_python_file(path: Path, repo_path: Path) -> dict[str, Any]:
    """Scan a single Python file for imports and CUDA usage."""
    result: dict[str, Any] = {
        "uses_torch": False,
        "uses_tensorflow": False,
        "requires_cuda": False,
        "cuda_optional": False,
        "cuda_files": [],
        "cuda_usages": [],
    }
    try:
        tree = ast.parse(path.read_text(errors="replace"))
    except SyntaxError:
        return result

    visitor = ImportVisitor()
    visitor.visit(tree)
    result["uses_torch"] = visitor.uses_torch
    result["uses_tensorflow"] = visitor.uses_tensorflow
    result["requires_cuda"] = visitor.requires_cuda
    result["cuda_optional"] = _has_cuda_conditional(tree)
    if visitor.requires_cuda:
        try:
            rel = str(path.relative_to(repo_path))
        except ValueError:
            rel = path.name
        result["cuda_files"] = [rel]
        for ln, kind in visitor.cuda_usages[:10]:  # cap for brevity
            result["cuda_usages"].append({"file": rel, "line": ln, "kind": kind})
    return result


def scan_python_tree(repo_path: Path, max_files: int = 100) -> dict[str, Any]:
    """Scan Python files in repo, aggregating results."""
    result: dict[str, Any] = {
        "uses_torch": False,
        "uses_tensorflow": False,
        "requires_cuda": False,
        "cuda_optional": False,
        "cuda_files": [],
        "cuda_usages": [],
    }
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "build", "dist", "eggs", "tests"}
    count = 0
    for py in repo_path.rglob("*.py"):
        if count >= max_files:
            break
        if any(part in py.parts for part in skip_dirs):
            continue
        try:
            file_result = scan_python_file(py, repo_path)
            result["uses_torch"] = result["uses_torch"] or file_result["uses_torch"]
            result["uses_tensorflow"] = result["uses_tensorflow"] or file_result["uses_tensorflow"]
            result["requires_cuda"] = result["requires_cuda"] or file_result["requires_cuda"]
            result["cuda_optional"] = result["cuda_optional"] or file_result.get("cuda_optional", False)
            result["cuda_files"].extend(file_result.get("cuda_files", []))
            result["cuda_usages"].extend(file_result.get("cuda_usages", []))
            count += 1
        except Exception:
            pass
    return result
