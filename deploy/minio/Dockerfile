# MinIO object storage built from source (AGPL-3.0, design doc G.9). MinIO no longer publishes
# community images on Docker Hub, so docker compose builds this one. Bump MINIO_RELEASE to update.
ARG MINIO_RELEASE=RELEASE.2025-10-15T17-29-55Z

FROM golang:1.24-alpine AS build
ARG MINIO_RELEASE
RUN apk add --no-cache git
RUN git clone --depth 1 --branch "${MINIO_RELEASE}" https://github.com/minio/minio.git /src
WORKDIR /src
# Same flags as MinIO's own `make build`; gen-ldflags stamps the release version into the binary.
RUN CGO_ENABLED=0 go build -tags kqueue -trimpath \
      -ldflags "$(go run buildscripts/gen-ldflags.go)" -o /out/minio

FROM alpine:3.22
RUN apk add --no-cache ca-certificates \
    && adduser -D -u 1000 minio \
    && mkdir /data && chown minio /data
COPY --from=build /out/minio /usr/bin/minio
USER minio
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
