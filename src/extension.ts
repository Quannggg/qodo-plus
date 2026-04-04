import * as vscode from 'vscode';
import * as path from 'path';
import { spawn, exec } from 'child_process';
import * as os from 'os';
import * as fs from 'fs';
import * as util from 'util';

const outputChannel = vscode.window.createOutputChannel("Qodo Cover");
const execAsync = util.promisify(exec);

// Create a venv for the extension's internal use and install the cover-agent package
async function setupPythonEnvironment(context: vscode.ExtensionContext, outputChannel: vscode.OutputChannel): Promise<boolean> {
    const isWindows = os.platform() === 'win32';
    const qodoCoverDir = path.join(context.extensionPath, 'python_service', 'qodo-cover');
    const venvRoot = path.join(qodoCoverDir, 'venv');
    const coverAgentPath = path.join(
        venvRoot, 
        isWindows ? 'Scripts' : 'bin', 
        isWindows ? 'cover-agent.exe' : 'cover-agent'
    );

    if (fs.existsSync(coverAgentPath)) {
        return true; 
    }

    return await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Qodo Plus: Installing the Extension Python environment",
        cancellable: false
    }, async (progress) => {
        try {
            outputChannel.show(true);
            outputChannel.appendLine(`[INFO] Creating Extension venv...`);
            
            const pythonCmd = isWindows ? 'py -3.11' : 'python3';
            await execAsync(`${pythonCmd} -m venv venv`, { cwd: qodoCoverDir });

            progress.report({ message: "Installing cover-agent dependencies..." });
            const pipCmd = isWindows ? path.join('venv', 'Scripts', 'pip') : path.join('venv', 'bin', 'pip');
            const { stdout, stderr } = await execAsync(`${pipCmd} install .`, { cwd: qodoCoverDir });
            
            outputChannel.appendLine(stdout);
            if (stderr) {outputChannel.appendLine(`[WARN] ${stderr}`);}
            
            outputChannel.appendLine(`[INFO] Extension environment setup complete`);
            return true;
        } catch (error: any) {
            vscode.window.showErrorMessage(`Extension Env Error: ${error.message}`);
            return false;
        }
    });
}

// Create venv, install pytest and dependencies for the current workspace
async function setupWorkspaceEnvironment(workspaceRoot: string, outputChannel: vscode.OutputChannel): Promise<boolean> {
    const isWindows = os.platform() === 'win32';
    const venvPath = path.join(workspaceRoot, 'venv');
    const pipCmd = isWindows ? path.join(venvPath, 'Scripts', 'pip') : path.join(venvPath, 'bin', 'pip');

    return await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Qodo Plus: Preparing Workspace Environment",
        cancellable: false
    }, async (progress) => {
        try {
            // Create venv if not exists
            if (!fs.existsSync(venvPath)) {
                outputChannel.appendLine(`[INFO] Creating workspace venv at ${venvPath}`);
                await execAsync(`${isWindows ? 'py -3' : 'python3'} -m venv venv`, { cwd: workspaceRoot });
            }

            // install pytest and plugin 
            progress.report({ message: "Installing testing tools (pytest, pytest-cov)" });
            outputChannel.appendLine(`[INFO] Installing pytest and pytest-cov...`);
            await execAsync(`${pipCmd} install pytest pytest-cov pytest-twisted pytest-asyncio`, { cwd: workspaceRoot });

            // dependencies 
            const reqPath = path.join(workspaceRoot, 'requirements.txt');
            if (fs.existsSync(reqPath)) {
                progress.report({ message: "Installing dependencies from requirements.txt" });
                outputChannel.appendLine(`[INFO] Found requirements.txt. Installing dependencies`);
                await execAsync(`${pipCmd} install -r requirements.txt`, { cwd: workspaceRoot });
            } else {
                // requirements.txt or pip install .
                progress.report({ message: "Installing project as a package (pip install .)" });
                outputChannel.appendLine(`[INFO] No requirements.txt found. Running pip install .`);
                try {
                    await execAsync(`${pipCmd} install .`, { cwd: workspaceRoot });
                    outputChannel.appendLine(`[INFO] Successfully installed current directory as a package.`);
                } catch (installErr: any) {
                    outputChannel.appendLine(`[WARN] 'pip install .' skipped: Directory does not contain a valid package setup.`);
                }
            }

            outputChannel.appendLine(`[INFO] Workspace environment ready!`);
            return true;
        } catch (error: any) {
            vscode.window.showErrorMessage(`Workspace Env Error: ${error.message}`);
            outputChannel.appendLine(`[ERROR] Workspace setup failed: ${error.message}`);
            return false;
        }
    });
}

export function activate(context: vscode.ExtensionContext) {
    console.log('Extension "qodo-plus" is active!');

    let disposable = vscode.commands.registerCommand('qodo-plus.generateTest', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('Open a Python code file first');
            return;
        }

        const currentWorkspaceFolder = vscode.workspace.getWorkspaceFolder(editor.document.uri);
        if (!currentWorkspaceFolder) {
            vscode.window.showErrorMessage('The file currently open does not belong to any workspace!');
            return;
        }

        const workspaceRoot = currentWorkspaceFolder.uri.fsPath;
        const sourceAbsPath = editor.document.fileName;
        const toPosixPath = (p: string) => p.split(path.sep).join('/');
        
        const sourceRelPath = toPosixPath(path.relative(workspaceRoot, sourceAbsPath));
        const fileName = path.basename(sourceAbsPath);
        const sourceDir = toPosixPath(path.dirname(sourceRelPath));

        const possibleEnvKeys = [
            'OPENAI_API_KEY', 'FIREWORKS_AI_API_KEY', 'DEEPSEEK_API_KEY',
            'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'GROQ_API_KEY', 'QODO_API_KEY'
        ];
        const config = vscode.workspace.getConfiguration('qodoPlus');
        let apiKey = config.get<string>('apiKey');

        if(!apiKey) {
            for (const envKey of possibleEnvKeys) {
                if (process.env[envKey]) {
                    apiKey = process.env[envKey];
                    break;
                }
            }
        }

        if (!apiKey) {
             vscode.window.showErrorMessage('Please configure the API Key in Settings or environment variables.');
             return;
        }

        const model = config.get<string>('model') || 'deepseek/deepseek-chat';
        const baseUrl = config.get<string>('baseUrl') || 'https://api.deepseek.com';
        const sourcePathTpl = config.get<string>('sourceFilePath') || '{relativeFilePath}';
        const testPathTpl = config.get<string>('testFilePath') || 'tests/test_{fileName}';
        const reportPath = config.get<string>('codeCoverageReportPath') || 'coverage.xml';
        
        // testCommand 
        const isWindows = os.platform() === 'win32';
        const defaultTestCmd = isWindows 
            ? 'venv\\Scripts\\pytest {testFilePath} --cov={sourceDir} --cov-branch --cov-report=xml --cov-report=html'
            : 'venv/bin/pytest {testFilePath} --cov={sourceDir} --cov-branch --cov-report=xml --cov-report=html';
        
        const testCmdTpl = config.get<string>('testCommand') || defaultTestCmd;
        const coverageType = config.get<string>('coverageType') || 'cobertura';
        const desiredCoverage = config.get<number>('desiredCoverage') ?? 100;
        const maxIterations = config.get<number>('maxIterations') ?? 3;
        const maxFixAttempts = config.get<number>('maxFixAttempts') ?? 1;

        const finalSourcePath = sourcePathTpl
            .replace(/{relativeFilePath}/g, sourceRelPath)
            .replace(/{fileName}/g, fileName)
            .replace(/{sourceDir}/g, sourceDir);

        const finalTestPath = testPathTpl
            .replace(/{relativeFilePath}/g, sourceRelPath)
            .replace(/{fileName}/g, fileName)
            .replace(/{sourceDir}/g, sourceDir);

        const finalTestCommand = testCmdTpl
            .replace(/{testFilePath}/g, finalTestPath)
            .replace(/{sourceDir}/g, sourceDir);

        // extension environment
        const isExtSetupSuccess = await setupPythonEnvironment(context, outputChannel);
        if (!isExtSetupSuccess) {
            return; 
        }
        // workspace environment
        outputChannel.show(true);
        const isWorkspaceSetupSuccess = await setupWorkspaceEnvironment(workspaceRoot, outputChannel);
        if (!isWorkspaceSetupSuccess) {
            return;
        }
        const testDirAbs = path.join(workspaceRoot, path.dirname(finalTestPath));
        if (!fs.existsSync(testDirAbs)) {
            try {
                fs.mkdirSync(testDirAbs, { recursive: true });
            } catch (err: any) {
                vscode.window.showErrorMessage(`Unable to create test folder: ${err.message}`);
                return;
            }
        }

        const venvRoot = path.join(context.extensionPath, 'python_service', 'qodo-cover', 'venv');
        const coverAgentPath = path.join(
            venvRoot, 
            isWindows ? 'Scripts' : 'bin', 
            isWindows ? 'cover-agent.exe' : 'cover-agent'
        );

        const args = [
            '--model', model,
            '--source-file-path', finalSourcePath,
            '--test-file-path', finalTestPath,
            '--code-coverage-report-path', reportPath,
            '--test-command', finalTestCommand,
            '--coverage-type', coverageType,
            '--desired-coverage', desiredCoverage.toString(),
            '--max-iterations', maxIterations.toString(),
            '--max-fix-attempts', maxFixAttempts.toString()
        ];

        outputChannel.clear();
        outputChannel.appendLine(`[INFO] Start running Qodo Cover`);
        outputChannel.appendLine(`[CMD] "${coverAgentPath}" ${args.join(' ')}`);
        
        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Qodo Plus: Generating tests with AI",
            cancellable: true 
        }, async (progress, token) => {
            return new Promise<void>((resolve) => {
                
                const childProcess = spawn(coverAgentPath, args, {
                    cwd: workspaceRoot,
                    env: { 
                        ...process.env, 
                        "OPENAI_API_KEY": apiKey,
                        "OPENAI_BASE_URL": baseUrl
                    },
                    shell: false 
                });

                token.onCancellationRequested(() => {
                    childProcess.kill(); 
                    vscode.window.showWarningMessage("Qodo Plus: The test generation process has been cancelled");
                    outputChannel.appendLine(`\n[WARN] Process cancelled by user`);
                    resolve(); 
                });

                childProcess.stdout.on('data', (data) => outputChannel.append(data.toString()));
                childProcess.stderr.on('data', (data) => outputChannel.append(data.toString()));

                childProcess.on('close', (code) => {
                    if (token.isCancellationRequested) {
                        return; 
                    }
                    if (code === 0) {
                        vscode.window.showInformationMessage(`Qodo Plus: Successfully completed test generation`);
                        outputChannel.appendLine(`\n[DONE] Complete.`);
                    } else {
                        vscode.window.showErrorMessage(`Qodo Plus: Error (Code: ${code}). Check output for details`);
                        outputChannel.appendLine(`\n[ERROR] Exit code: ${code}`);
                    }
                    resolve();
                });

                childProcess.on('error', (err) => {
                    vscode.window.showErrorMessage(`Launch error: ${err.message}`);
                    outputChannel.appendLine(`[FATAL] ${err.message}`);
                    resolve();
                });
            });
        });
    });

    context.subscriptions.push(disposable);
}

export function deactivate() {}