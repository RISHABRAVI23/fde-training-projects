#!/usr/bin/env bash
# test-sort.sh - automated checks for sort-downloads.sh.
# Usage: bash test-sort.sh   (run from this folder)
set -uo pipefail     # no -e: we want to keep going and report every failing check

here="$(cd "$(dirname "$0")" && pwd)"
script="$here/sort-downloads.sh"
tmp="$here/tmp-test-run"
pass=0
fail=0

check() {   # check DESCRIPTION CONDITION...
    local desc="$1"; shift
    if "$@"; then
        echo "PASS  $desc"; pass=$((pass + 1))
    else
        echo "FAIL  $desc"; fail=$((fail + 1))
    fi
}

fresh() { bash "$here/make-test-folder.sh" "$tmp" > /dev/null; }

# --- error cases: must exit non-zero ---
bash "$script" > /dev/null 2>&1;                  check "no folder -> exit 1"        test $? -eq 1
bash "$script" /does/not/exist > /dev/null 2>&1;  check "missing folder -> exit 1"   test $? -eq 1
bash "$script" --bogus "$here" > /dev/null 2>&1;  check "unknown option -> exit 1"   test $? -eq 1
bash "$script" a b > /dev/null 2>&1;              check "two folders -> exit 1"      test $? -eq 1
bash "$script" --help > /dev/null 2>&1;           check "--help -> exit 0"           test $? -eq 0

# --- dry run: must change nothing ---
fresh
before="$(find "$tmp" | sort)"
bash "$script" --dry-run "$tmp" > /dev/null
after="$(find "$tmp" | sort)"
check "dry run changes nothing"         test "$before" == "$after"
check "dry run writes no log file"      test ! -e "$tmp/sort.log"

# --- real run ---
fresh
bash "$script" "$tmp" > /dev/null
check "real run exits 0"                          test $? -eq 0
check "svg -> Images"                             test -f "$tmp/Images/diagram.svg"
check "uppercase .PNG -> Images"                  test -f "$tmp/Images/SCREENSHOT.PNG"
check "uppercase .MP4 -> Video"                   test -f "$tmp/Video/clip.MP4"
check "pdf with space -> Documents"               test -f "$tmp/Documents/report final.pdf"
check ".tar.gz -> Archives"                       test -f "$tmp/Archives/archive.tar.gz"
check "no extension -> Other"                     test -f "$tmp/Other/README"
check "unknown extension -> Other"                test -f "$tmp/Other/weird.unknownext"
check "hidden file left alone"                    test -f "$tmp/.hidden-config"
check "subfolder left alone"                      test -f "$tmp/already-a-folder/inside.txt"
check "name clash: original kept in place"        test -f "$tmp/holiday photo.jpg"
check "log file written"                          test -f "$tmp/sort.log"
check "log records the clash"                     grep -q "SKIPPED holiday photo.jpg" "$tmp/sort.log"

# --- second run on an already-sorted folder: nothing left to do ---
output="$(bash "$script" "$tmp")"
check "second run moves nothing"                  grep -q "moved 0" <<< "$output"

rm -rf "$tmp"
echo
echo "$pass passed, $fail failed"
[[ "$fail" -eq 0 ]]
