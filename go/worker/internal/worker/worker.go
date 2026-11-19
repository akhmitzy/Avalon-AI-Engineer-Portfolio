// Package worker consumes review requests from Kafka, calls the DxReview API,
// and publishes results.
//
// Delivery guarantees:
//   - At-least-once: an offset is committed only after the result (or the
//     dead-letter record) has been published. A crash in between means the
//     message is redelivered.
//   - Idempotent effects: redelivered messages are detected with the
//     idempotency key (the message's Idempotency-Key header, else request_id).
//     The same key is sent to the API, which replays its stored result.
//   - Poison messages go to the DLQ with the error and attempt count, and the
//     offset is committed, so one bad message cannot block a partition.
package worker

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"math/rand/v2"
	"time"
)

// Message is a broker-agnostic Kafka record.
type Message struct {
	Topic     string
	Partition int
	Offset    int64
	Key       []byte
	Value     []byte
	Headers   map[string]string
}

// Consumer fetches messages and commits offsets. Implemented by the kafka-go adapter.
type Consumer interface {
	Fetch(ctx context.Context) (Message, error)
	Commit(ctx context.Context, m Message) error
}

// Producer publishes records. Implemented by the kafka-go adapter.
type Producer interface {
	Publish(ctx context.Context, topic string, key, value []byte, headers map[string]string) error
}

// ReviewRequest mirrors the API's request body.
type ReviewRequest struct {
	RequestID  string   `json:"request_id"`
	CPTCode    string   `json:"cpt_code"`
	ICD10Codes []string `json:"icd10_codes,omitempty"`
	Note       string   `json:"note"`
	Payer      string   `json:"payer,omitempty"`
}

// Config controls topics and retry behaviour.
type Config struct {
	ResultsTopic string
	DLQTopic     string
	MaxAttempts  int
	BaseBackoff  time.Duration
	MaxBackoff   time.Duration
}

// Worker ties the pieces together.
type Worker struct {
	cfg      Config
	consumer Consumer
	producer Producer
	client   ReviewClient
	seen     IdempotencyStore
	log      *slog.Logger
	sleep    func(context.Context, time.Duration) error
}

// New builds a worker with defaults for unset config fields.
func New(cfg Config, c Consumer, p Producer, rc ReviewClient, s IdempotencyStore, log *slog.Logger) *Worker {
	if cfg.MaxAttempts <= 0 {
		cfg.MaxAttempts = 5
	}
	if cfg.BaseBackoff <= 0 {
		cfg.BaseBackoff = 200 * time.Millisecond
	}
	if cfg.MaxBackoff <= 0 {
		cfg.MaxBackoff = 10 * time.Second
	}
	if log == nil {
		log = slog.Default()
	}
	return &Worker{cfg: cfg, consumer: c, producer: p, client: rc, seen: s, log: log, sleep: sleepCtx}
}

// Run processes messages until ctx is cancelled or a non-recoverable error occurs.
func (w *Worker) Run(ctx context.Context) error {
	for {
		m, err := w.consumer.Fetch(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			return fmt.Errorf("fetch: %w", err)
		}
		if err := w.Handle(ctx, m); err != nil {
			// Not committed: the message will be redelivered after restart/rebalance.
			return err
		}
	}
}

// Handle processes one message and commits it when its effects are durable.
func (w *Worker) Handle(ctx context.Context, m Message) error {
	var req ReviewRequest
	if err := json.Unmarshal(m.Value, &req); err != nil || req.RequestID == "" || req.CPTCode == "" || req.Note == "" {
		reason := "invalid request: missing request_id, cpt_code or note"
		if err != nil {
			reason = "invalid JSON: " + err.Error()
		}
		return w.deadLetter(ctx, m, reason, 0)
	}
	key := m.Headers["Idempotency-Key"]
	if key == "" {
		key = req.RequestID
	}
	log := w.log.With("request_id", req.RequestID, "partition", m.Partition, "offset", m.Offset)

	done, err := w.seen.Seen(ctx, key)
	if err != nil {
		return fmt.Errorf("idempotency lookup: %w", err)
	}
	if done {
		log.Info("duplicate delivery skipped")
		return w.consumer.Commit(ctx, m)
	}

	var (
		result  []byte
		lastErr error
		attempt int
	)
	for attempt = 1; attempt <= w.cfg.MaxAttempts; attempt++ {
		result, lastErr = w.client.Review(ctx, req, key)
		if lastErr == nil {
			break
		}
		if !IsRetryable(lastErr) {
			break
		}
		if attempt < w.cfg.MaxAttempts {
			d := w.backoff(attempt)
			log.Warn("review failed, retrying", "attempt", attempt, "backoff", d, "err", lastErr)
			if err := w.sleep(ctx, d); err != nil {
				return err
			}
		}
	}
	if lastErr != nil {
		if attempt > w.cfg.MaxAttempts {
			attempt = w.cfg.MaxAttempts
		}
		return w.deadLetter(ctx, m, lastErr.Error(), attempt)
	}

	headers := map[string]string{"Idempotency-Key": key, "content-type": "application/json"}
	if err := w.producer.Publish(ctx, w.cfg.ResultsTopic, []byte(req.RequestID), result, headers); err != nil {
		return fmt.Errorf("publish result: %w", err)
	}
	if err := w.seen.MarkDone(ctx, key); err != nil {
		// The result is already published; a redelivery would republish the same
		// (idempotent) result, which consumers tolerate. Log and continue.
		log.Error("mark done failed", "err", err)
	}
	log.Info("review published")
	return w.consumer.Commit(ctx, m)
}

func (w *Worker) deadLetter(ctx context.Context, m Message, reason string, attempts int) error {
	headers := map[string]string{
		"dlq-reason":           reason,
		"dlq-attempts":         fmt.Sprint(attempts),
		"dlq-source-topic":     m.Topic,
		"dlq-source-partition": fmt.Sprint(m.Partition),
		"dlq-source-offset":    fmt.Sprint(m.Offset),
	}
	for k, v := range m.Headers {
		if _, clash := headers[k]; !clash {
			headers[k] = v
		}
	}
	if err := w.producer.Publish(ctx, w.cfg.DLQTopic, m.Key, m.Value, headers); err != nil {
		return fmt.Errorf("publish to DLQ: %w", err)
	}
	w.log.Warn("message dead-lettered", "partition", m.Partition, "offset", m.Offset, "reason", reason, "attempts", attempts)
	return w.consumer.Commit(ctx, m)
}

// backoff is exponential with full jitter, capped at MaxBackoff.
func (w *Worker) backoff(attempt int) time.Duration {
	d := w.cfg.BaseBackoff << (attempt - 1)
	if d <= 0 || d > w.cfg.MaxBackoff {
		d = w.cfg.MaxBackoff
	}
	return time.Duration(rand.Int64N(int64(d)) + 1)
}

func sleepCtx(ctx context.Context, d time.Duration) error {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

// RetryableError marks errors worth retrying (5xx, 429, network).
type RetryableError struct{ Err error }

func (e *RetryableError) Error() string { return e.Err.Error() }
func (e *RetryableError) Unwrap() error { return e.Err }

// IsRetryable reports whether err should be retried.
func IsRetryable(err error) bool {
	var r *RetryableError
	return errors.As(err, &r)
}
