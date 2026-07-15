"""Generate a practical EDA report for CSV, TSV, JSON, XLS, and XLSX files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import html
import json
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


MISSING_TOKENS = {"", "na", "n/a", "none", "null", "nan", "-", "--"}
SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".json", ".xls", ".xlsx"}
DATA_SHEET_TOKENS = {
    "data",
    "dataset",
    "raw",
    "source",
    "input",
    "sales",
    "orders",
    "transactions",
    "fact",
}
DERIVED_SHEET_TOKENS = {
    "analysis",
    "analytics",
    "clean",
    "cleaned",
    "summary",
    "pivot",
    "dashboard",
    "chart",
    "graph",
    "report",
    "output",
    "kpi",
    "insight",
    "visual",
}
MEASURE_NAME_TOKENS = {
    "amount",
    "balance",
    "cost",
    "discount",
    "margin",
    "price",
    "profit",
    "revenue",
    "sales",
    "score",
    "total",
    "value",
}
QUANTITY_NAME_TOKENS = {"qty", "quantity", "unit", "units", "volume"}
DATE_NAME_TOKENS = {"date", "day", "month", "period", "time", "year"}
ID_NAME_TOKENS = {"id", "code", "key", "number", "no"}


@dataclass(frozen=True)
class DatasetLoadResult:
    data: pd.DataFrame
    source_sheet: str | None = None
    sheet_scores: list[dict[str, Any]] | None = None
    workbook_profile: list[dict[str, Any]] | None = None
    sheet_relationships: list[dict[str, Any]] | None = None
    data_sheets: dict[str, pd.DataFrame] | None = None


def normalize_cell(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def slugify_column(value: Any, index: int) -> str:
    text = normalize_cell(value)
    text = re.sub(r"^unnamed:\s*\d+$", "", text, flags=re.I)
    text = re.sub(r"^__empty(?:_\d+)?$", "", text, flags=re.I)
    text = re.sub(r"^empty(?:_\d+)?$", "", text, flags=re.I)
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    return text or f"column_{index + 1}"


def clean_columns(columns: list[Any]) -> list[str]:
    seen: dict[str, int] = {}
    cleaned = []
    for index, column in enumerate(columns):
        base = slugify_column(column, index)
        seen[base] = seen.get(base, 0) + 1
        cleaned.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return cleaned


def is_generated_header(value: Any) -> bool:
    text = normalize_cell(value)
    return not text or bool(re.match(r"^(unnamed:\s*\d+|__empty(?:_\d+)?|empty(?:_\d+)?)$", text, re.I))


def mostly_numeric(values: list[str]) -> bool:
    useful = [value for value in values if value]
    if not useful:
        return False

    numeric_count = 0
    for value in useful:
        parsed_value = pd.to_numeric(value.replace(",", ""), errors="coerce")
        if pd.notna(parsed_value):
            numeric_count += 1
    return numeric_count / len(useful) >= 0.7


def header_row_score(row: list[Any], next_rows: list[list[Any]]) -> float:
    values = [normalize_cell(value) for value in row]
    useful = [value for value in values if value and not is_generated_header(value)]
    if not useful:
        return 0

    unique_ratio = len(set(value.lower() for value in useful)) / len(useful)
    text_ratio = sum(bool(re.search(r"[A-Za-z]", value)) for value in useful) / len(useful)
    generated_penalty = sum(is_generated_header(value) for value in values) * 0.35
    numeric_penalty = 1.5 if mostly_numeric(useful) else 0
    data_support = 0

    if next_rows:
        width = max(len(values), 1)
        following_values = [
            normalize_cell(next_row[index]) if index < len(next_row) else ""
            for next_row in next_rows[:3]
            for index in range(width)
        ]
        data_support = min(2, sum(bool(value) for value in following_values) / width)

    return (len(useful) * 1.2) + (unique_ratio * 2) + (text_ratio * 2) + data_support - generated_penalty - numeric_penalty


def promote_detected_header(raw_df: pd.DataFrame) -> pd.DataFrame:
    table = raw_df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if table.empty:
        return table

    rows = table.head(12).values.tolist()
    scored_rows = [
        (index, header_row_score(row, rows[index + 1:]))
        for index, row in enumerate(rows)
    ]
    best_index, best_score = max(scored_rows, key=lambda item: item[1])
    first_score = scored_rows[0][1]
    first_has_generated_headers = any(is_generated_header(value) for value in rows[0])

    header_index = best_index if best_index > 0 and (best_score >= first_score + 1 or first_has_generated_headers) else 0
    headers = clean_columns(list(table.iloc[header_index]))
    data = table.iloc[header_index + 1:].copy()
    data.columns = headers
    return data.reset_index(drop=True)


def sheet_name_score(sheet_name: str) -> float:
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", sheet_name).strip("_").lower()
    tokens = set(filter(None, normalized.split("_")))
    score = 0.0
    if tokens & DATA_SHEET_TOKENS:
        score += 8
    if tokens & DERIVED_SHEET_TOKENS:
        score -= 10
    return score


def worksheet_data_score(sheet_name: str, sheet_index: int, raw_df: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    candidate = promote_detected_header(raw_df)
    if candidate.empty:
        return -1000, candidate

    rows = len(candidate)
    columns = len(candidate.columns)
    non_empty_ratio = float(candidate.notna().mean().mean()) if rows and columns else 0
    numeric_columns = len(candidate.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all").columns)
    date_columns = 0

    for column in candidate.columns:
        if candidate[column].dtype == "object":
            parsed_dates = pd.to_datetime(candidate[column], errors="coerce")
            if parsed_dates.notna().mean() >= 0.55:
                date_columns += 1

    duplicate_column_penalty = len(candidate.columns) - len(set(candidate.columns))
    small_summary_penalty = 12 if rows <= 10 and columns <= 8 else 0
    first_sheet_bonus = 1.5 if sheet_index == 0 else 0

    score = (
        sheet_name_score(sheet_name)
        + min(rows, 10000) / 150
        + min(columns, 60) * 0.8
        + non_empty_ratio * 8
        + min(numeric_columns, 12) * 1.4
        + min(date_columns, 4) * 1.6
        + first_sheet_bonus
        - duplicate_column_penalty * 2
        - small_summary_penalty
    )
    return score, candidate


def infer_sheet_role(sheet_name: str, score: float, candidate: pd.DataFrame) -> str:
    if candidate.empty:
        return "empty"

    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", sheet_name).strip("_").lower()
    tokens = set(filter(None, normalized.split("_")))
    rows = len(candidate)
    columns = len(candidate.columns)

    if tokens & {"analysis", "analytics", "dashboard", "chart", "graph", "report", "kpi", "pivot", "summary", "insight", "visual"}:
        return "analysis_output"
    if tokens & {"clean", "cleaned", "output"}:
        return "clean_data"
    if tokens & DATA_SHEET_TOKENS:
        return "source_data"
    if rows <= 30 and columns <= 5 and any("id" in column for column in candidate.columns):
        return "lookup_reference"
    if score >= 14 and rows > 10 and columns >= 3:
        return "source_data"
    if rows > 3 and columns >= 2:
        return "possible_data"
    return "unknown"


def profile_sheet(sheet_name: str, score: float, candidate: pd.DataFrame, role: str) -> dict[str, Any]:
    if candidate.empty:
        return {
            "sheet": sheet_name,
            "role": role,
            "score": round(float(score), 2),
            "rows": 0,
            "columns": 0,
            "column_names": [],
            "numeric_columns": 0,
            "date_columns": 0,
            "missing_rate": 0,
        }

    numeric_columns = len(candidate.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all").columns)
    date_columns = 0
    for column in candidate.columns:
        if candidate[column].dtype == "object":
            parsed_dates = pd.to_datetime(candidate[column], errors="coerce")
            if parsed_dates.notna().mean() >= 0.55:
                date_columns += 1

    return {
        "sheet": sheet_name,
        "role": role,
        "score": round(float(score), 2),
        "rows": int(len(candidate)),
        "columns": int(len(candidate.columns)),
        "column_names": list(candidate.columns),
        "numeric_columns": int(numeric_columns),
        "date_columns": int(date_columns),
        "missing_rate": round(float(candidate.isna().mean().mean() * 100), 2),
    }


def normalized_non_empty_values(series: pd.Series) -> set[str]:
    values = series.dropna().astype(str).str.strip().str.lower()
    return {value for value in values if value and value not in MISSING_TOKENS}


def detect_sheet_relationships(data_sheets: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    names = list(data_sheets)

    for left_index, left_name in enumerate(names):
        left = data_sheets[left_name]
        for right_name in names[left_index + 1:]:
            right = data_sheets[right_name]
            shared_columns = sorted(set(left.columns) & set(right.columns))

            for column in shared_columns:
                left_values = normalized_non_empty_values(left[column])
                right_values = normalized_non_empty_values(right[column])
                if not left_values or not right_values:
                    continue

                overlap = len(left_values & right_values)
                base = min(len(left_values), len(right_values))
                confidence = round((overlap / base) * 100, 1) if base else 0

                if overlap:
                    relationships.append({
                        "left_sheet": left_name,
                        "right_sheet": right_name,
                        "column": column,
                        "matching_values": int(overlap),
                        "confidence": confidence,
                    })

    return sorted(
        relationships,
        key=lambda item: (item["confidence"], item["matching_values"]),
        reverse=True,
    )[:15]


def load_excel_dataset(path: Path, sheet: str | int | None) -> DatasetLoadResult:
    if sheet is not None:
        workbook = pd.ExcelFile(path)
        sheet_name = workbook.sheet_names[sheet] if isinstance(sheet, int) else str(sheet)
        raw_df = pd.read_excel(workbook, sheet_name=sheet, header=None)
        score, data = worksheet_data_score(sheet_name, 0, raw_df)
        role = infer_sheet_role(sheet_name, score, data)
        return DatasetLoadResult(
            data=data,
            source_sheet=sheet_name,
            workbook_profile=[profile_sheet(sheet_name, score, data, role)],
            data_sheets={sheet_name: data},
        )

    workbook = pd.ExcelFile(path)
    scored_sheets: list[tuple[float, str, pd.DataFrame]] = []
    score_details: list[dict[str, Any]] = []
    workbook_profile: list[dict[str, Any]] = []
    data_sheets: dict[str, pd.DataFrame] = {}

    for index, sheet_name in enumerate(workbook.sheet_names):
        raw_df = pd.read_excel(workbook, sheet_name=sheet_name, header=None)
        score, candidate = worksheet_data_score(sheet_name, index, raw_df)
        role = infer_sheet_role(sheet_name, score, candidate)
        scored_sheets.append((score, sheet_name, candidate))
        score_details.append({
            "sheet": sheet_name,
            "role": role,
            "score": round(float(score), 2),
            "rows": int(len(candidate)),
            "columns": int(len(candidate.columns)) if not candidate.empty else 0,
        })
        workbook_profile.append(profile_sheet(sheet_name, score, candidate, role))
        if role in {"source_data", "clean_data", "lookup_reference", "possible_data"} and not candidate.empty:
            data_sheets[sheet_name] = candidate

    primary_candidates = [
        item for item in scored_sheets
        if infer_sheet_role(item[1], item[0], item[2]) in {"source_data", "possible_data"}
    ] or [
        item for item in scored_sheets
        if infer_sheet_role(item[1], item[0], item[2]) in {"clean_data", "lookup_reference"}
    ] or scored_sheets

    best_score, best_sheet, best_data = max(primary_candidates, key=lambda item: item[0])
    if best_data.empty:
        raise ValueError(f"No usable data sheet found in {path}.")

    score_details.sort(key=lambda item: item["score"], reverse=True)
    workbook_profile.sort(key=lambda item: item["score"], reverse=True)
    return DatasetLoadResult(
        data=best_data,
        source_sheet=best_sheet,
        sheet_scores=score_details,
        workbook_profile=workbook_profile,
        sheet_relationships=detect_sheet_relationships(data_sheets),
        data_sheets=data_sheets,
    )


def load_dataset(path: Path, sheet: str | int | None) -> DatasetLoadResult:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return DatasetLoadResult(data=promote_detected_header(pd.read_csv(path, header=None)))
    if suffix == ".tsv":
        return DatasetLoadResult(data=promote_detected_header(pd.read_csv(path, sep="\t", header=None)))
    if suffix == ".json":
        df = pd.read_json(path)
        df.columns = clean_columns(list(df.columns))
        return DatasetLoadResult(data=df)
    if suffix in {".xls", ".xlsx"}:
        return load_excel_dataset(path, sheet)
    raise ValueError(f"Unsupported file type: {suffix}")


def find_local_dataset(input_dir: Path) -> Path:
    input_dir.mkdir(parents=True, exist_ok=True)
    files = [
        path for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise FileNotFoundError(
            f"No dataset found in {input_dir.resolve()}. "
            f"Add a local file with one of these formats: {supported}."
        )

    return max(files, key=lambda path: path.stat().st_mtime)


def safe_filename(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z._-]+", "_", value).strip("_") or "sheet"


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = clean_columns(list(cleaned.columns))
    cleaned = cleaned.dropna(axis=0, how="all").dropna(axis=1, how="all")

    for column in cleaned.columns:
        if cleaned[column].dtype == "object":
            cleaned[column] = cleaned[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
            cleaned[column] = cleaned[column].replace(list(MISSING_TOKENS), np.nan)

            numeric_candidate = pd.to_numeric(
                cleaned[column].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            )
            if numeric_candidate.notna().mean() >= 0.75:
                cleaned[column] = numeric_candidate
                continue

            date_candidate = pd.to_datetime(cleaned[column], errors="coerce")
            if date_candidate.notna().mean() >= 0.75:
                cleaned[column] = date_candidate

    return cleaned


def column_profile(df: pd.DataFrame, column: str) -> dict[str, Any]:
    series = df[column]
    name = column.lower()
    normalized_name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_")
    non_null = series.dropna()
    unique_count = int(series.nunique(dropna=True))
    unique_ratio = unique_count / max(len(df), 1)
    missing_rate = round(float(series.isna().mean() * 100), 2) if len(df) else 0
    numeric_ratio = float(pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce").notna().mean()) if len(df) else 0
    date_ratio = 0.0

    if len(df) and not pd.api.types.is_numeric_dtype(series):
        date_ratio = float(pd.to_datetime(series, errors="coerce").notna().mean())

    is_identifier_name = bool(re.search(r"(^id$|_id$|^id_|row_?id|record_?id|order|invoice|uuid|code|key|serial|number|^no$)", normalized_name))
    is_year_name = bool(re.search(r"(^year$|fiscal_?year|calendar_?year|financial_?year)", normalized_name))

    if is_identifier_name and unique_ratio >= 0.55:
        role = "identifier"
    elif is_year_name:
        role = "date"
    elif pd.api.types.is_datetime64_any_dtype(series) or date_ratio >= 0.75 or any(token in name for token in DATE_NAME_TOKENS):
        role = "date"
    elif pd.api.types.is_numeric_dtype(series) or numeric_ratio >= 0.75:
        if any(token in name for token in MEASURE_NAME_TOKENS):
            role = "measure"
        elif any(token in name for token in QUANTITY_NAME_TOKENS):
            role = "quantity"
        elif unique_count <= min(20, max(2, len(df) // 3)):
            role = "numeric_category"
        else:
            role = "numeric"
    elif any(token in name for token in ["city", "state", "country", "region", "location", "segment", "category", "type", "status"]):
        role = "category"
    elif unique_count <= min(50, max(3, len(df) // 2)):
        role = "category"
    else:
        role = "text"

    sample_values = [safe_json(value) for value in non_null.head(5).tolist()]
    return {
        "column": column,
        "role": role,
        "missing_rate": missing_rate,
        "unique_count": unique_count,
        "unique_ratio": round(float(unique_ratio), 3),
        "numeric_ratio": round(float(numeric_ratio), 3),
        "date_ratio": round(float(date_ratio), 3),
        "sample_values": sample_values,
    }


def profile_columns(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [column_profile(df, column) for column in df.columns]


def classify_columns(df: pd.DataFrame) -> dict[str, str]:
    return {item["column"]: item["role"] for item in profile_columns(df)}


def safe_json(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).isoformat()
    if pd.isna(value):
        return None
    return value


def build_analysis_blueprint(df: pd.DataFrame, column_profiles: list[dict[str, Any]]) -> dict[str, Any]:
    role_map = {item["column"]: item["role"] for item in column_profiles}
    date_columns = [column for column, role in role_map.items() if role == "date"]
    category_columns = [
        column for column, role in role_map.items()
        if role in {"category", "numeric_category"}
    ]
    numeric_columns = list(df.select_dtypes(include=np.number).columns)
    measure_columns = [
        column for column in numeric_columns
        if role_map.get(column) in {"measure", "quantity", "numeric"}
    ]
    measure_columns = [
        column for column in measure_columns
        if role_map.get(column) != "identifier"
    ]
    slicer_columns = category_columns[:5]

    recommended_views = []
    if category_columns and measure_columns:
        recommended_views.append({
            "name": "Segment performance",
            "description": f"Compare {measure_columns[0]} by {category_columns[0]}.",
            "category": category_columns[0],
            "measure": measure_columns[0],
        })
    if date_columns and measure_columns:
        recommended_views.append({
            "name": "Time trend",
            "description": f"Track {measure_columns[0]} over {date_columns[0]}.",
            "date": date_columns[0],
            "measure": measure_columns[0],
        })
    if len(measure_columns) >= 2:
        recommended_views.append({
            "name": "Numeric relationship",
            "description": f"Check relationship between {measure_columns[0]} and {measure_columns[1]}.",
            "left": measure_columns[0],
            "right": measure_columns[1],
        })

    if not recommended_views:
        recommended_views.append({
            "name": "Data quality review",
            "description": "Review missing values, duplicate rows, and usable columns before deeper analysis.",
        })

    return {
        "date_columns": date_columns,
        "category_columns": category_columns,
        "measure_columns": measure_columns,
        "slicer_columns": slicer_columns,
        "default_category": category_columns[0] if category_columns else None,
        "default_measure": measure_columns[0] if measure_columns else None,
        "recommended_views": recommended_views,
    }


def dataframe_records(df: pd.DataFrame, max_rows: int = 5000) -> list[dict[str, Any]]:
    limited = df.head(max_rows).replace({np.nan: None})
    records = limited.to_dict(orient="records")
    return [
        {key: safe_json(value) for key, value in record.items()}
        for record in records
    ]


def create_charts(df: pd.DataFrame, charts_dir: Path) -> list[str]:
    charts_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    chart_paths: list[str] = []

    missing = df.isna().mean().sort_values(ascending=False).head(15)
    if not missing.empty:
        plt.figure(figsize=(10, 5))
        sns.barplot(x=missing.values * 100, y=missing.index, color="#2563eb")
        plt.xlabel("Missing %")
        plt.ylabel("")
        plt.title("Missing Values by Column")
        path = charts_dir / "missing_values.png"
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        chart_paths.append(str(path))

    numeric_cols = list(df.select_dtypes(include=np.number).columns)
    category_cols = [
        col for col in df.columns
        if not pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_datetime64_any_dtype(df[col])
    ]
    date_cols = list(df.select_dtypes(include=["datetime", "datetimetz"]).columns)

    for column in numeric_cols[:4]:
        series = df[column].dropna()
        if series.empty:
            continue
        plt.figure(figsize=(9, 5))
        sns.histplot(series, kde=True, color="#0f766e")
        plt.title(f"Distribution: {column}")
        path = charts_dir / f"distribution_{column}.png"
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        chart_paths.append(str(path))

    for column in category_cols[:4]:
        counts = df[column].astype(str).replace("nan", np.nan).dropna().value_counts().head(10)
        if counts.empty:
            continue
        plt.figure(figsize=(10, 5))
        sns.barplot(x=counts.values, y=counts.index, color="#7c3aed")
        plt.xlabel("Rows")
        plt.ylabel("")
        plt.title(f"Top Values: {column}")
        path = charts_dir / f"top_values_{column}.png"
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        chart_paths.append(str(path))

    if len(numeric_cols) >= 2:
        corr = df[numeric_cols].corr(numeric_only=True)
        plt.figure(figsize=(8, 6))
        sns.heatmap(corr, annot=True, cmap="vlag", center=0, fmt=".2f")
        plt.title("Numeric Correlation")
        path = charts_dir / "correlation_heatmap.png"
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        chart_paths.append(str(path))

    if date_cols and numeric_cols:
        monthly = (
            df[[date_cols[0], numeric_cols[0]]]
            .dropna()
            .set_index(date_cols[0])
            .resample("ME")[numeric_cols[0]]
            .sum()
        )
        if len(monthly) > 1:
            plt.figure(figsize=(10, 5))
            monthly.plot(color="#dc2626", marker="o")
            plt.title(f"Monthly Trend: {numeric_cols[0]}")
            plt.xlabel("")
            plt.ylabel(numeric_cols[0])
            path = charts_dir / "monthly_trend.png"
            plt.tight_layout()
            plt.savefig(path, dpi=160)
            plt.close()
            chart_paths.append(str(path))

    return chart_paths


def build_summary(
    df: pd.DataFrame,
    original_rows: int,
    source_sheet: str | None = None,
    sheet_scores: list[dict[str, Any]] | None = None,
    workbook_profile: list[dict[str, Any]] | None = None,
    sheet_relationships: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    column_profiles = profile_columns(df)
    roles = {item["column"]: item["role"] for item in column_profiles}
    analysis_blueprint = build_analysis_blueprint(df, column_profiles)
    missing = (df.isna().mean() * 100).round(2).sort_values(ascending=False)
    numeric_cols = list(df.select_dtypes(include=np.number).columns)

    correlations: list[dict[str, Any]] = []
    if len(numeric_cols) >= 2:
        corr = df[numeric_cols].corr(numeric_only=True).abs()
        pairs = []
        for left in corr.columns:
            for right in corr.columns:
                if left < right:
                    pairs.append((left, right, corr.loc[left, right]))
        correlations = [
            {"left": left, "right": right, "correlation": round(float(value), 3)}
            for left, right, value in sorted(pairs, key=lambda item: item[2], reverse=True)[:5]
        ]

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "source_sheet": source_sheet,
        "sheet_scores": sheet_scores or [],
        "workbook_profile": workbook_profile or [],
        "sheet_relationships": sheet_relationships or [],
        "column_names": list(df.columns),
        "column_profiles": column_profiles,
        "analysis_blueprint": analysis_blueprint,
        "rows_removed": int(original_rows - len(df)),
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_rate": round(float(df.duplicated().mean() * 100), 2) if len(df) else 0,
        "column_roles": roles,
        "missing_percent": {key: safe_json(value) for key, value in missing.items()},
        "numeric_summary": json.loads(df[numeric_cols].describe().round(3).to_json()) if numeric_cols else {},
        "top_correlations": correlations,
    }


def write_markdown_report(summary: dict[str, Any], chart_paths: list[str], output_dir: Path) -> None:
    def format_column_list(columns: list[str]) -> str:
        return ", ".join(f"`{column}`" for column in columns) or "None detected"

    lines = [
        "# EDA Report",
        "",
        "## Dataset Health",
        "",
        f"- Source sheet: {summary['source_sheet'] or 'Not applicable'}",
        f"- Rows: {summary['rows']}",
        f"- Columns: {summary['columns']}",
        f"- Rows removed during cleaning: {summary['rows_removed']}",
        f"- Duplicate rows: {summary['duplicate_rows']} ({summary['duplicate_rate']}%)",
        "",
        "## Detected Column Names",
        "",
    ]
    lines.extend(f"- `{column}`" for column in summary["column_names"])
    lines.extend([
        "",
        "## Column Roles",
        "",
    ])
    lines.extend(f"- `{column}`: {role}" for column, role in summary["column_roles"].items())

    blueprint = summary["analysis_blueprint"]
    lines.extend(["", "## Data Understanding", ""])
    lines.append(f"- Date columns: {format_column_list(blueprint['date_columns'])}")
    lines.append(f"- Category columns: {format_column_list(blueprint['category_columns'])}")
    lines.append(f"- Measure columns: {format_column_list(blueprint['measure_columns'])}")
    lines.append(f"- Slicer columns: {format_column_list(blueprint['slicer_columns'])}")
    lines.extend(["", "## Recommended Analysis Views", ""])
    lines.extend(f"- {item['name']}: {item['description']}" for item in blueprint["recommended_views"])

    if summary["workbook_profile"]:
        lines.extend(["", "## Workbook Understanding", ""])
        for item in summary["workbook_profile"][:12]:
            lines.append(
                f"- `{item['sheet']}`: {item['role']} "
                f"({item['rows']} rows x {item['columns']} columns, score {item['score']})"
            )

    if summary["sheet_relationships"]:
        lines.extend(["", "## Cross-Sheet Relationships", ""])
        for item in summary["sheet_relationships"][:10]:
            lines.append(
                f"- `{item['left_sheet']}` -> `{item['right_sheet']}` on `{item['column']}`: "
                f"{item['confidence']}% overlap across {item['matching_values']} matching values"
            )
    elif summary["workbook_profile"]:
        lines.extend(["", "## Cross-Sheet Relationships", ""])
        lines.append("- No strong shared-column relationship was detected between data-like sheets.")

    if summary["sheet_scores"]:
        lines.extend(["", "## Sheet Selection Scores", ""])
        for item in summary["sheet_scores"][:8]:
            lines.append(
                f"- `{item['sheet']}`: {item['role']}, score {item['score']} "
                f"({item['rows']} rows x {item['columns']} columns)"
            )

    lines.extend(["", "## Highest Missing Values", ""])
    for column, value in list(summary["missing_percent"].items())[:10]:
        lines.append(f"- `{column}`: {value}%")

    lines.extend(["", "## Strongest Numeric Relationships", ""])
    if summary["top_correlations"]:
        for item in summary["top_correlations"]:
            lines.append(f"- `{item['left']}` vs `{item['right']}`: {item['correlation']}")
    else:
        lines.append("- Not enough numeric columns for correlation analysis.")

    lines.extend(["", "## Charts", ""])
    lines.extend(f"- `{Path(path).relative_to(output_dir)}`" for path in chart_paths)
    (output_dir / "eda_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def json_for_script(value: Any) -> str:
    return json.dumps(value, default=safe_json).replace("</", "<\\/")


def write_html_dashboard(df: pd.DataFrame, summary: dict[str, Any], output_dir: Path) -> None:
    records_json = json_for_script(dataframe_records(df))
    summary_json = json_for_script(summary)
    title = html.escape(f"Analysis Dashboard - {summary['source_sheet'] or 'Dataset'}")
    dashboard = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#f8fafc;color:#0f172a}
header{padding:28px 32px;background:#0f172a;color:#fff}
header h1{margin:0 0 8px;font-size:28px}
header p{margin:0;color:#cbd5e1}
main{padding:28px 32px;display:grid;gap:24px}
.panel{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:20px;box-shadow:0 10px 25px rgba(15,23,42,.06)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}
.control-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
label span{display:block;font-size:12px;font-weight:700;text-transform:uppercase;color:#64748b;margin-bottom:6px}
select{width:100%;padding:10px 12px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:#0f172a}
.kpi{padding:18px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc}
.kpi span{display:block;color:#64748b;font-size:12px;font-weight:700;text-transform:uppercase}
.kpi strong{display:block;font-size:26px;margin-top:6px;color:#0369a1}
.bars{display:grid;gap:10px}
.bar-row{display:grid;grid-template-columns:minmax(120px,220px) 1fr 90px;gap:12px;align-items:center}
.bar-label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#334155}
.bar-track{height:26px;background:#e2e8f0;border-radius:5px;overflow:hidden}
.bar-fill{height:100%;background:linear-gradient(90deg,#0891b2,#2563eb)}
.bar-value{text-align:right;font-variant-numeric:tabular-nums;color:#0f172a}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:left}
th{position:sticky;top:0;background:#f1f5f9;color:#334155}
.table-wrap{max-height:420px;overflow:auto}
.note{color:#64748b;font-size:14px}
@media(max-width:700px){header,main{padding:20px}.bar-row{grid-template-columns:1fr}.bar-value{text-align:left}}
</style>
</head>
<body>
<header>
<h1>__TITLE__</h1>
<p>Interactive slicer view generated from the detected primary dataset.</p>
</header>
<main>
<section class="panel">
<h2>Slicers</h2>
<div class="control-grid" id="slicer-controls"></div>
</section>
<section class="panel">
<h2>Analysis View</h2>
<div class="control-grid">
<label><span>Category</span><select id="category-select"></select></label>
<label><span>Measure</span><select id="measure-select"></select></label>
</div>
</section>
<section class="grid">
<div class="kpi"><span>Filtered Rows</span><strong id="kpi-rows">0</strong></div>
<div class="kpi"><span>Total Measure</span><strong id="kpi-total">0</strong></div>
<div class="kpi"><span>Average Measure</span><strong id="kpi-average">0</strong></div>
<div class="kpi"><span>Top Segment</span><strong id="kpi-top">-</strong></div>
</section>
<section class="panel">
<h2 id="chart-title">Top Segments</h2>
<div class="bars" id="bar-chart"></div>
</section>
<section class="panel">
<h2>Filtered Data Preview</h2>
<p class="note">Showing the first 100 filtered rows. Full cleaned data is saved separately as CSV.</p>
<div class="table-wrap"><table id="preview-table"></table></div>
</section>
</main>
<script>
const DATA = __DATA__;
const SUMMARY = __SUMMARY__;
const BLUEPRINT = SUMMARY.analysis_blueprint || {};
const slicerColumns = BLUEPRINT.slicer_columns || [];
const categoryColumns = BLUEPRINT.category_columns || [];
const measureColumns = BLUEPRINT.measure_columns || [];

const slicerState = {};
const controls = document.getElementById("slicer-controls");
const categorySelect = document.getElementById("category-select");
const measureSelect = document.getElementById("measure-select");

function uniqueValues(column){
  return [...new Set(DATA.map(row => row[column]).filter(value => value !== null && value !== undefined && value !== ""))]
    .map(String).sort().slice(0, 200);
}

function fillSelect(select, values, selected){
  select.innerHTML = "";
  values.forEach(value => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    if(value === selected) option.selected = true;
    select.appendChild(option);
  });
}

function buildControls(){
  controls.innerHTML = "";
  if(!slicerColumns.length){
    controls.innerHTML = '<p class="note">No low-cardinality category fields were detected for slicers.</p>';
  }
  slicerColumns.forEach(column => {
    const label = document.createElement("label");
    const title = document.createElement("span");
    const select = document.createElement("select");
    title.textContent = column;
    fillSelect(select, ["All", ...uniqueValues(column)], "All");
    select.addEventListener("change", () => {
      slicerState[column] = select.value;
      render();
    });
    label.appendChild(title);
    label.appendChild(select);
    controls.appendChild(label);
  });

  fillSelect(categorySelect, categoryColumns.length ? categoryColumns : Object.keys(DATA[0] || {}), BLUEPRINT.default_category || categoryColumns[0]);
  fillSelect(measureSelect, measureColumns.length ? measureColumns : Object.keys(DATA[0] || {}), BLUEPRINT.default_measure || measureColumns[0]);
  categorySelect.addEventListener("change", render);
  measureSelect.addEventListener("change", render);
}

function filteredRows(){
  return DATA.filter(row => slicerColumns.every(column => {
    const selected = slicerState[column] || "All";
    return selected === "All" || String(row[column]) === selected;
  }));
}

function numericValue(value){
  const parsed = Number(String(value ?? "").replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatNumber(value){
  return new Intl.NumberFormat(undefined, {maximumFractionDigits: 2}).format(value);
}

function escapeHtml(value){
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderBars(rows, category, measure){
  const totals = new Map();
  rows.forEach(row => {
    const label = String(row[category] ?? "Blank");
    totals.set(label, (totals.get(label) || 0) + numericValue(row[measure]));
  });
  const items = [...totals.entries()].sort((a,b) => b[1] - a[1]).slice(0, 12);
  const max = Math.max(...items.map(item => item[1]), 1);
  const chart = document.getElementById("bar-chart");
  chart.innerHTML = "";
  items.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `<div class="bar-label" title="${escapeHtml(label)}">${escapeHtml(label)}</div><div class="bar-track"><div class="bar-fill" style="width:${Math.max(2, value / max * 100)}%"></div></div><div class="bar-value">${formatNumber(value)}</div>`;
    chart.appendChild(row);
  });
  document.getElementById("kpi-top").textContent = items[0] ? items[0][0] : "-";
  document.getElementById("chart-title").textContent = `Top ${category} by ${measure}`;
}

function renderTable(rows){
  const table = document.getElementById("preview-table");
  const columns = Object.keys(DATA[0] || {});
  const bodyRows = rows.slice(0, 100);
  table.innerHTML = `<thead><tr>${columns.map(column => `<th>${escapeHtml(column)}</th>`).join("")}</tr></thead><tbody>${bodyRows.map(row => `<tr>${columns.map(column => `<td>${escapeHtml(row[column])}</td>`).join("")}</tr>`).join("")}</tbody>`;
}

function render(){
  const rows = filteredRows();
  const category = categorySelect.value;
  const measure = measureSelect.value;
  const values = rows.map(row => numericValue(row[measure]));
  const total = values.reduce((sum, value) => sum + value, 0);
  document.getElementById("kpi-rows").textContent = formatNumber(rows.length);
  document.getElementById("kpi-total").textContent = formatNumber(total);
  document.getElementById("kpi-average").textContent = formatNumber(rows.length ? total / rows.length : 0);
  renderBars(rows, category, measure);
  renderTable(rows);
}

buildControls();
render();
</script>
</body>
</html>
"""
    dashboard = (
        dashboard
        .replace("__TITLE__", title)
        .replace("__DATA__", records_json)
        .replace("__SUMMARY__", summary_json)
    )
    (output_dir / "analysis_dashboard.html").write_text(dashboard, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an EDA report with cleaned data and charts.")
    parser.add_argument("input", nargs="?", help="Optional path to a CSV, TSV, JSON, XLS, or XLSX file.")
    parser.add_argument("--input-dir", default="datasets", help="Local folder used when no input file is provided.")
    parser.add_argument("--output", default=None, help="Output folder for report files.")
    parser.add_argument("--sheet", default=None, help="Excel sheet name or index. Default: auto-detect the best data sheet.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input) if args.input else find_local_dataset(Path(args.input_dir))
    output_dir = Path(args.output) if args.output else Path("reports") / f"{input_path.stem}_eda"
    output_dir.mkdir(parents=True, exist_ok=True)

    sheet: str | int | None = args.sheet
    if isinstance(sheet, str) and sheet.isdigit():
        sheet = int(sheet)

    loaded = load_dataset(input_path, sheet)
    original = loaded.data
    cleaned = clean_dataset(original)
    cleaned.to_csv(output_dir / "cleaned_data.csv", index=False)

    if loaded.data_sheets and len(loaded.data_sheets) > 1:
        sheets_dir = output_dir / "cleaned_sheets"
        sheets_dir.mkdir(parents=True, exist_ok=True)
        for sheet_name, sheet_df in loaded.data_sheets.items():
            clean_dataset(sheet_df).to_csv(sheets_dir / f"{safe_filename(sheet_name)}.csv", index=False)

    summary = build_summary(
        cleaned,
        len(original),
        loaded.source_sheet,
        loaded.sheet_scores,
        loaded.workbook_profile,
        loaded.sheet_relationships,
    )
    charts = create_charts(cleaned, output_dir / "charts")

    (output_dir / "eda_summary.json").write_text(
        json.dumps(summary, indent=2, default=safe_json),
        encoding="utf-8",
    )
    write_markdown_report(summary, charts, output_dir)
    write_html_dashboard(cleaned, summary, output_dir)

    print(f"Dataset used: {input_path.resolve()}")
    if loaded.source_sheet:
        print(f"Excel sheet analyzed: {loaded.source_sheet}")
    print(f"EDA report created: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
