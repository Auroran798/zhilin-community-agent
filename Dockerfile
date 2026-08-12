# Azure Linux currently provides the patched minimal runtime used by CI. The
# build argument still permits a registry-specific override when required.
ARG PYTHON_BASE_IMAGE=mcr.microsoft.com/azurelinux/base/python:3.12
ARG PIP_RETRIES=5
ARG PIP_TIMEOUT=120
ARG PIP_INDEX_URL=https://pypi.org/simple
FROM ${PYTHON_BASE_IMAGE} AS builder
ARG PIP_RETRIES
ARG PIP_TIMEOUT
ARG PIP_INDEX_URL
WORKDIR /build

# Keep third-party packages in their own layer: code-only changes reuse it.
# chroma-hnswlib needs a C++ toolchain on platforms without a matching wheel.
# Build into a virtual environment in this disposable stage so compilers never
# enter the runtime image.
COPY requirements/docker-runtime.txt /tmp/docker-runtime.txt
RUN set -eux; \
    if command -v apt-get >/dev/null 2>&1; then \
        apt-get update; \
        apt-get install -y --no-install-recommends build-essential; \
    elif command -v tdnf >/dev/null 2>&1; then \
        tdnf install -y gcc-c++ make; \
    fi; \
    python3 -m venv /opt/venv; \
    /opt/venv/bin/python -m pip install --prefer-binary --retries ${PIP_RETRIES} --timeout ${PIP_TIMEOUT} --index-url ${PIP_INDEX_URL} -r /tmp/docker-runtime.txt

COPY . .
RUN /opt/venv/bin/python -m pip install --no-deps --no-build-isolation .

FROM ${PYTHON_BASE_IMAGE} AS runtime
WORKDIR /app

RUN if ! command -v groupadd >/dev/null 2>&1; then tdnf install -y shadow-utils && tdnf clean all; fi \
    && groupadd --system zhilin \
    && useradd --system --gid zhilin --home-dir /app --shell "$(command -v nologin || echo /bin/false)" zhilin

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
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN mkdir -p /app/data /app/runtime && chown -R zhilin:zhilin /app/data /app/runtime
USER zhilin
CMD ["uvicorn","api.main:app","--host","0.0.0.0","--port","8000"]
