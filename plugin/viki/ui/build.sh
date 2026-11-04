#!/bin/sh
# Install the Desktop half: ~/.hermes/desktop-plugins/viki/plugin.js
set -e; mkdir -p "$HOME/.hermes/desktop-plugins/viki"
cp "$(dirname "$0")/plugin.js" "$HOME/.hermes/desktop-plugins/viki/plugin.js"; echo installed
