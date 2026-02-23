import * as vscode from 'vscode';
import * as path from 'path';
import { spawn } from 'child_process';
import * as os from 'os';
import * as fs from 'fs';

const outputChannel = vscode.window.createOutputChannel("Qodo Cover");

export function activate(context: vscode.ExtensionContext) {
    console.log('Extension "qodo-plus" is active!');

    let disposable = vscode.commands.registerCommand('qodo-plus.generateTest', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('Hãy mở một file code Python trước!');
            return;
        }

        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage('Cần mở Folder dự án.');
            return;
        }

        // --- 1. BASIC INFORMATION ABOU THE PATH.---
        const workspaceRoot = workspaceFolders[0].uri.fsPath;
        const sourceAbsPath = editor.document.fileName;
        const toPosixPath = (p: string) => p.split(path.sep).join('/');
        
        // posix path
        const sourceRelPath = toPosixPath(path.relative(workspaceRoot, sourceAbsPath));
        const fileName = path.basename(sourceAbsPath);
        const sourceDir = toPosixPath(path.dirname(sourceRelPath));

        // --- 2. READ THE ENTIRE CONFIGURATION FROM SETTINGS ---
        const config = vscode.workspace.getConfiguration('qodoPlus');
        const apiKey = config.get<string>('apiKey') || process.env.OPENAI_API_KEY;

        if (!apiKey) {
             vscode.window.showErrorMessage('Please configure the API Key in Settings or environment variables.');
             return;
        }

        const model = config.get<string>('model') || 'deepseek/deepseek-chat';
        const sourcePathTpl = config.get<string>('sourceFilePath') || '{relativeFilePath}';
        const testPathTpl = config.get<string>('testFilePath') || 'tests/test_{fileName}';
        const reportPath = config.get<string>('codeCoverageReportPath') || 'coverage.xml';
        const testCmdTpl = config.get<string>('testCommand') || 'pytest "{testFilePath}" --cov="{sourceDir}" --cov-branch --cov-report=xml --cov-report=html';
        const coverageType = config.get<string>('coverageType') || 'cobertura';
        const desiredCoverage = config.get<number>('desiredCoverage') ?? 100;
        const maxIterations = config.get<number>('maxIterations') ?? 3;
        const maxFixAttempts = config.get<number>('maxFixAttempts') ?? 1;

        // --- 3. PLACEHOLDERS ---
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

        // --- 4. CREATE TEST FOLDER IF NOT EXIST ---
        const testDirAbs = path.join(workspaceRoot, path.dirname(finalTestPath));
        if (!fs.existsSync(testDirAbs)) {
            try {
                fs.mkdirSync(testDirAbs, { recursive: true });
            } catch (err: any) {
                vscode.window.showErrorMessage(`Không thể tạo thư mục test: ${err.message}`);
                return;
            }
        }

        // --- 5. FIND FILE EXE COVER-AGENT ---
        const isWindows = os.platform() === 'win32';
        const venvRoot = path.join(context.extensionPath, 'python_service', 'qodo-cover', 'venv');
        const coverAgentPath = path.join(
            venvRoot, 
            isWindows ? 'Scripts' : 'bin', 
            isWindows ? 'cover-agent.exe' : 'cover-agent'
        );

        if (!fs.existsSync(coverAgentPath)) {
            vscode.window.showErrorMessage(`Không tìm thấy file thực thi tại: ${coverAgentPath}.`);
            return;
        }

        // --- 6. PASS THE ENTIRE CONFIGURATION INTO THE ARGS ARRAY ---
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

        // --- 7. RUN ---
        outputChannel.show(true);
        outputChannel.clear();
        outputChannel.appendLine(`[INFO] Start running Qodo Cover...`);
        outputChannel.appendLine(`[CMD] "${coverAgentPath}" ${args.join(' ')}`);
        
        const childProcess = spawn(coverAgentPath, args, {
            cwd: workspaceRoot,
            env: { 
                ...process.env, 
                "OPENAI_API_KEY": apiKey,
                "OPENAI_BASE_URL": "https://api.deepseek.com"
            },
            shell: false 
        });

        childProcess.stdout.on('data', (data) => outputChannel.append(data.toString()));
        childProcess.stderr.on('data', (data) => outputChannel.append(data.toString()));

        childProcess.on('close', (code) => {
            if (code === 0) {
                vscode.window.showInformationMessage(`Success!`);
                outputChannel.appendLine(`\n[DONE] Complete.`);
            } else {
                vscode.window.showErrorMessage(`Error (Code: ${code}). Output.`);
                outputChannel.appendLine(`\n[ERROR] Exit code: ${code}`);
            }
        });

        childProcess.on('error', (err) => {
             vscode.window.showErrorMessage(`Launch error: ${err.message}`);
             outputChannel.appendLine(`[FATAL] ${err.message}`);
        });
    });

    context.subscriptions.push(disposable);
}

export function deactivate() {}