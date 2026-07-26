PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (
        source_type IN (
            'paper_api', 'venue', 'repository', 'model_hub',
            'wechat', 'official_blog', 'manual'
        )
    ),
    connector TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('S_Core', 'A_Active', 'Watch', 'Manual')),
    homepage_url TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_runs (
    run_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    collector_name TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    cursor_before TEXT,
    cursor_after TEXT,
    status TEXT NOT NULL CHECK (
        status IN ('running', 'ok', 'partial', 'blocked', 'error', 'unchanged')
    ),
    fetched_count INTEGER NOT NULL DEFAULT 0,
    created_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error_json TEXT,
    stats_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS source_cursors (
    source_id TEXT PRIMARY KEY REFERENCES sources(source_id),
    cursor_value TEXT,
    last_successful_run_id TEXT REFERENCES collection_runs(run_id),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_documents (
    raw_document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    collection_run_id TEXT REFERENCES collection_runs(run_id),
    external_id TEXT,
    document_type TEXT NOT NULL CHECK (
        document_type IN (
            'paper_record', 'paper_pdf', 'venue_event', 'release',
            'repository', 'model', 'dataset', 'benchmark',
            'review_article', 'official_blog', 'manual'
        )
    ),
    canonical_url TEXT,
    title TEXT NOT NULL,
    authors_json TEXT NOT NULL DEFAULT '[]',
    published_at TEXT,
    updated_at_source TEXT,
    discovered_at TEXT NOT NULL,
    language TEXT,
    summary TEXT,
    content_text TEXT,
    content_html TEXT,
    identifiers_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    raw_payload_json TEXT,
    content_hash TEXT NOT NULL,
    access_status TEXT NOT NULL DEFAULT 'ok' CHECK (
        access_status IN ('ok', 'metadata_only', 'partial', 'blocked', 'deleted')
    ),
    UNIQUE (source_id, external_id, content_hash),
    UNIQUE (source_id, canonical_url, content_hash)
);

CREATE TABLE IF NOT EXISTS research_items (
    item_id TEXT PRIMARY KEY,
    item_type TEXT NOT NULL CHECK (
        item_type IN (
            'paper', 'framework', 'benchmark', 'dataset',
            'venue_event', 'review_article', 'industry_update'
        )
    ),
    canonical_title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    canonical_url TEXT,
    abstract_or_summary TEXT,
    authors_json TEXT NOT NULL DEFAULT '[]',
    organizations_json TEXT NOT NULL DEFAULT '[]',
    first_published_at TEXT,
    latest_updated_at TEXT,
    language TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('active', 'superseded', 'withdrawn', 'deleted', 'archived')
    ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item_identifiers (
    identifier_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES research_items(item_id) ON DELETE CASCADE,
    scheme TEXT NOT NULL CHECK (
        scheme IN (
            'doi', 'arxiv', 'openreview_forum', 'github',
            'huggingface', 'venue_paper', 'url_fingerprint', 'other'
        )
    ),
    value TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE (scheme, value)
);

CREATE TABLE IF NOT EXISTS item_versions (
    version_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES research_items(item_id) ON DELETE CASCADE,
    raw_document_id TEXT REFERENCES raw_documents(raw_document_id),
    version_kind TEXT NOT NULL CHECK (
        version_kind IN (
            'arxiv', 'openreview_submission', 'openreview_revision',
            'accepted_manuscript', 'camera_ready', 'journal_extension',
            'release', 'tag', 'web_revision', 'other'
        )
    ),
    version_label TEXT NOT NULL,
    version_number INTEGER,
    published_at TEXT,
    canonical_url TEXT,
    content_hash TEXT NOT NULL,
    change_significance TEXT CHECK (
        change_significance IN ('unknown', 'none', 'minor', 'material', 'major')
    ),
    change_summary TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (item_id, version_kind, version_label, content_hash)
);

CREATE TABLE IF NOT EXISTS paper_contents (
    content_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES research_items(item_id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK (
        content_type IN ('html', 'pdf_text', 'markdown', 'plain_text')
    ),
    content_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    UNIQUE (item_id, source_url, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_paper_contents_item_fetched
    ON paper_contents(item_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS item_relations (
    relation_id TEXT PRIMARY KEY,
    from_item_id TEXT NOT NULL REFERENCES research_items(item_id) ON DELETE CASCADE,
    to_item_id TEXT NOT NULL REFERENCES research_items(item_id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK (
        relation_type IN (
            'interprets', 'implements', 'extends', 'compares_with',
            'introduces', 'uses_dataset', 'evaluates_on',
            'supersedes', 'mentions'
        )
    ),
    evidence_raw_document_id TEXT REFERENCES raw_documents(raw_document_id),
    confidence REAL,
    created_at TEXT NOT NULL,
    UNIQUE (from_item_id, to_item_id, relation_type)
);

CREATE TABLE IF NOT EXISTS evidence_claims (
    claim_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES research_items(item_id) ON DELETE CASCADE,
    raw_document_id TEXT NOT NULL REFERENCES raw_documents(raw_document_id),
    claim_type TEXT NOT NULL CHECK (
        claim_type IN (
            'fact', 'metric', 'publication_status', 'release_status',
            'interpretation', 'limitation', 'trend'
        )
    ),
    claim_text TEXT NOT NULL,
    evidence_url TEXT,
    evidence_excerpt TEXT,
    evidence_tier TEXT NOT NULL CHECK (
        evidence_tier IN ('primary', 'official', 'authoritative_review', 'secondary')
    ),
    extraction_method TEXT NOT NULL CHECK (
        extraction_method IN ('deterministic', 'llm', 'human')
    ),
    confidence REAL NOT NULL,
    human_verified INTEGER NOT NULL DEFAULT 0 CHECK (human_verified IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS department_assessments (
    assessment_id TEXT PRIMARY KEY,
    department_id TEXT NOT NULL,
    item_id TEXT NOT NULL REFERENCES research_items(item_id) ON DELETE CASCADE,
    topic_tags_json TEXT NOT NULL DEFAULT '[]',
    global_importance REAL NOT NULL,
    department_relevance REAL NOT NULL,
    novelty REAL NOT NULL,
    evidence_quality REAL NOT NULL,
    trend_signal REAL NOT NULL,
    recommendation TEXT NOT NULL CHECK (
        recommendation IN ('must_read', 'recommended', 'scan', 'archive', 'exclude')
    ),
    recommended_section TEXT,
    rationale TEXT NOT NULL,
    estimated_read_minutes REAL,
    model_version TEXT,
    prompt_version TEXT,
    assessed_at TEXT NOT NULL,
    human_status TEXT NOT NULL DEFAULT 'pending' CHECK (
        human_status IN ('pending', 'approved', 'adjusted', 'rejected')
    ),
    UNIQUE (department_id, item_id, assessed_at)
);

CREATE TABLE IF NOT EXISTS weekly_issues (
    issue_id TEXT PRIMARY KEY,
    department_id TEXT NOT NULL,
    iso_week TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('draft', 'review', 'approved', 'published')
    ),
    title TEXT NOT NULL,
    summary TEXT,
    target_read_minutes INTEGER NOT NULL DEFAULT 30,
    generated_at TEXT,
    approved_at TEXT,
    published_at TEXT,
    output_json_url TEXT,
    output_markdown_url TEXT,
    output_page_url TEXT,
    UNIQUE (department_id, iso_week)
);

CREATE TABLE IF NOT EXISTS weekly_selections (
    selection_id TEXT PRIMARY KEY,
    issue_id TEXT NOT NULL REFERENCES weekly_issues(issue_id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES research_items(item_id),
    assessment_id TEXT REFERENCES department_assessments(assessment_id),
    section TEXT NOT NULL,
    position INTEGER NOT NULL,
    content_role TEXT NOT NULL CHECK (
        content_role IN (
            'trend', 'must_read', 'deep_read', 'quick_scan',
            'venue_update', 'artifact_update', 'library_review'
        )
    ),
    selection_reason TEXT NOT NULL,
    display_summary TEXT,
    department_implication TEXT,
    estimated_read_minutes REAL,
    requires_human_review INTEGER NOT NULL DEFAULT 1 CHECK (
        requires_human_review IN (0, 1)
    ),
    created_at TEXT NOT NULL,
    UNIQUE (issue_id, item_id)
);

CREATE TABLE IF NOT EXISTS editorial_reviews (
    review_id TEXT PRIMARY KEY,
    issue_id TEXT NOT NULL REFERENCES weekly_issues(issue_id) ON DELETE CASCADE,
    selection_id TEXT REFERENCES weekly_selections(selection_id) ON DELETE CASCADE,
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('approve', 'reject', 'revise', 'defer')
    ),
    comment TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_documents_published
    ON raw_documents(published_at);
CREATE INDEX IF NOT EXISTS idx_raw_documents_source
    ON raw_documents(source_id, discovered_at);
CREATE INDEX IF NOT EXISTS idx_research_items_type_updated
    ON research_items(item_type, latest_updated_at);
CREATE INDEX IF NOT EXISTS idx_item_versions_item
    ON item_versions(item_id, published_at);
CREATE INDEX IF NOT EXISTS idx_claims_item
    ON evidence_claims(item_id, evidence_tier);
CREATE INDEX IF NOT EXISTS idx_assessments_department
    ON department_assessments(department_id, recommendation, assessed_at);
CREATE INDEX IF NOT EXISTS idx_weekly_selections_issue
    ON weekly_selections(issue_id, section, position);
