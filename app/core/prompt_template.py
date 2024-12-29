from typing import Dict, Any
import re


class CustomPromptTemplate:
    """Custom prompt template that uses single braces for variables"""

    def __init__(self, template: str):
        self.template = template
        # Find all variables in {variable} format
        self.variables = re.findall(r'\{([^}]+)\}', template)

    def format(self, **kwargs) -> str:
        """Format the template with the given variables"""
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            missing_var = str(e).strip("'")
            raise ValueError(f"Missing required variable: {missing_var}")
        except Exception as e:
            raise ValueError(f"Error formatting prompt: {str(e)}")
