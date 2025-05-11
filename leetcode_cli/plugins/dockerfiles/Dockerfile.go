FROM golang:1.22-alpine

# Install GNU time for memory measurement
RUN apk add --no-cache bash coreutils

# Create a non-root user for safety (optional)
RUN adduser -D runner
USER runner

WORKDIR /workspace
