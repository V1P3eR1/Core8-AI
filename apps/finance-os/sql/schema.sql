-- Sandbox development database bootstrap only; not a production migration.
CREATE TABLE IF NOT EXISTS finance_organizations (
  id text PRIMARY KEY, legal_name text NOT NULL
);
INSERT INTO finance_organizations(id, legal_name) VALUES ('core8', 'Core8-AI') ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS finance_stripe_event_inbox (
  event_id text PRIMARY KEY,
  organization_id text NOT NULL REFERENCES finance_organizations(id),
  event_type text NOT NULL,
  source_object_id text NOT NULL,
  event_created timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'received' CHECK(status IN ('received','processed','failed','dead')),
  attempts integer NOT NULL DEFAULT 0,
  next_attempt_at timestamptz,
  received_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  UNIQUE (event_id, organization_id)
);
CREATE INDEX IF NOT EXISTS finance_event_due ON finance_stripe_event_inbox(status,next_attempt_at);
CREATE TABLE IF NOT EXISTS finance_activity (
  stripe_event_id text PRIMARY KEY,
  organization_id text NOT NULL REFERENCES finance_organizations(id),
  event_type text NOT NULL,
  source_object_id text NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (stripe_event_id, organization_id)
    REFERENCES finance_stripe_event_inbox(event_id, organization_id)
);
-- finance_activity is an operational event log, NOT a general ledger.
