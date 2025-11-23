#!/bin/bash
# CUPS Backend Helper Functions for CTP500 Printer
# These functions are unit tested in tests/backend/

#------------------------------------------------------------------------------
# URI Parsing Functions
#------------------------------------------------------------------------------

extract_ble_address() {
  local uri="$1"

  # Return error if empty
  if [[ -z "$uri" ]]; then
    return 1
  fi

  # Strip ctp500:// prefix and remove query parameters
  echo "$uri" | sed 's|^ctp500://||' | cut -d'?' -f1
}

validate_uri() {
  local uri="$1"

  # Check if empty
  if [[ -z "$uri" ]]; then
    return 1
  fi

  # Check if starts with ctp500://
  if [[ ! "$uri" =~ ^ctp500:// ]]; then
    return 1
  fi

  return 0
}

validate_ble_address() {
  local addr="$1"

  # Check if empty
  if [[ -z "$addr" ]]; then
    return 1
  fi

  # Valid MAC address format: AA:BB:CC:DD:EE:FF
  if [[ "$addr" =~ ^[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}$ ]]; then
    return 0
  fi

  # Valid UUID format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
  if [[ "$addr" =~ ^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$ ]]; then
    return 0
  fi

  return 1
}

#------------------------------------------------------------------------------
# Config File Parsing Functions
#------------------------------------------------------------------------------

# Default values
DEFAULT_WRITE_UUID="49535343-8841-43f4-a8d4-ecbe34729bb3"
DEFAULT_CHUNK_SIZE="180"

read_config_value() {
  local config="$1"
  local key="$2"

  # Return empty if config doesn't exist
  if [[ ! -f "$config" ]]; then
    return 0
  fi

  # Extract value, strip quotes
  grep "^${key}=" "$config" 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'"
}

get_write_uuid() {
  local config="$1"
  local value

  value=$(read_config_value "$config" "WRITE_UUID")

  if [[ -z "$value" ]]; then
    echo "$DEFAULT_WRITE_UUID"
  else
    echo "$value"
  fi
}

get_chunk_size() {
  local config="$1"
  local value

  value=$(read_config_value "$config" "CHUNK_SIZE")

  if [[ -z "$value" ]]; then
    echo "$DEFAULT_CHUNK_SIZE"
  else
    echo "$value"
  fi
}

#------------------------------------------------------------------------------
# File Format Detection
#------------------------------------------------------------------------------

detect_format() {
  local file="$1"

  # Handle empty or nonexistent files
  if [[ -z "$file" ]] || [[ ! -f "$file" ]]; then
    echo "unknown"
    return 0
  fi

  # Use file command to detect MIME type
  local mime
  mime=$(file -b --mime-type "$file" 2>/dev/null)

  case "$mime" in
    application/postscript)
      echo "postscript"
      ;;
    application/pdf)
      echo "pdf"
      ;;
    image/*)
      echo "image"
      ;;
    text/plain)
      echo "text"
      ;;
    *)
      echo "unknown"
      ;;
  esac
}
