# Docker Hub is the default. Set PYTHON_BASE_IMAGE to the MCR fallback when a
# restricted network cannot reach Docker Hub.
ARG PYTHON_BASE_IMAGE=python:3.13-slim
ARG PIP_RETRIES=5
ARG PIP_TIMEOUT=120
ARG PIP_INDEX_URL=https://pypi.org/simple
FROM ${PYTHON_BASE_IMAGE}
ARG PIP_RETRIES
ARG PIP_TIMEOUT
ARG PIP_INDEX_URL
WORKDIR /app

RUN if ! command -v groupadd >/dev/null 2>&1; then tdnf install -y shadow-utils && tdnf clean all; fi \
    && groupadd --system zhilin \
    && useradd --system --gid zhilin --home-dir /app --shell "$(command -v nologin || echo /bin/false)" zhilin

# Keep third-party packages in their own layer: code-only changes reuse it and
# --prefer-binary avoids unexpectedly compiling packages inside the slim image.
COPY requirements/docker-runtime.txt /tmp/docker-runtime.txt
RUN python3 -m pip install --prefer-binary --retries ${PIP_RETRIES} --timeout ${PIP_TIMEOUT} --index-url ${PIP_INDEX_URL} -r /tmp/docker-runtime.txt

# Refresh security-fixable base packages after dependency installation. The
# conditional keeps the primary Debian and Azure Linux fallback builds aligned.
RUN if command -v tdnf >/dev/null 2>&1; then \
        tdnf upgrade -y libarchive && tdnf clean all; \
    elif command -v apt-get >/dev/null 2>&1; then \
        apt-get update; \
        for package in libarchive13t64 libarchive13; do \
            if dpkg-query -W "$package" >/dev/null 2>&1; then apt-get install -y --only-upgrade --no-install-recommends "$package"; fi; \
        done; \
        rm -rf /var/lib/apt/lists/*; \
    fi

COPY --chown=zhilin:zhilin . .
RUN python3 -m pip install --no-deps --no-build-isolation .
RUN mkdir -p /app/data && chown -R zhilin:zhilin /app/data
USER zhilin
CMD ["uvicorn","api.main:app","--host","0.0.0.0","--port","8000"]
