import pytest
import textwrap
from cover_agent.validator_utils.indentation_utils import prepare_test_code_with_indentation

def test_basic_indentation():
    """Test basic case: Unindented code needs to be indented by 4 spaces."""
    raw_code = "print('hello')"
    needed_indent = 4
    
    expected = "\n    print('hello')\n"
    
    assert prepare_test_code_with_indentation(needed_indent, raw_code) == expected

def test_multiline_indentation():
    """Test with multi-line code: All lines must be indented."""
    raw_code = textwrap.dedent("""\
    def test_example():
        assert True
    """)
    needed_indent = 4
    
    # Logic: Line 1 indents by 4, line 2 (already has 4) adds 4 -> becomes 8
    # Line 1: indent=0. Delta = 4 - 0 = 4.
    # Result: Add 4 spaces to the beginning of EVERY line.
    
    expected = "\n    def test_example():\n        assert True\n"
    
    assert prepare_test_code_with_indentation(needed_indent, raw_code) == expected

def test_already_indented_match():
    """Test when code is already indented to the needed level -> No further changes."""
    raw_code = "    print('hello')"
    needed_indent = 4
    
    # Initial indent = 4. Delta = 4 - 4 = 0.
    # Does not enter 'if', only wraps with \n
    expected = "\n    print('hello')\n"
    
    assert prepare_test_code_with_indentation(needed_indent, raw_code) == expected

def test_already_indented_more_than_needed():
    """
    Test case where code is indented deeper than required.
    Note: Current logic (delta > 0) will NOT decrease indentation (unindent/dedent).
    """
    raw_code = "        print('hello')" # Indented by 8
    needed_indent = 4
    
    # Initial = 8. Needed = 4. Delta = -4.
    # Delta < 0 so nothing is done.
    expected = "\n        print('hello')\n"
    
    assert prepare_test_code_with_indentation(needed_indent, raw_code) == expected

def test_increase_indentation():
    """Test case where code is slightly indented, needs further indentation."""
    raw_code = "  print('hello')" # Indented by 2
    needed_indent = 4
    
    # Initial = 2. Needed = 4. Delta = 2.
    # Add 2 spaces to the beginning.
    expected = "\n    print('hello')\n"
    
    assert prepare_test_code_with_indentation(needed_indent, raw_code) == expected

def test_zero_needed_indent():
    """Test when no indentation is required (needed = 0)."""
    raw_code = "print('hello')"
    needed_indent = 0
    
    expected = "\nprint('hello')\n"
    
    assert prepare_test_code_with_indentation(needed_indent, raw_code) == expected

def test_cleanup_newlines():
    """Test that the function automatically removes extra empty lines at start/end before wrapping."""
    raw_code = "\n\nprint('hello')\n\n"
    needed_indent = 4
    
    # The function uses .strip('\n'), so extra empty lines will be removed before wrapping with new \n
    expected = "\n    print('hello')\n"
    
    assert prepare_test_code_with_indentation(needed_indent, raw_code) == expected

def test_empty_string():
    """Test with an empty string."""
    raw_code = ""
    needed_indent = 4
    
    # Code splits into an empty list or list containing empty strings depending on implementation
    # But the final result is still \n + content + \n
    # With empty input, .strip('\n') results in empty.
    expected = "\n\n"
    
    assert prepare_test_code_with_indentation(needed_indent, raw_code) == expected