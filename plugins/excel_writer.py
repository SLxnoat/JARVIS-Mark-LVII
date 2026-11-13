"""
plugins/excel_writer.py - Excel spreadsheet generator and modifier.

Adheres to AGENTS.md:
- Thread-safe file writing with openpyxl (and CSV fallback).
- Thread-safe HUD feedback via player.write_log().
- Never raises exceptions, returns concise spoken feedback.
"""
import csv
from pathlib import Path

PLUGIN = {
    "name": "excel_writer",
    "description": (
        "Creates, reads, or appends rows to an Excel (.xlsx) spreadsheet or CSV file. "
        "Useful for tabular data, budgets, inventory, and exports."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'create', 'append_row', 'read'.",
                "enum": ["create", "append_row", "read"],
            },
            "file_path": {
                "type": "STRING",
                "description": "Path to the .xlsx or .csv spreadsheet file.",
            },
            "sheet_name": {
                "type": "STRING",
                "description": "Optional worksheet name (defaults to 'Sheet1').",
            },
            "headers": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "List of column headers for 'create'.",
            },
            "rows": {
                "type": "ARRAY",
                "items": {"type": "ARRAY", "items": {"type": "STRING"}},
                "description": "List of rows to write or append.",
            },
        },
        "required": ["action", "file_path"],
    },
}


def _write_xlsx(path: Path, sheet_name: str, headers: list, rows: list, append: bool = False):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise ImportError("openpyxl is not installed; falling back to CSV.")

    if append and path.is_file():
        wb = openpyxl.load_workbook(path)
        ws = wb[sheet_name] if sheet_name in wb.sheetnames else wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name or "Sheet1"
        if headers:
            ws.append(headers)
            header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")

    for r in rows:
        ws.append(r)

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _write_csv(path: Path, headers: list, rows: list, append: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(path, mode, newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not append and headers:
            writer.writerow(headers)
        for r in rows:
            writer.writerow(r)


def run(parameters: dict, player=None, session_memory=None) -> str:
    raw_action = str(parameters.get("action") or parameters.get("mode") or "create").strip().lower()
    if raw_action in ("write", "create_sheet", "make", "new"):
        action = "create"
    elif raw_action in ("append", "add", "add_row"):
        action = "append_row"
    else:
        action = raw_action

    raw_path = str(
        parameters.get("file_path")
        or parameters.get("path")
        or parameters.get("file")
        or ""
    ).strip()
    sheet = str(parameters.get("sheet_name") or "Sheet1").strip()
    headers = parameters.get("headers") or []
    rows = parameters.get("rows") or []

    if not raw_path:
        return "Please specify a destination file path for the spreadsheet."

    path = Path(raw_path).expanduser().resolve()

    try:
        if action == "create":
            if path.suffix.lower() == ".csv":
                _write_csv(path, headers, rows, append=False)
            else:
                if not path.suffix:
                    path = path.with_suffix(".xlsx")
                try:
                    _write_xlsx(path, sheet, headers, rows, append=False)
                except ImportError:
                    path = path.with_suffix(".csv")
                    _write_csv(path, headers, rows, append=False)

            if player:
                try:
                    player.write_log(f"[Excel] Created spreadsheet at {path.name} with {len(rows)} row(s).")
                except Exception:
                    pass
            return f"Successfully created spreadsheet '{path.name}' with {len(rows)} row(s)."

        elif action == "append_row":
            if not rows:
                return "Please provide rows to append."
            if path.suffix.lower() == ".csv":
                _write_csv(path, [], rows, append=True)
            else:
                try:
                    _write_xlsx(path, sheet, [], rows, append=True)
                except ImportError:
                    path = path.with_suffix(".csv")
                    _write_csv(path, [], rows, append=True)

            return f"Appended {len(rows)} row(s) to '{path.name}'."

        elif action == "read":
            if not path.is_file():
                return f"Spreadsheet file '{path.name}' not found."

            if path.suffix.lower() == ".csv":
                with open(path, "r", encoding="utf-8") as f:
                    content = list(csv.reader(f))
            else:
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True)
                ws = wb[sheet] if sheet in wb.sheetnames else wb.active
                content = [[str(cell or '') for cell in row] for row in ws.iter_rows(values_only=True)]

            if not content:
                return f"Spreadsheet '{path.name}' is empty."

            preview_lines = [" | ".join(row) for row in content[:8]]
            if player:
                try:
                    player.show_content(f"Sheet: {path.name}", "```\n" + "\n".join(preview_lines) + "\n```")
                except Exception:
                    pass
            return f"Spreadsheet '{path.name}' has {len(content)} row(s). Top rows previewed on HUD."

        else:
            return f"Unknown action '{action}'. Valid actions: create, append_row, read."

    except Exception as e:
        return f"Error with spreadsheet operations: {e}"
