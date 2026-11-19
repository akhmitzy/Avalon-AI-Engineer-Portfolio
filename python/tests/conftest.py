import pytest

from dxreview.graph import ReviewGraph
from dxreview.policies import default_store
from dxreview.providers import OfflineExtractor
from dxreview.rag import HybridRetriever


@pytest.fixture(scope="session")
def store():
    return default_store()


@pytest.fixture(scope="session")
def retriever(store):
    return HybridRetriever(store)


@pytest.fixture
def audit_log():
    return []


@pytest.fixture
def graph(store, retriever, audit_log):
    return ReviewGraph(store=store, extractor=OfflineExtractor(), retriever=retriever, audit_sink=audit_log.append)
