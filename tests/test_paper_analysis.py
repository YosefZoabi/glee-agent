"""Synthetic regression tests. These do not revalidate private competition results."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "paper" / "analysis"
sys.path.insert(0, str(ANALYSIS))

from common import buyer_seat, discounted_offer, fit, history_rows
from noise import csv_polls, figure_polls, summarize
from pers_pool import compare, welch_t
from power import illustrative_n
from validate import stability


def run_script(name, *args):
    return subprocess.run([sys.executable, str(ANALYSIS / name), *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, timeout=30)


@pytest.fixture
def private_inputs(tmp_path):
    human = tmp_path / "human"
    human.mkdir()
    for name in ("human_replays", "human_replays_rand", "human_barg_recent", "human_persuasion"):
        (human / (name + ".json")).write_text("{}", encoding="utf-8")
    (human / "human_hist_full.json").write_text("[]", encoding="utf-8")
    joined = tmp_path / "joined.jsonl"; joined.write_text("", encoding="utf-8")
    buyer = tmp_path / "buyer.jsonl"; buyer.write_text("", encoding="utf-8")
    history = tmp_path / "history.json"; history.write_text("[]", encoding="utf-8")
    return human, joined, buyer, history


def test_exact_submitted_pdf_and_assembled_sources():
    spec = importlib.util.spec_from_file_location("paper_build", ROOT / "paper" / "build.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    _, digest = module.check_submission()
    assert digest == "f916fe323968ca01be4c2f8ec860088f1b51f2f74db88d3e68bc223545d15097"


def test_figure_summary_is_explicitly_approximate():
    result = summarize(figure_polls(ROOT / "paper" / "fig_noise.tex"))
    assert result["polls"] == 45
    assert result["initial_spread"] == pytest.approx(85.4, abs=.2)
    assert result["maximum_spread"] == pytest.approx(88, abs=.2)
    assert result["maximum_at_hours"] < .2
    assert result["mean_spread"] == pytest.approx(48.1, abs=.2)
    assert result["final_spread"] == pytest.approx(45.7, abs=.2)


def test_family_not_fabricated_from_overall_figure():
    result = run_script("noise.py", "--metric", "bargaining")
    assert result.returncode != 0
    assert "cannot be recovered" in result.stderr


def test_polls_reject_missing_agent(tmp_path):
    path = tmp_path / "polls.csv"
    path.write_text("elapsed_hours,agent,overall\n0,A,2000\n0,B,2010\n1,A,2005\n")
    with pytest.raises(ValueError, match="same agent set"):
        csv_polls(path)


def test_polls_reject_duplicate_agent(tmp_path):
    path = tmp_path / "polls.csv"
    path.write_text("elapsed_hours,agent,overall\n0,A,2000\n0,A,2010\n")
    with pytest.raises(ValueError, match="Duplicate"):
        csv_polls(path)


def test_poll_summary_arithmetic(tmp_path):
    path = tmp_path / "polls.csv"
    path.write_text("elapsed_hours,agent,overall\n0,A,2000\n0,B,2010\n1,A,2020\n1,B,2024\n")
    result = summarize(csv_polls(path))
    assert result["mean_spread"] == 7
    assert result["final_spread"] == 4


def test_discounted_best_offer_is_not_nominal_maximum():
    assert discounted_offer(.4, 2, .5) > discounted_offer(.6, 4, .5)


@pytest.mark.parametrize("round_number,delta", [(0,.9),(1,0),(1,1.1)])
def test_invalid_discount_inputs(round_number, delta):
    with pytest.raises(ValueError):
        discounted_offer(.5, round_number, delta)


def test_refusal_cli_uses_discounted_max_and_reports_ties(private_inputs):
    human, joined, _, _ = private_inputs
    game = {"game_family": "bargaining", "your_player": "player_1",
            "config": {"money_to_divide": 100, "delta_1": .5, "delta_2": .9},
            "result": {"player_1_payoff": 15},
            "moves": [{"move_type": "offer", "round": 2, "move_data": {"alice_gain": 40}},
                      {"move_type": "offer", "round": 4, "move_data": {"alice_gain": 60}}]}
    (human / "human_replays.json").write_text(json.dumps({"x": game}))
    joined.write_text(json.dumps({"fam":"bargaining", "my_share":.15, "d_us":.5,
                                 "faced":[[2,.4,"reject"],[4,.6,"reject"]]})+"\n")
    result = run_script("human2.py", human, joined)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("-0.0500 of pot") == 2
    assert "ties=0" in result.stdout and "denominator=1" in result.stdout


def test_buyer_role_not_inferred_from_missing_metadata():
    assert not buyer_seat({"your_player":"player_2", "state":{}})
    assert buyer_seat({"your_player":"player_1", "state":{"player_1_role":"buyer"}})
    assert buyer_seat({"your_player":"player_2", "state":{"player_1_role":"seller"}})


def test_persuasion_missing_payoff_is_not_zero():
    humans = [{"your_player":"player_1", "state":{"player_1_role":"buyer"},
               "config":{"v":2,"p":.8,"product_price":10},
               "result":{"player_1_payoff":20}}]
    agents = [{"fam":"persuasion", "role":"buyer", "m":2, "p":.8, "price":10, "my_pay":10},
              {"fam":"persuasion", "role":"buyer", "m":2, "p":.8, "price":10}]
    result = compare(humans, agents)
    assert result["rows"][0]["agent_n"] == 1
    assert result["rows"][0]["agent_mean"] == 1
    assert result["omitted"]["agent_missing_payoff"] == 1


def test_persuasion_two_documented_arguments_work(private_inputs):
    human, joined, _, _ = private_inputs
    result = run_script("pers_pool.py", human, joined)
    assert result.returncode == 0, result.stderr
    assert "Not computed" in json.loads(result.stdout)["agent_purchase_quality"]


def test_unknown_quality_not_counted_as_low(private_inputs):
    human, joined, buyer, _ = private_inputs
    buyer.write_text(json.dumps({"history":[{"bought":True,"quality":"high"},
                                          {"bought":True,"quality":None}]})+"\n")
    result = run_script("pers_pool.py", human, joined, "--buyer-replays", buyer)
    data = json.loads(result.stdout)["agent_purchase_quality"]
    assert data == {"high":1,"low":0,"unknown":1,"known_quality_n":1,"high_rate":1.0}


def test_welch_small_samples_and_sign():
    assert welch_t([1], [2,3]) is None
    assert welch_t([3,4,5], [1,2,3]) > 0
    assert welch_t([1,1], [1,1]) is None


def test_iid_formula():
    assert illustrative_n(1,1) == 18
    with pytest.raises(ValueError):
        illustrative_n(1,0)


def test_zero_crossing_is_computed_without_range_clipping():
    assert fit([(0,-4), (1,-3)])["root"] == pytest.approx(4)
    assert fit([(0,1), (1,1)])["root"] is None
    assert fit([(1,1), (1,2)]) is None


def test_stability_discloses_historical_filter():
    cells = {
        "inside": [(0,-.5,"1"),(1,.5,"2"),(0,-.5,"3"),(1,.5,"4")],
        "outside": [(0,-4,"1"),(1,-3,"2"),(0,-4,"3"),(1,-3,"4")],
    }
    result = stability(cells, min_games=4)
    assert result["all_defined_roots"]["n_cells"] == 2
    assert result["historical_filter_both_roots_in_0_to_1_3"]["n_cells"] == 1
    assert result["excluded_by_historical_root_filter"] == 1


def test_duplicate_history_not_counted_twice(tmp_path):
    path = tmp_path/"history.json"
    row = {"game_id":"x","your_player":"player_1","rating_delta":-5,
           "result":{"outcome":"timeout"}}
    path.write_text(json.dumps([row,row]))
    assert len(history_rows([path,path])) == 1


def test_conflicting_history_rejected(tmp_path):
    path = tmp_path/"history.json"
    path.write_text(json.dumps([{"game_id":"x","rating_delta":1},{"game_id":"x","rating_delta":2}]))
    with pytest.raises(ValueError, match="Conflicting"):
        history_rows([path])


def test_timeout_has_no_persistent_cost(private_inputs):
    *_, history = private_inputs
    history.write_text(json.dumps([{"game_id":"x","rating_delta":-5,
                                    "result":{"outcome":"timeout"}}]))
    result = run_script("timeouts3.py", history)
    data = json.loads(result.stdout)
    assert data["persistent_cost_estimate"] is None
    assert data["rows"][0]["sum_recorded_deltas"] == -5


SCRIPTS = ["breakeven.py","validate.py","power.py","noise.py","human.py","human2.py",
           "parserbug.py","parser2.py","pers_check.py","pers_cmp.py","pers_pool.py",
           "table_human.py","nego_pers.py","timeouts.py","timeouts2.py","timeouts3.py"]


@pytest.mark.parametrize("script", SCRIPTS)
def test_cli_help(script):
    result = run_script(script, "--help")
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


@pytest.mark.parametrize("script", SCRIPTS)
def test_empty_valid_inputs_do_not_crash(script, private_inputs):
    human, joined, buyer, history = private_inputs
    if script == "noise.py":
        args = []
    elif script in ("human.py","human2.py","pers_cmp.py","pers_pool.py","table_human.py"):
        args = [human,joined]
    elif script == "pers_check.py":
        args = [human]
    elif script in ("parserbug.py","parser2.py"):
        args = [buyer]
    elif script in ("timeouts2.py","timeouts3.py"):
        args = [history]
    else:
        args = [joined]
    result = run_script(script, *args)
    assert result.returncode == 0, result.stderr


def test_executable_final_night_defaults_untouched():
    from glee_agent.params import BARGAINING, PERSUASION
    assert BARGAINING.open_converge_on is True
    assert PERSUASION.require_seller_declined is True
    assert PERSUASION.certified_first_buy is True

