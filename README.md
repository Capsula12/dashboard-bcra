# Tablero BCRA - Paquete rápido

Este paquete incluye:
- `app.py` (dashboard Streamlit)
- `requirements.txt` (dependencias)
- `run_dashboard.bat` (Windows CMD, auto-setup)
- `run_dashboard.ps1` (PowerShell, auto-setup)
- `data/` (poné acá tus CSV)

## Cómo usar (Windows - CMD)
1. Extraé el ZIP donde quieras.
2. Copiá tus **CSVs mensuales** a la carpeta `data/`.
3. Doble clic a `run_dashboard.bat` (o abrir CMD y ejecutar `run_dashboard.bat`).

El script:
- Crea `.venv` (si no existe)
- Instala dependencias
- Lanza `streamlit run app.py`

Si preferís PowerShell: clic derecho **Ejecutar con PowerShell** en `run_dashboard.ps1`.
Si hay bloqueo de scripts: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` y reintentar.

## macOS / Linux (manual)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
mkdir -p data
python -m streamlit run app.py
```

## Estructura esperada
```
carpeta/
  app.py
  requirements.txt
  run_dashboard.bat
  run_dashboard.ps1
  data/
    2024-03.csv
    2024-04.csv
    ...
```

## Notas
- Acepta CSV con `,` o `;` y varios encodings.
- La columna **Fecha** debería ser tipo `YYYYMM` (ej.: `202504`) o similar reconocible.
- Podés editar `app.py` para agregar más vistas o KPIs.
