-- Human-approved newsroom examples for future LoRA/QLoRA fine-tuning
CREATE TABLE IF NOT EXISTS newsroom_training_examples (
    id SERIAL PRIMARY KEY,
    raw_input TEXT NOT NULL,
    final_output TEXT NOT NULL,
    source_grade VARCHAR(8),
    verification_status VARCHAR(64),
    editor_notes TEXT,
    approved_by_human BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_newsroom_training_approved
    ON newsroom_training_examples(approved_by_human)
    WHERE approved_by_human = TRUE;
