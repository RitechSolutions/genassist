def replace_template_vars(template: str, values: dict) -> str:
    """
    Replace both @value and {{value}} patterns in a string with values from a dictionary.
    
    Args:
        template (str): The template string containing variables
        values (dict): Dictionary containing the values to replace
        
    Returns:
        str: The string with all variables replaced
    """
    if not template or not values:
        return template
        
    result = template
    for key, value in values.items():
        # Replace @value pattern
        result = result.replace(f"@{key}", str(value))
        # Replace {{value}} pattern
        result = result.replace(f"{{{{{key}}}}}", str(value))
    
    return result 