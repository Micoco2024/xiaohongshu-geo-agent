"""Live GEO observation: plan AI-product runs, record them, and summarize.

Question-bank quality and observed GEO performance stay separate. This module
only records what AI products answered; it never changes the release decision.

A run is one question (or one multi-turn chain) asked once to one product.
Responses are captured by a person or by Claude Code driving a browser; the
module fills the deterministic part of the observation (is the brand named at
all) and leaves judgment fields for review.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


BRAND_POSITIONS = ("absent", "mentioned", "compared", "recommended", "not_applicable")
JUDGMENTS = ("pass", "fail", "review", "not_assessed")
CITATION_JUDGMENTS = ("pass", "fail", "review", "not_applicable")
RUN_STATUSES = ("completed", "failed", "blocked")
RUN_ID_PATTERN = re.compile(r"^[^/\\.][^/\\]*/\d{8}-\d{6}$")


class LiveTestError(ValueError):
    """Raised when a live-run record is malformed."""


def build_test_plan(
    question_bank: dict[str, Any],
    products: Iterable[str],
    *,
    repeats: int = 1,
) -> list[dict[str, Any]]:
    """One plan item per question or chain, per product, per repeat."""
    products = [p.strip() for p in products if p and p.strip()]
    if not products:
        raise LiveTestError("at least one AI product is required")
    if repeats < 1:
        raise LiveTestError("repeats must be at least 1")
    cases = [
        {"question_ref": q["question_id"], "mode": "single_turn", "turns": [q["question"]],
         "brand_visibility": q["brand_visibility"], "scene": q["scene"], "intent": q["intent"]}
        for q in question_bank.get("single_turn_questions", [])
    ] + [
        {"question_ref": c["question_chain_id"], "mode": "multi_turn",
         "turns": [t["question"] for t in sorted(c["turns"], key=lambda t: t["turn"])],
         "brand_visibility": "chain", "scene": c["scene"], "intent": c["intent"]}
        for c in question_bank.get("multi_turn_chains", [])
    ]
    return [
        {**case, "product": product, "repeat_index": repeat}
        for product in products
        for case in cases
        for repeat in range(1, repeats + 1)
    ]


def brand_terms(brand_name: str, aliases: Iterable[str] = ()) -> list[str]:
    terms = {brand_name, *aliases}
    # Also match spacing and case variants such as "WonderWander" / "wonder wander".
    return sorted({t.strip() for t in terms if t and t.strip()}, key=len, reverse=True)


def mentions_brand(text: str, terms: Iterable[str]) -> bool:
    squashed = "".join(text.split()).casefold()
    return any("".join(term.split()).casefold() in squashed for term in terms)


def build_observation(
    record: dict[str, Any],
    terms: list[str],
    *,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Normalize one captured run into an evaluation-report live observation.

    `record` needs product, question_ref, repeat_index and turns
    ([{"question", "response"}]). Optional: model_or_version, citations,
    run_status, brand_position, factual_accuracy, citation_quality,
    intent_satisfaction, notes, trace_ref.
    """
    for field in ("product", "question_ref"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise LiveTestError(f"{field} is required")
    repeat = record.get("repeat_index", 1)
    if not isinstance(repeat, int) or repeat < 1:
        raise LiveTestError("repeat_index must be a positive integer")
    turns = record.get("turns")
    if not isinstance(turns, list) or not turns:
        raise LiveTestError("turns must list each question and response")
    for turn in turns:
        if not isinstance(turn, dict) or not str(turn.get("question", "")).strip():
            raise LiveTestError("each turn needs a question")
    status = record.get("run_status", "completed")
    _choice(status, RUN_STATUSES, "run_status")
    citations = [c for c in record.get("citations", []) if isinstance(c, str) and c.strip()]
    sources = [normalize_source(src, terms) for src in record.get("sources", []) if isinstance(src, dict)]

    responses = " ".join(str(t.get("response", "")) for t in turns)
    named = status == "completed" and mentions_brand(responses, terms)
    # Deterministic floor: absent vs mentioned. Only a reviewer may raise it to
    # compared/recommended, and a reviewer can never mark an unnamed brand as present.
    position = record.get("brand_position") or ("mentioned" if named else "absent")
    if status != "completed":
        position = "not_applicable"
    _choice(position, BRAND_POSITIONS, "brand_position")
    if position in ("mentioned", "compared", "recommended") and not named:
        raise LiveTestError(f"{record['question_ref']}: brand_position={position} but the response never names the brand")
    if position == "absent" and named:
        position = "mentioned"

    accuracy = record.get("factual_accuracy") or ("review" if named else "not_assessed")
    citation = record.get("citation_quality") or ("review" if citations else "not_applicable")
    intent = record.get("intent_satisfaction") or ("review" if status == "completed" else "not_assessed")
    _choice(accuracy, JUDGMENTS, "factual_accuracy")
    _choice(citation, CITATION_JUDGMENTS, "citation_quality")
    _choice(intent, JUDGMENTS, "intent_satisfaction")

    return {
        "product": record["product"].strip(),
        "model_or_version": record.get("model_or_version") or None,
        "question_ref": record["question_ref"].strip(),
        "repeat_index": repeat,
        "run_status": status,
        "brand_position": position,
        "factual_accuracy": accuracy,
        "citation_quality": citation,
        "intent_satisfaction": intent,
        "trace_ref": record.get("trace_ref") or None,
        "notes": str(record.get("notes") or ""),
        # Raw capture kept beside the observation for later review.
        "captured_at": captured_at or record.get("captured_at") or datetime.now().replace(microsecond=0).isoformat(),
        "turns": [{"question": str(t["question"]), "response": str(t.get("response", ""))} for t in turns],
        "citations": citations,
        # Notes the AI product says it drew on; used to look for what cited notes share.
        "sources": sources,
    }


SOURCE_FIELDS = ("title", "url", "author", "author_type", "note_type", "published", "likes", "collects", "comments")


def normalize_source(source: dict[str, Any], terms: Iterable[str]) -> dict[str, Any]:
    """One cited note as shown in the product's source list.

    Counts may be missing or shown as text such as "1.2万"; they are parsed to ints.
    `mentions_brand` is computed from title and excerpt, never taken from input.
    """
    out: dict[str, Any] = {field: source.get(field) for field in SOURCE_FIELDS}
    for field in ("likes", "collects", "comments"):
        out[field] = parse_count(out[field])
    text = " ".join(str(source.get(k) or "") for k in ("title", "excerpt"))
    out["excerpt"] = str(source.get("excerpt") or "")
    out["mentions_brand"] = mentions_brand(text, terms)
    return out


def parse_count(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace(",", "").replace("+", "")
    scale = 10000 if text.endswith(("万", "w", "W")) else 1000 if text.endswith(("千", "k", "K")) else 1
    try:
        return int(float(text.rstrip("万wW千kK")) * scale)
    except ValueError:
        return None


def note_id(url: Any) -> str | None:
    """Xiaohongshu note id from /explore/<id> or /discovery/item/<id> URLs."""
    if not isinstance(url, str):
        return None
    match = re.search(r"/(?:explore|discovery/item)/([0-9a-f]{24})", url)
    return match.group(1) if match else None


def analyze_sources(observations: list[dict[str, Any]], evidence_urls: Iterable[str] = ()) -> dict[str, Any]:
    """Describe what the cited notes have in common.

    Reports distributions side by side for answers that named the brand and
    answers that did not, so a reader can see which note traits go with the
    brand appearing. These are observed associations in a small sample, not causes.
    """
    evidence_ids = {i for i in (note_id(u) for u in evidence_urls) if i}
    groups = {"brand_named": [], "brand_absent": []}
    for o in observations:
        if o["run_status"] != "completed" or not o.get("sources"):
            continue
        key = "brand_absent" if o["brand_position"] == "absent" else "brand_named"
        groups[key].append(o)

    def profile(obs: list[dict[str, Any]]) -> dict[str, Any] | None:
        notes = [src for o in obs for src in o["sources"]]
        if not notes:
            return None
        likes = sorted(n["likes"] for n in notes if n["likes"] is not None)
        share = lambda pred: round(sum(1 for n in notes if pred(n)) / len(notes), 2)  # noqa: E731
        by_type: dict[str, int] = {}
        for n in notes:
            by_type[n["note_type"] or "未知"] = by_type.get(n["note_type"] or "未知", 0) + 1
        by_author: dict[str, int] = {}
        for n in notes:
            by_author[n["author_type"] or "未知"] = by_author.get(n["author_type"] or "未知", 0) + 1
        return {
            "answers": len(obs),
            "cited_notes": len(notes),
            "likes_median": likes[len(likes) // 2] if likes else None,
            "likes_min": likes[0] if likes else None,
            "likes_max": likes[-1] if likes else None,
            "share_mentions_brand": share(lambda n: n["mentions_brand"]),
            "share_in_our_evidence": share(lambda n: note_id(n["url"]) in evidence_ids),
            "note_types": by_type,
            "author_types": by_author,
        }

    counts: dict[str, dict[str, Any]] = {}
    for o in groups["brand_named"] + groups["brand_absent"]:
        for src in o["sources"]:
            key = note_id(src["url"]) or src["title"] or ""
            entry = counts.setdefault(key, {"title": src["title"], "url": src["url"], "questions": set()})
            entry["questions"].add(o["question_ref"])
    repeated = sorted(
        ({"title": v["title"], "url": v["url"], "questions": sorted(v["questions"])} for v in counts.values() if len(v["questions"]) > 1),
        key=lambda v: -len(v["questions"]),
    )
    return {
        "brand_named": profile(groups["brand_named"]),
        "brand_absent": profile(groups["brand_absent"]),
        "cited_by_multiple_questions": repeated,
        "caveat": "样本很小时只能看出相关，不能说明因果。",
    }


def merge_observations(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same product + question + repeat replaces the earlier record."""
    key = lambda o: (o["product"], o["question_ref"], o["repeat_index"])  # noqa: E731
    merged = {key(o): o for o in existing}
    merged.update({key(o): o for o in new})
    return sorted(merged.values(), key=lambda o: (o["product"], o["question_ref"], o["repeat_index"]))


def live_status(plan_size: int, observations: list[dict[str, Any]]) -> str:
    done = sum(1 for o in observations if o["run_status"] == "completed")
    if done == 0:
        return "not_run"
    return "complete" if plan_size and done >= plan_size else "partial"


def summarize(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-product counts. Each measure is reported on its own, never combined."""
    rows = []
    for product in sorted({o["product"] for o in observations}):
        runs = [o for o in observations if o["product"] == product]
        done = [o for o in runs if o["run_status"] == "completed"]
        count = lambda field, value: sum(1 for o in done if o[field] == value)  # noqa: E731
        rows.append({
            "product": product,
            "runs": len(runs),
            "completed": len(done),
            "absent": count("brand_position", "absent"),
            "mentioned": count("brand_position", "mentioned"),
            "compared": count("brand_position", "compared"),
            "recommended": count("brand_position", "recommended"),
            "accuracy_fail": count("factual_accuracy", "fail"),
            "intent_pass": count("intent_satisfaction", "pass"),
            "needs_review": sum(1 for o in done if "review" in (o["factual_accuracy"], o["citation_quality"], o["intent_satisfaction"])),
        })
    return rows


def report_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Strip raw capture fields to match evaluation-report.schema.json."""
    fields = ("product", "model_or_version", "question_ref", "repeat_index", "run_status", "brand_position",
              "factual_accuracy", "citation_quality", "intent_satisfaction", "trace_ref", "notes")
    return {field: observation[field] for field in fields}


# ---- storage: data/live/<run_id>.json beside data/runs/<run_id>.json ----

def _paths(data_root: str | Path, run_id: str) -> tuple[Path, Path]:
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.match(run_id):
        raise LiveTestError("invalid run_id")
    root = Path(data_root)
    return root / "live" / f"{run_id}.json", root / "runs" / f"{run_id}.json"


def load_session(data_root: str | Path, run_id: str) -> dict[str, Any] | None:
    path, _ = _paths(data_root, run_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def start_session(
    data_root: str | Path,
    run_id: str,
    products: Iterable[str],
    *,
    repeats: int = 1,
    aliases: Iterable[str] = (),
    evidence_urls: Iterable[str] = (),
) -> dict[str, Any]:
    """Create or re-plan a live test for one saved question-bank run.

    Re-planning keeps observations already recorded.
    """
    path, run_path = _paths(data_root, run_id)
    if not run_path.is_file():
        raise LiveTestError("question-bank run not found")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    bank = run["result"]["question_bank"]
    previous = load_session(data_root, run_id) or {}
    session = {
        "run_id": run_id,
        "target_brand": bank["target_brand"],
        "brand_terms": brand_terms(bank["target_brand"], [*aliases, *previous.get("brand_terms", [])]),
        "products": [p.strip() for p in products if p and p.strip()],
        "repeats": repeats,
        "plan": build_test_plan(bank, products, repeats=repeats),
        "observations": previous.get("observations", []),
        # Our own evidence URLs, to see how often the AI cites the same notes.
        "evidence_urls": sorted(set(evidence_urls) | set(previous.get("evidence_urls", []))),
    }
    _save(path, run_path, run, session)
    return session


def record_runs(data_root: str | Path, run_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    path, run_path = _paths(data_root, run_id)
    session = load_session(data_root, run_id)
    if session is None:
        raise LiveTestError("start a live test plan before recording runs")
    new = [build_observation(r, session["brand_terms"]) for r in records]
    session["observations"] = merge_observations(session["observations"], new)
    _save(path, run_path, json.loads(run_path.read_text(encoding="utf-8")), session)
    return session


def _save(path: Path, run_path: Path, run: dict[str, Any], session: dict[str, Any]) -> None:
    session["live_test_status"] = live_status(len(session["plan"]), session["observations"])
    session["summary"] = summarize(session["observations"])
    session["source_profile"] = analyze_sources(session["observations"], session.get("evidence_urls", []))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    # Mirror into the run's evaluation report; the release decision is untouched.
    run["evaluation"]["live_test_status"] = session["live_test_status"]
    run["evaluation"]["live_observations"] = [report_observation(o) for o in session["observations"]]
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")


def _choice(value: Any, allowed: tuple[str, ...], field: str) -> None:
    if value not in allowed:
        raise LiveTestError(f"{field} must be one of {', '.join(allowed)}")
