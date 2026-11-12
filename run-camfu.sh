#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "====================================================="
echo " CamFu | Intelligent Surveillance System"
echo "====================================================="

# Check Java
if ! command -v java &> /dev/null; then
    echo "[ERROR] Java is not installed. Please install Java 21+."
    exit 1
fi

# Locate Maven
if command -v mvn &> /dev/null; then
    MVN_CMD="mvn"
elif [ -f "./mvnw" ]; then
    chmod +x ./mvnw
    MVN_CMD="./mvnw"
else
    echo "[ERROR] Maven is not installed and mvnw wrapper not found."
    exit 1
fi

# Python dependencies
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python is not installed."
    exit 1
fi

$PYTHON_CMD -c "import flask, flask_cors, cv2, yaml, requests" 2>/dev/null || {
    echo "[INFO] Installing Python dependencies..."
    $PYTHON_CMD -m pip install -r python/requirements.txt
}

# Classpath
if [ ! -f "cp.txt" ] || [ ! -s "cp.txt" ]; then
    echo "[INFO] Generating classpath..."
    $MVN_CMD dependency:build-classpath -Dmdep.outputFile=cp.txt -q
fi

# Compile
if [ ! -d "target/classes" ]; then
    echo "[INFO] Compiling classes..."
    $MVN_CMD compiler:compile resources:resources -q
fi

CP="target/classes:$(cat cp.txt)"

java -cp "$CP" com.camfu.surveillance.Main
