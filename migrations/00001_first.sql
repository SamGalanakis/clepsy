-- +goose Up
-- +goose StatementBegin
SELECT 'up SQL query';

CREATE TABLE user_settings (
  id TEXT PRIMARY KEY CHECK (id='default'),
  username TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT (datetime('now')),
  timezone TEXT NOT NULL DEFAULT 'UTC',
  productivity_prompt TEXT NOT NULL,
  text_model_provider TEXT NOT NULL DEFAULT '',
  text_model_base_url TEXT,
  text_model TEXT NOT NULL DEFAULT '',
  image_processing_approach TEXT NOT NULL DEFAULT 'ocr',
  image_model_provider TEXT NOT NULL DEFAULT '',
  image_model_base_url TEXT,
  image_model TEXT NOT NULL DEFAULT '',

  -- encrypted secrets (AES-GCM blob: nonce|ciphertext|tag)
  text_model_api_key_enc BLOB,
  image_model_api_key_enc BLOB
);




-- Draft table to support multi-step account creation
-- Stores partially completed user settings until finalization
CREATE TABLE user_settings_draft (
  wizard_id TEXT PRIMARY KEY,
  -- basics
  username TEXT,                       -- may be NULL until provided
  timezone TEXT,
  description TEXT,
  -- productivity
  productivity_prompt TEXT,
  -- LLM configs (optional)
  text_model_provider TEXT,
  text_model_base_url TEXT,
  text_model TEXT,
  text_model_api_key_enc BLOB,         -- encrypted on write
  image_model_provider TEXT,
  image_model_base_url TEXT,
  image_model TEXT,
  image_model_api_key_enc BLOB,        -- encrypted on write
  image_processing_approach TEXT,
  -- Tags collected during wizard (JSON-encoded array of {name, description})
  tags_json TEXT,
  created_at DATETIME NOT NULL DEFAULT (datetime('now')),
  expires_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_user_settings_draft_expires_at ON user_settings_draft(expires_at);


-- Authentication table: stores the single user's password hash
CREATE TABLE user_auth (
  id TEXT PRIMARY KEY CHECK (id='default'),
  password_hash TEXT NOT NULL,          -- Argon2id string
  created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);


CREATE TABLE recovery_codes (
  id INTEGER PRIMARY KEY,
  code_hash TEXT NOT NULL,              -- Argon2id string of 128-bit random code
  used INTEGER NOT NULL DEFAULT 0 CHECK (used IN (0,1)),
  created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
-- exactly one active recovery code
CREATE UNIQUE INDEX uq_active_recovery ON recovery_codes(used) WHERE used=0;

CREATE TABLE sources (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,            -- "Sam Laptop"
  source_type TEXT NOT NULL,       -- "desktop_app", "mobile_app" ...
  token_hash TEXT NOT NULL,             -- Argon2id string of device_token
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
  last_seen DATETIME,
  created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_sources_status ON sources(status);
CREATE INDEX idx_sources_token_hash ON sources(token_hash);  -- Critical for auth lookups



CREATE TABLE source_enrollment_codes (
  id INTEGER PRIMARY KEY,
  code_hash TEXT NOT NULL,              -- Argon2id string of short-lived code
  expires_at DATETIME,                  -- nullable if you skip expiry
  used INTEGER NOT NULL DEFAULT 0 CHECK (used IN (0,1)),
  created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
-- exactly one active enrollment code
CREATE UNIQUE INDEX uq_active_enroll ON source_enrollment_codes(used) WHERE used=0;



CREATE TABLE aggregations (
    created_at DATETIME DEFAULT (datetime('now')),
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    first_timestamp DATETIME NOT NULL,
    last_timestamp DATETIME NOT NULL
);
CREATE TABLE activities (
  created_at           DATETIME DEFAULT (datetime('now')),
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  name                 TEXT NOT NULL,
  description          TEXT,
  productivity_level   TEXT NOT NULL CHECK (productivity_level IN ('very_productive','productive','neutral','distracting','very_distracting')),
  last_manual_action_time DATETIME NULL,
  source             TEXT NOT NULL CHECK (source IN ('auto','manual'))

);
CREATE TABLE tag_mappings (
    created_at DATETIME DEFAULT (datetime('now')),
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_id INTEGER NOT NULL,
    activity_id INTEGER NOT NULL,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
);
CREATE TABLE activity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    event_time DATETIME NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('open','close')),
    aggregation_id INTEGER NULL,
    last_manual_action_time DATETIME NULL,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
    FOREIGN KEY (aggregation_id) REFERENCES aggregations(id) ON DELETE CASCADE
);
-- Optimized indexes for activity_events (hot path for desktop worker)
CREATE INDEX idx_activity_events_activity_id ON activity_events (activity_id);
CREATE INDEX idx_activity_events_event_time ON activity_events (event_time);
CREATE INDEX idx_activity_events_activity_event_time ON activity_events (activity_id, event_time DESC);
CREATE INDEX idx_activity_events_time_activity ON activity_events (event_time, activity_id);

-- Tag mapping indexes
CREATE INDEX idx_tag_mappings_activity_id ON tag_mappings (activity_id);
CREATE INDEX idx_tag_mappings_tag_id ON tag_mappings (tag_id);

CREATE TABLE IF NOT EXISTS "tags" (
    created_at DATETIME DEFAULT (datetime('now')),
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    deleted_at DATETIME NULL
);
CREATE INDEX idx_tags_deleted_at ON tags (deleted_at);

-- Productivity filter index for goal calculations
CREATE INDEX idx_activities_productivity ON activities (productivity_level);
CREATE TABLE goals (
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  -- immutable per goal
  metric                 TEXT NOT NULL CHECK (metric IN ('total_activity_duration','productivity_level')),
  operator               TEXT NOT NULL CHECK (operator IN ('less_than','greater_than')),
  period                 TEXT NOT NULL CHECK (period IN ('day','week','month')),
  timezone               TEXT NOT NULL,
  created_at             DATETIME DEFAULT (datetime('now'))
);

-- Track goal pause/resume events (history)
CREATE TABLE goal_pause_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  goal_id       INTEGER NOT NULL,
  event_type    TEXT NOT NULL CHECK (event_type IN ('pause','resume')),
  at            DATETIME NOT NULL,            -- when the pause/resume occurred (UTC)
  created_at    DATETIME DEFAULT (datetime('now')),
  FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE
);
CREATE INDEX idx_goal_pause_events_goal_at ON goal_pause_events(goal_id, at);
CREATE TABLE goal_definitions (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  goal_id            INTEGER NOT NULL,
  name               TEXT NOT NULL,
  description        TEXT,
  metric_params_json TEXT DEFAULT NULL,
  -- target_value semantics:
  --   - For metric 'total_activity_duration': store duration in seconds (REAL)
  --   - For metric 'productivity_level': store value in [0,1] (REAL)
  target_value       ANY NOT NULL,
  include_mode       TEXT NOT NULL CHECK (include_mode IN ('any','all')),
  day_filter_json    TEXT DEFAULT NULL,  -- days to include - null means all
  time_filter_json   TEXT DEFAULT NULL,  -- time of day to include - null means all
  productivity_filter_json TEXT DEFAULT NULL, -- productivity level to include - null means all
  effective_from     DATETIME NOT NULL,

  created_at         DATETIME DEFAULT (datetime('now')),

  FOREIGN KEY(goal_id) REFERENCES goals(id) ON DELETE CASCADE
);
CREATE INDEX idx_goal_definitions_goal ON goal_definitions(goal_id);
CREATE INDEX idx_goal_definitions_goal_effective ON goal_definitions(goal_id, effective_from DESC);
CREATE TABLE goal_tags (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  goal_definition_id    INTEGER NOT NULL,
  tag_id                INTEGER NOT NULL,
  role                  TEXT NOT NULL CHECK (role IN ('include','exclude')),
  UNIQUE(goal_definition_id, tag_id, role),
  FOREIGN KEY(goal_definition_id) REFERENCES goal_definitions(id) ON DELETE CASCADE,
  FOREIGN KEY(tag_id)  REFERENCES tags(id) ON DELETE RESTRICT
);
CREATE INDEX idx_goal_tags_def ON goal_tags(goal_definition_id);
CREATE INDEX idx_goal_tags_tag ON goal_tags(tag_id);
CREATE TABLE goal_results (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  goal_definition_id   INTEGER NOT NULL,
  period_start         DATETIME NOT NULL,       -- UTC ISO8601
  period_end           DATETIME NOT NULL,       -- exclusive
  metric_value         REAL NOT NULL,
  success              INTEGER,
  eval_state           TEXT NOT NULL CHECK (eval_state IN ('ok','partial','na','paused')),
  eval_state_reason    TEXT,
  created_at           DATETIME DEFAULT (datetime('now')),
  UNIQUE(goal_definition_id, period_start),
  FOREIGN KEY(goal_definition_id) REFERENCES goal_definitions(id) ON DELETE CASCADE
);
CREATE INDEX idx_goal_results_def_period ON goal_results(goal_definition_id, period_start DESC);
CREATE TABLE goal_progress_current (
  goal_definition_id   INTEGER PRIMARY KEY,     -- one active row per goal def
  period_start         DATETIME NOT NULL,       -- UTC ISO8601
  period_end           DATETIME NOT NULL,       -- exclusive
  metric_value         REAL NOT NULL,
  success              INTEGER,        -- 0/1 (based on current calc)
  eval_state           TEXT NOT NULL CHECK (eval_state IN ('ok','partial','na')),
  eval_state_reason    TEXT,
  updated_at           DATETIME DEFAULT (datetime('now'))
);




CREATE TABLE sessions (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  llm_id TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT (datetime('now')),
  sessionization_run_id INTEGER NOT NULL,
  FOREIGN KEY (sessionization_run_id) REFERENCES sessionization_run(id)
);




CREATE TABLE session_to_activity (
  session_id INTEGER NOT NULL,
  activity_id INTEGER NOT NULL,
  created_at DATETIME NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (session_id, activity_id),
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
  UNIQUE(activity_id)
);





CREATE TABLE candidate_session_to_activity (
  session_id INTEGER NOT NULL,
  activity_id INTEGER NOT NULL,
  created_at DATETIME NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (session_id, activity_id),
  FOREIGN KEY (session_id) REFERENCES candidate_sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
);
CREATE INDEX idx_candidate_session_to_activity_session_created ON candidate_session_to_activity(session_id, created_at, activity_id);


CREATE TABLE sessionization_run (
  id INTEGER PRIMARY KEY,
  created_at DATETIME NOT NULL DEFAULT (datetime('now')),
  candidate_creation_start DATETIME NOT NULL,
  candidate_creation_end DATETIME NOT NULL,
  finalized_horizon DATETIME,
  overlap_start DATETIME,
  right_tail_end DATETIME
);

CREATE TABLE candidate_sessions (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  llm_id TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT (datetime('now')),
  sessionization_run_id INTEGER NOT NULL,
  FOREIGN KEY (sessionization_run_id) REFERENCES sessionization_run(id)
);


-- Unique aggregation window (start_time, end_time)
CREATE UNIQUE INDEX IF NOT EXISTS idx_aggregations_window_unique
ON aggregations(start_time, end_time);

-- Unique activity event by (activity_id, event_time, event_type)
CREATE UNIQUE INDEX IF NOT EXISTS idx_activity_events_unique
ON activity_events(activity_id, event_time, event_type);

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

-- Drop indexes first (if they exist)
-- Goal system indexes
DROP INDEX IF EXISTS idx_goal_tags_def;
DROP INDEX IF EXISTS idx_goal_tags_tag;
DROP INDEX IF EXISTS idx_goal_definitions_goal;
DROP INDEX IF EXISTS idx_goal_definitions_goal_effective;
DROP INDEX IF EXISTS idx_goal_results_def_period;
DROP INDEX IF EXISTS idx_goal_pause_events_goal_at;

-- Session system indexes
DROP INDEX IF EXISTS idx_candidate_session_to_activity_session_created;

DROP INDEX IF EXISTS idx_user_settings_draft_expires_at;

-- Activity and tag indexes
DROP INDEX IF EXISTS idx_tag_mappings_activity_id;
DROP INDEX IF EXISTS idx_tag_mappings_tag_id;
DROP INDEX IF EXISTS idx_activity_events_activity_id;
DROP INDEX IF EXISTS idx_activity_events_event_time;
DROP INDEX IF EXISTS idx_activity_events_activity_event_time;
DROP INDEX IF EXISTS idx_activity_events_time_activity;
DROP INDEX IF EXISTS idx_activities_productivity;

DROP INDEX IF EXISTS idx_tags_deleted_at;

-- Source indexes
DROP INDEX IF EXISTS idx_sources_status;
DROP INDEX IF EXISTS idx_sources_token_hash;

-- Unique constraint indexes
DROP INDEX IF EXISTS uq_active_recovery;
DROP INDEX IF EXISTS uq_active_enroll;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS goal_tags;
DROP TABLE IF EXISTS goal_results;
DROP TABLE IF EXISTS goal_progress_current;
DROP TABLE IF EXISTS goal_definitions;
DROP TABLE IF EXISTS goal_pause_events;
DROP TABLE IF EXISTS goals;

DROP TABLE IF EXISTS tag_mappings;
DROP TABLE IF EXISTS activity_events;
DROP TABLE IF EXISTS activities;
DROP TABLE IF EXISTS aggregations;

DROP TABLE IF EXISTS sources;
DROP TABLE IF EXISTS source_enrollment_codes;
DROP TABLE IF EXISTS recovery_codes;

DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS user_settings_draft;
DROP TABLE IF EXISTS user_settings;
DROP TABLE IF EXISTS user_auth;



DROP TABLE IF EXISTS session_to_activity;
DROP TABLE IF EXISTS sessions;



DROP TABLE IF EXISTS candidate_session_to_activity;
DROP TABLE IF EXISTS candidate_sessions;
DROP TABLE IF EXISTS sessionization_run;

DROP INDEX IF EXISTS idx_activity_events_unique;
DROP INDEX IF EXISTS idx_aggregations_window_unique;

-- +goose StatementEnd
