def prepare_test_code_with_indentation(needed_indent:int, test_code: str) -> str:
        """
        Prepare test code with proper indentation.
        
        Parameters:
            test_code (str): Original test code
            
        Returns:
            str: Test code with proper indentation
        """
        test_code_indented = test_code
        needed_indent = needed_indent
        
        if needed_indent:
            initial_indent = len(test_code) - len(test_code.lstrip())
            delta_indent = int(needed_indent) - initial_indent
            if delta_indent > 0:
                test_code_indented = "\n".join(
                    [delta_indent * " " + line for line in test_code.split("\n")]
                )
        
        return "\n" + test_code_indented.strip("\n") + "\n"