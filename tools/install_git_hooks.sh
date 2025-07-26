#!/bin/bash

# YamlForge Git Hooks Installation Script
# Installs pre-commit and post-commit hooks for Vulture integration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Installing YamlForge Git Hooks${NC}"
echo "=================================="

# Check if we're in a Git repository
if [ ! -d ".git" ]; then
    echo -e "${RED}Error: Not in a Git repository${NC}"
    echo "   Please run this script from the root of the YamlForge repository"
    exit 1
fi

# Create hooks directory if it doesn't exist
mkdir -p .git/hooks

# Copy pre-commit hook
if [ -f ".git/hooks/pre-commit" ]; then
    echo -e "${YELLOW}Pre-commit hook already exists${NC}"
    echo "   Backing up existing hook to .git/hooks/pre-commit.backup"
    cp .git/hooks/pre-commit .git/hooks/pre-commit.backup
fi

# Copy post-commit hook
if [ -f ".git/hooks/post-commit" ]; then
    echo -e "${YELLOW}Post-commit hook already exists${NC}"
    echo "   Backing up existing hook to .git/hooks/post-commit.backup"
    cp .git/hooks/post-commit .git/hooks/post-commit.backup
fi

# Make hooks executable
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/post-commit

echo -e "${GREEN}Git hooks installed successfully!${NC}"
echo ""
echo -e "${BLUE}What happens now:${NC}"
echo "   • Pre-commit: Vulture will check staged Python files before each commit"
echo "   • Post-commit: Vulture will analyze the entire codebase after each commit"
echo ""
echo -e "${YELLOW}Usage:${NC}"
echo "   git add ."
echo "   git commit -m 'Your commit message'  # Vulture will run automatically"
echo ""
echo -e "${YELLOW}To bypass Vulture (not recommended):${NC}"
echo "   git commit --no-verify -m 'Your commit message'"
echo ""
echo -e "${BLUE}Manual Vulture runs:${NC}"
echo "   ./tools/run_vulture.sh              # Run Vulture manually"
echo "   vulture yamlforge/ --min-confidence 80  # Run with higher confidence" 
