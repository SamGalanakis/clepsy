-- +goose Up
-- +goose StatementBegin
-- Add unique indexes to enforce idempotency for aggregation windows and events

-- Unique aggregation window (start_time, end_time)
CREATE UNIQUE INDEX IF NOT EXISTS idx_aggregations_window_unique
ON aggregations(start_time, end_time);

-- Unique activity event by (activity_id, event_time, event_type)
CREATE UNIQUE INDEX IF NOT EXISTS idx_activity_events_unique
ON activity_events(activity_id, event_time, event_type);
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
DROP INDEX IF EXISTS idx_activity_events_unique;
DROP INDEX IF EXISTS idx_aggregations_window_unique;
-- +goose StatementEnd
