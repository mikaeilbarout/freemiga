"""
Build-step-free CSS/JS minification: rewrites the source files into .min.*
siblings, served instead of the originals. There's no separate build
pipeline (webpack/vite) for this project, so this runs once at process
start rather than as a Docker build stage — cheap (a few KB of text) and
keeps the minified files in sync with source in every environment (local,
Docker, CI) without an extra stage to maintain.
"""
import logging
import os

import rcssmin
import rjsmin

logger = logging.getLogger("minify")

CSS_FILES = ["app/static/css/style.css"]
JS_FILES = ["app/static/js/nav.js", "app/static/js/toast.js"]


def _minify_one(src_path: str, minify_fn) -> None:
    root, ext = os.path.splitext(src_path)
    min_path = f"{root}.min{ext}"
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            source = f.read()
        minified = minify_fn(source)
        with open(min_path, "w", encoding="utf-8") as f:
            f.write(minified)
    except OSError:
        logger.exception("Failed to minify %s", src_path)


def build_minified_assets() -> None:
    for path in CSS_FILES:
        _minify_one(path, rcssmin.cssmin)
    for path in JS_FILES:
        _minify_one(path, rjsmin.jsmin)
