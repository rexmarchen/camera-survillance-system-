# 🚀 CamFu Quick Start Guide

**CamFu** is an intelligent CCTV surveillance application featuring real-time AI priority detection, crowd estimation, anomaly behavior detection, and dynamic grid auto-layout.

---

## ⚡ 1-Click Launch (Recommended)

### **Windows**
Simply double-click:
```bat
CamFu.bat
```
*Or in PowerShell:*
```powershell
powershell -ExecutionPolicy Bypass -File .\run-camfu.ps1
```

### **Linux / macOS**
```bash
chmod +x run-camfu.sh
./run-camfu.sh
```

---

## 📋 Prerequisites
Only two standard runtimes are required:
1. **Java 21+** (from [Adoptium Temurin](https://adoptium.net/) or [Oracle](https://www.oracle.com/java/technologies/downloads/))
2. **Python 3.9+** (from [python.org](https://www.python.org/downloads/))

> **Note:** You do **not** need to install Maven, MySQL, or VLC manually:
> - **Maven Wrapper (`mvnw.cmd` / `mvnw`)** is included and handles dependencies automatically.
> - **Embedded SQLite (`camfu.db`)** is built-in; MySQL is optional.
> - **Python packages** (`opencv-python`, `flask`, `flask-cors`, `pyyaml`, `requests`) are automatically installed on first run if missing.

---

## 🌐 Live AI Dashboard
While CamFu is running, you can also view live analytics in your web browser:
- **Web Dashboard**: [http://localhost:5000](http://localhost:5000)
- **Health Check**: [http://localhost:5000/health](http://localhost:5000/health)
- **Live Scores API**: [http://localhost:5000/api/scores](http://localhost:5000/api/scores)

---

## 🎯 Features
- **Dynamic Smart Grid**: Highest-activity camera automatically promotes to a large **⭐ PRIORITY** hero tile. Idle feeds are dimmed.
- **Motion & Crowd Detection**: Real-time OpenCV MOG2 background subtraction with contour filtering.
- **Anomaly Detection**: Flags sudden speed surges, panic, or chaos with **🔴 ALERT** tags.
- **Automatic Recording**: Meaningful events are automatically recorded to the `recordings/` directory.
