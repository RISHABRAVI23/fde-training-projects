#!/usr/bin/env bash
# Written with Claude (Claude Code) as a guided example. (since i couldnt understand it well)
set -euo pipefail

# ---------- settings and counters ----------
dry_run=false
target=""
log_file=""
moved=0
skipped=0
failed=0

# ---------- functions ----------
usage() {
    cat <<EOF
Usage: $(basename "$0") [--dry-run] <folder>

Sort the files in <folder> into subfolders by file type:
Images, Documents, Audio, Video, Archives, Code, Other.

Options:
  --dry-run    show what would be moved, without changing anything
  -h, --help   show this help and exit
EOF
}

# log MESSAGE: print a timestamped line; also append it to the log file (not in dry-run).
log() {
    local line
    line="$(date '+%Y-%m-%d %H:%M:%S') $*"
    echo "$line"
    if [[ "$dry_run" == false ]]; then
        echo "$line" >> "$log_file"
    fi
}

# category_for FILENAME: print the category folder name for a file.
category_for() {
    local name="$1"
    local ext

    if [[ "$name" != *.* ]]; then      # no dot at all, e.g. README
        echo "Other"
        return
    fi

    ext="${name##*.}"                  # text after the last dot: "photo.JPG" -> "JPG"
    ext="${ext,,}"                     # lowercase: "JPG" -> "jpg"

    case "$ext" in
        jpg|jpeg|png|gif|svg) echo "Images" ;;
        pdf|txt|docx|xlsx)    echo "Documents" ;;
        mp3|wav)              echo "Audio" ;;
        mp4|mov)              echo "Video" ;;
        zip|gz|tar)           echo "Archives" ;;
        py|sh|js)             echo "Code" ;;
        *)                    echo "Other" ;;
    esac
}

# ---------- parse arguments ----------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "Error: unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
        *)
            if [[ -n "$target" ]]; then
                echo "Error: only one folder can be given" >&2
                usage >&2
                exit 1
            fi
            target="$1"
            shift
            ;;
    esac
done

# ---------- validate ----------
if [[ -z "$target" ]]; then
    echo "Error: no folder given" >&2
    usage >&2
    exit 1
fi

if [[ ! -d "$target" ]]; then
    echo "Error: not a directory: $target" >&2
    exit 1
fi

log_file="$target/sort.log"

# ---------- main loop ----------
for path in "$target"/*; do
    [[ -f "$path" ]] || continue       # skip folders (and the literal "*" if the folder is empty)

    name="$(basename "$path")"
    [[ "$name" == "sort.log" ]] && continue   # never move our own log

    category="$(category_for "$name")"
    dest="$target/$category/$name"

    if [[ -e "$dest" ]]; then
        log "SKIPPED $name (already exists in $category/)"
        skipped=$((skipped + 1))
        continue
    fi

    if [[ "$dry_run" == true ]]; then
        log "WOULD MOVE $name -> $category/"
        moved=$((moved + 1))
        continue
    fi

    if mkdir -p "$target/$category" && mv -- "$path" "$dest"; then
        log "MOVED $name -> $category/"
        moved=$((moved + 1))
    else
        log "FAILED $name -> $category/" >&2
        failed=$((failed + 1))
    fi
done

# ---------- summary ----------
if [[ "$dry_run" == true ]]; then
    log "DRY RUN: would move $moved, would skip $skipped. Nothing was changed."
else
    log "DONE: moved $moved, skipped $skipped, failed $failed"
fi

if [[ "$failed" -gt 0 ]]; then
    exit 1
fi
