# Submitted competition paper

[Read the submitted PDF](glee_competition_paper.pdf).

The camera-ready version, revised after review and accepted as a Spotlight,
lives in [camera_ready/](camera_ready/README.md). It is derived from these
submitted sources by a script of asserted edits, so the submission below stays
byte-for-byte unchanged.

Competition paper submitted on 6 September 2026.
Its SHA-256 is recorded in [submission.json](submission.json). The submission
has four main-text pages, one reference page, and three appendix pages, using
NeurIPS 2026 preprint styling. Publication here does not independently certify
the competition's appendix or anonymity requirements.

## Source and build

`_head.tex` + `_body.tex` + `_tail.tex` concatenate to
`glee_competition_paper.tex`. The submitted figure is `fig_noise.tex`;
`neurips_2026.sty` is retained unchanged. Run from any directory:

```sh
python paper/build.py --check
python paper/build.py
```

The first command verifies the submitted PDF hash and source consistency without
compiling. The second also builds in `paper/build/`, stops on LaTeX errors,
and checks the main-text page count. It never overwrites the submitted PDF or
its assembled source. Building requires pdfLaTeX and the packages in the source;
Poppler's `pdftotext` enables a text comparison with the submitted PDF.
A locally rebuilt PDF need not have the same bytes because metadata, fonts and
TeX versions can differ.

## Evidence and later corrections

[Analysis instructions](analysis/README.md) distinguish scripts, aggregate
outputs, rounded figure coordinates, and missing private inputs.
[Audit notes](AUDIT_NOTES.md) document analysis limitations and implementation
details. The reported empirical results and the code checks have distinct
provenance; the private inputs needed for full reproduction are not included.

[The historical change register](change-register.html) is an incomplete
mid-competition notebook, not a current specification or a validated causal
intervention ledger. Its historical claims are qualified by the audit notes.

## Agent configuration

The executable agent retains the final-night parameters. The historical
472-test suite has a separately named reference configuration; see the root
[README](../README.md#tests-and-configuration-provenance). Passing the reference
suite is not a claim that the final-night configuration passes those expectations.
