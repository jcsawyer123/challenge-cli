FROM node:18-slim

# Install GNU time for memory measurement
RUN apt-get update && apt-get install -y --no-install-recommends time \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create a non-root user for safety
RUN useradd -m runner
USER runner

WORKDIR /workspace