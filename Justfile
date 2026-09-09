# Build tasks. Tools managed by mise; recipes call `mise exec` so no shell activation needed.

set shell := ["bash", "-cu"]

ui_dir := "../gravitymon-ui"
default_env := "gravity-32c3_mini"

@default:
    just --list

# Build UI and sync artifacts into html/
ui-build:
    #!/usr/bin/env bash
    set -euo pipefail
    cd {{ui_dir}}
    test -x node_modules/.bin/vite || npm ci --include=dev
    mise exec -- npm run build
    cp dist/assets/style.css.gz ../gravitymon/html/app.css.gz
    cp dist/assets/index.js.gz ../gravitymon/html/app.js.gz
    cp dist/chart.umd.min.js.gz ../gravitymon/html/chart.umd.min.js.gz
    cp gravitymon.html ../gravitymon/html/index.html

# Build firmware: just build [env]
build env=default_env:
    mise exec -- pio run -e {{env}}

# UI build + firmware build
release: (ui-build) (build)

# Clean all envs and build artifacts
clean:
    mise exec -- pio run -t clean
    rm -rf bin
