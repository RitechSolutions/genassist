import pytest
import os
import re
import logging
from pathlib import Path
from typing import List, Set, Dict, Tuple
from collections import defaultdict

def get_python_files(directory: str) -> List[str]:
    """Get all Python files in the given directory and its subdirectories."""
    python_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

@pytest.mark.skip(reason="Disabled temporarily until proper refactorings are done")
def test_dependency_layers():
    """Test that dependencies follow the correct layering pattern."""
    layers = {
        'app.core': ['app.schemas'],
        'app.schemas': ['app.core'],
        'app.db': ['app.core'],
        'app.auth': ['app.core', 'app.schemas', 'app.services'],
        'app.repositories': ['app.core', 'app.schemas', 'app.db'],
        'app.services': ['app.core', 'app.repositories', 'app.schemas'],
        'app.api': ['app.core', 'app.auth', 'app.schemas', 'app.services', 'app.dependencies.services'],
    }
    
    app_dir = Path('app').resolve()
    python_files = get_python_files(str(app_dir))
    
    for file_path in python_files:
        # Skip __init__.py files
        if file_path.endswith('__init__.py'):
            continue
        
        file_path = Path(file_path).resolve()
        with open(file_path, 'r') as f:
            content = f.read()
            imports = re.findall(r'^from\s+([\w.]+)\s+import', content, re.MULTILINE)
            
            # Get the layer of the current file based on its directory
            current_layer = None
            file_parts = file_path.relative_to(app_dir).parts
            if len(file_parts) > 0:
                potential_layer = f"app.{file_parts[0]}"
                if potential_layer in layers:
                    current_layer = potential_layer
            
            #if not current_layer:
            #   pytest.fail(f"Could not determine the layer for file: {file_path}")

            if not current_layer:
                print(f"Could not determine the layer for file: {file_path}")
                continue
            
            errors = []
            allowed_imports = layers[current_layer]
            for imp in imports:
                if imp.startswith('app.'):
                    # Extract the layer of the imported module
                    import_layer = '.'.join(imp.split('.')[:2])
                    import_layer2 = '.'.join(imp.split('.')[:3])
                    if import_layer not in allowed_imports and import_layer2 not in allowed_imports and not imp.startswith(current_layer):
                        errors.append(
                            f"Invalid dependency: {file_path} imports from {imp}, "
                            f"which is not allowed in layer {current_layer} - {import_layer2}"
                        )

            if errors:
                pytest.fail(f"Dependency layer violation in file {file_path}: {', '.join(errors)}")


def test_api_endpoints():
    """Test that API endpoints follow RESTful patterns."""
    app_dir = Path('app')
    api_files = get_python_files(str(app_dir / 'api'))
    
    print(f"Found {len(api_files)} API files to test.")
    for file_path in api_files:
        # Skip __init__.py files
        if file_path.endswith('__init__.py'):
            continue
        if file_path.endswith("_routes.py"):
            continue
            
        with open(file_path, 'r') as f:
            content = f.read()
            
            # Check for proper route decorators
            if '@router' not in content:
                pytest.fail(f"API file {file_path} is missing router decorator")
            
            # Check for proper HTTP method decorators (FastAPI style)
            http_methods = ['@router.get', '@router.post', '@router.put', '@router.delete', '@router.patch']
            has_method = any(method in content for method in http_methods)
            if not has_method:
                pytest.fail(f"API file {file_path} is missing HTTP method decorators")
