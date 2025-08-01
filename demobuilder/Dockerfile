# Build argument for base image selection
# Default to RHEL UBI9, but allow Fedora for broader accessibility
ARG BASE_IMAGE=registry.access.redhat.com/ubi9/python-311:latest
FROM ${BASE_IMAGE}

# Set working directory
WORKDIR /app

# Install system dependencies as root
USER 0

# Conditional package installation based on base image
RUN if command -v dnf >/dev/null 2>&1; then \
        # RHEL/Fedora uses dnf \
        dnf update -y && dnf clean all; \
    elif command -v microdnf >/dev/null 2>&1; then \
        # Some UBI images use microdnf \
        microdnf update -y && microdnf clean all; \
    elif command -v apt-get >/dev/null 2>&1; then \
        # Debian/Ubuntu fallback \
        apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*; \
    fi

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set appropriate permissions for OpenShift
RUN chgrp -R 0 /app && \
    chmod -R g=u /app

# Switch to non-root user (OpenShift will assign UID)
USER 1001

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run the application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]