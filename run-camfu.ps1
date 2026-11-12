# CamFu Launcher Script
$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$m2Repo = Join-Path $env:USERPROFILE ".m2\repository\org\openjfx"
$cpFile = Join-Path $projectDir "cp.txt"

# Add Maven to PATH if available in user profile
$mvnDirs = @(
    (Join-Path $env:USERPROFILE ".maven\apache-maven-3.9.16\bin"),
    (Join-Path $env:USERPROFILE ".m2\bin")
)
foreach ($dir in $mvnDirs) {
    if (Test-Path $dir) {
        $env:PATH = "$dir;$env:PATH"
        break
    }
}

# Generate classpath file if missing
if (-not (Test-Path $cpFile)) {
    Write-Host "Generating dependency classpath..."
    mvn dependency:build-classpath "-Dmdep.outputFile=cp.txt" -q
}

# Compile latest changes if classes directory is missing
$classesDir = Join-Path $projectDir "target\classes"
if (-not (Test-Path $classesDir)) {
    Write-Host "Compiling classes..."
    mvn compiler:compile resources:resources -q
}

$cpContent = (Get-Content $cpFile -Raw).Trim()
$fullClasspath = "target\classes;$cpContent"

# Save cp.args for cmd/argument file support
$targetDir = Join-Path $projectDir "target"
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}
[System.IO.File]::WriteAllText((Join-Path $targetDir "cp.args"), "-cp`n$fullClasspath")

# Construct module path with JavaFX modules
$modulePath = @(
    "$m2Repo\javafx-base\21\javafx-base-21-win.jar",
    "$m2Repo\javafx-controls\21\javafx-controls-21-win.jar",
    "$m2Repo\javafx-fxml\21\javafx-fxml-21-win.jar",
    "$m2Repo\javafx-graphics\21\javafx-graphics-21-win.jar",
    "$m2Repo\javafx-swing\21\javafx-swing-21-win.jar"
) -join ";"

Write-Host "CamFu - Intelligent Surveillance System"
Write-Host "======================================="
Write-Host "Launching CamFu Surveillance UI..."

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

Write-Host "Application exited"

