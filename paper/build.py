"""Assemble head + body + tail into the submission .tex, build it, and report
how far the main body runs. Run:  python build.py
"""
import re
import subprocess
import sys

HEAD, BODY, TAIL = "_head.tex", "_body.tex", "_tail.tex"
OUT = "glee_competition_paper"

head = open(HEAD, encoding="utf-8").read()
body = open(BODY, encoding="utf-8").read()
tail = open(TAIL, encoding="utf-8").read()

# The geometry fallback does not define a macro the 2026 class provides; stub it
# so the draft still builds cleanly without the official style file.
if "@trackname" not in head:
    guard = ("\\makeatletter\n"
             "\\@ifundefined{@trackname}{\\gdef\\@trackname{}}{}\n"
             "\\makeatother\n\\makeatother")
    head = head.replace("\\makeatother", guard, 1)

BANNER = (
    "% ###################################################################\n"
    "% #  GENERATED FILE -- DO NOT EDIT.                                 #\n"
    "% #                                                                 #\n"
    "% #  Assembled by build.py from _head.tex + _body.tex + _tail.tex.  #\n"
    "% #  Any edit here is silently overwritten on the next build.       #\n"
    "% #  Edit the fragments instead, then run:  python build.py         #\n"
    "% ###################################################################\n\n"
)

doc = BANNER + head + body + tail
probe = "--probe" in sys.argv
if probe:
    doc = doc.replace("\\bibliographystyle{plain}",
                      "\\phantomsection\\label{END}\n\\bibliographystyle{plain}", 1)
open(OUT + ".tex", "w", encoding="utf-8").write(doc)

for _ in range(2):
    subprocess.run(["pdflatex", "-interaction=nonstopmode", OUT + ".tex"],
                   capture_output=True)

log = open(OUT + ".log", encoding="utf-8", errors="ignore").read()
pages = re.findall(r"Output written on \S+ \((\d+) pages", log)
errs = [l[:78] for l in log.split("\n") if l.startswith("!")]
words = len(re.sub(r"[\\{}$&~^_%]", " ", body).split())
print("body words: %d   total pages: %s" % (words, pages))
if errs:
    print("LaTeX errors:", errs[:5])

if probe:
    aux = open(OUT + ".aux", encoding="utf-8", errors="ignore").read()
    m = re.search(r"newlabel\{END\}\{\{[^}]*\}\{(\d+)\}", aux)
    if m:
        p = m.group(1)
        txt = subprocess.run(["pdftotext", "-f", p, "-l", p, OUT + ".pdf", "-"],
                             capture_output=True, text=True).stdout
        print("main body ends on page %s; that page carries %d words"
              % (p, len(txt.split())))
