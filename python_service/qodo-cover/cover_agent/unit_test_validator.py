import datetime
import json
import logging
import os

from typing import Optional, Dict, List, Tuple, Any

from diff_cover.diff_cover_tool import main as diff_cover_main
from wandb.sdk.data_types.trace_tree import Trace

from cover_agent.agent_completion_abc import AgentCompletionABC
from cover_agent.coverage_processor import CoverageProcessor
from cover_agent.custom_logger import CustomLogger
from cover_agent.file_preprocessor import FilePreprocessor
from cover_agent.runner import Runner
from cover_agent.settings.config_loader import get_settings
from cover_agent.settings.config_schema import CoverageType
from cover_agent.utils import load_yaml

from cover_agent.validator_utils.import_utils import clean_imports
from cover_agent.validator_utils.indentation_utils import prepare_test_code_with_indentation
from cover_agent.validator_utils.insert_utils import insert_test_code
from cover_agent.validator_utils.stub_utils import is_trivial_stub
from cover_agent.validator_utils.validator_utils import validate_initialization_params
class UnitTestValidator:
    """
    Validates and generates unit tests with coverage tracking.
    
    This class manages the lifecycle of test generation, validation, and coverage
    measurement for a given source file and its corresponding test file.
    """
    
    DEFAULT_DESIRED_COVERAGE = 90
    DEFAULT_MAX_FIX_ATTEMPTS = 1
    COVERAGE_PRECISION = 2  # decimal places for coverage percentages
    DEFAULT_TEST_HEADERS_INDENTATION_ATTEMPTS = 3
    
    def __init__(
        self,
        source_file_path: str,
        test_file_path: str,
        code_coverage_report_path: str,
        test_command: str,
        llm_model: str,
        max_run_time_sec: int,
        agent_completion: AgentCompletionABC,
        desired_coverage: int,
        comparison_branch: str,
        coverage_type: CoverageType,
        diff_coverage: bool,
        num_attempts: int,
        test_command_dir: str,
        additional_instructions: str,
        included_files: list,
        use_report_coverage_feature_flag: bool,
        project_root: str = "",
        logger: Optional[CustomLogger] = None,
        generate_log_files: bool = True,
        max_fix_attempts: int = DEFAULT_MAX_FIX_ATTEMPTS,
    ):
        """
        Initialize the UnitTestValidator class with the provided parameters.

        Parameters:
            source_file_path (str): The path to the source file being tested.
            test_file_path (str): The path to the test file where generated tests will be written.
            code_coverage_report_path (str): The path to the code coverage report file.
            test_command (str): The command to run tests.
            llm_model (str): The language model to be used for test generation.
            max_run_time_sec (int): The maximum time in seconds to run the test command.
            agent_completion (AgentCompletionABC): The agent completion object to use for test generation.
            desired_coverage (int): The desired coverage percentage.
            comparison_branch (str): Branch to compare against for diff coverage.
            coverage_type (CoverageType): The type of coverage report.
            diff_coverage (bool): Whether to use diff coverage mode.
            num_attempts (int): Number of attempts for test generation.
            test_command_dir (str): The directory where the test command should be executed.
            additional_instructions (str): Additional instructions for test generation.
            included_files (list): A list of paths to included files.
            use_report_coverage_feature_flag (bool): Consider coverage of all files in the coverage report.
            project_root (str, optional): Root directory of the project. Defaults to "".
            logger (CustomLogger, optional): The logger object for logging messages.
            generate_log_files (bool): Whether or not to generate logs. Defaults to True.
            max_fix_attempts (int): Maximum number of attempts to fix failing tests. Defaults to 1.

        Raises:
            FileNotFoundError: If source_file_path does not exist.
            ValueError: If parameters are out of valid range.
        """
        # Validate inputs first
        validate_initialization_params(
            source_file_path = source_file_path,
            desired_coverage = desired_coverage,
            max_run_time_sec = max_run_time_sec, 
            num_attempts = num_attempts, 
            max_fix_attempts = max_fix_attempts
        )
        
        # Initialize core attributes
        self.project_root = project_root
        self.source_file_path = source_file_path
        self.test_file_path = test_file_path
        self.code_coverage_report_path = code_coverage_report_path
        self.test_command = test_command
        self.test_command_dir = test_command_dir
        self.included_files = self.get_included_files(included_files)
        self.coverage_type = coverage_type
        self.desired_coverage = desired_coverage
        self.additional_instructions = additional_instructions
        self.language = self.get_code_language(source_file_path)
        self.use_report_coverage_feature_flag = use_report_coverage_feature_flag
        self.last_coverage_percentages: Dict[str, float] = {}
        self.llm_model = llm_model
        self.diff_coverage = diff_coverage
        self.comparison_branch = comparison_branch
        self.num_attempts = num_attempts
        self.agent_completion = agent_completion
        self.max_run_time_sec = max_run_time_sec
        self.generate_log_files = generate_log_files
        self.max_fix_attempts = max_fix_attempts

        # Get the logger instance
        self.logger = logger or CustomLogger.get_logger(__name__, generate_log_files=self.generate_log_files)

        # Configure diff coverage if enabled
        self._configure_diff_coverage()

        # Initialize state attributes
        self.relevant_line_number_to_insert_imports_after = None
        self.relevant_line_number_to_insert_tests_after = None
        self.test_headers_indentation = None
        self.preprocessor = FilePreprocessor(self.test_file_path)
        self.failed_test_runs: List[Dict[str, Any]] = []
        self.total_input_token_count = 0
        self.total_output_token_count = 0
        self.testing_framework = "Unknown"
        self.code_coverage_report = ""

        # Read source file
        with open(self.source_file_path, "r") as f:
            self.source_code = f.read()

        # Initialize coverage processor
        self.coverage_processor = CoverageProcessor(
            file_path=self.code_coverage_report_path,
            src_file_path=self.source_file_path,
            coverage_type=self.coverage_type,
            use_report_coverage_feature_flag=self.use_report_coverage_feature_flag,
            diff_coverage_report_path=getattr(self, 'diff_cover_report_path', ''),
            generate_log_files=self.generate_log_files,
        )


    def _configure_diff_coverage(self) -> None:
        """Configure diff coverage settings if enabled."""
        if self.diff_coverage:
            self.coverage_type = "diff_cover_json"
            self.diff_coverage_report_name = "diff-cover-report.json"
            self.diff_cover_report_path = os.path.join(
                self.test_command_dir, self.diff_coverage_report_name
            )
            self.logger.info(f"Diff coverage enabled. Using coverage report: {self.diff_cover_report_path}")
        else:
            self.diff_cover_report_path = ""

    def get_coverage(self) -> Tuple[List[Dict], str, str, str]:
        """
        Run code coverage and build the prompt to be used for generating tests.

        Returns:
            Tuple containing:
                - failed_test_runs (list): List of failed test run details
                - language (str): Programming language of the source file
                - testing_framework (str): Detected testing framework
                - code_coverage_report (str): Coverage report string
        """
        self.run_coverage()
        return (
            self.failed_test_runs,
            self.language,
            self.testing_framework,
            self.code_coverage_report,
        )

    def get_code_language(self, source_file_path: str) -> str:
        """
        Get the programming language based on the file extension of the provided source file path.

        Parameters:
            source_file_path (str): The path to the source file for which the programming language needs to be determined.

        Returns:
            str: The programming language inferred from the file extension of the provided source file path. Defaults to 'unknown' if the language cannot be determined.
        """
        # Retrieve the mapping of languages to their file extensions from settings
        language_extension_map_org = get_settings().language_extension_map_org

        # Initialize a dictionary to map file extensions to their corresponding languages
        extension_to_language = {}

        # Populate the extension_to_language dictionary
        for language, extensions in language_extension_map_org.items():
            for ext in extensions:
                extension_to_language[ext] = language

        # Extract the file extension from the source file path
        extension_s = "." + source_file_path.rsplit(".")[-1]

        # Initialize the default language name as 'unknown'
        language_name = "unknown"

        # Check if the extracted file extension is in the dictionary
        if extension_s and (extension_s in extension_to_language):
            # Set the language name based on the file extension
            language_name = extension_to_language[extension_s]

        # Return the language name in lowercase
        return language_name.lower()

    def initial_test_suite_analysis(self) -> None:
        """
        Perform the initial analysis of the test suite structure.
        
        This method analyzes test headers indentation, line numbers for inserting
        tests and imports, and detects the testing framework.
        
        Raises:
            Exception: If analysis fails after all attempts.
        """
        try:
            settings = get_settings().get("default")
            test_headers_indentation = None
            allowed_attempts = settings.get(
                "test_headers_indentation_attempts", 
                self.DEFAULT_TEST_HEADERS_INDENTATION_ATTEMPTS
            )
            counter_attempts = 0
            
            # Analyze test headers indentation
            while test_headers_indentation is None and counter_attempts < allowed_attempts:
                test_file_content = self._read_file(self.test_file_path)
                response, prompt_token_count, response_token_count, prompt = (
                    self.agent_completion.analyze_suite_test_headers_indentation(
                        language=self.language,
                        test_file_name=self._get_relative_path(self.test_file_path),
                        test_file=test_file_content,
                    )
                )

                self._update_token_counts(prompt_token_count, response_token_count)
                tests_dict = load_yaml(response)
                test_headers_indentation = tests_dict.get("test_headers_indentation", None)
                counter_attempts += 1

            if test_headers_indentation is None:
                raise Exception(
                    f"Failed to analyze test headers indentation. YAML response: {response}. tests_dict: {tests_dict}"
                )

            # Analyze insertion points
            relevant_line_number_to_insert_tests_after = None
            relevant_line_number_to_insert_imports_after = None
            counter_attempts = 0
            
            while not relevant_line_number_to_insert_tests_after and counter_attempts < allowed_attempts:
                test_file_numbered = self._create_numbered_file_content(self.test_file_path)
                response, prompt_token_count, response_token_count, prompt = (
                    self.agent_completion.analyze_test_insert_line(
                        language=self.language,
                        test_file_numbered=test_file_numbered,
                        additional_instructions_text=self.additional_instructions,
                        test_file_name=self._get_relative_path(self.test_file_path),
                    )
                )

                self._update_token_counts(prompt_token_count, response_token_count)
                tests_dict = load_yaml(response)
                relevant_line_number_to_insert_tests_after = tests_dict.get(
                    "relevant_line_number_to_insert_tests_after", None
                )
                relevant_line_number_to_insert_imports_after = tests_dict.get(
                    "relevant_line_number_to_insert_imports_after", None
                )
                self.testing_framework = tests_dict.get("testing_framework", "Unknown")
                counter_attempts += 1

            if not relevant_line_number_to_insert_tests_after:
                raise Exception(
                    f"Failed to analyze the relevant line number to insert new tests. tests_dict: {tests_dict}"
                )
            if not relevant_line_number_to_insert_imports_after:
                raise Exception(
                    f"Failed to analyze the relevant line number to insert new imports. tests_dict: {tests_dict}"
                )

            self.test_headers_indentation = test_headers_indentation
            self.relevant_line_number_to_insert_tests_after = relevant_line_number_to_insert_tests_after
            self.relevant_line_number_to_insert_imports_after = relevant_line_number_to_insert_imports_after
            
        except Exception as e:
            self.logger.error(f"Error during initial test suite analysis: {e}")
            raise Exception("Error during initial test suite analysis")

    def _create_numbered_file_content(self, file_path: str) -> str:
        """
        Create a numbered version of file content for analysis.
        
        Parameters:
            file_path (str): Path to the file
            
        Returns:
            str: File content with line numbers
        """
        content = self._read_file(file_path)
        lines = content.split("\n")
        return "\n".join(f"{i + 1} {line}" for i, line in enumerate(lines))

    def run_coverage(self) -> None:
        """
        Perform an initial build/test command to generate coverage report and get a baseline.
        
        Raises:
            AssertionError: If test command fails.
        """
        self.logger.info(f'Running build/test command to generate coverage report: "{self.test_command}"')
        stdout, stderr, exit_code, time_of_test_command = Runner.run_command(
            command=self.test_command,
            max_run_time_sec=self.max_run_time_sec,
            cwd=self.test_command_dir,
        )
        
        assert exit_code == 0, (
            f'Fatal: Error running test command. Are you sure the command is correct? "{self.test_command}"\n'
            f'Exit code {exit_code}. \nStdout: \n{stdout} \nStderr: \n{stderr}'
        )

        try:
            coverage, coverage_percentages = self.post_process_coverage_report(time_of_test_command)
            self.current_coverage = coverage
            self.last_coverage_percentages = coverage_percentages.copy()
            self.logger.info(f"Initial coverage: {self.format_coverage_percentage(self.current_coverage)}%")

        except AssertionError as error:
            # Handle the case where the coverage report does not exist or was not updated after the test command
            self.logger.error(f"Error in coverage processing: {error}")
            # Optionally, re-raise the error or handle it as deemed appropriate for your application
            raise
        except (ValueError, NotImplementedError) as e:
            # Handle errors related to unsupported coverage report types or issues in parsing
            self.logger.warning(f"Error parsing coverage report: {e}")
            self.logger.info(
                "Will default to using the full coverage report. You will need to check coverage manually for each passing test."
            )
            with open(self.code_coverage_report_path, "r") as f:
                self.code_coverage_report = f.read()

    @staticmethod
    def get_included_files(included_files):
        """
        A method to read and concatenate the contents of included files into a single string.

        Parameters:
            included_files (list): A list of paths to included files.

        Returns:
            str: A string containing the concatenated contents of the included files, or an empty string if the input list is empty.
        """
        if included_files:
            included_files_content = []
            file_names = []
            for file_path in included_files:
                try:
                    with open(file_path, "r") as file:
                        included_files_content.append(file.read())
                        file_names.append(file_path)
                except IOError as e:
                    print(f"Error reading file {file_path}: {str(e)}")
            out_str = ""
            if included_files_content:
                for i, content in enumerate(included_files_content):
                    out_str += f"file_path: `{file_names[i]}`\ncontent:\n```\n{content}\n```\n"

            return out_str.strip()
        return ""

    def validate_test(self, generated_test: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a generated test by inserting it into the test file, running the test,
        and checking for pass/fail. If the test fails, it attempts to 'fix' the test
        via AI up to max_fix_attempts.
        
        Parameters:
            generated_test (dict): Dictionary containing test_code, new_imports_code,
                                  test_behavior, and lines_to_cover
                                  
        Returns:
            dict: Result dictionary with status (PASS/FAIL), exit_code, stdout, stderr,
                  test code, and other metadata
        """
        # Store original content
        with open(self.test_file_path, "r") as test_file:
            original_content = test_file.read()

        current_test_code = generated_test.get("test_code", "").rstrip()
        additional_imports = clean_imports(generated_test.get("new_imports_code", "").strip())
        
        # Track fix history to avoid repeating same fixes
        previous_test_codes = [current_test_code]
        
        # Initialize result variables
        final_exit_code = -1
        final_stderr = ""
        final_stdout = ""
        processed_test = ""
        
        # Loop for attempts: original + fix attempts
        attempts_range = range(self.max_fix_attempts + 1)
        coverage_increased = False

        for attempt in attempts_range:
            # Restore original file state
            self._restore_test_file(original_content)

            # Prepare test code with proper indentation
            test_code_indented = prepare_test_code_with_indentation(
                needed_indent=self.test_headers_indentation,
                test_code = current_test_code
            )
            
            # Insert test code into file
            processed_test = insert_test_code(
                original_content = original_content,
                test_code_indented = test_code_indented, 
                additional_imports = additional_imports,
                import_index = self.relevant_line_number_to_insert_imports_after,
                test_index = self.relevant_line_number_to_insert_tests_after
            )
            
            if not processed_test:
                continue
                
            # Write the candidate test file
            with open(self.test_file_path, "w") as test_file:
                test_file.write(processed_test)
                test_file.flush()

            # Run the test command (with flakiness retry)
            final_stdout, final_stderr, final_exit_code, time_of_test_command = self._run_test_with_retry(attempt)
            
            if final_exit_code == 0:
                # Test passed - check coverage
                coverage_result = self._check_coverage_increase(
                    time_of_test_command, attempt, generated_test, current_test_code, previous_test_codes
                )
                
                if coverage_result.get("coverage_increased"):
                    coverage_increased = True
                    new_percentage_covered = coverage_result["new_percentage_covered"]
                    new_coverage_percentages = coverage_result["new_coverage_percentages"]
                    break
                elif coverage_result.get("should_break"):
                    break
                elif coverage_result.get("new_test_code"):
                    current_test_code = coverage_result["new_test_code"]
                    previous_test_codes.append(current_test_code)
                    continue
            else:
                # Test failed - attempt to fix
                fix_result = self._attempt_test_fix(
                    attempt, original_content, generated_test, current_test_code, final_exit_code, 
                    final_stdout, final_stderr, previous_test_codes
                )
                
                if fix_result.get("should_break"):
                    break
                elif fix_result.get("new_test_code"):
                    current_test_code = fix_result["new_test_code"]
                    previous_test_codes.append(current_test_code)
                    continue

        # Final decision logic
        if final_exit_code != 0 or not coverage_increased:
            return self._handle_test_failure(
                original_content, generated_test, processed_test,
                final_exit_code, final_stdout, final_stderr, previous_test_codes
            )
        
        # Test passed and coverage increased
        return self._handle_test_success(
            generated_test, processed_test, original_content,
            final_exit_code, final_stdout, final_stderr,
            time_of_test_command, additional_imports, previous_test_codes
        )

    def _restore_test_file(self, original_content: str) -> None:
        """Restore test file to original content."""
        with open(self.test_file_path, "w") as test_file:
            test_file.write(original_content)
            test_file.flush()


    def _run_test_with_retry(self, attempt: int) -> Tuple[str, str, int, float]:
        """
        Run test command with retry for flakiness.
        
        Parameters:
            attempt (int): Current attempt number
            
        Returns:
            Tuple of (stdout, stderr, exit_code, time_of_test_command)
        """
        for _ in range(self.num_attempts):
            self.logger.info(
                f'Running test (Attempt {attempt+1}/{self.max_fix_attempts+1}) '
                f'with command: "{self.test_command}"'
            )
            stdout, stderr, exit_code, time_of_test_command = Runner.run_command(
                command=self.test_command,
                cwd=self.test_command_dir,
                max_run_time_sec=self.max_run_time_sec,
            )
            if exit_code != 0:
                break  # Break flakiness loop if failed
        
        return stdout, stderr, exit_code, time_of_test_command

    def _check_coverage_increase(
        self,
        time_of_test_command: float,
        attempt: int,
        generated_test: Dict[str, Any],
        current_test_code: str,
        previous_test_codes: List[str]
    ) -> Dict[str, Any]:
        """
        Check if coverage increased and attempt fix if not.
        
        Returns:
            dict with keys: coverage_increased, new_percentage_covered, new_coverage_percentages,
                          should_break, new_test_code
        """
        try:
            new_percentage_covered, new_coverage_percentages = self.post_process_coverage_report(
                time_of_test_command
            )
        except Exception as e:
            self.logger.error(f"Error during coverage verification inside loop: {e}")
            return {"coverage_increased": False, "should_break": True}

        if new_percentage_covered > self.current_coverage:
            return {
                "coverage_increased": True,
                "new_percentage_covered": new_percentage_covered,
                "new_coverage_percentages": new_coverage_percentages
            }

        # Test passed but coverage didn't increase
        self.logger.info("Test passed but did not increase coverage. Attempting to fix for better coverage")

        if attempt >= self.max_fix_attempts:
            self.logger.info("No fix attempts left for coverage improvement")
            return {"coverage_increased": False, "should_break": True}

        new_test_code = self._fix_test_for_coverage(
            generated_test, current_test_code, previous_test_codes,
            new_percentage_covered
        )
        
        if new_test_code:
            return {"coverage_increased": False, "new_test_code": new_test_code}
        else:
            return {"coverage_increased": False, "should_break": True}

    def _fix_test_for_coverage(
        self,
        generated_test: Dict[str, Any],
        current_test_code: str,
        previous_test_codes: List[str],
        new_percentage_covered: float
    ) -> Optional[str]:
        """
        Attempt to fix test to improve coverage.
        
        Returns:
            str: New test code if successful, None otherwise
        """
        test_behavior = generated_test.get("test_behavior", "")
        lines_to_cover = generated_test.get("lines_to_cover", "")

        enhanced_error_message = f"""
        The test executed successfully (exit_code=0) but DID NOT increase code coverage.

        Current coverage: {self.format_coverage_percentage(self.current_coverage)}%
        New coverage after this test: {self.format_coverage_percentage(new_percentage_covered)}%

        Original Test Purpose: {test_behavior}
        Lines intended to cover: {lines_to_cover}

        IMPORTANT:
        - Modify the test to execute previously uncovered branches/lines.
        - Add meaningful assertions and real logic (no 'pass' stubs).
        - Avoid testing the same already-covered path again.
        """

        fix_response, _, _, _ = self.agent_completion.fix_test(
            source_file_name=self._get_relative_path(self.source_file_path),
            source_file=self.source_code,
            test_code=current_test_code,
            error_message=enhanced_error_message,
            language=self.language,
            test_file_name=self._get_relative_path(self.test_file_path),
        )

        try:
            fix_dict = load_yaml(fix_response)
            if isinstance(fix_dict, dict) and "test_code" in fix_dict:
                new_test_code = fix_dict["test_code"]
            else:
                new_test_code = fix_response

            # Prevent duplicate fixes
            if new_test_code in previous_test_codes:
                self.logger.warning("AI generated identical fix (coverage mode). Stopping fix attempts")
                return None

            # Prevent trivial stubs
            if is_trivial_stub(new_test_code):
                self.logger.warning("AI generated a trivial stub (coverage mode). Stopping fix attempts")
                return None

            self.logger.info("Received potential fix from AI (coverage mode). Retrying validation")
            return new_test_code
            
        except Exception as parse_error:
            self.logger.error(f"Error parsing fix response (coverage mode): {parse_error}")
            return None

    def _attempt_test_fix(
        self,
        attempt: int,
        original_content :str,
        generated_test: Dict[str, Any],
        current_test_code: str,
        final_exit_code: str,
        final_stdout: str,
        final_stderr: str,
        previous_test_codes: List[str]
    ) -> Dict[str, Any]:
        """
        Attempt to fix a failing test using AI.
        
        Returns:
            dict with keys: should_break, new_test_code
        """
        self.logger.info(f"Test failed on attempt {attempt+1}.")
        
        if attempt >= self.max_fix_attempts:
            self.logger.info("Max fix attempts reached. Marking test as failed")
            return {"should_break": True}

        self.logger.info("Attempting to auto-fix the test using AI")
        
        try:
            # Check if test is a stub
            if is_trivial_stub(current_test_code) and attempt > 0:
                self.logger.warning("AI generated a test stub with no logic. Skipping further fixes")
                return {"should_break": True}
            
            # Call AI to fix
            fail_details = {
                "status": "FAIL",
                "reason": "Test failed",
                "exit_code": final_exit_code,
                "stderr": final_stderr,
                "stdout": final_stdout,
                "test": generated_test,
                "language": self.language,
                "source_file": self.source_code,
                "original_test_file": original_content,
                "processed_test_file": current_test_code,        
            }
            error_message = self.extract_error_message(fail_details)
            if error_message:
                logging.error(f"Error message summary:\n{error_message}")

            self.failed_test_runs.append(
                {"code": generated_test, "error_message": error_message}
            )
            new_test_code = self._call_ai_fix(
                generated_test, current_test_code, final_stdout, final_stderr, error_message
            )
            
            if not new_test_code:
                return {"should_break": True}
                
            # Validate fix
            if new_test_code in previous_test_codes:
                self.logger.warning("AI generated identical fix. Stopping fix attempts")
                return {"should_break": True}
            
            if is_trivial_stub(new_test_code):
                self.logger.warning("AI generated a trivial test stub. Stopping fix attempts")
                return {"should_break": True}
            
            self.logger.info("Received potential fix from AI. Retrying validation")
            return {"new_test_code": new_test_code}
            
        except Exception as e:
            self.logger.error(f"Error during auto-fix attempt: {e}")
            return {"should_break": True}

    def _call_ai_fix(
        self,
        generated_test: Dict[str, Any],
        current_test_code: str,
        final_stdout: str,
        final_stderr: str,
        error_message: str
    ) -> Optional[str]:
        """
        Call AI to fix failing test.
        
        Returns:
            str: Fixed test code or None if parsing fails
        """
        test_behavior = generated_test.get("test_behavior", "")
        lines_to_cover = generated_test.get("lines_to_cover", "")
        
        enhanced_error_message = f"""
        Original Test Purpose: {test_behavior}
        Lines intended to cover: {lines_to_cover}

        Execution Error:
        Stdout: {final_stdout}
        Stderr: {final_stderr}

        IMPORTANT: Do NOT generate a test stub with just 'pass'. 
        Generate a complete, working test that actually tests the behavior described above 
        and covers the specified lines.
        The test must include actual assertions and test logic.
        """       
        fix_response, _, _, _ = self.agent_completion.fix_test(
            source_file_name=self._get_relative_path(self.source_file_path),
            source_file=self.source_code,
            test_code=current_test_code,
            error_message=enhanced_error_message,
            language=self.language,
            test_file_name=self._get_relative_path(self.test_file_path),
            additional_instructions_text= error_message
        )
        
        try:
            fix_dict = load_yaml(fix_response)
            if isinstance(fix_dict, dict) and "test_code" in fix_dict:
                return fix_dict["test_code"]
            else:
                return fix_response
        except Exception as parse_error:
            self.logger.error(f"Error parsing fix response: {parse_error}")
            return None


    def _handle_test_failure(
        self,
        original_content: str,
        generated_test: Dict[str, Any],
        processed_test: str,
        final_exit_code: int,
        final_stdout: str,
        final_stderr: str,
        previous_test_codes: List[str]
    ) -> Dict[str, Any]:
        """
        Handle test failure by rolling back and logging.
        
        Returns:
            dict: Failure details
        """
        # Rollback
        with open(self.test_file_path, "w") as test_file:
            test_file.write(original_content)
        
        self.logger.info(f"Skipping a generated test that failed after {len(previous_test_codes)} attempts")
        
        fail_details = {
            "status": "FAIL",
            "reason": "Test failed after auto-fix attempts",
            "exit_code": final_exit_code,
            "stderr": final_stderr,
            "stdout": final_stdout,
            "test": generated_test,
            "language": self.language,
            "source_file": self.source_code,
            "original_test_file": original_content,
            "processed_test_file": processed_test,
            "fix_attempts": len(previous_test_codes) - 1,
        }

        error_message = self.extract_error_message(fail_details)
        if error_message:
            logging.error(f"Error message summary:\n{error_message}")

        self.failed_test_runs.append(
            {"code": generated_test, "error_message": error_message}
        )

        # Log to WandB if configured
        if "WANDB_API_KEY" in os.environ:
            fail_details["error_message"] = error_message
            root_span = Trace(
                name="fail_details_" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                kind="llm",
                inputs={"test_code": fail_details["test"]},
                outputs=fail_details,
            )
            root_span.log(name="inference")

        return fail_details

    def _handle_test_success(
        self,
        generated_test: Dict[str, Any],
        processed_test: str,
        original_content: str,
        final_exit_code: int,
        final_stdout: str,
        final_stderr: str,
        time_of_test_command: float,
        additional_imports: str,
        previous_test_codes: List[str]
    ) -> Dict[str, Any]:
        """
        Handle successful test with coverage increase.
        
        Returns:
            dict: Success details
        """
        # Verify coverage increased one more time
        try:
            new_percentage_covered, new_coverage_percentages = self.post_process_coverage_report(
                time_of_test_command
            )

            if new_percentage_covered <= self.current_coverage:
                # Rollback if coverage didn't actually increase
                self._restore_test_file(original_content)
                self.logger.info("Test did not increase coverage. Rolling back.")
                
                fail_details = {
                    "status": "FAIL",
                    "reason": "Coverage did not increase.",
                    "exit_code": final_exit_code,
                    "stderr": final_stderr,
                    "stdout": final_stdout,
                    "test": generated_test,
                    "language": self.language,
                    "source_file": self.source_code,
                    "original_test_file": original_content,
                    "processed_test_file": processed_test,
                }
                
                self.failed_test_runs.append({
                    "code": fail_details["test"],
                    "error_message": "Test did not increase code coverage",
                })

                if "WANDB_API_KEY" in os.environ:
                    root_span = Trace(
                        name="fail_details_" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                        kind="llm",
                        inputs={"test_code": fail_details["test"]},
                        outputs=fail_details,
                    )
                    root_span.log(name="inference")

                return fail_details
                
        except Exception as e:
            self.logger.error(f"Error during coverage verification: {e}")
            self._restore_test_file(original_content)
            
            return {
                "status": "FAIL",
                "reason": "Runtime error",
                "exit_code": final_exit_code,
                "stderr": final_stderr,
                "stdout": final_stdout,
                "test": generated_test,
                "language": self.language,
                "source_file": self.source_code,
                "original_test_file": original_content,
                "processed_test_file": processed_test,
            }

        # Success - update state
        self.relevant_line_number_to_insert_tests_after += len(
            additional_imports.split("\n") if additional_imports else []
        )

        # Log coverage improvements
        self._log_coverage_improvements(new_coverage_percentages)
        
        self.current_coverage = new_percentage_covered
        self.last_coverage_percentages = new_coverage_percentages.copy()

        self.logger.info(
            f"Test passed and coverage increased after {len(previous_test_codes)} attempts. "
            f"Current coverage: {self.format_coverage_percentage(new_percentage_covered)}%"
        )
        
        return {
            "status": "PASS",
            "reason": "",
            "exit_code": final_exit_code,
            "stderr": final_stderr,
            "stdout": final_stdout,
            "test": generated_test,
            "language": self.language,
            "source_file": self.source_code,
            "original_test_file": original_content,
            "processed_test_file": processed_test,
            "fix_attempts": len(previous_test_codes) - 1,
        }

    def _log_coverage_improvements(self, new_coverage_percentages: Dict[str, float]) -> None:
        """Log which files had coverage improvements."""
        for key in new_coverage_percentages:
            if key not in self.last_coverage_percentages:
                continue
                
            old_cov = self.format_coverage_percentage(self.last_coverage_percentages[key])
            new_cov = self.format_coverage_percentage(new_coverage_percentages[key])
            
            if new_coverage_percentages[key] > self.last_coverage_percentages[key]:
                if key == self.source_file_path.split("/")[-1]:
                    self.logger.info(
                        f"Coverage for provided source file: {key} increased from {old_cov} to {new_cov}"
                    )
                else:
                    self.logger.info(
                        f"Coverage for non-source file: {key} increased from {old_cov} to {new_cov}"
                    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert validator state to dictionary.
        
        Returns:
            dict: Dictionary representation of key validator attributes
        """
        return {
            "source_file_path": self.source_file_path,
            "test_file_path": self.test_file_path,
            "code_coverage_report_path": self.code_coverage_report_path,
            "test_command": self.test_command,
            "llm_model": self.llm_model,
            "test_command_dir": self.test_command_dir,
            "included_files": self.included_files,
            "coverage_type": self.coverage_type,
            "desired_coverage": self.desired_coverage,
            "additional_instructions": self.additional_instructions,
            "language": self.language,
            "testing_framework": self.testing_framework,
            "current_coverage": getattr(self, 'current_coverage', 0),
        }

    def to_json(self) -> str:
        """
        Convert validator state to JSON string.
        
        Returns:
            str: JSON representation of validator state
        """
        return json.dumps(self.to_dict(), indent=2)

    def extract_error_message(self, fail_details: Dict[str, Any]) -> str:
        """
        Extract error message from fail details using AI analysis.

        Parameters:
            fail_details (dict): Dictionary containing test failure details

        Returns:
            str: The error summary or empty string if extraction fails
        """
        try:
            if not self._validate_fail_details(fail_details):
                self.logger.error("Invalid fail_details structure")
                return ""
            
            response, prompt_token_count, response_token_count, prompt = (
                self.agent_completion.analyze_test_failure(
                    source_file_name=self._get_relative_path(self.source_file_path),
                    source_file=self._read_file(self.source_file_path),
                    processed_test_file=fail_details["processed_test_file"],
                    stderr=fail_details["stderr"],
                    stdout=fail_details["stdout"],
                    test_file_name=self._get_relative_path(self.test_file_path),
                )
            )
            
            self._update_token_counts(prompt_token_count, response_token_count)
            return response.strip()
            
        except KeyError as e:
            self.logger.error(f"Missing required key in fail_details: {e}")
            return ""
        except Exception as e:
            self.logger.error(f"Error extracting error message: {e}")
            return ""

    def _validate_fail_details(self, fail_details: Dict[str, Any]) -> bool:
        """Validate that fail_details contains required keys."""
        required_keys = ["processed_test_file", "stderr", "stdout"]
        return all(key in fail_details for key in required_keys)

    def post_process_coverage_report(
        self, time_of_test_command: float
    ) -> Tuple[float, Dict[str, float]]:
        """
        Process coverage report and return metrics.
        
        Parameters:
            time_of_test_command (float): Timestamp of test command execution
            
        Returns:
            Tuple of (percentage_covered, coverage_percentages)
        """
        coverage_percentages: Dict[str, float] = {}
        
        if self.use_report_coverage_feature_flag:
            percentage_covered = self._process_full_report_coverage(
                time_of_test_command, coverage_percentages
            )
        elif self.diff_coverage:
            percentage_covered = self._process_diff_coverage(time_of_test_command)
        else:
            percentage_covered = self._process_standard_coverage(time_of_test_command)
        
        return percentage_covered, coverage_percentages

    def _process_full_report_coverage(
        self, time_of_test_command: float, coverage_percentages: Dict[str, float]
    ) -> float:
        """Process coverage report for all files."""
        self.logger.info("Using the report coverage feature flag to process the coverage report")
        
        file_coverage_dict = self.coverage_processor.process_coverage_report(
            time_of_test_command=time_of_test_command
        )
        
        total_lines_covered = 0
        total_lines_missed = 0
        
        for key, (lines_covered, lines_missed, percentage_covered) in file_coverage_dict.items():
            total_lines_covered += len(lines_covered)
            total_lines_missed += len(lines_missed)
            
            if key == self.source_file_path:
                self.last_source_file_coverage = percentage_covered
            
            coverage_percentages[key] = percentage_covered
        
        total_lines = total_lines_covered + total_lines_missed
        percentage_covered = self._calculate_coverage_percentage(total_lines_covered, total_lines)
        
        self._log_coverage_summary(total_lines_covered, total_lines_missed, total_lines, percentage_covered)
        
        return percentage_covered

    def _process_diff_coverage(self, time_of_test_command: float) -> float:
        """Process diff coverage report."""
        self.generate_diff_coverage_report()
        lines_covered, lines_missed, percentage_covered = self.coverage_processor.process_coverage_report(
            time_of_test_command=time_of_test_command
        )
        self.code_coverage_report = self._format_coverage_report(
            lines_covered, lines_missed, percentage_covered
        )
        return percentage_covered

    def _process_standard_coverage(self, time_of_test_command: float) -> float:
        """Process standard coverage report."""
        lines_covered, lines_missed, percentage_covered = self.coverage_processor.process_coverage_report(
            time_of_test_command=time_of_test_command
        )
        self.code_coverage_report = self._format_coverage_report(
            lines_covered, lines_missed, percentage_covered
        )
        return percentage_covered

    def _calculate_coverage_percentage(self, lines_covered: int, total_lines: int) -> float:
        """Calculate coverage percentage safely handling division by zero."""
        if total_lines == 0:
            self.logger.error(
                f"ZeroDivisionError: Attempting to divide {lines_covered} / {total_lines}"
            )
            return 0.0
        return lines_covered / total_lines

    def _format_coverage_report(
        self, lines_covered: Any, lines_missed: Any, percentage_covered: float
    ) -> str:
        """Format coverage report as string."""
        return (
            f"Lines covered: {lines_covered}\n"
            f"Lines missed: {lines_missed}\n"
            f"Percentage covered: {self.format_coverage_percentage(percentage_covered)}%"
        )

    def _log_coverage_summary(
        self, total_lines_covered: int, total_lines_missed: int, 
        total_lines: int, percentage_covered: float
    ) -> None:
        """Log coverage summary information."""
        self.logger.info(
            f"Total lines covered: {total_lines_covered}, "
            f"Total lines missed: {total_lines_missed}, "
            f"Total lines: {total_lines}"
        )
        self.logger.info(
            f"coverage: Percentage {self.format_coverage_percentage(percentage_covered)}%"
        )

    def generate_diff_coverage_report(self) -> None:
        """
        Generate a JSON diff coverage report using the diff-cover tool.
        
        Raises:
            Exception: If an error occurs while running the diff-cover command.
        """
        diff_cover_args = [
            "diff-cover",
            "--json-report",
            self.diff_cover_report_path,
            f"--compare-branch={self.comparison_branch}",
            self.code_coverage_report_path,
        ]
        
        self.logger.info(f'Running diff coverage module with args: "{diff_cover_args}"')
        
        try:
            diff_cover_main(diff_cover_args)
        except Exception as e:
            self.logger.error(f"Error running diff-cover: {e}")
            raise

    def get_current_coverage(self) -> float:
        """Get the current coverage percentage."""
        return getattr(
            self, 'current_coverage_report', 
            type('obj', (object,), {'total_coverage': 0.0})()
        ).total_coverage

    def format_coverage_percentage(self, coverage: float) -> float:
        """Format coverage percentage to specified precision."""
        return round(coverage * 100, self.COVERAGE_PRECISION)

    def _get_relative_path(self, file_path: str) -> str:
        """Get relative path from project root."""
        if self.project_root:
            return os.path.relpath(file_path, self.project_root)
        return file_path

    def _update_token_counts(self, input_tokens: int, output_tokens: int) -> None:
        """Update total token counts."""
        self.total_input_token_count += input_tokens
        self.total_output_token_count += output_tokens

    def _read_file(self, file_path: str) -> str:
        """
        Read file contents safely.

        Parameters:
            file_path (str): Path to the file

        Returns:
            str: File content or error message
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            error_msg = f"File not found: {file_path}"
            self.logger.error(error_msg)
            return f"Error: {error_msg}"
        except PermissionError:
            error_msg = f"Permission denied: {file_path}"
            self.logger.error(error_msg)
            return f"Error: {error_msg}"
        except UnicodeDecodeError:
            error_msg = f"Unable to decode file (encoding issue): {file_path}"
            self.logger.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Error reading {file_path}: {e}"
            self.logger.error(error_msg)
            return f"Error: {error_msg}"

    def get_token_usage(self) -> Dict[str, int]:
        """Get token usage statistics."""
        return {
            "input_tokens": self.total_input_token_count,
            "output_tokens": self.total_output_token_count,
            "total_tokens": self.total_input_token_count + self.total_output_token_count,
        }

    def reset_coverage_state(self) -> None:
        """Reset coverage tracking state."""
        self.last_coverage_percentages.clear()
        self.failed_test_runs.clear()
        self.code_coverage_report = ""
        self.logger.info("Coverage state reset")