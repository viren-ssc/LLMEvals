"""Safely refresh a pristine generated workbook after authoring improvements."""

from time import time_ns

from openpyxl import load_workbook

from canadianness_eval.cli import main
from canadianness_eval.settings import ROOT

if __name__ == "__main__":
    path = ROOT / "review/Canadian_Ness_GEVAL_Review.xlsx"
    if path.exists():
        book = load_workbook(path)
        if any(
            row[9].value or row[10].value or row[11].value or row[12].value
            for row in book["Step Candidates"].iter_rows(min_row=2)
        ):
            raise SystemExit("Human step edits exist; choose a new workbook path instead.")
        if any(row[4].value for row in book["Rubric Review"].iter_rows(min_row=2)):
            raise SystemExit("Human rubric approvals exist; choose a new workbook path instead.")
        # Compare descriptions/guidance too: do not discard unapproved human rubric edits.
        from canadianness_eval.rubric_builder import load_rubrics

        rubrics = load_rubrics()
        for row in book["Rubric Review"].iter_rows(min_row=2):
            mid = row[0].value
            index = [0, 3, 5, 7, 9].index(row[1].value)
            if row[3].value != rubrics[mid]["bands"][index]["description"]:
                raise SystemExit("Human rubric edits exist; choose a new workbook path instead.")
        book.close()
        archive = ROOT / "review/archive" / f"initial_draft_{time_ns()}.xlsx"
        archive.parent.mkdir(parents=True, exist_ok=True)
        path.rename(archive)
        print(f"Preserved original generated workbook: {archive}")
    raise SystemExit(main(["prepare-review", "--offline"]))
