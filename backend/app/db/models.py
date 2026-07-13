"""
資料庫 Schema
欄位：圖片路徑、checkpoint、LoRA、seed、steps、prompt、生成時間
"""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, Column, Integer, String, Text, DateTime, Float, BigInteger, ForeignKey, UniqueConstraint

from app.db.database import Base


class GeneratedImage(Base):
    """生成圖片記錄"""
    __tablename__ = "generated_images"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), nullable=True, index=True)
    image_path = Column(String(512), nullable=False)
    checkpoint = Column(String(256), nullable=True)
    lora = Column(String(256), nullable=True)
    # 重生所需：使用的 workflow 模板與 diffusion-model 家族（如 Anima）的元件檔名
    template = Column(String(128), nullable=True)
    diffusion_model = Column(String(256), nullable=True)  # UNETLoader.unet_name
    text_encoder = Column(String(256), nullable=True)  # CLIPLoader.clip_name
    vae = Column(String(256), nullable=True)  # VAELoader.vae_name
    seed = Column(Integer, nullable=True)
    steps = Column(Integer, nullable=True)
    cfg = Column(Float, nullable=True)
    prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    # 忠實重生所需：實際送出 ComfyUI 的完整 workflow（JSON 字串），以及來源圖/遮罩的
    # gallery 相對路徑（workflow_json 內只嵌 ComfyUI 暫存輸入檔名，重生需重新上傳原圖）。
    workflow_json = Column(Text, nullable=True)
    source_image = Column(String(512), nullable=True)
    source_mask = Column(String(512), nullable=True)
    # CIV-E immutable recipe-provenance bundle. All fields remain nullable for legacy rows.
    recipe_json = Column(Text, nullable=True)
    recipe_sha256 = Column(String(64), nullable=True)
    recipe_workflow_json = Column(Text, nullable=True)
    recipe_workflow_sha256 = Column(String(64), nullable=True)
    recipe_input_hashes_json = Column(Text, nullable=True)
    recipe_resource_locks_json = Column(Text, nullable=True)
    recipe_runtime_provenance_json = Column(Text, nullable=True)
    recipe_reproduction_level = Column(String(64), nullable=True)
    # CIV-V-F immutable Parent/Child lineage; both remain null for legacy rows.
    recipe_variant_lineage_json = Column(Text, nullable=True)
    recipe_variant_lineage_sha256 = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GeneratedArtifact(Base):
    """Generic generated artifact record for images, videos, and future files."""
    __tablename__ = "generated_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), nullable=True, index=True)
    artifact_type = Column(String(32), nullable=False, index=True)
    gallery_path = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=True)
    source_node_id = Column(String(64), nullable=True)
    source_node_type = Column(String(256), nullable=True)
    file_size = Column(Integer, nullable=True)
    workflow_json = Column(Text, nullable=True)
    prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    fps = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CivitaiSourceAliasRegistryRecord(Base):
    """CIV-SA-A immutable audited source binding; its primary key is the registry version."""
    __tablename__ = "civitai_source_alias_registry_records"
    __table_args__ = (
        CheckConstraint("length(acquisition_evidence_sha256) = 64", name="ck_source_alias_evidence_sha256_length"),
        CheckConstraint("length(parent_recipe_sha256) = 64", name="ck_source_alias_parent_recipe_sha256_length"),
        {"sqlite_autoincrement": True},
    )

    registry_version = Column(Integer, primary_key=True, autoincrement=True)
    source_identity_json = Column(Text, nullable=False)
    acquisition_evidence_json = Column(Text, nullable=False)
    acquisition_evidence_sha256 = Column(String(64), nullable=False)
    parent_recipe_sha256 = Column(String(64), nullable=False)
    thumbnail_url = Column(Text, nullable=True)
    thumbnail_path = Column(String(1024), nullable=True)
    user_note = Column(Text, nullable=True)
    approved_tags_json = Column(Text, nullable=False, default="[]")
    prompt_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    # CIV-SA-I terminal lifecycle marker. Alias rows and immutable source evidence
    # are deliberately retained forever; this timestamp never re-enables a target.
    archived_at = Column(DateTime(timezone=True), nullable=True)


class CivitaiSourceAlias(Base):
    """One exact normalized key in the single global source-alias namespace."""
    __tablename__ = "civitai_source_aliases"
    __table_args__ = (
        UniqueConstraint("normalized_key", name="uq_civitai_source_alias_normalized_key"),
        CheckConstraint("alias_kind IN ('primary', 'alternate')", name="ck_source_alias_kind"),
    )

    id = Column(Integer, primary_key=True, index=True)
    registry_version = Column(Integer, ForeignKey("civitai_source_alias_registry_records.registry_version"), nullable=False, index=True)
    original_alias = Column(String(512), nullable=False)
    normalized_key = Column(String(512), nullable=False)
    alias_kind = Column(String(16), nullable=False)


class CivitaiSourceAliasHistory(Base):
    """Append-only CIV-SA-H/I rename/archive audit chain for one immutable registry target."""
    __tablename__ = "civitai_source_alias_history"
    __table_args__ = (
        CheckConstraint("operation IN ('rename', 'archive')", name="ck_source_alias_history_operation"),
        CheckConstraint("length(event_sha256) = 64", name="ck_source_alias_history_event_sha256_length"),
    )

    id = Column(Integer, primary_key=True, index=True)
    registry_version = Column(
        Integer,
        ForeignKey("civitai_source_alias_registry_records.registry_version"),
        nullable=False,
        index=True,
    )
    operation = Column(String(16), nullable=False)
    before_aliases_json = Column(Text, nullable=False)
    after_aliases_json = Column(Text, nullable=False)
    previous_event_sha256 = Column(String(64), nullable=True)
    event_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class CivitaiSourceAliasRepointTransition(Base):
    """CIV-SA-N append-only audited edge between immutable source-alias targets."""
    __tablename__ = "civitai_source_alias_repoint_transitions"
    __table_args__ = (
        UniqueConstraint("from_registry_version", name="uq_source_alias_repoint_from_version"),
        UniqueConstraint("to_registry_version", name="uq_source_alias_repoint_to_version"),
        CheckConstraint("length(from_record_sha256) = 64", name="ck_source_alias_repoint_from_hash_length"),
        CheckConstraint("length(to_record_sha256) = 64", name="ck_source_alias_repoint_to_hash_length"),
        CheckConstraint("length(event_sha256) = 64", name="ck_source_alias_repoint_event_hash_length"),
    )

    id = Column(Integer, primary_key=True, index=True)
    from_registry_version = Column(Integer, ForeignKey("civitai_source_alias_registry_records.registry_version"), nullable=False, index=True)
    to_registry_version = Column(Integer, ForeignKey("civitai_source_alias_registry_records.registry_version"), nullable=False, index=True)
    aliases_json = Column(Text, nullable=False)
    from_record_sha256 = Column(String(64), nullable=False)
    to_record_sha256 = Column(String(64), nullable=False)
    source_history_tail_sha256 = Column(String(64), nullable=True)
    previous_repoint_event_sha256 = Column(String(64), nullable=True)
    event_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class CivitaiVariationSet(Base):
    """CIV-V-G immutable variation-set identity; members/events are append-only."""
    __tablename__ = "civitai_variation_sets"

    id = Column(Integer, primary_key=True, index=True)
    variation_set_id = Column(String(64), nullable=False, unique=True, index=True)
    parent_recipe_sha256 = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CivitaiVariationSetMember(Base):
    __tablename__ = "civitai_variation_set_members"

    id = Column(Integer, primary_key=True, index=True)
    variation_set_id = Column(String(64), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False)
    client_child_key = Column(String(128), nullable=False)
    identity_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CivitaiVariationSetEvent(Base):
    __tablename__ = "civitai_variation_set_events"

    id = Column(Integer, primary_key=True, index=True)
    variation_set_id = Column(String(64), nullable=False, index=True)
    member_ordinal = Column(Integer, nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LoraTrainingJob(Base):
    """Durable LoRA training job state."""
    __tablename__ = "lora_training_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), nullable=False, unique=True, index=True)
    folder = Column(String(512), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    stage = Column(String(64), nullable=False, default="queued")
    progress = Column(Float, nullable=False, default=0.0)
    current_epoch = Column(Integer, nullable=True)
    total_epochs = Column(Integer, nullable=True)
    log_path = Column(String(1024), nullable=True)
    output_path = Column(String(1024), nullable=True)
    registered_lora_name = Column(String(512), nullable=True)
    registration_error = Column(Text, nullable=True)
    error_code = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    dataset_hash = Column(String(64), nullable=True, index=True)
    normalized_trigger_token = Column(String(128), nullable=True)
    params_json = Column(Text, nullable=True)
    smoke_test_status = Column(String(64), nullable=True)
    smoke_test_job_id = Column(String(64), nullable=True)
    smoke_test_artifact = Column(String(512), nullable=True)
    smoke_test_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancel_requested_at = Column(DateTime, nullable=True)


class DownloadedResource(Base):
    """Downloaded model/resource ledger kept in the local database.

    Files may live on local or external storage, but this metadata remains in the
    local SQLite DB so a missing external disk can be audited and resources can
    be re-downloaded from their original URLs.
    """
    __tablename__ = "downloaded_resources"

    id = Column(Integer, primary_key=True, index=True)
    resource_name = Column(String(512), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False, index=True)
    provider = Column(String(64), nullable=True, index=True)
    source_url = Column(Text, nullable=False)
    resolved_download_url = Column(Text, nullable=True)
    local_path = Column(String(1024), nullable=True)
    storage_root = Column(String(256), nullable=True, index=True)
    file_size = Column(BigInteger, nullable=True)
    sha256 = Column(String(64), nullable=True, index=True)
    model_id = Column(String(128), nullable=True)
    version_id = Column(String(128), nullable=True)
    # Civitai immutable file/AIR identities are nullable for historical rows.
    civitai_file_id = Column(String(128), nullable=True, index=True)
    air = Column(String(512), nullable=True, index=True)
    status = Column(String(64), nullable=False, default="planned", index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    downloaded_at = Column(DateTime, nullable=True)
