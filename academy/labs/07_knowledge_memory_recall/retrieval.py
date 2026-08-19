"""A small, dependency-free BM25 implementation for Academy Lab 07."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union


TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*|\d+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """Tokenize identifiers, numbers, and individual CJK characters."""

    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


@dataclass(frozen=True)
class Document:
    """One fixture document indexed by the teaching retriever."""

    doc_id: str
    title: str
    text: str


@dataclass(frozen=True)
class SearchHit:
    """One scored BM25 result."""

    document: Document
    score: float


def load_fixture_documents(
    directory: Optional[Union[str, Path]] = None,
) -> list[Document]:
    """Load the three checked-in Markdown fixtures in deterministic order."""

    fixture_dir = Path(directory) if directory else Path(__file__).with_name("fixtures")
    documents: list[Document] = []
    for path in sorted(fixture_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        first_line = next((line for line in text.splitlines() if line.strip()), path.stem)
        title = first_line.removeprefix("#").strip()
        documents.append(Document(doc_id=path.name, title=title, text=text))
    if not documents:
        raise ValueError(f"no Markdown documents found in {fixture_dir}")
    return documents


class BM25Index:
    """Minimal Okapi BM25 index suitable for deterministic offline teaching."""

    def __init__(self, documents: list[Document], *, k1: float = 1.5, b: float = 0.75):
        if not documents:
            raise ValueError("BM25 requires at least one document")
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 requires k1 > 0 and 0 <= b <= 1")

        self.documents = tuple(documents)
        self.k1 = k1
        self.b = b
        self._tokens = tuple(tokenize(document.text) for document in documents)
        self._term_frequencies = tuple(Counter(tokens) for tokens in self._tokens)
        self._document_frequency = Counter(
            token for tokens in self._tokens for token in set(tokens)
        )
        self._average_length = sum(map(len, self._tokens)) / len(self._tokens)

    def _inverse_document_frequency(self, token: str) -> float:
        document_count = len(self.documents)
        document_frequency = self._document_frequency.get(token, 0)
        return math.log(
            1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
        )

    def search(self, query: str, *, limit: int = 3) -> list[SearchHit]:
        """Return positive-scoring hits ordered by score and then document id."""

        if limit < 1:
            raise ValueError("limit must be at least 1")
        query_terms = Counter(tokenize(query))
        hits: list[SearchHit] = []

        for document, tokens, frequencies in zip(
            self.documents, self._tokens, self._term_frequencies
        ):
            length_normalizer = 1 - self.b + self.b * len(tokens) / self._average_length
            score = 0.0
            for token, query_frequency in query_terms.items():
                term_frequency = frequencies.get(token, 0)
                if not term_frequency:
                    continue
                numerator = term_frequency * (self.k1 + 1)
                denominator = term_frequency + self.k1 * length_normalizer
                score += (
                    query_frequency
                    * self._inverse_document_frequency(token)
                    * numerator
                    / denominator
                )
            if score > 0:
                hits.append(SearchHit(document=document, score=score))

        return sorted(hits, key=lambda hit: (-hit.score, hit.document.doc_id))[:limit]
