package worker

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"
)

// ReviewClient calls the DxReview API. It returns the raw JSON result.
type ReviewClient interface {
	Review(ctx context.Context, req ReviewRequest, idempotencyKey string) ([]byte, error)
}

// HTTPReviewClient calls POST /v1/reviews.
type HTTPReviewClient struct {
	BaseURL string
	APIKey  string
	HTTP    *http.Client
}

// NewHTTPReviewClient returns a client with a sane timeout.
func NewHTTPReviewClient(baseURL, apiKey string) *HTTPReviewClient {
	return &HTTPReviewClient{BaseURL: baseURL, APIKey: apiKey, HTTP: &http.Client{Timeout: 60 * time.Second}}
}

// Review sends the request. 5xx, 429 and transport errors are retryable; other 4xx are not.
func (c *HTTPReviewClient) Review(ctx context.Context, req ReviewRequest, idempotencyKey string) ([]byte, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+"/v1/reviews", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Idempotency-Key", idempotencyKey)
	if c.APIKey != "" {
		httpReq.Header.Set("X-API-Key", c.APIKey)
	}
	resp, err := c.HTTP.Do(httpReq)
	if err != nil {
		return nil, &RetryableError{Err: fmt.Errorf("transport: %w", err)}
	}
	defer resp.Body.Close()
	out, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		return nil, &RetryableError{Err: fmt.Errorf("read body: %w", err)}
	}
	switch {
	case resp.StatusCode == http.StatusOK:
		return out, nil
	case resp.StatusCode == http.StatusTooManyRequests || resp.StatusCode >= 500:
		return nil, &RetryableError{Err: fmt.Errorf("api status %d", resp.StatusCode)}
	default:
		// Never include the body: validation errors can echo the note back.
		return nil, fmt.Errorf("api status %d (not retryable)", resp.StatusCode)
	}
}

// IdempotencyStore records which keys have been fully processed.
// Production uses Postgres (INSERT ... ON CONFLICT DO NOTHING) or Redis SETNX with a TTL.
type IdempotencyStore interface {
	Seen(ctx context.Context, key string) (bool, error)
	MarkDone(ctx context.Context, key string) error
}

// MemoryStore is a bounded in-memory IdempotencyStore (FIFO eviction).
type MemoryStore struct {
	mu    sync.Mutex
	keys  map[string]struct{}
	order []string
	max   int
}

// NewMemoryStore returns a store holding at most max keys.
func NewMemoryStore(max int) *MemoryStore {
	return &MemoryStore{keys: make(map[string]struct{}), max: max}
}

func (s *MemoryStore) Seen(_ context.Context, key string) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	_, ok := s.keys[key]
	return ok, nil
}

func (s *MemoryStore) MarkDone(_ context.Context, key string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.keys[key]; ok {
		return nil
	}
	s.keys[key] = struct{}{}
	s.order = append(s.order, key)
	for len(s.order) > s.max {
		delete(s.keys, s.order[0])
		s.order = s.order[1:]
	}
	return nil
}
