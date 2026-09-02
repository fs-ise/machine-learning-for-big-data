FROM ghcr.io/quarto-dev/quarto:1.6.43

ARG DECKTAPE_VERSION=3.14.0

ENV DEBIAN_FRONTEND=noninteractive

# Installing the pinned Decktape package runs its Puppeteer installer, which
# downloads the matching Chrome for Testing release into root's Puppeteer
# cache. The libraries below support that browser; Python serves the rendered
# slides, and Ghostscript compresses the resulting PDF.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        fonts-liberation \
        ghostscript \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        python3 \
        xdg-utils \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install --global "decktape@${DECKTAPE_VERSION}" \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.npm

WORKDIR /work
