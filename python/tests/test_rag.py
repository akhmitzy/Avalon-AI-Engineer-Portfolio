from dxreview.rag import rrf
from dxreview.rag.bm25 import BM25Index
from dxreview.rag.embeddings import HashingEmbedder, cosine
from dxreview.rag.tokenize import tokenize
from dxreview.rag.vectorstore import InMemoryVectorStore


def test_slash_splits_gene_names():
    """Regression: BRCA1/BRCA2 used to stay one token."""
    assert tokenize("BRCA1/BRCA2") == ["brca1", "brca2"]


def test_hyphen_emits_parts_and_joined():
    assert tokenize("MSI-H") == ["msi", "h", "msih"]


def test_stemming_joins_word_forms():
    assert tokenize("covered")[0] == tokenize("coverage")[0]
    assert tokenize("documented")[0] == tokenize("documentation")[0]


def test_codes_are_not_stemmed():
    assert tokenize("CYP2C19 81225") == ["cyp2c19", "81225"]


def test_bm25_ranks_matching_doc_first():
    idx = BM25Index().build([("a", "clopidogrel CYP2C19 genotype"), ("b", "vitamin D level"), ("c", "BRCA2 sequencing")])
    assert idx.search("BRCA2")[0][0] == "c"
    assert idx.search("unrelated words") == []


def test_rrf_rewards_agreement():
    fused = dict(rrf([["a", "b", "c"], ["b", "a", "d"]]))
    assert fused["a"] == fused["b"] > fused["c"] == fused["d"]


def test_hashing_embedder_is_deterministic_and_normalized():
    e = HashingEmbedder(dim=64)
    v1, v2 = e.embed(["genetic counseling"])[0], e.embed(["genetic counseling"])[0]
    assert v1 == v2
    assert abs(cosine(v1, v1) - 1.0) < 1e-9


def test_vector_store_delete_policy():
    s = InMemoryVectorStore()
    s.upsert([("P1#a", [1.0, 0.0], {"policy_id": "P1"}), ("P2#a", [0.0, 1.0], {"policy_id": "P2"})])
    s.delete_policy("P1")
    assert len(s) == 1 and s.search([0.0, 1.0], 5)[0][0] == "P2#a"


def test_retriever_finds_brca2_coverage(retriever):
    ids = [h.chunk.chunk_id for h in retriever.search("BRCA2 coverage criteria genetic counseling", k=3)]
    assert "LAB-GEN-001#coverage-criteria" in ids


def test_retriever_policy_filter(retriever):
    hits = retriever.search("coverage criteria", k=5, policy_id="LAB-PGX-003")
    assert hits and all(h.chunk.policy_id == "LAB-PGX-003" for h in hits)


def test_reindex_single_policy(retriever):
    assert retriever.reindex(["LAB-CHEM-004"]) == len(retriever.store.get("LAB-CHEM-004").chunks)
