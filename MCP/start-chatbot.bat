@echo off
echo ============================================
echo  Smart-Truck MCP Fleet Assistant
echo ============================================
echo.
echo Prerequisites:
echo   1. Backend API running on port 8000
echo   2. ML Service running on port 8001
echo.
echo Starting Streamlit chatbot...
echo (MCP servers start automatically via stdio)
echo.

cd /d "%~dp0smart-truck-client"
uv run streamlit run app.py --server.port 8501
