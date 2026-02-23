import pytest
from cover_agent.validator_utils.insert_utils import insert_test_code

# Case 1: Happy Path
# Insert both imports and test code into the correct locations
def test_insert_imports_and_code_success():
    original = """import os
def main():
    print("Hello")"""
    
    new_imports = "import sys"
    new_test = """def test_main():
    assert True"""
    
    # Scenario: Insert import at line 1 (after import os)
    # Insert test at line 3 (after the main function)
    # Note: When inserting imports, the test insertion line will be pushed down by 1 line
    result = insert_test_code(
        original_content=original,
        test_code_indented=new_test,
        additional_imports=new_imports,
        import_index=1, 
        test_index=3 
    )

    expected = """import os
import sys
def main():
    print("Hello")
def test_main():
    assert True"""
    
    assert result.strip() == expected.strip()

# Case 2: Automatic duplicate import filtering (Deduplication)
def test_skip_duplicate_imports():
    original = "import os\nimport sys"
    
    # 'import os' already exists, 'import json' does not
    new_imports = "import os\nimport json"
    new_test = "def test_x(): pass"
    
    result = insert_test_code(
        original_content=original,
        test_code_indented=new_test,
        additional_imports=new_imports,
        import_index=0,
        test_index=2
    )
    
    # Expectation: Only insert 'import json', do not re-insert 'import os'
    assert "import json" in result
    assert result.count("import os") == 1 # Should appear only once

# Case 3: Position recalculation (Index Shifting)
# This is the most critical logic to test
def test_index_shifting_logic():
    original = """line1
line2
line3"""
    
    # Insert 2 lines of imports at the beginning (index 0)
    new_imports = "import A\nimport B"
    new_test = "TEST_CODE"
    
    # Want to insert test after line2 (originally index 2)
    # But because 2 import lines are inserted above, the test must be at index 4 to be correct
    result = insert_test_code(
        original_content=original,
        test_code_indented=new_test,
        additional_imports=new_imports,
        import_index=0,
        test_index=2
    )
    
    lines = result.split("\n")
    # Expected structure:
    # 0: import A
    # 1: import B
    # 2: line1
    # 3: line2
    # 4: TEST_CODE  <-- Must be here
    # 5: line3
    
    assert lines[4] == "TEST_CODE"

# Case 4: No imports (Insert test only)
def test_insert_only_test_code():
    original = "line1"
    new_test = "test"
    
    result = insert_test_code(
        original_content=original,
        test_code_indented=new_test,
        additional_imports="", # Empty
        import_index=0,
        test_index=1
    )
    
    expected = "line1\ntest"
    assert result.strip() == expected.strip()

# Case 5: Empty or invalid input (Edge Cases)
def test_missing_test_code_returns_empty_or_original():
    # Returns ""
    result = insert_test_code("content", "", "import a", 0, 0)
    assert result == ""