@echo off
echo Installation des dépendances...
pip install -r requirements.txt

echo Lancement de CXS-Graph...
python CXS-graph.py

pause
