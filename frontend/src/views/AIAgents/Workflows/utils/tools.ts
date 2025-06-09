export const generatePythonTemplate = () => {
  return `
# Generated Python function template
# Access parameters via the 'params' dictionary
# Store your result in the 'result' variable

# Import any additional libraries you need
# import json
# import requests
# import datetime

try:
    # Extract parameters with type validation
    # Parameter: parameter1
    parameter1 = params.get('parameter1', '')
    if not isinstance(parameter1, str):
        parameter1 = str(parameter1) if parameter1 is not None else ''

    # Your code logic here - example using the parameters:
    result = {
        'parameter1': parameter1,
    }

except Exception as e:
    # Handle any errors
    import traceback
    result = f"Error processing parameters: {str(e)}\n{traceback.format_exc()}"
  `;
};
