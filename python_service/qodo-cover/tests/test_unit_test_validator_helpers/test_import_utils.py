import pytest
from cover_agent.validator_utils.import_utils import clean_imports

@pytest.mark.parametrize("input_str, expected_output", [
    # Case 1: A normal string, without quotation marks surrounding it.
    ("import os", "import os"),
    ("import os\nimport sys", "import os\nimport sys"),

    # Case 2: The string is surrounded by double quotes.
    ('"import os"', "import os"),
    ('"import os\nimport sys"', "import os\nimport sys"),

    # Case 3: Extra space inside quotation marks
    ('"  import os  "', "  import os  "), 
  
    # Case 4: Empty string
    ("", ""),

    # Case 5: Special string '""'
    ('""', ""), 
    
    # Case 6: Multiple overlapping double quotes (Edge case)
    # The .strip('"') method will remove all leading and trailing double quotes
    ('""import os""', "import os"), 
    
    # Case 7: String with a double quote at only one end (Does not satisfy the first if condition)
    ('"import os', '"import os'),
    ('import os"', 'import os"'),
])
def test_clean_imports(input_str, expected_output):
    """
    Test the clean_imports function with various input scenarios.
    """
    assert clean_imports(input_str) == expected_output

def test_clean_imports_none():
    """
    Test the case where input is None (if necessary).
    Based on the code: 'if imports_str' will evaluate to False, returning None.
    """
    assert clean_imports(None) is None