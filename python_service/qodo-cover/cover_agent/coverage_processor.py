import csv
import json
import os
import re
import xml.etree.ElementTree as ET

from typing import List, Optional, Tuple, Union

from cover_agent.custom_logger import CustomLogger
from cover_agent.settings.config_schema import CoverageType


class CoverageProcessor:
    def __init__(
        self,
        file_path: str,
        src_file_path: str,
        coverage_type: CoverageType,
        use_report_coverage_feature_flag: bool = False,
        diff_coverage_report_path: str = None,
        logger: Optional[CustomLogger] = None,
        generate_log_files: bool = True,
    ):
        """
        Initializes a CoverageProcessor object.

        Args:
            file_path (str): The path to the coverage report file.
            src_file_path (str): The fully qualified path of the file for which coverage data is being processed.
            coverage_type (CoverageType): The type of coverage report being processed.
            logger (CustomLogger): The logger object for logging messages.
            generate_log_files (bool): Whether or not to generate logs.

        Attributes:
            file_path (str): The path to the coverage report file.
            src_file_path (str): The fully qualified path of the file for which coverage data is being processed.
            coverage_type (CoverageType): The type of coverage report being processed.
            logger (CustomLogger): The logger object for logging messages.

        Returns:
            None
        """
        self.file_path = file_path
        self.src_file_path = src_file_path
        self.coverage_type = coverage_type
        self.logger = logger or CustomLogger.get_logger(__name__, generate_log_files=generate_log_files)
        self.use_report_coverage_feature_flag = use_report_coverage_feature_flag
        self.diff_coverage_report_path = diff_coverage_report_path

    def process_coverage_report(self, time_of_test_command: int) -> Tuple[list, list, float, float, dict]:
        """
        Verifies the coverage report's existence and update time, and then
        parses the report based on its type to extract coverage data.

        Args:
            time_of_test_command (int): The time the test command was run, in milliseconds.

        Returns:
            Tuple[list, list, float]: A tuple containing lists of covered and missed line numbers, and the coverage percentage.
        """
        self.verify_report_update(time_of_test_command)
        return self.parse_coverage_report()

    def verify_report_update(self, time_of_test_command: int):
        """
        Verifies the coverage report's existence and update time.

        Args:
            time_of_test_command (int): The time the test command was run, in milliseconds.

        Raises:
            AssertionError: If the coverage report does not exist or was not updated after the test command.
        """
        assert os.path.exists(self.file_path), f'Fatal: Coverage report "{self.file_path}" was not generated.'

        # Convert file modification time to milliseconds for comparison
        file_mod_time_ms = int(round(os.path.getmtime(self.file_path) * 1000))

        if not file_mod_time_ms > time_of_test_command:
            self.logger.warning(
                f"The coverage report file was not updated after the test command. file_mod_time_ms: {file_mod_time_ms}, time_of_test_command: {time_of_test_command}. {file_mod_time_ms > time_of_test_command}"
            )

    def parse_coverage_report(self) -> Tuple[list, list, float, float, dict]:
        """
        Parses a code coverage report to extract covered and missed line numbers for a specific file,
        and calculates the coverage percentage, based on the specified coverage report type.

        Returns:
            Tuple[list, list, float]: A tuple containing lists of covered and missed line numbers, coverage percentage and branch coverage
        """
        if self.use_report_coverage_feature_flag:
            if self.coverage_type == "cobertura":
                return self.parse_coverage_report_cobertura()
            elif self.coverage_type == "lcov":
                return self.parse_coverage_report_lcov()
            elif self.coverage_type == "jacoco":
                return self.parse_coverage_report_jacoco()
            else:
                raise ValueError(f"Unsupported coverage report type: {self.coverage_type}")
        else:
            if self.coverage_type == "cobertura":
                # Default behavior is to parse out a single file from the report
                return self.parse_coverage_report_cobertura(filename=os.path.basename(self.src_file_path))
            elif self.coverage_type == "lcov":
                return self.parse_coverage_report_lcov()
            elif self.coverage_type == "jacoco":
                return self.parse_coverage_report_jacoco()
            elif self.coverage_type == "diff_cover_json":
                return self.parse_json_diff_coverage_report()
            else:
                raise ValueError(f"Unsupported coverage report type: {self.coverage_type}")

    def parse_coverage_report_cobertura(self, filename: str = None) -> Union[Tuple[list, list, float, float, dict], dict]:
        """
        Parses a Cobertura XML code coverage report to extract covered and missed line numbers
        for a specific file or for all files (if filename is None). Aggregates coverage data from
        multiple <class> entries that share the same filename.

        Args:
            filename (str, optional): Filename to process. If None, process all files.

        Returns:
            If filename is provided, returns (covered_lines, missed_lines, coverage_percent, branch_coverage_percentage).
            If filename is None, returns a dict: { filename: (covered_lines, missed_lines, coverage_percent, branch_coverage_percentage) }.
        """
        tree = ET.parse(self.file_path)
        root = tree.getroot()

        if filename:
            # Collect coverage for all <class> elements matching the given filename
            all_covered, all_missed = [], []
            total_b_covered, total_b_count =  0, 0
            all_branches_missed = {}
            for cls in root.findall(".//class"):
                name_attr = cls.get("filename")
                if name_attr and name_attr.endswith(filename):
                    c_covered, c_missed, b_covered, b_total, b_missed_info = self.parse_coverage_data_for_class(cls)
                    all_covered.extend(c_covered)
                    all_missed.extend(c_missed)
                    total_b_covered += b_covered
                    total_b_count += b_total
                    all_branches_missed.update(b_missed_info)

            # Deduplicate and compute coverage
            covered_set = set(all_covered)
            missed_set = set(all_missed) - covered_set
            total_lines = len(covered_set) + len(missed_set)
            coverage_percentage = (len(covered_set) / total_lines) if total_lines else 0
            branch_coverage = (total_b_covered / total_b_count) if total_b_count else 0

            return list(covered_set), list(missed_set), coverage_percentage, branch_coverage, all_branches_missed

        else:
            # Collect coverage for every <class>, grouping by filename
            coverage_data = {}
            file_map = {}  # filename -> ([covered], [missed])

            for cls in root.findall(".//class"):
                cls_filename = cls.get("filename")
                if cls_filename:
                    c_covered, c_missed, b_covered, b_total, b_missed_info = self.parse_coverage_data_for_class(cls)
                    if cls_filename not in file_map:
                        file_map[cls_filename] = ([], [], 0, 0, {})
                    curr_c, curr_m, curr_bc, curr_bt, curr_bmi = file_map[cls_filename]
                    curr_c.extend(c_covered)
                    curr_m.extend(c_missed)
                    curr_bmi.update(b_missed_info)
                    file_map[cls_filename] = (curr_c, curr_m, curr_bc + b_covered, curr_bt + b_total, curr_bmi)

            # Convert raw lists to sets, compute coverage, store results
            for f_name, (c_covered, c_missed, bc, bt, bmi) in file_map.items():
                covered_set = set(c_covered)
                missed_set = set(c_missed) - covered_set
                total_lines = len(covered_set) + len(missed_set)
                coverage_percentage = (len(covered_set) / total_lines) if total_lines else 0
                branch_coverage = (bc / bt) if bt else 0
                coverage_data[f_name] = (
                    list(covered_set),
                    list(missed_set),
                    coverage_percentage,
                    branch_coverage,
                    bmi
                )

            return coverage_data

    def parse_coverage_data_for_class(self, cls) -> Tuple[list, list, float, float, dict]:
        """
        Parses coverage data for a single class.

        Args:
            cls (Element): XML element representing the class.

        Returns:
            Tuple[list, list, float]: A tuple containing lists of covered and missed line numbers,
                                    and the coverage percentage.
        """
        lines_covered, lines_missed = [], []
        branches_covered, total_branches = 0, 0
        branches_missed_info = {}  # line_number -> condition coverage info for missed branches
        for line in cls.findall(".//line"):
            line_number = int(line.get("number"))
            hits = int(line.get("hits"))
            if hits > 0:
                lines_covered.append(line_number)
            else:
                lines_missed.append(line_number)
            if line.get("branch") == "true":
                condition = line.get("condition-coverage", "")
                #  Regex "(X/Y)"
                match = re.search(r'\((\d+)/(\d+)\)', condition)
                if match:
                    branches_covered += int(match.group(1))
                    total_branches += int(match.group(2))
                    
                missing_branches_str = line.get("missing-branches")
                if missing_branches_str:
                    branches_missed_info[line_number] = [b.strip() for b in missing_branches_str.split(",")]

        total_lines = len(lines_covered) + len(lines_missed)
        coverage_percentage = (len(lines_covered) / total_lines) if total_lines > 0 else 0

        return lines_covered, lines_missed, branches_covered, total_branches,branches_missed_info

    def parse_coverage_report_lcov(self) -> Tuple[list, list, float, float, dict]:
            lines_covered, lines_missed = [], []
            branches_covered, total_branches = 0, 0
            branches_missed_info = {}
            
            filename = os.path.basename(self.src_file_path)
            try:
                with open(self.file_path, "r") as file:
                    for line in file:
                        line = line.strip()
                        if line.startswith("SF:") and line.endswith(filename):
                            for line in file:
                                line = line.strip()
                                if line.startswith("DA:"):
                                    line_number = int(line.replace("DA:", "").split(",")[0])
                                    hits = int(line.replace("DA:", "").split(",")[1])
                                    if hits > 0:
                                        lines_covered.append(line_number)
                                    else:
                                        lines_missed.append(line_number)
                                elif line.startswith("BRDA:"):
                                    # Định dạng: BRDA:line_number,block_number,branch_number,taken
                                    parts = line.replace("BRDA:", "").split(",")
                                    line_number = int(parts[0])
                                    branch_id = parts[2]
                                    taken = parts[3]
                                    
                                    total_branches += 1
                                    if taken != '-' and int(taken) > 0:
                                        branches_covered += 1
                                    else:
                                        if line_number not in branches_missed_info:
                                            branches_missed_info[line_number] = []
                                        branches_missed_info[line_number].append(f"Branch {branch_id} missed")
                                        
                                elif line.startswith("end_of_record"):
                                    break

            except (FileNotFoundError, IOError) as e:
                self.logger.error(f"Error reading file {self.file_path}: {e}")
                raise

            total_lines = len(lines_covered) + len(lines_missed)
            coverage_percentage = (len(lines_covered) / total_lines) if total_lines > 0 else 0
            branch_coverage = (branches_covered / total_branches) if total_branches > 0 else 0.0

            return lines_covered, lines_missed, coverage_percentage, branch_coverage, branches_missed_info

    def parse_coverage_report_jacoco(self) -> Tuple[list, list, float, float, dict]:
            lines_covered, lines_missed = [], []
            source_file_extension = self.get_file_extension(self.src_file_path)

            package_name, class_name = "", ""
            if source_file_extension == "java":
                package_name, class_name = self.extract_package_and_class_java()
            elif source_file_extension == "kt":
                package_name, class_name = self.extract_package_and_class_kotlin()
            else:
                self.logger.warn(f"Unsupported Bytecode Language: {source_file_extension}. Using default Java logic.")
                package_name, class_name = self.extract_package_and_class_java()

            file_extension = self.get_file_extension(self.file_path)

            missed, covered = 0, 0
            branches_covered, total_branches = 0, 0
            branches_missed_info = {}

            if file_extension == "xml":
                lines_missed, lines_covered, branches_covered, total_branches, branches_missed_info = self.parse_missed_covered_lines_jacoco_xml(class_name)
                missed, covered = len(lines_missed), len(lines_covered)
            elif file_extension == "csv":
                missed, covered, b_missed, b_covered = self.parse_missed_covered_lines_jacoco_csv(package_name, class_name)
                branches_covered = b_covered
                total_branches = b_covered + b_missed
            else:
                raise ValueError(f"Unsupported JaCoCo code coverage report format: {file_extension}")

            total_lines = missed + covered
            coverage_percentage = (float(covered) / total_lines) if total_lines > 0 else 0
            branch_coverage_percentage = (float(branches_covered) / total_branches) if total_branches > 0 else 0.0

            return lines_covered, lines_missed, coverage_percentage, branch_coverage_percentage, branches_missed_info

    def parse_missed_covered_lines_jacoco_xml(self, class_name: str) -> tuple[list, list, int, int, dict]:
            """Parses a JaCoCo XML code coverage report to extract covered and missed line and branch numbers."""
            tree = ET.parse(self.file_path)
            root = tree.getroot()
            sourcefile = root.find(f".//sourcefile[@name='{class_name}.java']") or root.find(
                f".//sourcefile[@name='{class_name}.kt']"
            )

            if sourcefile is None:
                return [], [], 0, 0, {}

            missed, covered = [], []
            branches_covered, total_branches = 0, 0
            branches_missed_info = {}
            
            for line in sourcefile.findall("line"):
                line_nr = int(line.attrib.get("nr", 0))
                if line.attrib.get("mi") == "0":
                    covered.append(line_nr)
                else:
                    missed.append(line_nr)
                    
                cb = int(line.attrib.get("cb", 0))
                mb = int(line.attrib.get("mb", 0))
                if cb > 0 or mb > 0:
                    branches_covered += cb
                    total_branches += (cb + mb)
                    if mb > 0:
                        branches_missed_info[line_nr] = [f"Missed {mb} out of {cb + mb} branches"]

            return missed, covered, branches_covered, total_branches, branches_missed_info

    def parse_missed_covered_lines_jacoco_csv(self, package_name: str, class_name: str) -> tuple[int, int, int, int]:
            with open(self.file_path, "r") as file:
                reader = csv.DictReader(file)
                missed, covered = 0, 0
                b_missed, b_covered = 0, 0
                for row in reader:
                    if row["PACKAGE"] == package_name and row["CLASS"] == class_name:
                        try:
                            missed = int(row["LINE_MISSED"])
                            covered = int(row["LINE_COVERED"])
                            b_missed = int(row["BRANCH_MISSED"])
                            b_covered = int(row["BRANCH_COVERED"])
                            break
                        except KeyError as e:
                            self.logger.error(f"Missing expected column in CSV: {str(e)}")
                            raise

            return missed, covered, b_missed, b_covered

    def extract_package_and_class_java(self):
        package_pattern = re.compile(r"^\s*package\s+([\w\.]+)\s*;.*$")
        class_pattern = re.compile(r"^\s*(?:public\s+)?(?:class|interface|record)\s+(\w+)(?:(?:<|\().*?(?:>|\)))?(?:\s+extends|\s+implements|\s*\{|$)")


        package_name = ""
        class_name = ""
        try:
            with open(self.src_file_path, "r") as file:
                for line in file:
                    if not package_name:  # Only match package if not already found
                        package_match = package_pattern.match(line)
                        if package_match:
                            package_name = package_match.group(1)

                    if not class_name:  # Only match class if not already found
                        class_match = class_pattern.match(line)
                        if class_match:
                            class_name = class_match.group(1)

                    if package_name and class_name:  # Exit loop if both are found
                        break
        except (FileNotFoundError, IOError) as e:
            self.logger.error(f"Error reading file {self.src_file_path}: {e}")
            raise

        return package_name, class_name

    def extract_package_and_class_kotlin(self):
        package_pattern = re.compile(r"^\s*package\s+([\w.]+)\s*(?:;)?\s*(?://.*)?$")
        class_pattern = re.compile(
            r"^\s*(?:public|internal|abstract|data|sealed|enum|open|final|private|protected)*\s*class\s+(\w+).*"
        )

        package_name = ""
        class_name = ""
        try:
            with open(self.src_file_path, "r") as file:
                for line in file:
                    if not package_name:  # Only match package if not already found
                        package_match = package_pattern.match(line)
                        if package_match:
                            package_name = package_match.group(1)

                    if not class_name:  # Only match class if not already found
                        class_match = class_pattern.match(line)
                        if class_match:
                            class_name = class_match.group(1)

                    if package_name and class_name:  # Exit loop if both are found
                        break
        except (FileNotFoundError, IOError) as e:
            self.logger.error(f"Error reading file {self.src_file_path}: {e}")
            raise

        return package_name, class_name

    def parse_json_diff_coverage_report(self) -> Tuple[List[int], List[int], float]:
        """
        Parses a JSON-formatted diff coverage report to extract covered lines, missed lines,
        and the coverage percentage for the specified src_file_path.
        Returns:
            Tuple[List[int], List[int], float]: A tuple containing lists of covered and missed lines,
                                                and the coverage percentage.
        """
        with open(self.diff_coverage_report_path, "r") as file:
            report_data = json.load(file)

        # Create relative path components of `src_file_path` for matching
        src_relative_path = os.path.relpath(self.src_file_path)
        src_relative_components = src_relative_path.split(os.sep)

        # Initialize variables for covered and missed lines
        relevant_stats = None

        for file_path, stats in report_data["src_stats"].items():
            # Split the JSON's file path into components
            file_path_components = file_path.split(os.sep)

            # Match if the JSON path ends with the same components as `src_file_path`
            if file_path_components[-len(src_relative_components) :] == src_relative_components:
                relevant_stats = stats
                break

        # If a match is found, extract the data
        if relevant_stats:
            covered_lines = relevant_stats["covered_lines"]
            violation_lines = relevant_stats["violation_lines"]
            coverage_percentage = relevant_stats["percent_covered"] / 100 
        else:
            covered_lines = []
            violation_lines = []
            coverage_percentage = 0.0

        # Diff cover thường không có chi tiết branch coverage mặc định, trả về dữ liệu rỗng.
        return covered_lines, violation_lines, coverage_percentage, 0.0, {}

    def get_file_extension(self, filename: str) -> str | None:
        """Get the file extension from a given filename."""
        return os.path.splitext(filename)[1].lstrip(".")
