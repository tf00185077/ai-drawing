BEGIN TRANSACTION;
CREATE TABLE civitai_source_alias_backfill_candidates (
	id INTEGER NOT NULL,
	gallery_image_id INTEGER NOT NULL,
	source_identity_json TEXT NOT NULL,
	acquisition_evidence_json TEXT NOT NULL,
	acquisition_evidence_sha256 VARCHAR(64) NOT NULL,
	parent_recipe_sha256 VARCHAR(64) NOT NULL,
	thumbnail_path VARCHAR(1024),
	suggested_alias VARCHAR(512) NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_source_alias_backfill_gallery_image_id UNIQUE (gallery_image_id),
	CONSTRAINT ck_source_alias_backfill_evidence_sha256_length CHECK (length(acquisition_evidence_sha256) = 64),
	CONSTRAINT ck_source_alias_backfill_parent_recipe_sha256_length CHECK (length(parent_recipe_sha256) = 64),
	FOREIGN KEY(gallery_image_id) REFERENCES generated_images (id)
);
CREATE TABLE civitai_source_alias_history (
	id INTEGER NOT NULL,
	registry_version INTEGER NOT NULL,
	operation VARCHAR(16) NOT NULL,
	before_aliases_json TEXT NOT NULL,
	after_aliases_json TEXT NOT NULL,
	previous_event_sha256 VARCHAR(64),
	event_sha256 VARCHAR(64) NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_source_alias_history_operation CHECK (operation IN ('rename', 'archive')),
	CONSTRAINT ck_source_alias_history_event_sha256_length CHECK (length(event_sha256) = 64),
	FOREIGN KEY(registry_version) REFERENCES civitai_source_alias_registry_records (registry_version)
);
CREATE TABLE civitai_source_alias_registry_records (
	registry_version INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	source_identity_json TEXT NOT NULL,
	acquisition_evidence_json TEXT NOT NULL,
	acquisition_evidence_sha256 VARCHAR(64) NOT NULL,
	parent_recipe_sha256 VARCHAR(64) NOT NULL,
	thumbnail_url TEXT,
	thumbnail_path VARCHAR(1024),
	user_note TEXT,
	approved_tags_json TEXT NOT NULL,
	prompt_summary TEXT,
	created_at DATETIME NOT NULL,
	archived_at DATETIME,
	CONSTRAINT ck_source_alias_evidence_sha256_length CHECK (length(acquisition_evidence_sha256) = 64),
	CONSTRAINT ck_source_alias_parent_recipe_sha256_length CHECK (length(parent_recipe_sha256) = 64)
);
CREATE TABLE civitai_source_alias_repoint_transitions (
	id INTEGER NOT NULL,
	from_registry_version INTEGER NOT NULL,
	to_registry_version INTEGER NOT NULL,
	aliases_json TEXT NOT NULL,
	from_record_sha256 VARCHAR(64) NOT NULL,
	to_record_sha256 VARCHAR(64) NOT NULL,
	source_history_tail_sha256 VARCHAR(64),
	previous_repoint_event_sha256 VARCHAR(64),
	event_sha256 VARCHAR(64) NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_source_alias_repoint_from_version UNIQUE (from_registry_version),
	CONSTRAINT uq_source_alias_repoint_to_version UNIQUE (to_registry_version),
	CONSTRAINT ck_source_alias_repoint_from_hash_length CHECK (length(from_record_sha256) = 64),
	CONSTRAINT ck_source_alias_repoint_to_hash_length CHECK (length(to_record_sha256) = 64),
	CONSTRAINT ck_source_alias_repoint_event_hash_length CHECK (length(event_sha256) = 64),
	FOREIGN KEY(from_registry_version) REFERENCES civitai_source_alias_registry_records (registry_version),
	FOREIGN KEY(to_registry_version) REFERENCES civitai_source_alias_registry_records (registry_version)
);
CREATE TABLE civitai_source_aliases (
	id INTEGER NOT NULL,
	registry_version INTEGER NOT NULL,
	original_alias VARCHAR(512) NOT NULL,
	normalized_key VARCHAR(512) NOT NULL,
	alias_kind VARCHAR(16) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_civitai_source_alias_normalized_key UNIQUE (normalized_key),
	CONSTRAINT ck_source_alias_kind CHECK (alias_kind IN ('primary', 'alternate')),
	FOREIGN KEY(registry_version) REFERENCES civitai_source_alias_registry_records (registry_version)
);
CREATE TABLE civitai_variation_set_events (
	id INTEGER NOT NULL,
	variation_set_id VARCHAR(64) NOT NULL,
	member_ordinal INTEGER NOT NULL,
	event_type VARCHAR(64) NOT NULL,
	payload_json TEXT NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE civitai_variation_set_members (
	id INTEGER NOT NULL,
	variation_set_id VARCHAR(64) NOT NULL,
	ordinal INTEGER NOT NULL,
	client_child_key VARCHAR(128) NOT NULL,
	identity_json TEXT NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE civitai_variation_sets (
	id INTEGER NOT NULL,
	variation_set_id VARCHAR(64) NOT NULL,
	parent_recipe_sha256 VARCHAR(64) NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE downloaded_resources (
	id INTEGER NOT NULL,
	resource_name VARCHAR(512) NOT NULL,
	resource_type VARCHAR(64) NOT NULL,
	provider VARCHAR(64),
	source_url TEXT NOT NULL,
	resolved_download_url TEXT,
	local_path VARCHAR(1024),
	storage_root VARCHAR(256),
	file_size BIGINT,
	sha256 VARCHAR(64),
	model_id VARCHAR(128),
	version_id VARCHAR(128),
	civitai_file_id VARCHAR(128),
	air VARCHAR(512),
	status VARCHAR(64) NOT NULL,
	notes TEXT,
	created_at DATETIME,
	downloaded_at DATETIME,
	PRIMARY KEY (id)
);
CREATE TABLE generated_artifacts (
	id INTEGER NOT NULL,
	job_id VARCHAR(64),
	artifact_type VARCHAR(32) NOT NULL,
	gallery_path VARCHAR(512) NOT NULL,
	mime_type VARCHAR(128),
	source_node_id VARCHAR(64),
	source_node_type VARCHAR(256),
	file_size INTEGER,
	workflow_json TEXT,
	prompt TEXT,
	negative_prompt TEXT,
	metadata_json TEXT,
	fps FLOAT,
	frame_count INTEGER,
	duration FLOAT,
	width INTEGER,
	height INTEGER,
	created_at DATETIME,
	PRIMARY KEY (id)
);
CREATE TABLE generated_images (
	id INTEGER NOT NULL,
	job_id VARCHAR(64),
	image_path VARCHAR(512) NOT NULL,
	checkpoint VARCHAR(256),
	lora VARCHAR(256),
	template VARCHAR(128),
	diffusion_model VARCHAR(256),
	text_encoder VARCHAR(256),
	vae VARCHAR(256),
	seed INTEGER,
	steps INTEGER,
	cfg FLOAT,
	prompt TEXT,
	negative_prompt TEXT,
	workflow_json TEXT,
	source_image VARCHAR(512),
	source_mask VARCHAR(512),
	revision_context_json TEXT,
	recipe_json TEXT,
	recipe_sha256 VARCHAR(64),
	recipe_workflow_json TEXT,
	recipe_workflow_sha256 VARCHAR(64),
	recipe_input_hashes_json TEXT,
	recipe_resource_locks_json TEXT,
	recipe_runtime_provenance_json TEXT,
	recipe_reproduction_level VARCHAR(64),
	recipe_variant_lineage_json TEXT,
	recipe_variant_lineage_sha256 VARCHAR(64),
	created_at DATETIME,
	PRIMARY KEY (id)
);
CREATE TABLE generation_batch_members (
	id INTEGER NOT NULL,
	public_job_id VARCHAR(64) NOT NULL,
	execution_id VARCHAR(64) NOT NULL,
	batch_index INTEGER NOT NULL,
	seed BIGINT NOT NULL,
	status VARCHAR(32) NOT NULL,
	failure_code VARCHAR(64),
	failure_message TEXT,
	started_at DATETIME,
	completed_at DATETIME,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_generation_batch_member_ordinal UNIQUE (public_job_id, batch_index),
	CONSTRAINT uq_generation_batch_member_seed UNIQUE (public_job_id, seed),
	CONSTRAINT ck_generation_batch_member_status CHECK (status IN ('queued', 'running', 'completed', 'failed')),
	CONSTRAINT ck_generation_batch_member_ordinal CHECK (batch_index >= 0),
	FOREIGN KEY(public_job_id) REFERENCES generation_batches (public_job_id)
);
CREATE TABLE generation_batches (
	id INTEGER NOT NULL,
	public_job_id VARCHAR(64) NOT NULL,
	batch_seed_mode VARCHAR(32) NOT NULL,
	status VARCHAR(32) NOT NULL,
	batch_total INTEGER NOT NULL,
	batch_completed INTEGER NOT NULL,
	batch_failed INTEGER NOT NULL,
	current_batch_index INTEGER,
	submitted_at DATETIME NOT NULL,
	started_at DATETIME,
	completed_at DATETIME,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_generation_batch_status CHECK (status IN ('queued', 'running', 'completed', 'failed')),
	CONSTRAINT ck_generation_batch_total CHECK (batch_total > 0),
	CONSTRAINT ck_generation_batch_counts CHECK (batch_completed >= 0 AND batch_failed >= 0)
);
CREATE TABLE lora_output_reservations (
	job_id VARCHAR(64) NOT NULL,
	requested_name VARCHAR(256) NOT NULL,
	request_key VARCHAR(256) NOT NULL,
	resolved_name VARCHAR(256) NOT NULL,
	resolved_key VARCHAR(256) NOT NULL,
	serial INTEGER NOT NULL,
	run_locator VARCHAR(512) NOT NULL,
	PRIMARY KEY (job_id),
	CONSTRAINT uq_lora_request_serial UNIQUE (request_key, serial),
	UNIQUE (resolved_key),
	UNIQUE (run_locator)
);
CREATE TABLE lora_training_jobs (
	id INTEGER NOT NULL,
	job_id VARCHAR(64) NOT NULL,
	folder VARCHAR(512) NOT NULL,
	status VARCHAR(32) NOT NULL,
	stage VARCHAR(64) NOT NULL,
	progress FLOAT NOT NULL,
	current_epoch INTEGER,
	total_epochs INTEGER,
	log_path VARCHAR(1024),
	output_path VARCHAR(1024),
	registered_lora_name VARCHAR(512),
	registration_error TEXT,
	error_code VARCHAR(128),
	error_message TEXT,
	error_details_json TEXT,
	dataset_hash VARCHAR(64),
	profile_hash VARCHAR(64),
	normalized_trigger_token VARCHAR(128),
	params_json TEXT,
	recipe_schema_version VARCHAR(64),
	recipe_hash VARCHAR(64),
	recipe_json TEXT,
	execution_evidence_json TEXT,
	output_name VARCHAR(256),
	resolved_output_name VARCHAR(256),
	output_serial INTEGER,
	run_locator VARCHAR(512),
	output_config_hash VARCHAR(64),
	validation_status VARCHAR(32),
	output_sha256 VARCHAR(64),
	registration_status VARCHAR(32),
	smoke_test_status VARCHAR(64),
	smoke_test_job_id VARCHAR(64),
	smoke_test_artifact VARCHAR(512),
	smoke_test_error TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	started_at DATETIME,
	completed_at DATETIME,
	cancel_requested_at DATETIME,
	PRIMARY KEY (id)
);
CREATE INDEX ix_generated_images_job_id ON generated_images (job_id);
CREATE INDEX ix_generated_images_id ON generated_images (id);
CREATE INDEX ix_generated_artifacts_artifact_type ON generated_artifacts (artifact_type);
CREATE INDEX ix_generated_artifacts_job_id ON generated_artifacts (job_id);
CREATE INDEX ix_generated_artifacts_id ON generated_artifacts (id);
CREATE INDEX ix_generation_batches_id ON generation_batches (id);
CREATE INDEX ix_generation_batches_status ON generation_batches (status);
CREATE UNIQUE INDEX ix_generation_batches_public_job_id ON generation_batches (public_job_id);
CREATE INDEX ix_civitai_variation_sets_id ON civitai_variation_sets (id);
CREATE UNIQUE INDEX ix_civitai_variation_sets_variation_set_id ON civitai_variation_sets (variation_set_id);
CREATE INDEX ix_civitai_variation_sets_parent_recipe_sha256 ON civitai_variation_sets (parent_recipe_sha256);
CREATE INDEX ix_civitai_variation_set_members_id ON civitai_variation_set_members (id);
CREATE INDEX ix_civitai_variation_set_members_variation_set_id ON civitai_variation_set_members (variation_set_id);
CREATE INDEX ix_civitai_variation_set_events_id ON civitai_variation_set_events (id);
CREATE INDEX ix_civitai_variation_set_events_variation_set_id ON civitai_variation_set_events (variation_set_id);
CREATE INDEX ix_civitai_variation_set_events_member_ordinal ON civitai_variation_set_events (member_ordinal);
CREATE INDEX ix_lora_training_jobs_dataset_hash ON lora_training_jobs (dataset_hash);
CREATE INDEX ix_lora_training_jobs_status ON lora_training_jobs (status);
CREATE INDEX ix_lora_training_jobs_id ON lora_training_jobs (id);
CREATE INDEX ix_lora_training_jobs_recipe_hash ON lora_training_jobs (recipe_hash);
CREATE UNIQUE INDEX ix_lora_training_jobs_job_id ON lora_training_jobs (job_id);
CREATE INDEX ix_lora_training_jobs_folder ON lora_training_jobs (folder);
CREATE INDEX ix_downloaded_resources_resource_name ON downloaded_resources (resource_name);
CREATE INDEX ix_downloaded_resources_sha256 ON downloaded_resources (sha256);
CREATE INDEX ix_downloaded_resources_storage_root ON downloaded_resources (storage_root);
CREATE INDEX ix_downloaded_resources_resource_type ON downloaded_resources (resource_type);
CREATE INDEX ix_downloaded_resources_status ON downloaded_resources (status);
CREATE INDEX ix_downloaded_resources_provider ON downloaded_resources (provider);
CREATE INDEX ix_downloaded_resources_civitai_file_id ON downloaded_resources (civitai_file_id);
CREATE INDEX ix_downloaded_resources_id ON downloaded_resources (id);
CREATE INDEX ix_downloaded_resources_air ON downloaded_resources (air);
CREATE INDEX ix_lora_output_reservations_request_key ON lora_output_reservations (request_key);
CREATE UNIQUE INDEX ix_generation_batch_members_execution_id ON generation_batch_members (execution_id);
CREATE INDEX ix_generation_batch_members_public_job_id ON generation_batch_members (public_job_id);
CREATE INDEX ix_generation_batch_members_id ON generation_batch_members (id);
CREATE INDEX ix_generation_batch_members_status ON generation_batch_members (status);
CREATE INDEX ix_civitai_source_alias_backfill_candidates_id ON civitai_source_alias_backfill_candidates (id);
CREATE UNIQUE INDEX ix_civitai_source_alias_backfill_candidates_gallery_image_id ON civitai_source_alias_backfill_candidates (gallery_image_id);
CREATE INDEX ix_civitai_source_aliases_registry_version ON civitai_source_aliases (registry_version);
CREATE INDEX ix_civitai_source_aliases_id ON civitai_source_aliases (id);
CREATE INDEX ix_civitai_source_alias_history_id ON civitai_source_alias_history (id);
CREATE INDEX ix_civitai_source_alias_history_registry_version ON civitai_source_alias_history (registry_version);
CREATE INDEX ix_civitai_source_alias_repoint_transitions_id ON civitai_source_alias_repoint_transitions (id);
CREATE INDEX ix_civitai_source_alias_repoint_transitions_to_registry_version ON civitai_source_alias_repoint_transitions (to_registry_version);
CREATE INDEX ix_civitai_source_alias_repoint_transitions_from_registry_version ON civitai_source_alias_repoint_transitions (from_registry_version);
DELETE FROM "sqlite_sequence";
COMMIT;
