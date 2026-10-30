"""Audit Figure 1 coordinates, or original simultaneous polls if supplied.

Default input is the rounded TikZ figure, NOT raw logs. It checks plotted overall
spreads approximately; it cannot recover family scores, game counts, build
hashes, absolute timestamps, or a statistical detection threshold.
"""
import argparse
import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path


def figure_polls(path):
    text = path.read_text(encoding="utf-8")
    ticks = re.findall(r"at \(-0\.080,([\d.]+)\) \{(\d+)\}", text)
    if len(ticks) < 2:
        raise ValueError("Cannot calibrate this figure's rating axis.")
    y0, rating0 = map(float, ticks[0]); y1, rating1 = map(float, ticks[-1])
    scale = (rating1 - rating0) / (y1 - y0)
    series = {}
    for line in text.splitlines():
        match = re.match(r"\\draw\[c([1-5])(?:,|\])", line)
        if not match:
            continue
        points = [(float(x), float(y)) for x, y in re.findall(r"\(([\d.]+),([\d.]+)\)", line)]
        if len(points) > 2:
            series["B" + match[1]] = [(x / 1.44, rating0 + (y - y0) * scale) for x, y in points]
    if len(series) != 5:
        raise ValueError("Expected five submitted figure series.")
    grids = [tuple(x for x, _ in points) for points in series.values()]
    if len(set(grids)) != 1:
        raise ValueError("Figure series do not share a simultaneous grid.")
    return [{"elapsed_hours": x, **{name: points[i][1] for name, points in series.items()}}
            for i, x in enumerate(grids[0])]


def csv_polls(path, metric="overall"):
    """CSV: elapsed_hours,agent,overall[,bargaining,negotiation,persuasion]."""
    polls = defaultdict(dict)
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            time, agent = float(row["elapsed_hours"]), row["agent"]
            if agent in polls[time]:
                raise ValueError(f"Duplicate agent {agent} at {time} hours.")
            polls[time][agent] = float(row[metric])
    if not polls or len({tuple(sorted(p)) for p in polls.values()}) != 1:
        raise ValueError("Every poll must contain the same agent set; no silent missing-poll filtering.")
    return [{"elapsed_hours": t, **polls[t]} for t in sorted(polls)]


def summarize(polls):
    if not polls:
        raise ValueError("No polls supplied.")
    names = sorted(set(polls[0]) - {"elapsed_hours"})
    if len(names) < 2:
        raise ValueError("At least two agents are needed for a spread.")
    spreads = [max(p[n] for n in names) - min(p[n] for n in names) for p in polls]
    index = max(range(len(spreads)), key=spreads.__getitem__)
    return {"agents": names, "polls": len(polls),
            "duration_hours": polls[-1]["elapsed_hours"] - polls[0]["elapsed_hours"],
            "initial_spread": spreads[0], "final_spread": spreads[-1],
            "mean_spread": statistics.mean(spreads), "median_spread": statistics.median(spreads),
            "maximum_spread": spreads[index], "maximum_at_hours": polls[index]["elapsed_hours"],
            "interpretation": "Observed range, not a confidence interval or estimated noise floor."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots", type=Path, help="Original long-form rating-poll CSV.")
    parser.add_argument("--metric", choices=["overall", "bargaining", "negotiation", "persuasion"], default="overall")
    parser.add_argument("--figure", type=Path, default=Path(__file__).resolve().parents[1] / "submitted" / "fig_noise.tex")
    args = parser.parse_args()
    try:
        if args.snapshots:
            result = summarize(csv_polls(args.snapshots, args.metric))
            result["provenance"] = "User-supplied polls; verify deployment metadata separately."
        else:
            if args.metric != "overall":
                parser.error("Family scores cannot be recovered from the overall-rating figure.")
            result = summarize(figure_polls(args.figure))
            result["provenance"] = "Approximate values decoded from rounded submitted figure coordinates."
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
