#!/bin/bash
# Test config parsing functions for CUPS backend
# Following TDD: RED phase - these will fail initially

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../files/backend_functions.sh" 2>/dev/null || true

TEST_CONFIG="${SCRIPT_DIR}/fixtures/test.conf"

test_read_config_value_write_uuid() {
  local result
  result=$(read_config_value "$TEST_CONFIG" "WRITE_UUID")
  assertEquals "49535343-8841-43f4-a8d4-ecbe34729bb3" "$result"
}

test_read_config_value_chunk_size() {
  local result
  result=$(read_config_value "$TEST_CONFIG" "CHUNK_SIZE")
  assertEquals "20" "$result"
}

test_read_config_value_font_path() {
  local result
  result=$(read_config_value "$TEST_CONFIG" "FONT_PATH")
  assertEquals "/System/Library/Fonts/Menlo.ttc" "$result"
}

test_read_config_value_nonexistent_key() {
  local result
  result=$(read_config_value "$TEST_CONFIG" "NONEXISTENT_KEY")
  assertEquals "" "$result"
}

test_read_config_value_missing_file() {
  local result
  result=$(read_config_value "/nonexistent.conf" "WRITE_UUID")
  assertEquals "" "$result"
}

test_get_write_uuid_from_config() {
  local result
  result=$(get_write_uuid "$TEST_CONFIG")
  assertEquals "49535343-8841-43f4-a8d4-ecbe34729bb3" "$result"
}

test_get_write_uuid_uses_default() {
  local result
  result=$(get_write_uuid "/nonexistent.conf")
  # Should return default UUID
  assertEquals "49535343-8841-43f4-a8d4-ecbe34729bb3" "$result"
}

test_get_chunk_size_from_config() {
  local result
  result=$(get_chunk_size "$TEST_CONFIG")
  assertEquals "20" "$result"
}

test_get_chunk_size_uses_default() {
  local result
  result=$(get_chunk_size "/nonexistent.conf")
  # Should return default chunk size
  assertEquals "180" "$result"
}

# Load shunit2
. /opt/homebrew/bin/shunit2
