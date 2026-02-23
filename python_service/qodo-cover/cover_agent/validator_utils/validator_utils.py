import os

def validate_initialization_params(
        source_file_path: str,
        desired_coverage: int,
        max_run_time_sec: int,
        num_attempts: int,
        max_fix_attempts: int
    ) -> None:
        """
        Validate initialization parameters.
        
        Parameters:
            source_file_path (str): Path to source file
            desired_coverage (int): Desired coverage percentage
            max_run_time_sec (int): Maximum runtime in seconds
            num_attempts (int): Number of test generation attempts
            max_fix_attempts (int): Maximum fix attempts
            
        Raises:
            FileNotFoundError: If source file doesn't exist
            ValueError: If parameters are out of valid range
        """
        if not os.path.exists(source_file_path):
            raise FileNotFoundError(f"Source file not found: {source_file_path}")
        
        if not 0 <= desired_coverage <= 100:
            raise ValueError(f"desired_coverage must be between 0 and 100, got {desired_coverage}")
        
        if max_run_time_sec <= 0:
            raise ValueError(f"max_run_time_sec must be positive, got {max_run_time_sec}")
        
        if num_attempts <= 0:
            raise ValueError(f"num_attempts must be positive, got {num_attempts}")
            
        if max_fix_attempts < 0:
            raise ValueError(f"max_fix_attempts must be non-negative, got {max_fix_attempts}")    