#!/bin/bash
#
# Build script for CTP500 macOS CLI
# This script builds the standalone binary and prepares for release
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================"
echo "CTP500 BLE CLI - Build Script"
echo "======================================"
echo ""

#------------------------------------------------------------------------------
# 1. Environment Check
#------------------------------------------------------------------------------

echo "[1/7] Checking environment..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.9 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python version: $PYTHON_VERSION"

# Check if virtual environment exists
if [[ ! -d "venv" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
if [[ ! -f "venv/.deps_installed" ]]; then
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pip install pyinstaller
    touch venv/.deps_installed
fi

echo "✓ Dependencies installed"

#------------------------------------------------------------------------------
# 2. Run Python Tests
#------------------------------------------------------------------------------

echo ""
echo "[2/7] Running Python unit tests..."

if pytest tests/ -v; then
    echo "✓ All Python tests passed"
else
    echo "ERROR: Python tests failed"
    exit 1
fi

#------------------------------------------------------------------------------
# 3. Run Shell Script Tests
#------------------------------------------------------------------------------

echo ""
echo "[3/7] Running shell script tests..."

if command -v shunit2 &> /dev/null; then
    SHUNIT2_BIN="shunit2"
elif [[ -f "/opt/homebrew/bin/shunit2" ]]; then
    SHUNIT2_BIN="/opt/homebrew/bin/shunit2"
else
    echo "WARNING: shunit2 not found. Skipping shell tests."
    echo "Install with: brew install shunit2"
    SHUNIT2_BIN=""
fi

if [[ -n "$SHUNIT2_BIN" ]]; then
    for test_file in tests/backend/test_*.sh; do
        echo "Running: $(basename "$test_file")"
        if ! "$SHUNIT2_BIN" "$test_file"; then
            echo "ERROR: Shell test failed: $test_file"
            exit 1
        fi
    done
    echo "✓ All shell tests passed"
fi

#------------------------------------------------------------------------------
# 4. Build Binary with PyInstaller
#------------------------------------------------------------------------------

echo ""
echo "[4/7] Building standalone binary..."

# Clean previous builds
rm -rf build dist

# Build with PyInstaller
if pyinstaller ctp500_ble_cli.spec; then
    echo "✓ Binary built successfully: dist/ctp500_ble_cli"
else
    echo "ERROR: PyInstaller build failed"
    exit 1
fi

# Test the binary
echo "Testing binary..."
if ./dist/ctp500_ble_cli --help > /dev/null 2>&1; then
    echo "✓ Binary is executable"
else
    echo "ERROR: Binary test failed"
    exit 1
fi

#------------------------------------------------------------------------------
# 5. Verify All Required Files
#------------------------------------------------------------------------------

echo ""
echo "[5/7] Verifying release files..."

REQUIRED_FILES=(
    "dist/ctp500_ble_cli"
    "files/ctp500"
    "files/backend_functions.sh"
    "files/CTP500.ppd"
    "files/ctp500.conf"
    "Formula/ctp500-printer.rb"
    "README.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "✓ $file"
    else
        echo "ERROR: Missing required file: $file"
        exit 1
    fi
done

#------------------------------------------------------------------------------
# 6. Create Distribution Archive
#------------------------------------------------------------------------------

echo ""
echo "[6/7] Creating distribution archive..."

VERSION="${1:-1.0.0}"
DIST_NAME="ctp500-macos-cli-${VERSION}"
DIST_DIR="dist/${DIST_NAME}"

# Create distribution directory structure
mkdir -p "${DIST_DIR}"/{bin,files,Formula,docs,tests/backend/fixtures}

# Copy files
cp dist/ctp500_ble_cli "${DIST_DIR}/bin/"
cp files/ctp500 "${DIST_DIR}/files/"
cp files/backend_functions.sh "${DIST_DIR}/files/"
cp files/CTP500.ppd "${DIST_DIR}/files/"
cp files/ctp500.conf "${DIST_DIR}/files/"
cp Formula/ctp500-printer.rb "${DIST_DIR}/Formula/"
cp README.md "${DIST_DIR}/"
cp docs/*.md "${DIST_DIR}/docs/" 2>/dev/null || true
cp tests/backend/*.sh "${DIST_DIR}/tests/backend/"
cp tests/backend/fixtures/* "${DIST_DIR}/tests/backend/fixtures/"

# Create tarball
cd dist
tar -czf "${DIST_NAME}.tar.gz" "${DIST_NAME}"
cd ..

echo "✓ Distribution created: dist/${DIST_NAME}.tar.gz"

# Calculate SHA256
SHA256=$(shasum -a 256 "dist/${DIST_NAME}.tar.gz" | cut -d' ' -f1)
echo "✓ SHA256: $SHA256"

#------------------------------------------------------------------------------
# 7. Build Complete
#------------------------------------------------------------------------------

echo ""
echo "======================================"
echo "Build Complete!"
echo "======================================"
echo ""
echo "Next Steps:"
echo "----------"
echo ""
echo "1. Test the binary locally:"
echo "   ./dist/ctp500_ble_cli scan"
echo ""
echo "2. Create a GitHub release:"
echo "   git tag v${VERSION}"
echo "   git push origin v${VERSION}"
echo ""
echo "3. Upload the tarball to GitHub releases:"
echo "   dist/${DIST_NAME}.tar.gz"
echo ""
echo "4. Update Formula/ctp500-printer.rb:"
echo "   - Update the version to: ${VERSION}"
echo "   - Update the URL to point to the GitHub release"
echo "   - Update sha256 to: ${SHA256}"
echo ""
echo "5. Create Homebrew tap repository:"
echo "   - Create repo: unxmaal/homebrew-ctp500"
echo "   - Copy Formula/ctp500-printer.rb to it"
echo ""
echo "6. Users can then install with:"
echo "   brew tap unxmaal/ctp500"
echo "   brew install ctp500-printer"
echo ""
echo "Distribution: dist/${DIST_NAME}.tar.gz"
echo "SHA256: ${SHA256}"
echo ""
