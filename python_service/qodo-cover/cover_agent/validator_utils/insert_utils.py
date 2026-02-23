def insert_test_code(
        original_content: str, 
        test_code_indented: str, 
        additional_imports: str, 
        import_index: int, 
        test_index: int
    ) -> str:
        """
        Insert test code and imports into original content.
        
        Parameters:
            original_content (str): Original file content
            test_code_indented (str): Test code with indentation
            additional_imports (str): Import statements to add
            
        Returns:
            str: Processed test file content
        """
        if not test_code_indented or test_index is None:
            return ""
            
        additional_imports_lines = []
        original_content_lines = original_content.split("\n")

        # Process imports
        if additional_imports:
            raw_import_lines = additional_imports.split("\n")
            for line in raw_import_lines:
                if line.strip() and all(
                    line.strip() != existing.strip() for existing in original_content_lines
                ):
                    additional_imports_lines.append(line)

        # Insert imports
        inserted_lines_count = 0
        if import_index is not None and additional_imports_lines:
            inserted_lines_count = len(additional_imports_lines)
            original_content_lines = (
                original_content_lines[:import_index]
                + additional_imports_lines
                + original_content_lines[import_index:]
            )

        # Adjust test insertion point
        updated_test_insertion_point = test_index
        if inserted_lines_count > 0:
            updated_test_insertion_point += inserted_lines_count

        # Insert test code
        test_code_lines = test_code_indented.split("\n")
        processed_test_lines = (
            original_content_lines[:updated_test_insertion_point]
            + test_code_lines
            + original_content_lines[updated_test_insertion_point:]
        )
        
        return "\n".join(processed_test_lines)