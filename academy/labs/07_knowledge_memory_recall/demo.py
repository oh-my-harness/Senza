"""Lab 07: run offline BM25 evidence or delegate to canonical live examples."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


LAB_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = LAB_DIR.parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from academy.common import load_trace, render_trace, run_live_example  # noqa: E402

try:
    from .retrieval import BM25Index, load_fixture_documents
except ImportError:  # Direct script execution.
    from retrieval import BM25Index, load_fixture_documents


LIVE_EXAMPLES = {
    "rag": "36_rag_qa.py",
    "infra": "23_infra_integration.py",
}

RECORDED_QUERIES = (
    "Senza local_source BM25 knowledge_search knowledge_read",
    "MemoryStore Mutex Vec persistence recall projector index population",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("recorded", "live"), default="recorded")
    parser.add_argument("--live-example", choices=tuple(LIVE_EXAMPLES), default="rag")
    parser.add_argument("--top-k", type=int, default=3)
    return parser


def recorded_searches(*, top_k: int = 3) -> list[tuple[str, list[tuple[str, float]]]]:
    """Run the deterministic fixture queries and return serializable evidence."""

    index = BM25Index(load_fixture_documents())
    return [
        (
            query,
            [
                (hit.document.doc_id, round(hit.score, 4))
                for hit in index.search(query, limit=top_k)
            ],
        )
        for query in RECORDED_QUERIES
    ]


def main() -> None:
    args = build_parser().parse_args()
    if args.mode == "live":
        run_live_example(LIVE_EXAMPLES[args.live_example])
        return

    trace = load_trace(LAB_DIR / "expected_trace.json")
    print(render_trace(trace))
    print("\nOffline BM25 evidence (three checked-in Senza documents)")
    for query, hits in recorded_searches(top_k=args.top_k):
        print(f"- query: {query}")
        for rank, (doc_id, score) in enumerate(hits, start=1):
            print(f"  {rank}. {doc_id} score={score:.4f}")


if __name__ == "__main__":
    main()
