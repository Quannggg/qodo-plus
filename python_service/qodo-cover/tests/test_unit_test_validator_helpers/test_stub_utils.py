import pytest
import textwrap
from cover_agent.validator_utils.stub_utils import is_trivial_stub

def test_basic_pass_stub():
    """Test case containing only a pass statement."""
    code = textwrap.dedent("""
        def test_example():
            pass
    """)
    assert is_trivial_stub(code) is True

def test_pass_with_comments():
    """Test case with pass accompanied by comments (still considered a stub)."""
    code = textwrap.dedent("""
        def test_todo():
            # TODO: Implement later
            # This is just a placeholder
            pass
    """)
    assert is_trivial_stub(code) is True

def test_pass_with_print():
    """Test case with a print statement and a pass (Still considered a stub as it has <= 2 lines of logic)."""
    code = textwrap.dedent("""
        def test_log():
            print("Running test")
            pass
    """)
    assert is_trivial_stub(code) is True

def test_empty_function_body():
    """Test a completely empty function (no logic code)."""
    code = textwrap.dedent("""
        def test_empty():
            
    """)
    assert is_trivial_stub(code) is True

def test_real_assertion():
    """Test code containing actual testing logic."""
    code = textwrap.dedent("""
        def test_math():
            x = 1 + 1
            assert x == 2
    """)
    assert is_trivial_stub(code) is False

def test_only_assertion():
    """Test code with only 1 line, but it is an assertion."""
    code = textwrap.dedent("""
        def test_simple():
            assert True
    """)
    assert is_trivial_stub(code) is False

def test_variable_named_password():
    """
    Test variable containing the word 'pass' (e.g., 'password').
    """
    code = textwrap.dedent("""
        def test_login():
            password = "123" 
            assert login(password)
    """)
    assert is_trivial_stub(code) is False

def test_variable_passed():
    """Test variable named 'passed'."""
    code = textwrap.dedent("""
        def test_status():
            is_passed = True
            assert is_passed
    """)
    assert is_trivial_stub(code) is False

def test_empty_string_input():
    """Test input is an empty string."""
    assert is_trivial_stub("") is True

def test_input_with_only_comments():
    """Test input containing only comments."""
    code = """
    # Just a comment
    # Another comment
    """
    assert is_trivial_stub(code) is True

def test_input_without_def():
    """Test code snippet without 'def' (only body)."""
    code = "pass"
    assert is_trivial_stub(code) is True

def test_input_without_def_real_code():
    """Test code snippet without 'def' but is real code."""
    code = "x = 1\nassert x"
    assert is_trivial_stub(code) is False