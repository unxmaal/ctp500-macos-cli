#!/bin/bash
# Test file format detection for CUPS backend
# Following TDD: RED phase - will fail initially

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../files/backend_functions.sh" 2>/dev/null || true

FIXTURES="${SCRIPT_DIR}/fixtures"

test_detect_postscript() {
  local result
  result=$(detect_format "${FIXTURES}/sample.ps")
  assertEquals "postscript" "$result"
}

test_detect_text() {
  local result
  result=$(detect_format "${FIXTURES}/sample.txt")
  assertEquals "text" "$result"
}

test_detect_png_image() {
  local result
  result=$(detect_format "${FIXTURES}/sample.png")
  assertEquals "image" "$result"
}

test_detect_nonexistent_file() {
  local result
  result=$(detect_format "${FIXTURES}/nonexistent.file")
  assertEquals "unknown" "$result"
}

test_detect_empty_filename() {
  local result
  result=$(detect_format "")
  assertEquals "unknown" "$result"
}

# Load shunit2
. /opt/homebrew/bin/shunit2
