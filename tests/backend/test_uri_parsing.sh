#!/bin/bash
# Test URI parsing functions for CUPS backend
# Following TDD: These tests will FAIL until we implement the functions

# Source the functions we'll be testing
# (They don't exist yet - this is RED phase!)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../files/backend_functions.sh" 2>/dev/null || true

test_extract_ble_address_simple() {
  local uri="ctp500://AA:BB:CC:DD:EE:FF"
  local result
  result=$(extract_ble_address "$uri")
  assertEquals "AA:BB:CC:DD:EE:FF" "$result"
}

test_extract_ble_address_with_query_params() {
  local uri="ctp500://D210000E-A47D-2971-6819-A5F4389E7B86?chunk_size=30"
  local result
  result=$(extract_ble_address "$uri")
  assertEquals "D210000E-A47D-2971-6819-A5F4389E7B86" "$result"
}

test_extract_ble_address_with_multiple_params() {
  local uri="ctp500://AA:BB:CC:DD:EE:FF?chunk_size=20&timeout=5"
  local result
  result=$(extract_ble_address "$uri")
  assertEquals "AA:BB:CC:DD:EE:FF" "$result"
}

test_extract_ble_address_empty_returns_error() {
  local uri=""
  extract_ble_address "$uri" >/dev/null 2>&1
  assertNotEquals "Should return non-zero for empty URI" 0 $?
}

test_validate_uri_correct_scheme() {
  local uri="ctp500://AA:BB:CC:DD:EE:FF"
  validate_uri "$uri"
  assertEquals "Valid URI should return 0" 0 $?
}

test_validate_uri_wrong_scheme() {
  local uri="http://example.com"
  validate_uri "$uri" >/dev/null 2>&1
  assertNotEquals "Invalid scheme should return non-zero" 0 $?
}

test_validate_uri_empty() {
  local uri=""
  validate_uri "$uri" >/dev/null 2>&1
  assertNotEquals "Empty URI should return non-zero" 0 $?
}

test_validate_ble_address_format() {
  local addr="AA:BB:CC:DD:EE:FF"
  validate_ble_address "$addr"
  assertEquals "Valid MAC format should return 0" 0 $?
}

test_validate_ble_address_uuid_format() {
  local addr="D210000E-A47D-2971-6819-A5F4389E7B86"
  validate_ble_address "$addr"
  assertEquals "Valid UUID format should return 0" 0 $?
}

test_validate_ble_address_invalid() {
  local addr="invalid-address"
  validate_ble_address "$addr" >/dev/null 2>&1
  assertNotEquals "Invalid address should return non-zero" 0 $?
}

test_validate_ble_address_empty() {
  local addr=""
  validate_ble_address "$addr" >/dev/null 2>&1
  assertNotEquals "Empty address should return non-zero" 0 $?
}

# Load shunit2
. /opt/homebrew/bin/shunit2
