PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category_id, slug)
);

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(module_id, slug)
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    module_id INTEGER REFERENCES modules(id) ON DELETE SET NULL,
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    question TEXT NOT NULL,
    answer TEXT,
    personal_answer TEXT,
    explanation TEXT,
    question_type TEXT NOT NULL DEFAULT 'general',
    difficulty TEXT NOT NULL DEFAULT 'medium',
    interview_trick TEXT,
    follow_up TEXT,
    interviewer_expectation TEXT,
    thinking_approach TEXT,
    sql_solution TEXT,
    alternative_solution TEXT,
    common_trap TEXT,
    interview_style TEXT,
    source TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    answer TEXT NOT NULL,
    is_preferred INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tricks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS question_tags (
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (question_id, tag_id)
);

CREATE TABLE IF NOT EXISTS interview_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER REFERENCES questions(id) ON DELETE SET NULL,
    asked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    response TEXT,
    score REAL,
    notes TEXT,
    source TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    interview_type TEXT
);

CREATE TABLE IF NOT EXISTS interview_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_key TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,
    interview_type TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    selected_topics TEXT,
    question_count INTEGER NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'not_started',
    current_question INTEGER NOT NULL DEFAULT 0,
    completed_questions INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    candidate_profile_id INTEGER REFERENCES candidate_profiles(id) ON DELETE SET NULL,
    job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    resume_document_id INTEGER REFERENCES resume_documents(id) ON DELETE SET NULL,
    resume_version_id INTEGER REFERENCES resume_versions(id) ON DELETE SET NULL,
    application_id INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    mode TEXT DEFAULT 'Structured Interview',
    voice_mode INTEGER NOT NULL DEFAULT 0,
    voice_provider TEXT DEFAULT 'mock',
    tts_provider TEXT DEFAULT 'mock',
    session_context_json TEXT DEFAULT '{}',
    voice_config_json TEXT DEFAULT '{}',
    metadata_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS interview_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    speaker TEXT NOT NULL CHECK (speaker IN ('interviewer', 'user', 'system')),
    message TEXT NOT NULL,
    question_id INTEGER REFERENCES questions(id) ON DELETE SET NULL,
    source_question_id INTEGER REFERENCES questions(id) ON DELETE SET NULL,
    follow_up INTEGER NOT NULL DEFAULT 0,
    transcript_text TEXT,
    voice_mode INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interview_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL UNIQUE REFERENCES interview_sessions(id) ON DELETE CASCADE,
    overall_summary TEXT,
    strengths TEXT,
    weaknesses TEXT,
    key_observations TEXT,
    recommended_next_steps TEXT,
    evaluation_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interview_weaknesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER REFERENCES interview_evaluations(id) ON DELETE CASCADE,
    session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    evidence TEXT,
    question_id INTEGER REFERENCES questions(id) ON DELETE SET NULL,
    confidence TEXT DEFAULT 'medium',
    severity TEXT DEFAULT 'medium',
    category TEXT DEFAULT 'general',
    source TEXT DEFAULT 'structured-fallback',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, name)
);

CREATE TABLE IF NOT EXISTS interview_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER REFERENCES interview_evaluations(id) ON DELETE CASCADE,
    session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    weakness TEXT NOT NULL,
    reason TEXT,
    recommended_question TEXT,
    practice_objective TEXT,
    priority INTEGER NOT NULL DEFAULT 1,
    source TEXT DEFAULT 'structured-fallback',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, weakness)
);

CREATE TABLE IF NOT EXISTS mission_adaptations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    weakness_name TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    reason TEXT,
    topic_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, weakness_name)
);

CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    module_id INTEGER REFERENCES modules(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'not_started',
    completed_at TEXT,
    UNIQUE(category_id, module_id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT,
    source TEXT NOT NULL,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    remote_type TEXT,
    description TEXT,
    requirements TEXT,
    skills TEXT,
    required_skills TEXT,
    preferred_skills TEXT,
    responsibilities TEXT,
    education TEXT,
    sql_requirements TEXT,
    sql TEXT,
    tools TEXT,
    experience TEXT,
    salary TEXT,
    posting_date TEXT,
    application_url TEXT,
    source_url TEXT,
    source_metadata TEXT,
    metadata TEXT,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS candidate_profiles (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    full_name TEXT, headline TEXT, email TEXT, phone TEXT, location TEXT,
    links TEXT, summary TEXT, skills TEXT, experience TEXT, education TEXT,
    tools TEXT, sql TEXT, projects TEXT, certifications TEXT, preferred_roles TEXT,
    preferred_locations TEXT, experience_level TEXT, availability TEXT,
    resume_information TEXT, additional_information TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saved_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'saved',
    applied_at TEXT, notes TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    candidate_profile_id INTEGER REFERENCES candidate_profiles(id) ON DELETE SET NULL,
    resume_document_id INTEGER REFERENCES resume_documents(id) ON DELETE SET NULL,
    resume_version_id INTEGER REFERENCES resume_versions(id) ON DELETE SET NULL,
    official_application_url TEXT,
    source_url TEXT,
    application_method TEXT DEFAULT 'external',
    confirmed_submitted INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT DEFAULT '{}',
    UNIQUE(job_id)
);

CREATE TABLE IF NOT EXISTS application_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    status TEXT NOT NULL, notes TEXT, changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    analysis_json TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'mock',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, provider)
);

CREATE TABLE IF NOT EXISTS candidate_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    match_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id)
);

CREATE TABLE IF NOT EXISTS resume_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, content_json TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resume_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id INTEGER NOT NULL REFERENCES resume_drafts(id) ON DELETE CASCADE,
    suggestion_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_source_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'unavailable',
    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result_count INTEGER NOT NULL DEFAULT 0,
    message TEXT
);

CREATE TABLE IF NOT EXISTS job_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL,
    delivered INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, notification_type)
);

CREATE TABLE IF NOT EXISTS application_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    note_type TEXT NOT NULL DEFAULT 'general',
    note_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application_resume_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    resume_document_id INTEGER REFERENCES resume_documents(id) ON DELETE SET NULL,
    resume_version_id INTEGER REFERENCES resume_versions(id) ON DELETE SET NULL,
    template TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(application_id, resume_version_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_external_identity ON jobs(source, external_id);
CREATE INDEX IF NOT EXISTS idx_job_notifications_pending ON job_notifications(delivered, created_at);
