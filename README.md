# Qodo Plus

Qodo Plus is an AI-powered VS Code extension that automatically generates, refines, and validates test cases for your Python projects.

## Features
* **AI-Powered Generation**: Automatically generates unit tests using advanced AI models (DeepSeek, OpenAI, etc.).
* **Iterative Refinement**: Self-heals and improves tests based on tests failed, coverage reports and error logs.
* **Auto Environment Setup**: Automatically sets up the required Python virtual environment (`venv`) on the first run.
* **Fully Customizable**: Flexible configuration for test commands, file paths, and coverage targets using dynamic placeholders.

## Requirements
* Python 3.x installed on your machine.
* An API Key for the AI model (e.g., DeepSeek, OpenAI, or Fireworks AI).

## Extension Settings

This extension contributes the following settings. You can access them by opening VS Code Settings (`Ctrl + ,`) and searching for **Qodo Plus**:

* `qodoPlus.apiKey`: **(Required)** Your AI provider API key.
* `qodoPlus.model`: Select the AI model to use (default: `deepseek/deepseek-chat`).
* `qodoPlus.sourceFilePath`: Template for the source file path. Supports placeholders like `{relativeFilePath}`, `{fileName}`, and `{sourceDir}`. (default: `{relativeFilePath}`).
* `qodoPlus.testFilePath`: Template for the generated test file path. Supports the same placeholders. (default: `tests/test_{fileName}`).
* `qodoPlus.testCommand`: The command used to execute tests and generate coverage. Supports `{testFilePath}` and `{sourceDir}`. (default: `pytest {testFilePath} --cov={sourceDir} --cov-branch --cov-report=xml --cov-report=html`).
* `qodoPlus.codeCoverageReportPath`: The path where the coverage report XML will be saved (default: `coverage.xml`).
* `qodoPlus.coverageType`: The format of the coverage report (default: `cobertura`).
* `qodoPlus.desiredCoverage`: The target code coverage percentage the AI should aim for, from 0 to 100 (default: `100`).
* `qodoPlus.maxIterations`: The maximum number of iterations the AI will run to improve tests and coverage (default: `3`).
* `qodoPlus.maxFixAttempts`: The maximum number of attempts the AI will make to fix failing tests within a single iteration (default: `1`).

## Known Issues

Please report any issues on the GitHub repository.

## Release Notes

### 0.0.1
Initial release of Qodo Plus.