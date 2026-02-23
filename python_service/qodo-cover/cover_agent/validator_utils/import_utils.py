def clean_imports(imports_str: str) -> str:
        """
        Clean import string by removing quotes and empty strings.
        
        Parameters:
            imports_str (str): Raw imports string
            
        Returns:
            str: Cleaned imports string
        """
        if imports_str and imports_str[0] == '"' and imports_str[-1] == '"':
            imports_str = imports_str.strip('"')
        if imports_str == '""':
            imports_str = ""
        return imports_str