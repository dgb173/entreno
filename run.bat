@echo off
echo Instalando dependencias de Python...
py -m pip install -r requirements.txt

echo Instalando Playwright...
py -m playwright install chromium

echo Ejecutando la aplicacion Streamlit...
py -m streamlit run app.py

pause