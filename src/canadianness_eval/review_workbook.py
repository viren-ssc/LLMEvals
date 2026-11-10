from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation


def create_workbook(path, candidates, coverage, rubrics, report):
    path = Path(path)
    if path.exists():
        raise ValueError(
            "Review workbook already exists; preserve human edits. Choose --workbook with a new filename."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for mid, rubric in rubrics.items():
        for band in rubric["bands"]:
            rows.append(
                dict(
                    metric_id=mid,
                    score_min=band["score_range"][0],
                    score_max=band["score_range"][1],
                    description=band["description"],
                    approved="",
                    guidance=rubric["guidance"],
                    ambiguities=rubric["ambiguities"],
                    examples=rubric.get("example_question", "") + "\n" + str(rubric["examples"]),
                )
            )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        candidates.to_excel(writer, sheet_name="Step Candidates", index=False)
        coverage.to_excel(writer, sheet_name="Metric Coverage", index=False)
        pd.DataFrame(rows).to_excel(writer, sheet_name="Rubric Review", index=False)
        pd.DataFrame([{"item": k, "value": str(v)} for k, v in report.items()]).to_excel(
            writer, sheet_name="Review Summary", index=False
        )
        for sheet in writer.book:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="24465B")
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = (
                    24 if column[0].column < 5 else 55
                )
                for cell in column[1:]:
                    # Prevent generated text from becoming an executable Excel formula.
                    if isinstance(cell.value, str) and cell.value.startswith(("=", "+", "-", "@")):
                        cell.data_type = "s"
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
            for row in range(2, sheet.max_row + 1):
                sheet.row_dimensions[row].height = 75
        choices = DataValidation(type="list", formula1='"Keep,Reject,Revise,Undecided"')
        sheet = writer.book["Step Candidates"]
        sheet.add_data_validation(choices)
        choices.add("J2:J1048576")
        approvals = DataValidation(type="list", formula1='"Yes,No"')
        sheet = writer.book["Rubric Review"]
        sheet.add_data_validation(approvals)
        approvals.add("E2:E36")
        sheet = writer.book["Review Summary"]
        start = sheet.max_row + 1
        sheet.append(["Live metric review", "Selected steps", "Approved bands", "Readiness"])
        for index, mid in enumerate(rubrics, start + 1):
            sheet.append(
                [
                    mid,
                    f"=COUNTIFS('Step Candidates'!A:A,A{index},'Step Candidates'!J:J,\"Keep\")+COUNTIFS('Step Candidates'!A:A,A{index},'Step Candidates'!J:J,\"Revise\")",
                    f"=COUNTIFS('Rubric Review'!A:A,A{index},'Rubric Review'!E:E,\"Yes\")",
                    f'=IF(AND(B{index}>0,C{index}=5),"Validate with freeze-review","Needs human review")',
                ]
            )
