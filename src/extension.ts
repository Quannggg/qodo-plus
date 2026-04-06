import * as vscode from 'vscode';
import * as path from 'path';
import { spawn, exec } from 'child_process';
import * as os from 'os';
import * as fs from 'fs';

const outputChannel = vscode.window.createOutputChannel("Qodo Cover");

function runStreamedCommand(command: string, args: string[], cwd: string, outputChannel: vscode.OutputChannel): Promise<void> {
    return new Promise((resolve, reject) => {
        outputChannel.appendLine(`\n[CMD] ${command} ${args.join(' ')}`);
        
        const isWindows = os.platform() === 'win32';
        const childProcess = spawn(command, args, { cwd, shell: isWindows });

        // stream log for stdout
        childProcess.stdout.on('data', (data) => {
            outputChannel.append(data.toString());
        });

        // stream log for stderr
        childProcess.stderr.on('data', (data) => {
            outputChannel.append(data.toString());
        });

        childProcess.on('close', (code) => {
            if (code === 0) {
                resolve();
            } else {
                reject(new Error(`Command failed with exit code ${code}`));
            }
        });

        childProcess.on('error', (err) => {
            reject(err);
        });
    });
}
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
        title: "Qodo Plus: Installing Extension Environment (Check Output)",
        cancellable: true
    }, async (progress) => {
        try {
            // show output and logs
            outputChannel.show(true);
            
            // create venv
            progress.report({ message: "Creating Extension venv..." });
            outputChannel.appendLine(`\n[INFO] Creating Extension venv...`);
            
            // arguments for runStreamedCommand
            const pythonCmd = isWindows ? 'py' : 'python3';
            const pythonArgs = isWindows ? ['-3.11', '-m', 'venv', 'venv'] : ['-m', 'venv', 'venv'];
            
            await runStreamedCommand(pythonCmd, pythonArgs, qodoCoverDir, outputChannel);

            // install cover-agent dependencies
            progress.report({ message: "Installing cover-agent dependencies..." });
            outputChannel.appendLine(`\n[INFO] Installing cover-agent...`);
            
            const pipCmd = isWindows ? path.join('venv', 'Scripts', 'pip') : path.join('venv', 'bin', 'pip');
            
            // pip install -e .
            await runStreamedCommand(pipCmd, ['install', '-e', '.'], qodoCoverDir, outputChannel);
            
            outputChannel.appendLine(`\n[INFO] Extension environment setup complete!`);
            return true;
        } catch (error: any) {
            vscode.window.showErrorMessage(`Extension Env Error: Check Output panel for details.`);
            outputChannel.appendLine(`\n[ERROR] Extension setup failed: ${error.message}`);
            return false;
        }
    });
}
// Create venv, install pytest and dependencies for the current workspace
async function setupWorkspaceEnvironment(workspaceRoot: string, outputChannel: vscode.OutputChannel): Promise<boolean> {
    const isWindows = os.platform() === 'win32';
    const venvPath = path.join(workspaceRoot, 'venv');
    const pipCmd = isWindows ? path.join(venvPath, 'Scripts', 'pip') : path.join(venvPath, 'bin', 'pip');
    const pythonCmd = isWindows ? 'py' : 'python3';
    const pythonArgs = isWindows ? ['-3.11', '-m', 'venv', 'venv'] : ['-m', 'venv', 'venv'];
    
    // marker File
    const markerPath = path.join(venvPath, '.qodo_env_ready');
    if (fs.existsSync(venvPath) && fs.existsSync(markerPath)) {
        outputChannel.appendLine(`[INFO] Workspace environment already configured. Skipping install.`);
        return true;
    }

    return await vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Qodo Plus: Preparing Workspace Environment (Check Output Panel)",
        cancellable: true
    }, async (progress) => {
        try {
            // show output and logs
            outputChannel.show(true);

            // create venv if not exist
            if (!fs.existsSync(venvPath)) {
                outputChannel.appendLine(`[INFO] Creating workspace venv at ${venvPath}`);
                progress.report({ message: "Creating virtual environment..." });
                await runStreamedCommand(pythonCmd, pythonArgs, workspaceRoot, outputChannel);
            }

            // install pytest and tools
            progress.report({ message: "Installing testing tools..." });
            outputChannel.appendLine(`[INFO] Installing pytest and tools...`);
            await runStreamedCommand(pipCmd, [
                'install',
                'pytest',
                'pytest-cov',
                'pytest-twisted',
                'pytest-asyncio',
                'pytest-timeout',
                'pytest-xdist',
                'pytest-mock',
                'twisted'
            ], workspaceRoot, outputChannel);

            // install dependencies from requirements.txt if exist, otherwise try pip install -e .
            const reqPath = path.join(workspaceRoot, 'requirements.txt');
            if (fs.existsSync(reqPath)) {
                progress.report({ message: "Installing from requirements.txt..." });
                outputChannel.appendLine(`[INFO] Found requirements.txt. Installing dependencies...`);
                await runStreamedCommand(pipCmd, ['install', '-r', 'requirements.txt'], workspaceRoot, outputChannel);
            } else {
                progress.report({ message: "Running pip install -e ." });
                outputChannel.appendLine(`[INFO] No requirements.txt found. Running pip install -e .`);
                try {
                    await runStreamedCommand(pipCmd, ['install', '-e', '.'], workspaceRoot, outputChannel);
                } catch (installErr: any) {
                    outputChannel.appendLine(`[WARN] 'pip install .' skipped: Directory does not contain a valid package setup.`);
                }
            }

            fs.writeFileSync(markerPath, `Setup completed at ${new Date().toISOString()}`);

            outputChannel.appendLine(`\n[INFO] Workspace environment ready!`);
            return true;
        } catch (error: any) {
            vscode.window.showErrorMessage(`Workspace Env Error: Check Output channel for details.`);
            outputChannel.appendLine(`\n[ERROR] Workspace setup failed: ${error.message}`);
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