import pytest
from unittest.mock import patch
from cover_agent.validator_utils.validator_utils import validate_initialization_params

# ==========================================
# 1. Test success case (Happy Path)
# ==========================================

@patch("os.path.exists")
def test_validate_params_success(mock_exists):
    """
    Test case where all parameters are valid.
    """
    # Simulate that the file always exists
    mock_exists.return_value = True

    # Call function with standard parameters
    # No exception raised means the test passed
    validate_initialization_params(
        source_file_path="valid_file.py",
        desired_coverage=80,      # 0 <= 80 <= 100
        max_run_time_sec=10,      # > 0
        num_attempts=3,           # > 0
        max_fix_attempts=0        # >= 0 (0 is valid)
    )

# ==========================================
# 2. Test file not found error
# ==========================================

@patch("os.path.exists")
def test_source_file_not_found(mock_exists):
    """
    Test case where the file does not exist -> Must raise FileNotFoundError.
    """
    # Simulate that the file does NOT exist
    mock_exists.return_value = False

    with pytest.raises(FileNotFoundError) as exc_info:
        validate_initialization_params(
            source_file_path="ghost_file.py",
            desired_coverage=80,
            max_run_time_sec=10,
            num_attempts=3,
            max_fix_attempts=2
        )
    
    assert "Source file not found" in str(exc_info.value)

# ==========================================
# 3. Test value errors (Validation Logic)
# ==========================================

# Use parametrize to test multiple invalid cases without writing many functions
@pytest.mark.parametrize("coverage, runtime, attempts, fix_attempts, error_msg_fragment", [
    # Case: Coverage < 0
    (-1, 10, 1, 1, "desired_coverage must be between"),
    # Case: Coverage > 100
    (101, 10, 1, 1, "desired_coverage must be between"),
    # Case: Runtime = 0 (Error because it must be > 0)
    (50, 0, 1, 1, "max_run_time_sec must be positive"),
    # Case: Runtime < 0
    (50, -5, 1, 1, "max_run_time_sec must be positive"),
    # Case: Num attempts = 0
    (50, 10, 0, 1, "num_attempts must be positive"),
    # Case: Fix attempts < 0
    (50, 10, 1, -1, "max_fix_attempts must be non-negative"),
])
@patch("os.path.exists")
def test_validate_params_value_errors(mock_exists, coverage, runtime, attempts, fix_attempts, error_msg_fragment):
    """
    Comprehensive test for out-of-range parameter cases.
    """
    # Always simulate that the file exists to pass the first check
    mock_exists.return_value = True

    with pytest.raises(ValueError) as exc_info:
        validate_initialization_params(
            source_file_path="dummy.py",
            desired_coverage=coverage,
            max_run_time_sec=runtime,
            num_attempts=attempts,
            max_fix_attempts=fix_attempts
        )
    
    # Check if the error message matches each case correctly
    assert error_msg_fragment in str(exc_info.value)

# ==========================================
# 4. Test boundary values
# ==========================================

@patch("os.path.exists")
def test_boundary_values(mock_exists):
    """
    Test values right at the limit edges (still valid).
    """
    mock_exists.return_value = True
    
    # Coverage = 0 (Lower bound)
    validate_initialization_params("f.py", 0, 1, 1, 0)
    
    # Coverage = 100 (Upper bound)
    validate_initialization_params("f.py", 100, 1, 1, 0)
    
    # Fix attempts = 0 (Lower bound, 0 is allowed)
    validate_initialization_params("f.py", 50, 1, 1, 0)