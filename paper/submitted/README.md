# Submitted competition paper

[Read the submitted PDF](glee_competition_paper.pdf).

This is the version submitted on 6 September 2026 as *Below the Noise Floor: A Deterministic GLEE Agent and the Measurement Problem It Exposed*, the one the two reviews
(yxm9 and w8XP) refer to. It is kept byte-for-byte unchanged as an archive. The
published camera-ready version is in [the parent folder](../README.md), which
derives it from these sources by a script of asserted edits and lists every
change made in response to the reviews.

Its SHA-256 is recorded in [submission.json](submission.json). The submission
has four main-text pages, one reference page, and three appendix pages, using
NeurIPS 2026 preprint styling. Publication here does not independently certify
the competition's appendix or anonymity requirements.

## Source and build

`_head.tex` + `_body.tex` + `_tail.tex` concatenate to
`glee_competition_paper.tex`. The submitted figure is `fig_noise.tex`;
`neurips_2026.sty` is retained unchanged. Run from any directory:

```sh
python paper/submitted/build.py --check
python paper/submitted/build.py
```

The first command verifies the submitted PDF hash and source consistency without
compiling. The second also builds in `paper/submitted/build/`, stops on LaTeX
errors, and checks the main-text page count. It never overwrites the submitted
PDF or its assembled source. Building requires pdfLaTeX and the packages in the
source; Poppler's `pdftotext` enables a text comparison with the submitted PDF.
A locally rebuilt PDF need not have the same bytes because metadata, fonts and
TeX versions can differ.

The [audit notes](../AUDIT_NOTES.md) were written for this version.
