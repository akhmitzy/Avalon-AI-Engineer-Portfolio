package worker

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"
)

type published struct {
	topic   string
	key     string
	value   string
	headers map[string]string
}

type fakeBus struct {
	mu        sync.Mutex
	msgs      []Message
	committed []int64
	out       []published
	failTopic string
	cancel    context.CancelFunc
}

// run drives the worker until the fake bus is drained.
func run(w *Worker, bus *fakeBus) error {
	ctx, cancel := context.WithCancel(context.Background())
	bus.cancel = cancel
	return w.Run(ctx)
}

func (b *fakeBus) Fetch(ctx context.Context) (Message, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if len(b.msgs) == 0 {
		b.cancel()
		return Message{}, ctx.Err()
	}
	m := b.msgs[0]
	b.msgs = b.msgs[1:]
	return m, nil
}

func (b *fakeBus) Commit(_ context.Context, m Message) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.committed = append(b.committed, m.Offset)
	return nil
}

func (b *fakeBus) Publish(_ context.Context, topic string, key, value []byte, h map[string]string) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if topic == b.failTopic {
		return errors.New("broker unavailable")
	}
	b.out = append(b.out, published{topic, string(key), string(value), h})
	return nil
}

type scriptedClient struct {
	errs  []error
	calls int
	keys  []string
}

func (c *scriptedClient) Review(_ context.Context, req ReviewRequest, key string) ([]byte, error) {
	c.calls++
	c.keys = append(c.keys, key)
	if c.calls <= len(c.errs) && c.errs[c.calls-1] != nil {
		return nil, c.errs[c.calls-1]
	}
	return json.Marshal(map[string]string{"request_id": req.RequestID, "decision": "APPROVE"})
}

func msg(offset int64, body string) Message {
	return Message{Topic: "reviews.requests", Offset: offset, Key: []byte("k"), Value: []byte(body), Headers: map[string]string{}}
}

const good = `{"request_id":"r-1","cpt_code":"81225","note":"Plan clopidogrel after PCI."}`

func newWorker(bus *fakeBus, c ReviewClient) *Worker {
	w := New(Config{ResultsTopic: "reviews.results", DLQTopic: "reviews.dlq", MaxAttempts: 3},
		bus, bus, c, NewMemoryStore(100), slog.New(slog.NewTextHandler(io.Discard, nil)))
	w.sleep = func(context.Context, time.Duration) error { return nil }
	return w
}

func TestSuccessPublishesThenCommits(t *testing.T) {
	bus := &fakeBus{msgs: []Message{msg(7, good)}}
	c := &scriptedClient{}
	if err := run(newWorker(bus, c), bus); err != nil {
		t.Fatal(err)
	}
	if len(bus.out) != 1 || bus.out[0].topic != "reviews.results" || bus.out[0].key != "r-1" {
		t.Fatalf("unexpected publish: %+v", bus.out)
	}
	if len(bus.committed) != 1 || bus.committed[0] != 7 {
		t.Fatalf("expected commit of offset 7, got %v", bus.committed)
	}
	if c.keys[0] != "r-1" {
		t.Fatalf("request_id should be the default idempotency key, got %q", c.keys[0])
	}
}

func TestDuplicateDeliveryIsSkipped(t *testing.T) {
	m := msg(1, good)
	m.Headers["Idempotency-Key"] = "idem-9"
	dup := m
	dup.Offset = 2
	bus := &fakeBus{msgs: []Message{m, dup}}
	c := &scriptedClient{}
	if err := run(newWorker(bus, c), bus); err != nil {
		t.Fatal(err)
	}
	if c.calls != 1 || len(bus.out) != 1 || len(bus.committed) != 2 {
		t.Fatalf("calls=%d out=%d committed=%v", c.calls, len(bus.out), bus.committed)
	}
}

func TestRetryableErrorThenSuccess(t *testing.T) {
	bus := &fakeBus{msgs: []Message{msg(1, good)}}
	c := &scriptedClient{errs: []error{&RetryableError{Err: errors.New("api status 503")}, nil}}
	if err := run(newWorker(bus, c), bus); err != nil {
		t.Fatal(err)
	}
	if c.calls != 2 || bus.out[0].topic != "reviews.results" {
		t.Fatalf("calls=%d out=%+v", c.calls, bus.out)
	}
}

func TestPermanentErrorAndExhaustedRetriesGoToDLQ(t *testing.T) {
	retry := &RetryableError{Err: errors.New("api status 502")}
	cases := []struct {
		name      string
		errs      []error
		wantCalls int
		attempts  string
	}{
		{"permanent", []error{errors.New("api status 422 (not retryable)")}, 1, "1"},
		{"exhausted", []error{retry, retry, retry}, 3, "3"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			bus := &fakeBus{msgs: []Message{msg(4, good)}}
			c := &scriptedClient{errs: tc.errs}
			if err := run(newWorker(bus, c), bus); err != nil {
				t.Fatal(err)
			}
			if c.calls != tc.wantCalls || len(bus.out) != 1 || bus.out[0].topic != "reviews.dlq" {
				t.Fatalf("calls=%d out=%+v", c.calls, bus.out)
			}
			if bus.out[0].headers["dlq-attempts"] != tc.attempts || bus.out[0].headers["dlq-source-offset"] != "4" {
				t.Fatalf("headers=%v", bus.out[0].headers)
			}
			if len(bus.committed) != 1 {
				t.Fatal("DLQ'd message must be committed so the partition moves on")
			}
		})
	}
}

func TestMalformedMessageGoesToDLQWithoutCallingAPI(t *testing.T) {
	bus := &fakeBus{msgs: []Message{msg(1, `{not json`), msg(2, `{"request_id":"r"}`)}}
	c := &scriptedClient{}
	if err := run(newWorker(bus, c), bus); err != nil {
		t.Fatal(err)
	}
	if c.calls != 0 || len(bus.out) != 2 || bus.out[0].topic != "reviews.dlq" || bus.out[1].topic != "reviews.dlq" {
		t.Fatalf("calls=%d out=%+v", c.calls, bus.out)
	}
}

func TestPublishFailureDoesNotCommit(t *testing.T) {
	for _, topic := range []string{"reviews.results", "reviews.dlq"} {
		bus := &fakeBus{msgs: []Message{msg(1, good)}, failTopic: topic}
		c := &scriptedClient{}
		if topic == "reviews.dlq" {
			c.errs = []error{errors.New("api status 400 (not retryable)")}
		}
		if err := run(newWorker(bus, c), bus); err == nil {
			t.Fatalf("%s: expected error", topic)
		}
		if len(bus.committed) != 0 {
			t.Fatalf("%s: offset committed before effects were durable", topic)
		}
	}
}

func TestHTTPClientClassifiesStatus(t *testing.T) {
	status := http.StatusOK
	var gotKey, gotAPIKey string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotKey, gotAPIKey = r.Header.Get("Idempotency-Key"), r.Header.Get("X-API-Key")
		w.WriteHeader(status)
		_, _ = w.Write([]byte(`{"decision":"APPROVE","note_echo":"PHI"}`))
	}))
	defer srv.Close()
	c := NewHTTPReviewClient(srv.URL, "secret")
	req := ReviewRequest{RequestID: "r", CPTCode: "82306", Note: "x"}

	if _, err := c.Review(context.Background(), req, "k1"); err != nil || gotKey != "k1" || gotAPIKey != "secret" {
		t.Fatalf("ok case: err=%v key=%q apikey=%q", err, gotKey, gotAPIKey)
	}
	for _, s := range []int{500, 503, 429} {
		status = s
		if _, err := c.Review(context.Background(), req, "k"); !IsRetryable(err) {
			t.Fatalf("%d should be retryable: %v", s, err)
		}
	}
	status = 422
	_, err := c.Review(context.Background(), req, "k")
	if err == nil || IsRetryable(err) {
		t.Fatalf("422 should be permanent: %v", err)
	}
	if contains(err.Error(), "PHI") {
		t.Fatal("error message must not echo the response body")
	}
}

func TestMemoryStoreEvicts(t *testing.T) {
	s := NewMemoryStore(2)
	ctx := context.Background()
	for _, k := range []string{"a", "b", "c"} {
		_ = s.MarkDone(ctx, k)
	}
	if ok, _ := s.Seen(ctx, "a"); ok {
		t.Fatal("oldest key should be evicted")
	}
	if ok, _ := s.Seen(ctx, "c"); !ok {
		t.Fatal("newest key should be present")
	}
}

func TestBackoffIsCapped(t *testing.T) {
	w := New(Config{BaseBackoff: time.Second, MaxBackoff: 3 * time.Second}, nil, nil, nil, nil, nil)
	for i := 1; i < 70; i++ {
		if d := w.backoff(i); d <= 0 || d > 3*time.Second {
			t.Fatalf("attempt %d: backoff %v out of range", i, d)
		}
	}
}

func contains(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
