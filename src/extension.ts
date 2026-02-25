import * as vscode from 'vscode';
import * as path from 'path';
import { spawn, exec } from 'child_process';
import * as os from 'os';
import * as fs from 'fs';
import * as util from 'util';

const outputChannel = vscode.window.createOutputChannel("Qodo Cover");
const execAsync = util.promisify(exec);
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
        title: "Qodo Plus: Installing the Python environment",
        cancellable: false
    }, async (progress) => {
        try {
            outputChannel.show(true);
            outputChannel.appendLine(`[INFO] Creating a Virtual Environment (venv)`);
            
            // Create environment
            const pythonCmd = isWindows ? 'py' : 'python3';
            await execAsync(`${pythonCmd} -3.11 -m venv venv`, { cwd: qodoCoverDir });

            // Install dependency
            progress.report({ message: "Downloading the library (this may take a few minutes)" });
            outputChannel.appendLine(`[INFO] Running pip install -e .`);
            
            const pipCmd = isWindows ? path.join('venv', 'Scripts', 'pip') : path.join('venv', 'bin', 'pip');
            const { stdout, stderr } = await execAsync(`${pipCmd} install -e .`, { cwd: qodoCoverDir });
            
            outputChannel.appendLine(stdout);
            if (stderr) {outputChannel.appendLine(`[WARN] ${stderr}`);}
            
            outputChannel.appendLine(`[INFO] Python environment setup complete`);
            vscode.window.showInformationMessage("Qodo Plus: Environment setup complete. Starting test generation");
            return true;

        } catch (error: any) {
            vscode.window.showErrorMessage(`Environment setup error: Please check if Python is installed on your machine`);
            outputChannel.appendLine(`[ERROR] ${error.message}`);
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

        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage('You need to open the project folder');
            return;
        }

        // BASIC INFORMATION ABOU THE PATH
        const workspaceRoot = workspaceFolders[0].uri.fsPath;
        const sourceAbsPath = editor.document.fileName;
        const toPosixPath = (p: string) => p.split(path.sep).join('/');
        
        // posix path
        const sourceRelPath = toPosixPath(path.relative(workspaceRoot, sourceAbsPath));
        const fileName = path.basename(sourceAbsPath);
        const sourceDir = toPosixPath(path.dirname(sourceRelPath));

        // READ THE ENTIRE CONFIGURATION FROM SETTINGS
        const possibleEnvKeys = [
            'OPENAI_API_KEY',
            'FIREWORKS_AI_API_KEY',
            'DEEPSEEK_API_KEY',
            'ANTHROPIC_API_KEY',
            'GEMINI_API_KEY',
            'GROQ_API_KEY',
            'QODO_API_KEY'
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
        const testCmdTpl = config.get<string>('testCommand') || 'pytest {testFilePath} --cov={sourceDir} --cov-branch --cov-report=xml --cov-report=html';
        const coverageType = config.get<string>('coverageType') || 'cobertura';
        const desiredCoverage = config.get<number>('desiredCoverage') ?? 100;
        const maxIterations = config.get<number>('maxIterations') ?? 3;
        const maxFixAttempts = config.get<number>('maxFixAttempts') ?? 1;

        // PLACEHOLDERS
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

        const isSetupSuccess = await setupPythonEnvironment(context, outputChannel);
        if (!isSetupSuccess) {
            return; 
        }
        // CREATE TEST FOLDER IF NOT EXIST
        const testDirAbs = path.join(workspaceRoot, path.dirname(finalTestPath));
        if (!fs.existsSync(testDirAbs)) {
            try {
                fs.mkdirSync(testDirAbs, { recursive: true });
            } catch (err: any) {
                vscode.window.showErrorMessage(`Unable to create test folder: ${err.message}`);
                return;
            }
        }

        // FIND FILE EXE COVER-AGENT
        const isWindows = os.platform() === 'win32';
        const venvRoot = path.join(context.extensionPath, 'python_service', 'qodo-cover', 'venv');
        const coverAgentPath = path.join(
            venvRoot, 
            isWindows ? 'Scripts' : 'bin', 
            isWindows ? 'cover-agent.exe' : 'cover-agent'
        );

        // PASS THE ENTIRE CONFIGURATION INTO THE ARGS ARRAY 
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

        // RUN
        outputChannel.show(true);
        outputChannel.clear();
        outputChannel.appendLine(`[INFO] Start running Qodo Cover`);
        outputChannel.appendLine(`[CMD] "${coverAgentPath}" ${args.join(' ')}`);
        
        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Qodo Plus: Generating tests with AI",
            cancellable: true // Cancelable
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

                // Listen event cancel
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