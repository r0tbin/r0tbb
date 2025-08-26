"""
Template rendering and variable substitution for the bug bounty tool.
Handles YAML task templating with environment variables and path resolution.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Template, Environment, BaseLoader

from .config import config


class StringTemplateLoader(BaseLoader):
    """Simple string template loader for Jinja2."""
    
    def __init__(self, template_string: str):
        self.template_string = template_string
    
    def get_source(self, environment, template):
        return self.template_string, None, lambda: True


class TemplateRenderer:
    """Template renderer with variable substitution."""
    
    def __init__(self):
        self.env = Environment(loader=BaseLoader())
    
    def render(self, text: str, variables: Dict[str, Any]) -> str:
        """Render text with variable substitution."""
        if not text:
            return text
        
        # First pass: simple {VAR} substitution
        result = text
        for key, value in variables.items():
            pattern = f"{{{key}}}"
            result = result.replace(pattern, str(value))
        
        # Second pass: Jinja2 template rendering for advanced features
        try:
            template = self.env.from_string(result)
            result = template.render(**variables)
        except Exception:
            # If Jinja2 fails, return the simple substitution result
            pass
        
        return result
    
    def render_dict(self, data: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively render all string values in a dictionary."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.render(value, variables)
            elif isinstance(value, dict):
                result[key] = self.render_dict(value, variables)
            elif isinstance(value, list):
                result[key] = self.render_list(value, variables)
            else:
                result[key] = value
        return result
    
    def render_list(self, data: list, variables: Dict[str, Any]) -> list:
        """Recursively render all string values in a list."""
        result = []
        for item in data:
            if isinstance(item, str):
                result.append(self.render(item, variables))
            elif isinstance(item, dict):
                result.append(self.render_dict(item, variables))
            elif isinstance(item, list):
                result.append(self.render_list(item, variables))
            else:
                result.append(item)
        return result


def materialize_env(target: str, custom_vars: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Create environment variables dictionary for template rendering.
    
    Args:
        target: Target name (e.g., "example.com")
        custom_vars: Additional variables from tasks.yaml
    
    Returns:
        Dictionary with all template variables
    """
    target_dir = config.target_dir(target)
    
    # Base template variables
    variables = {
        "TARGET": target,
        "ROOT": str(config.ROOT_DIR),
        "OUT": str(target_dir),
        "LOGS": str(config.logs_dir(target)),
        "OUTPUTS": str(config.outputs_dir(target)),
        "REPORTS": str(config.reports_dir(target)),
        "TMP": str(config.tmp_dir(target)),
    }
    
    # Add environment variables
    variables.update(os.environ)
    
    # Add custom variables from tasks.yaml
    if custom_vars:
        variables.update(custom_vars)
    
    # Resolve any nested template variables
    resolver = TemplateRenderer()
    max_iterations = 5  # Prevent infinite loops
    
    for _ in range(max_iterations):
        old_variables = variables.copy()
        variables = resolver.render_dict(variables, variables)
        
        # Check for convergence
        if variables == old_variables:
            break
    
    return variables


def render_task_command(cmd: str, variables: Dict[str, str]) -> str:
    """
    Render a task command with variable substitution.
    
    Args:
        cmd: Command template string
        variables: Variable dictionary
    
    Returns:
        Rendered command string
    """
    renderer = TemplateRenderer()
    return renderer.render(cmd, variables)


def validate_template_vars(text: str, available_vars: Dict[str, str]) -> list:
    """
    Validate that all template variables in text are available.
    
    Args:
        text: Text to validate
        available_vars: Available variables
    
    Returns:
        List of missing variable names
    """
    if not text:
        return []
    
    # Find all {VAR} patterns
    pattern = r'\{([A-Za-z_][A-Za-z0-9_]*)\}'
    required_vars = set(re.findall(pattern, text))
    available_vars_set = set(available_vars.keys())
    
    missing_vars = required_vars - available_vars_set
    return list(missing_vars)


def escape_shell_arg(arg: str) -> str:
    """
    Escape shell argument for safe execution.
    
    Args:
        arg: Argument to escape
    
    Returns:
        Escaped argument
    """
    # For Windows, we need to escape quotes and backslashes
    if os.name == 'nt':
        # Escape quotes
        arg = arg.replace('"', '\\"')
        # Wrap in quotes if contains spaces
        if ' ' in arg:
            arg = f'"{arg}"'
    else:
        # For Unix-like systems
        import shlex
        arg = shlex.quote(arg)
    
    return arg


# Global renderer instance
renderer = TemplateRenderer()