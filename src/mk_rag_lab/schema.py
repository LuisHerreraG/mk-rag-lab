"""The index definition — one source of truth for the Search side.

Kept in code (not in the portal) so the index is reproducible and reviewable:
`python -m mk_rag_lab.ingest --recreate` builds it from this file.
"""

from __future__ import annotations

from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

EMBEDDING_DIMS = 1536  # text-embedding-3-small


def build_index(name: str) -> SearchIndex:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        # content is what gets embedded AND what gets searched by keyword
        SearchableField(name="content", type=SearchFieldDataType.String),
        # heading is the human anchor for a citation ("SKILL.md › Confidentiality")
        SearchableField(name="heading", type=SearchFieldDataType.String),
        SimpleField(name="path", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMS,
            vector_search_profile_name="default-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
        profiles=[
            VectorSearchProfile(
                name="default-profile", algorithm_configuration_name="default-hnsw"
            )
        ],
    )

    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="default-semantic",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="heading"),
                    content_fields=[SemanticField(field_name="content")],
                    keywords_fields=[SemanticField(field_name="path")],
                ),
            )
        ]
    )

    return SearchIndex(
        name=name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )
