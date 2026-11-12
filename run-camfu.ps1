# ============================================================
# CamFu - Intelligent Surveillance System
# Cross-Machine PowerShell Launcher
# ============================================================

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

$m2Repo = Join-Path $env:USERPROFILE ".m2\repository\org\openjfx"
$cpFile = Join-Path $projectDir "cp.txt"
$mvnwCmd = Join-Path $projectDir "mvnw.cmd"

Write-Host "====================================================="
Write-Host " CamFu | Intelligent Surveillance System"
Write-Host "====================================================="

# ── 1. Check Java ────────────────────────────────────────────
$javaCmd = Get-Command java -ErrorAction SilentlyContinue
if (-not $javaCmd) {
    Write-Host "[ERROR] Java is not installed or not in PATH."
    Write-Host "Please install Java 21+ from https://adoptium.net/ or https://www.oracle.com/java/technologies/downloads/"
    exit 1
}
Write-Host "[OK] Java detected."

# ── 2. Find or configure Maven ───────────────────────────────
$mvnCommand = ""
$systemMvn = Get-Command mvn -ErrorAction SilentlyContinue
if ($systemMvn) {
    $mvnCommand = "mvn"
} else {
    # Check known local user profile directories
    $mvnDirs = @(
        (Join-Path $env:USERPROFILE ".maven\apache-maven-3.9.16\bin"),
        (Join-Path $env:USERPROFILE ".m2\bin")
    )
    foreach ($dir in $mvnDirs) {
        if (Test-Path (Join-Path $dir "mvn.cmd")) {
            $env:PATH = "$dir;$env:PATH"
            $mvnCommand = "mvn"
            break
        }
    }
    if (-not $mvnCommand -and (Test-Path $mvnwCmd)) {
        Write-Host "[INFO] Using included Maven Wrapper (mvnw.cmd)..."
        $mvnCommand = $mvnwCmd
    }
}

function Invoke-Mvn {
    param([string[]]$MvnArgs)
    & $mvnCommand $MvnArgs
}

# ── 3. Check Python Dependencies ──────────────────────────────
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Host "[WARN] Python not found in PATH. AI background engine will be skipped."
} else {
    $null = & python -c "import flask, flask_cors, cv2, yaml, requests" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Python AI Engine dependencies detected."
    } else {
        Write-Host "[INFO] Installing required Python dependencies (first-time setup)..."
        & python -m pip install -r (Join-Path $projectDir "python\requirements.txt")
    }
}

# ── 4. Verify & Generate Classpath ────────────────────────────
$needClasspath = $false
if (-not (Test-Path $cpFile)) {
    $needClasspath = $true
} else {
    $content = (Get-Content $cpFile -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($content)) {
        $needClasspath = $true
    } else {
        $firstJar = $content.Split(';')[0].Trim()
        if (-not (Test-Path $firstJar)) {
            Write-Host "[INFO] Detected classpath from another computer. Regenerating for this machine..."
            $needClasspath = $true
        }
    }
}

if ($needClasspath) {
    Write-Host "[INFO] Resolving dependencies and generating local classpath..."
    Invoke-Mvn @("dependency:build-classpath", "-Dmdep.outputFile=cp.txt", "-q")
}

# ── 5. Ensure JavaFX Modules are present ──────────────────────
$fxBase = "$m2Repo\javafx-base\21\javafx-base-21-win.jar"
if (-not (Test-Path $fxBase)) {
    Write-Host "[INFO] Downloading JavaFX dependencies (first run only)..."
    Invoke-Mvn @("dependency:resolve", "-q")
}

# ── 6. Ensure Classes are Compiled ────────────────────────────
$mainClassFile = Join-Path $projectDir "target\classes\com\camfu\surveillance\Main.class"
if (-not (Test-Path $mainClassFile)) {
    Write-Host "[INFO] Compiling CamFu Java application..."
    Invoke-Mvn @("compiler:compile", "resources:resources", "-q")
}

# ── 7. Prepare Classpath & Arguments ──────────────────────────
$cpContent = (Get-Content $cpFile -Raw).Trim()
$fullClasspath = "target\classes;$cpContent"

$targetDir = Join-Path $projectDir "target"
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}
[System.IO.File]::WriteAllText((Join-Path $targetDir "cp.args"), "-cp`n$fullClasspath")

$modulePath = @(
    "$m2Repo\javafx-base\21\javafx-base-21-win.jar",
    "$m2Repo\javafx-controls\21\javafx-controls-21-win.jar",
    "$m2Repo\javafx-fxml\21\javafx-fxml-21-win.jar",
    "$m2Repo\javafx-graphics\21\javafx-graphics-21-win.jar",
    "$m2Repo\javafx-swing\21\javafx-swing-21-win.jar"
) -join ";"

# ── 8. Launch Application ─────────────────────────────────────
Write-Host "[OK] Launching CamFu Surveillance UI..."

& java `
    "-Djava.awt.headless=false" `
    "-Dprism.order=d3d" `
    "-Dprism.vsync=true" `
    "--module-path=$modulePath" `
    "--add-modules=javafx.controls,javafx.fxml,javafx.base,javafx.graphics,javafx.swing" `
    "--add-opens=javafx.graphics/com.sun.javafx.application=ALL-UNNAMED" `
    "--enable-native-access=ALL-UNNAMED,javafx.graphics" `
    "-cp" `
    $fullClasspath `
    "com.camfu.surveillance.Main"

Write-Host "CamFu Application exited."
