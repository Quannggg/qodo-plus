# Qodo Plus

Qodo Plus is an AI-powered VS Code extension that automatically generates, refines, and validates test cases for your Python projects. 

Built as an advanced evolution of the original [Qodo Cover](python_service\qodo-cover\README_QODO_COVER.md), Qodo Plus wraps the core test-generation capabilities into a seamless IDE experience and introduces a robust **LLM-driven Self-Healing Engine**.

## The Core Development

The original Qodo Cover operates on a **"fire and forget"** mechanism: it generates test cases, but if those tests fail during execution, they are simply discarded or left broken. 

**Qodo Plus** directly solves this limitation. Instead of abandoning failed tests, it implements a closed-loop **Self-Healing** process:
1. **Analyzes** the failure (stderr, stack traces, and coverage gaps).
2. **Consults** the LLM to propose patches for the broken test code.
3. **Applies** the fixes and re-runs the suite iteratively until the test passes or hits the maximum iteration limit.

## Key Features

* **AI-Powered Generation**: Automatically generates unit tests using advanced AI models (DeepSeek, OpenAI, etc.).
* **Iterative Refinement (Self-Healing)**: Actively self-corrects and improves tests based on execution failures, coverage XML reports, and error logs.
* **Auto Environment Setup**: Automatically provisions the required Python virtual environment (`venv`) and installs testing dependencies on the first run.
* **Fully Customizable**: Flexible configuration for test commands, file paths, and coverage targets using dynamic placeholders within VS Code.

## Experimental Results

Extensive experimental research conducted in 2026 targeting 10 complex open-source Python projects (including [scrapy](https://github.com/scrapy/scrapy), [HanLP](https://github.com/hankcs/hanlp), [tqdm](https://github.com/tqdm/tqdm), [Gymnasium](https://github.com/Farama-Foundation/Gymnasium), [django-rest-framework](https://github.com/encode/django-rest-framework), [pipenv](https://github.com/pypa/pipenv), [locust](https://github.com/locustio/locust), [flask](https://github.com/pallets/flask), [localstack](https://github.com/localstack/localstack) and [openai-python](https://github.com/openai/openai-python)) demonstrated the significant impact of the self-healing architecture. Compared to the baseline Qodo Cover, Qodo Plus consistently delivers:

* **Line Coverage Boost:** Achieves an absolute increase of **8-14%** in total line coverage by successfully salvaging and fixing generated tests that the original tool would have discarded.
* **Branch Coverage Boost:** Delivers an impressive **12-20%** increase in branch coverage, ensuring that edge cases, conditional statements, and complex logical paths are thoroughly validated by the AI.

## Installation

You can install and run Qodo Plus either by using the pre-packaged extension file or by building it directly from the source code.

### Option A: Quick Install (For End-Users)
1. Download the latest `qodo-plus-x.x.x.vsix` file from the repository's [Releases](https://github.com/Quannggg/qodo-plus/releases) page.
2. Open VS Code and navigate to the **Extensions** view (`Ctrl+Shift+X` or `Cmd+Shift+X`).
3. Click the `...` menu at the top right of the Extensions panel and select **"Install from VSIX..."**.
4. Select the downloaded `.vsix` file and reload VS Code if prompted.

### Option B: Run from Source (For Developers & Reviewers)
If you want to evaluate the source code, inspect the self-healing logic, or run it in a development environment:

1. **Prerequisites:** Ensure you have [Node.js](https://nodejs.org/) and [Git](https://git-scm.com/) installed.
2. **Clone the repository:**
    ```bash
    git clone https://github.com/Quannggg/qodo-plus.git
    ```
3. **Install dependencies:**
    ```bash
    cd qodo-plus
    npm install
    ```
4. **Run the extension in development mode:** Press F5 in VS Code. This will open a new Extension Development Host window where **Qodo Plus** is loaded and ready to test.

## Extension Settings

Before running the extension, configure your AI provider. Open VS Code Settings (Ctrl + ,), search for **Qodo Plus**, and configure the following:

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


## Usage & Demo

Qodo Plus is designed to handle complex, real-world Python projects. It has been successfully tested on 10 open-source python repositories which have the top stars on [GitHub](https://gitstar-ranking.com/repositories)


### Step-by-step Execution

In development mode, you can easily test the extension on any Python project. Follow these steps:

1. **Open a Python project:** Open the root directory of your Python project in VS Code.
2. **Select a source file:** Open any Python source file you want to generate tests for.
3. **Run Qodo Plus:** 
    - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) to open the Command Palette.
    - Type `Qodo Plus: Generate Tests` and select it.
4. **Watch the magic happen:** The extension will automatically generate tests, run them, and iteratively improve them based on failures and coverage gaps. You can monitor the output in the VS Code terminal.

### Expected Workflow Log (Demonstrating Self-Healing)
Unlike traditional tools that stop after generating bad code, Qodo Plus actively works to fix it. Notice the loop below:

```text
2026-05-05 22:41:27,467 - cover_agent.unit_test_validator - INFO - Received potential fix from AI. Retrying validation
2026-05-05 22:41:27,468 - cover_agent.unit_test_validator - INFO - Running test (Attempt 2/3) with command: "venv\Scripts\pytest tests\unit\test_core.py --cov=pipenv\vendor\click --cov-branch --cov-report=xml --cov-report=html"
2026-05-05 22:41:31,154 - cover_agent.unit_test_validator - INFO - Test passed and coverage increased after 2 attempts. Current coverage: 57.82%. Current branch coverage: 39.07%
2026-05-05 22:41:31,177 - cover_agent.unit_test_validator - INFO - Running build/test command to generate coverage report: "venv\Scripts\pytest tests\unit\test_core.py --cov=pipenv\vendor\click --cov-branch --cov-report=xml --cov-report=html"
2026-05-05 22:41:34,278 - cover_agent.unit_test_validator - INFO - Initial coverage: 57.82%
2026-05-05 22:41:34,278 - cover_agent.unit_test_validator - INFO - Initial branch coverage: 39.07%
2026-05-05 22:41:34,278 - cover_agent.cover_agent - INFO - Iteration 2 of 2.
2026-05-05 22:41:34,278 - cover_agent.cover_agent - INFO - Current Coverage: 57.82%
2026-05-05 22:41:34,278 - cover_agent.cover_agent - INFO - Desired Coverage: 100%
```

## Acknowledgements & License

This project is built upon the core functionalities of the original [Qodo Cover](https://github.com/qodo-ai/qodo-cover) repository. Qodo Plus is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.

## Known Issues

Please report any issues on the GitHub repository.

## Release Notes

### 0.0.1
Added full extraction and validation for Branch Coverage metrics.