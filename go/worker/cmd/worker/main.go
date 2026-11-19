// Command worker runs the DxReview Kafka worker.
//
// Environment:
//
//	KAFKA_BROKERS        comma-separated, e.g. b-1.msk:9098,b-2.msk:9098
//	KAFKA_GROUP_ID       default dxreview-worker
//	KAFKA_REQUEST_TOPIC  default reviews.requests
//	KAFKA_RESULT_TOPIC   default reviews.results
//	KAFKA_DLQ_TOPIC      default reviews.dlq
//	DXREVIEW_API_URL     e.g. http://dxreview-api.internal:8080
//	DXREVIEW_API_KEY     optional
//	MAX_ATTEMPTS         default 5
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"

	"github.com/segmentio/kafka-go"

	"github.com/dxreview/worker/internal/worker"
)

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

// kafkaConsumer adapts kafka.Reader. CommitInterval 0 means synchronous, explicit commits.
type kafkaConsumer struct{ r *kafka.Reader }

func (c *kafkaConsumer) Fetch(ctx context.Context) (worker.Message, error) {
	m, err := c.r.FetchMessage(ctx)
	if err != nil {
		return worker.Message{}, err
	}
	h := make(map[string]string, len(m.Headers))
	for _, x := range m.Headers {
		h[x.Key] = string(x.Value)
	}
	return worker.Message{Topic: m.Topic, Partition: m.Partition, Offset: m.Offset, Key: m.Key, Value: m.Value, Headers: h}, nil
}

func (c *kafkaConsumer) Commit(ctx context.Context, m worker.Message) error {
	return c.r.CommitMessages(ctx, kafka.Message{Topic: m.Topic, Partition: m.Partition, Offset: m.Offset})
}

// kafkaProducer adapts kafka.Writer. RequireAll acks so a published result survives a broker loss.
type kafkaProducer struct{ w *kafka.Writer }

func (p *kafkaProducer) Publish(ctx context.Context, topic string, key, value []byte, headers map[string]string) error {
	hs := make([]kafka.Header, 0, len(headers))
	for k, v := range headers {
		hs = append(hs, kafka.Header{Key: k, Value: []byte(v)})
	}
	return p.w.WriteMessages(ctx, kafka.Message{Topic: topic, Key: key, Value: value, Headers: hs})
}

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	brokers := strings.Split(env("KAFKA_BROKERS", "localhost:9092"), ",")
	attempts, _ := strconv.Atoi(env("MAX_ATTEMPTS", "5"))

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:        brokers,
		GroupID:        env("KAFKA_GROUP_ID", "dxreview-worker"),
		Topic:          env("KAFKA_REQUEST_TOPIC", "reviews.requests"),
		MinBytes:       1,
		MaxBytes:       10 << 20,
		CommitInterval: 0,
	})
	defer reader.Close()
	writer := &kafka.Writer{
		Addr:         kafka.TCP(brokers...),
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
	}
	defer writer.Close()

	w := worker.New(worker.Config{
		ResultsTopic: env("KAFKA_RESULT_TOPIC", "reviews.results"),
		DLQTopic:     env("KAFKA_DLQ_TOPIC", "reviews.dlq"),
		MaxAttempts:  attempts,
	}, &kafkaConsumer{reader}, &kafkaProducer{writer},
		worker.NewHTTPReviewClient(env("DXREVIEW_API_URL", "http://localhost:8080"), os.Getenv("DXREVIEW_API_KEY")),
		worker.NewMemoryStore(100_000), log)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	log.Info("worker started", "brokers", brokers)
	if err := w.Run(ctx); err != nil {
		log.Error("worker stopped", "err", err)
		os.Exit(1)
	}
	log.Info("worker stopped cleanly")
}
