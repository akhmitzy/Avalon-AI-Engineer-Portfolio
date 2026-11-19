# Build context: repository root.
FROM golang:1.23 AS build
WORKDIR /src
COPY go/worker/ ./
RUN go mod tidy && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/worker ./cmd/worker

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/worker /worker
USER 10001:10001
ENTRYPOINT ["/worker"]
