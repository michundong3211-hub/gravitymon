# Build tasks. Tools managed by mise; recipes call `mise exec` so no shell activation needed.

set shell := ["bash", "-cu"]

ui_dir := "../gravitymon-ui"

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

# file:// 依赖不会自动同步: 打包前清掉 libdeps 拷贝, 强制使用最新 espframework 源码
[private]
sync-espframework:
    rm -rf .pio/libdeps/*/espframework

# 打包: 不带参数 = 32c3 两个变体(13dBm + 8.5dBm)打进同一时间戳目录; 带环境名 = 只打该环境
# 例: just build / just build gravity-8266
build env="": sync-espframework
    #!/usr/bin/env bash
    set -euo pipefail
    export PKG_STAMP="$(date +%Y.%m.%d.%H%M)"
    if [ -n "{{env}}" ]; then
        mise exec -- pio run -e {{env}}
    else
        mise exec -- pio run -e gravity-32c3_mini -e gravity-32c3_mini_85
    fi

# UI build + firmware build
release: (ui-build) (build)

# Clean all envs and build artifacts
clean:
    mise exec -- pio run -t clean
    rm -rf bin
