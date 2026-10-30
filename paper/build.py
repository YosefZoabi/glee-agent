"""Regenerate and check the camera-ready paper.

    python paper/build.py --check   # regenerate figure, data and source; compare with committed files
    python paper/build.py           # also compile a verification copy in paper/build/

The camera-ready source is derived from the submitted paper in submitted/ by
gen_fig.py (Figure 1 and data/) and make_camera_ready.py (asserted text edits).
This script never overwrites the committed PDF, which is the uploaded file.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys

PAPER = Path(__file__).resolve().parent
NAME = "glee_competition_paper"
GENERATED = ("fig_noise.tex", NAME + ".tex", "data/fig1_overall_snapshots.csv")


def regenerate(paper=PAPER):
    """Run both generators; restore the committed files if anything changed."""
    before = {name: (paper / name).read_bytes() for name in GENERATED}
    for script in ("gen_fig.py", "make_camera_ready.py"):
        subprocess.run([sys.executable, str(paper / script)], check=True, capture_output=True, text=True)
    changed = [name for name in GENERATED if (paper / name).read_bytes() != before[name]]
    if changed:
        for name, data in before.items():
            (paper / name).write_bytes(data)
        raise ValueError("Regenerated files differ from the committed ones: " + ", ".join(changed))


def compile_copy(paper=PAPER):
    if not shutil.which("pdflatex"):
        raise ValueError("pdfLaTeX is required to build; --check needs only Python.")
    target = paper / "build"
    target.mkdir(exist_ok=True)
    for filename in (NAME + ".tex", "neurips_2026.sty", "fig_noise.tex"):
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
    if not match or int(match[1]) != 5:
        raise ValueError("Main text does not end on page 5.")
    if shutil.which("pdffonts"):
        fonts = subprocess.run(["pdffonts", str(target / (NAME + ".pdf"))], check=True,
                               capture_output=True, text=True).stdout
        if "Type 3" in fonts:
            raise ValueError("Bitmap (Type 3) fonts in the build; install lmodern.")
    if shutil.which("pdftotext"):
        texts = [subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True,
                                capture_output=True, text=True).stdout
                 for path in (paper / (NAME + ".pdf"), target / (NAME + ".pdf"))]
        if texts[0] != texts[1]:
            print("Note: rebuilt text/layout differs from the committed PDF.")
        else:
            print("Rebuilt text/layout matches the committed PDF.")
    return target / (NAME + ".pdf")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Regenerate and compare only; do not compile.")
    args = parser.parse_args()
    try:
        regenerate()
        print("Figure, data and source regenerate exactly from submitted/.")
        if not args.check:
            print("Verification PDF:", compile_copy())
    except subprocess.CalledProcessError as error:
        parser.exit(1, "Generation or LaTeX build failed; see paper/build/*.log.\n" + (error.stderr or ""))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
