#!/usr/bin/env python3
"""
Hawaiʻi Appleseed Writing Bot
RAG-powered writing assistant: ChromaDB + Claude Sonnet 4.6 + prompt caching.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

GENERATION_MODEL = "claude-sonnet-4-6"
COLLECTION_NAME = "appleseed_docs_v2"   # bumped — new metadata schema
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 150
DEFAULT_N_RESULTS = 8

# Relationship-memory module. These chunks live in the SAME Chroma collection as
# the public writing corpus but carry doc_type == MEMORY_DOC_TYPE so they can be
# included or excluded as a unit. They hold internal coalition/meeting/people
# notes — background only, never public-facing source material (see the guardrail
# in SYSTEM_INSTRUCTIONS and relationship-memory/METHODOLOGY.md). Public-writing
# retrieval excludes them by default; pass --memory (CLI) or the UI toggle to
# fold a small number of memory chunks in as background context.
MEMORY_DOC_TYPE = "relationship_memory"
DEFAULT_MEMORY_N = 6

ROOT = Path(__file__).parent
POSITIONS_PATH = ROOT / "positions.md"
DB_PATH = ROOT / ".chroma"

SYSTEM_INSTRUCTIONS = """You are a writing assistant for Hawaiʻi Appleseed Center for Law & Economic Justice, a nonprofit that advocates for economic justice for working families in Hawaiʻi.

Your job is to draft testimony, blog posts, and other content in HA's voice, anchored to HA's actual positions. You are writing what will go out under HA's name — accuracy and faithfulness matter more than fluency.

You will receive up to four things in every conversation:
1. A POSITIONS document — HA's curated stances, voice rules, and language conventions. Treat this as authoritative when it conflicts with retrieved context.
2. RETRIEVED CONTEXT — relevant excerpts from prior HA testimony, blog posts, and publications, each with a [SOURCE] tag.
3. RELATIONSHIP CONTEXT (optional) — internal, private notes on coalition partners, legislators, meetings, decisions, and campaign strategy, each with a [CONTEXT] tag. This is background to help you understand the legislative landscape, who the players are, what is already underway, and how to frame and target the piece.
4. A TASK — what the user wants written.

Rules:
- Ground every factual claim in either the POSITIONS document or RETRIEVED CONTEXT. Use inline numeric citations like [1], [2] referring to the [SOURCE] of the chunk you drew from. Do not invent statistics, bill numbers, or hearing details.
- RELATIONSHIP CONTEXT is INTERNAL and BACKGROUND ONLY. Use it to inform strategy, framing, and emphasis — never reproduce it. Do NOT quote it, do NOT cite it in the Sources section, do NOT attribute private positions, assessments, or characterizations to named legislators or partners in the published text, and do NOT reveal internal coalition strategy. If a fact is needed in the final piece, it must be supported by the POSITIONS document or RETRIEVED CONTEXT, not by RELATIONSHIP CONTEXT.
- After the body, list the sources used in a "Sources" section: "[1] filename — brief note on what was drawn from it."
- Match the voice conventions in the POSITIONS document exactly: ʻokina/kahakō usage, "working families" not "low-income," named populations not "vulnerable groups."
- For testimony, use HA's standard structure: greeting → position → urgent context → evidence → counter to opposition → restate ask → mahalo close.
- For blog posts, use HA's narrative arc: values-grounded opening → problem → why the system fails → evidence → proven model → the bill or action.
- If the task asks for a position that is not covered in the POSITIONS document or contradicts it, FLAG that and ask for clarification rather than inventing a stance.
- If retrieved context is thin or off-topic, say so explicitly rather than padding."""


# ---------------------------------------------------------------------------
# Document discovery + metadata extraction
# ---------------------------------------------------------------------------

INGEST_PATTERNS = [
    "blog-posts/**/*.txt",
    "reference/**/*.txt",
    "testimony/**/*.txt",
    "publications/*.txt",
    # Relationship-memory module — internal coalition/meeting/people notes.
    # Markdown, not .txt; the ingest pipeline (relationship-memory/ingest/)
    # writes these. The METHODOLOGY/README docs are deliberately not ingested.
    "relationship-memory/data/**/*.md",
]

# testimony/<topic>/HB1234_<...>_2026.txt or similar
BILL_RE = re.compile(r"\b([HS][BR]\s?\d{3,5})\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20\d{2})\b")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_")  # publications/2024-08-19_xxx.txt

# Relationship-memory filename conventions (see relationship-memory/METHODOLOGY.md):
#   meetings/mtg_2026-01-29_tax-fairness.md  → date + source group
#   people/person_nicole-woo.md, rep_chris_todd.md, sen_chris_lee.md → person
MEETING_RE = re.compile(r"^mtg_(\d{4}-\d{2}-\d{2})_(.+)\.md$")
_PERSON_PREFIX_RE = re.compile(r"^(person|rep|sen|ag|cm|gov)[_-]", re.IGNORECASE)


def _person_name(fname: str) -> str:
    """'person_nicole-woo.md'/'rep_chris_todd.md' → 'Nicole Woo'/'Chris Todd'."""
    stem = Path(fname).stem
    stem = _PERSON_PREFIX_RE.sub("", stem)
    return re.sub(r"[_-]+", " ", stem).strip().title()


def extract_metadata(rel_path: str, content: str) -> dict:
    """Derive doc_type, topic, year, bill from path + content. Stance is no
    longer stored here — it is resolved at query time from the document's
    explicit header + positions.md (see search.effective_stance)."""
    parts = Path(rel_path).parts
    top = parts[0] if parts else ""

    meta: dict = {"source": rel_path}

    # doc_type from top-level folder
    if top == "testimony":
        meta["doc_type"] = "testimony"
        meta["topic"] = parts[1] if len(parts) > 1 else "unknown"
    elif top == "blog-posts":
        meta["doc_type"] = "blog"
        # blog-posts/2026/title.txt → year from the folder
        if len(parts) > 1 and parts[1].isdigit():
            meta["year"] = int(parts[1])
    elif top == "publications":
        meta["doc_type"] = "publication"
        m = DATE_RE.match(parts[-1])
        if m:
            meta["year"] = int(m.group(1)[:4])
            meta["pub_date"] = m.group(1)
    elif top == "reference":
        meta["doc_type"] = "reference"
    elif top == "relationship-memory":
        meta["doc_type"] = MEMORY_DOC_TYPE
        # parts: relationship-memory/data/<kind>/<file>, or .../data/<file>
        sub = parts[2] if len(parts) > 3 else None
        fname = parts[-1]
        if sub == "people":
            meta["mem_kind"] = "person"
            meta["person"] = _person_name(fname)
        elif sub == "meetings":
            meta["mem_kind"] = "meeting"
            m = MEETING_RE.match(fname)
            if m:
                meta["mem_date"] = m.group(1)
                meta["year"] = int(m.group(1)[:4])  # YEAR_RE misses it: '_2026' has no \b
                meta["group"] = m.group(2)  # all-staff | lat | tax-fairness | ...
        elif sub == "projects":
            meta["mem_kind"] = "project"
        elif sub in ("action-items", "decisions", "archive"):
            meta["mem_kind"] = sub.replace("-", "_")
        else:
            meta["mem_kind"] = "synthesis"  # current-state, timeline, etc.
    else:
        meta["doc_type"] = "other"

    # is this a sample/template (lower priority for retrieval)?
    meta["is_sample"] = parts[-1].lower().startswith("sample_")

    # year from filename if not already set (testimony often: HB1234_2026_*.txt)
    if "year" not in meta:
        m = YEAR_RE.search(parts[-1])
        if m:
            meta["year"] = int(m.group(1))

    # bill from filename → fall back to first bill mentioned in body
    fname_bill = BILL_RE.search(parts[-1])
    if fname_bill:
        meta["bill"] = fname_bill.group(1).upper().replace(" ", "")
    else:
        body_bill = BILL_RE.search(content[:2000])
        if body_bill:
            meta["bill"] = body_bill.group(1).upper().replace(" ", "")

    return meta


def discover_documents() -> list[Path]:
    docs: list[Path] = []
    for pattern in INGEST_PATTERNS:
        docs.extend(Path(p) for p in glob.glob(str(ROOT / pattern), recursive=True))
    # Dedupe + sort for determinism
    return sorted(set(docs))


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> Iterable[str]:
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        if end == len(text):
            break
        start += size - overlap


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def get_embedding_function():
    if os.environ.get("OPENAI_API_KEY"):
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        print("Using OpenAI embeddings (text-embedding-3-small)")
        return OpenAIEmbeddingFunction(
            api_key=os.environ["OPENAI_API_KEY"],
            model_name="text-embedding-3-small",
        )
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    print("OPENAI_API_KEY not set — using local embeddings (all-MiniLM-L6-v2).")
    return DefaultEmbeddingFunction()


def index_documents(force: bool = False):
    import chromadb

    ef = get_embedding_function()

    if not force and DB_PATH.exists():
        try:
            client = chromadb.PersistentClient(path=str(DB_PATH))
            coll = client.get_collection(COLLECTION_NAME, embedding_function=ef)
            count = coll.count()
            if count > 0:
                print(f"Using existing index ({count} chunks). Use --reindex to rebuild.")
                return coll
        except Exception:
            pass

    if DB_PATH.exists():
        import shutil
        shutil.rmtree(DB_PATH)

    docs = discover_documents()
    print(f"Found {len(docs)} documents to index.")

    ids: list[str] = []
    texts: list[str] = []
    metas: list[dict] = []

    for path in docs:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"  skip {path}: {e}")
            continue

        rel = str(path.relative_to(ROOT))
        base_meta = extract_metadata(rel, content)

        for i, chunk in enumerate(chunk_text(content)):
            chunk_id = f"{rel}::{i}"
            ids.append(chunk_id)
            texts.append(chunk)
            metas.append({**base_meta, "chunk": i})

    print(f"Chunked into {len(ids)} pieces. Computing embeddings...")
    embeddings = ef(texts)
    print(f"Embeddings computed ({len(embeddings)} vectors). Writing to ChromaDB...")

    client = chromadb.PersistentClient(path=str(DB_PATH))
    coll = client.create_collection(COLLECTION_NAME, embedding_function=ef)

    batch = 100
    for i in range(0, len(ids), batch):
        end = min(i + batch, len(ids))
        coll.add(
            ids=ids[i:end],
            documents=texts[i:end],
            metadatas=metas[i:end],
            embeddings=embeddings[i:end],
        )
        print(f"  stored {end}/{len(ids)}")

    print(f"Done. {len(ids)} chunks from {len(docs)} documents.")
    return coll


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _eq_or_in(field: str, value) -> dict | None:
    """{field: v} for a scalar, {field: {$in: [...]}} for a list, None if empty."""
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        vals = [v for v in value if v]
        if not vals:
            return None
        return {field: vals[0]} if len(vals) == 1 else {field: {"$in": list(vals)}}
    return {field: value}


def build_where_filter(doc_type: str | list | None, topic: str | list | None,
                       year_min: int | None, year_max: int | None = None) -> dict | None:
    """ChromaDB metadata filter. None when no filters apply.

    `doc_type` and `topic` accept a scalar or a list (list -> $in)."""
    clauses: list[dict] = []
    for clause in (_eq_or_in("doc_type", doc_type), _eq_or_in("topic", topic)):
        if clause:
            clauses.append(clause)
    if year_min is not None:
        clauses.append({"year": {"$gte": year_min}})
    if year_max is not None:
        clauses.append({"year": {"$lte": year_max}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _with_clause(where: dict | None, clause: dict) -> dict:
    """AND `clause` into an existing Chroma where-filter (or return it alone)."""
    if not where:
        return clause
    if "$and" in where:
        return {"$and": where["$and"] + [clause]}
    return {"$and": [where, clause]}


def retrieve(collection, query: str, n: int, where: dict | None,
             *, use_bm25: bool = True, use_rerank: bool = True,
             include_memory: bool = False, dense_k: int = 30, bm25_k: int = 30,
             rerank_k: int | None = None) -> list[tuple[str, dict]]:
    """Return list of (text, metadata) via hybrid retrieval (dense + BM25 + cross-encoder rerank).

    `dense_k`/`bm25_k` widen the candidate pool (raise them when `n` is large,
    e.g. to fill several pages of distinct documents); `rerank_k` caps how many
    of those candidates the cross-encoder actually scores (the slow step).

    Relationship-memory chunks are excluded by default so public-facing drafts are
    grounded only in HA's published corpus. Pass include_memory=True to allow them
    (or use retrieve_memory to pull them as a separate, clearly-labeled block)."""
    from retrieval import hybrid_retrieve
    if not include_memory:
        where = _with_clause(where, {"doc_type": {"$ne": MEMORY_DOC_TYPE}})
    return hybrid_retrieve(collection, query, n, where, use_bm25=use_bm25,
                           use_rerank=use_rerank, dense_k=dense_k, bm25_k=bm25_k,
                           rerank_k=rerank_k)


def retrieve_memory(collection, query: str, n: int,
                    *, use_bm25: bool = True, use_rerank: bool = True) -> list[tuple[str, dict]]:
    """Retrieve only relationship-memory chunks (coalition/meeting/people notes)."""
    from retrieval import hybrid_retrieve
    return hybrid_retrieve(collection, query, n, {"doc_type": MEMORY_DOC_TYPE},
                           use_bm25=use_bm25, use_rerank=use_rerank)


def format_context(hits: list[tuple[str, dict]]) -> str:
    blocks = []
    for i, (text, meta) in enumerate(hits, start=1):
        tag = f"[{i}] SOURCE: {meta.get('source', '?')}"
        extras = []
        for k in ("doc_type", "topic", "year", "bill"):
            if meta.get(k):
                extras.append(f"{k}={meta[k]}")
        if extras:
            tag += f"  ({', '.join(extras)})"
        blocks.append(f"{tag}\n{text}")
    return "\n\n---\n\n".join(blocks)


def format_memory_context(hits: list[tuple[str, dict]]) -> str:
    """Format relationship-memory chunks as [CONTEXT] blocks (internal/background)."""
    blocks = []
    for i, (text, meta) in enumerate(hits, start=1):
        tag = f"[CONTEXT {i}] {meta.get('source', '?')}"
        extras = []
        for k in ("mem_kind", "person", "group", "mem_date", "year"):
            if meta.get(k):
                extras.append(f"{k}={meta[k]}")
        if extras:
            tag += f"  ({', '.join(extras)})"
        blocks.append(f"{tag}\n{text}")
    return "\n\n---\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def load_positions() -> str:
    if not POSITIONS_PATH.exists():
        print(f"WARNING: {POSITIONS_PATH.name} not found — proceeding without positions doc.")
        return "(no positions document available)"
    return POSITIONS_PATH.read_text(encoding="utf-8")


def generate(prompt: str, hits: list[tuple[str, dict]], *, mode: str | None = None, client=None,
             memory_hits: list[tuple[str, dict]] | None = None) -> tuple[str, dict]:
    import anthropic

    positions = load_positions()
    context = format_context(hits)

    mode_hint = ""
    if mode:
        mode_hint = f"\n\nMODE: {mode} — follow the structural conventions for this mode in the POSITIONS document."

    memory_block = ""
    if memory_hits:
        memory_block = (
            f"RELATIONSHIP CONTEXT (internal — background only, do not quote or cite):\n\n"
            f"{format_memory_context(memory_hits)}\n\n=====\n\n"
        )

    if client is None:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Cache the system prompt + positions doc + retrieved context.
    # The system prompt is stable across runs; positions doc changes only when
    # staff edit it; retrieved context changes per query but is reused if the
    # follow-up is within the 5-minute TTL on the same hits.
    response = client.messages.create(
        model=GENERATION_MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_INSTRUCTIONS,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"POSITIONS:\n\n{positions}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"RETRIEVED CONTEXT:\n\n{context}\n\n"
                            f"=====\n\n"
                            f"{memory_block}"
                            f"TASK: {prompt}{mode_hint}"
                        ),
                    },
                ],
            }
        ],
    )

    text = response.content[0].text
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
    }
    return text, usage


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Hawaiʻi Appleseed Writing Bot")
    parser.add_argument("prompt", nargs="?", help="Writing prompt")
    parser.add_argument("--reindex", action="store_true", help="Rebuild the document index")
    parser.add_argument("--mode", choices=["testimony", "blog", "op-ed"], help="Output mode")
    parser.add_argument("--doc-type", choices=["testimony", "blog", "publication", "reference", "relationship_memory"],
                        help="Restrict retrieval to this doc type (relationship_memory = query the coalition/meeting/people notes directly)")
    parser.add_argument("--topic", help="Restrict retrieval to this testimony topic (e.g. labor, housing)")
    parser.add_argument("--year-min", type=int, help="Restrict retrieval to documents from this year or later")
    parser.add_argument("-n", "--n-results", type=int, default=DEFAULT_N_RESULTS,
                        help=f"Number of chunks to retrieve (default {DEFAULT_N_RESULTS})")
    parser.add_argument("--show-sources", action="store_true",
                        help="Print full retrieved chunks before generation (for debugging)")
    parser.add_argument("--no-bm25", action="store_true", help="Skip BM25 leg of hybrid retrieval (dense + rerank only)")
    parser.add_argument("--no-rerank", action="store_true", help="Skip cross-encoder rerank (dense + BM25 fused only)")
    parser.add_argument("--memory", action="store_true",
                        help="Fold in relationship-memory (coalition/meeting/people notes) as internal background context")
    parser.add_argument("--memory-n", type=int, default=DEFAULT_MEMORY_N,
                        help=f"Number of relationship-memory chunks to include with --memory (default {DEFAULT_MEMORY_N})")
    args = parser.parse_args()

    if not args.prompt and not args.reindex:
        parser.print_help()
        sys.exit(1)

    collection = index_documents(force=args.reindex)

    if not args.prompt:
        return

    where = build_where_filter(args.doc_type, args.topic, args.year_min)
    if where:
        print(f"Retrieval filter: {json.dumps(where)}")

    memory_only = args.doc_type == MEMORY_DOC_TYPE
    hits = retrieve(collection, args.prompt, args.n_results, where,
                    use_bm25=not args.no_bm25, use_rerank=not args.no_rerank,
                    include_memory=memory_only)
    print(f"Retrieved {len(hits)} chunks.")

    # Separate background pass over relationship memory (skipped if we're already
    # querying memory directly via --doc-type relationship_memory).
    memory_hits = None
    if args.memory and not memory_only:
        memory_hits = retrieve_memory(collection, args.prompt, args.memory_n,
                                      use_bm25=not args.no_bm25, use_rerank=not args.no_rerank)
        print(f"Retrieved {len(memory_hits)} relationship-memory chunks (internal background).")

    if args.show_sources:
        print("\n--- RETRIEVED CHUNKS ---")
        print(format_context(hits))
        if memory_hits:
            print("\n--- RELATIONSHIP CONTEXT (internal) ---")
            print(format_memory_context(memory_hits))
        print("--- END CHUNKS ---\n")

    print(f"\nGenerating with {GENERATION_MODEL}...\n{'=' * 60}\n")
    text, usage = generate(args.prompt, hits, mode=args.mode, memory_hits=memory_hits)
    print(text)
    print(f"\n{'=' * 60}")
    sources = sorted({m.get("source", "?") for _, m in hits})
    print(f"Sources retrieved: {', '.join(sources)}")
    print(
        f"Tokens — input: {usage['input_tokens']}, output: {usage['output_tokens']}, "
        f"cache_create: {usage['cache_creation_input_tokens']}, cache_read: {usage['cache_read_input_tokens']}"
    )


if __name__ == "__main__":
    main()
