"""Check the submitted artifact and build a separate verification copy.

Run from any working directory. Never overwrite the submitted
PDF or the committed assembled TeX file.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

PAPER = Path(__file__).resolve().parent
NAME = "glee_competition_paper"


def check_submission(paper=PAPER):
    manifest = json.loads((paper / "submission.json").read_text(encoding="utf-8"))
    pdf = paper / manifest["submitted_pdf"]
    actual = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if actual != manifest["sha256"]:
        raise ValueError("Submitted PDF does not match submission.json; refusing to rebuild over it.")
    source = "".join((paper / p).read_text(encoding="utf-8") for p in ("_head.tex", "_body.tex", "_tail.tex"))
    if source != (paper / (NAME + ".tex")).read_text(encoding="utf-8"):
        raise ValueError("Committed assembled source differs from the three fragments.")
    for filename in ("neurips_2026.sty", "fig_noise.tex"):
        if not (paper / filename).is_file():
            raise ValueError("Required submitted input missing: " + filename)
    return source, actual


def compile_copy(source, paper=PAPER):
    if not shutil.which("pdflatex"):
        raise ValueError("pdfLaTeX is required to build; --check needs only Python.")
    target = paper / "build"
    target.mkdir(exist_ok=True)
    (target / (NAME + ".tex")).write_text(source, encoding="utf-8")
    for filename in ("neurips_2026.sty", "fig_noise.tex"):
        shutil.copyfile(paper / filename, target / filename)
    for _ in range(2):
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                        "-file-line-error", NAME + ".tex"], cwd=target, capture_output=True,
                       text=True, check=True)
    log = (target / (NAME + ".log")).read_text(encoding="utf-8", errors="replace")
    if re.search(r"undefined references|undefined citations|Overfull \\hbox|Overfull \\vbox", log):
        raise ValueError("Unresolved references/citations or overflowing boxes in verification build.")
    aux = (target / (NAME + ".aux")).read_text(encoding="utf-8")
    match = re.search(r"\\newlabel\{endmain\}\{\{[^}]*\}\{(\d+)\}", aux)
    if not match or int(match[1]) != 4:
        raise ValueError("Main-text endpoint did not resolve to page 4.")
    if shutil.which("pdftotext"):
        texts = [subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True,
                                capture_output=True, text=True).stdout
                 for path in (paper / (NAME + ".pdf"), target / (NAME + ".pdf"))]
        if texts[0] != texts[1]:
            raise ValueError("Rebuilt text/layout differs from the submitted PDF. Submitted file was not changed.")
        print("Rebuilt text/layout matches the submitted PDF.")
    else:
        print("pdftotext unavailable: rebuilt text comparison was not performed.")
    return target / (NAME + ".pdf")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check hash/source only; do not compile.")
    parser.add_argument("--probe", action="store_true", help="Compatibility alias: page-count check is always enabled.")
    args = parser.parse_args()
    try:
        source, digest = check_submission()
        print("Submitted PDF SHA-256:", digest)
        print("Source fragments match committed assembled TeX.")
        if not args.check:
            print("Verification PDF:", compile_copy(source))
            check_submission()
    except subprocess.CalledProcessError as error:
        parser.exit(1, "LaTeX build failed; see paper/submitted/build/*.log. Submitted file remains unchanged.\n")
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
