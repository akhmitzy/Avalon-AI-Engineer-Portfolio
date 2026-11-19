# Build context: repository root. Produces a tiny image with the phi-scrub CLI.
FROM rust:1.83 AS build
WORKDIR /src
COPY shared/ ./shared/
COPY rust/ ./rust/
RUN cargo build --release --manifest-path rust/phi-scrubber/Cargo.toml

FROM gcr.io/distroless/cc-debian12:nonroot
COPY --from=build /src/rust/phi-scrubber/target/release/phi-scrub /phi-scrub
ENTRYPOINT ["/phi-scrub"]
