# Python EDA Tool

Use this tool when a dataset needs deeper analysis than the static website preview can provide.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r tools\requirements.txt
```

## Run

Put your local dataset inside the project `datasets/` folder, then run:

```powershell
python tools\eda_report.py
```

The tool automatically picks the newest supported file from `datasets/`.

You can still pass a file manually when needed:

```powershell
python tools\eda_report.py path\to\data.csv --output reports\sales_eda
python tools\eda_report.py path\to\data.xlsx --sheet Sheet1 --output reports\sales_eda
```

For Excel workbooks with multiple tabs, the default behavior is workbook-aware:

```powershell
python tools\eda_report.py path\to\workbook.xlsx --output reports\workbook_eda
```

The script first profiles every sheet, classifies each tab as source data, clean data, lookup/reference data, possible data, analysis output, or empty, then chooses the best primary sheet for detailed EDA. It also checks shared columns across data-like sheets to detect relationships before creating the report. Use `--sheet` only when you want to force a specific tab.

The script writes:

- `cleaned_data.csv`
- `eda_summary.json`
- `eda_report.md`
- `analysis_dashboard.html` with slicer-style filters, KPI cards, chart view, and filtered table preview
- chart images in `charts/`
- extra cleaned sheet CSVs in `cleaned_sheets/` when multiple data-like Excel sheets are found

It also scans the first rows of CSV, TSV, and Excel files to detect the real header row. This helps when a file starts with blank rows, title text, or Excel-generated columns such as `empty`, `empty_1`, or `Unnamed: 0`. For Excel files, the report records the workbook profile, selected primary sheet, sheet scores, and detected cross-sheet relationships. The HTML dashboard uses the detected category fields as slicers and the detected numeric fields as measures.

Supported inputs: CSV, TSV, JSON, XLS, and XLSX.
