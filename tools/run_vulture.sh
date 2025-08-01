#!/bin/bash

# YamlForge Vulture Analysis Script
# Optimized script for finding truly unused code with smart configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
CONFIDENCE=70
SORT_BY_SIZE=false
VERBOSE=false
USE_WHITELIST=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --confidence)
            CONFIDENCE="$2"
            shift 2
            ;;
        --sort-by-size)
            SORT_BY_SIZE=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --make-whitelist)
            USE_WHITELIST=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --confidence N      Set minimum confidence (default: 70)"
            echo "  --sort-by-size      Sort results by code size"
            echo "  --verbose           Show verbose output"
            echo "  --make-whitelist    Generate whitelist format"
            echo "  --help              Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}YamlForge Vulture Analysis${NC}"
echo "=================================="

# Check if vulture is installed
if ! command -v vulture &> /dev/null; then
    echo -e "${RED}Vulture is not installed. Please install it with:${NC}"
    echo "   pip install vulture"
    exit 1
fi

# Show configuration
echo -e "${CYAN}Configuration:${NC}"
echo "   Confidence level: $CONFIDENCE%"
echo "   Sort by size: $SORT_BY_SIZE"
echo "   Verbose mode: $VERBOSE"
echo "   Whitelist mode: $USE_WHITELIST"
echo "   Using .vulture file for ignore patterns"
echo ""

# Build vulture command
VULTURE_CMD="vulture yamlforge/ demobuilder/ .vulture --min-confidence $CONFIDENCE"

if [ "$SORT_BY_SIZE" = true ]; then
    VULTURE_CMD="$VULTURE_CMD --sort-by-size"
fi

if [ "$VERBOSE" = true ]; then
    VULTURE_CMD="$VULTURE_CMD --verbose"
fi

if [ "$USE_WHITELIST" = true ]; then
    VULTURE_CMD="$VULTURE_CMD --make-whitelist"
fi

echo -e "${YELLOW}Running: $VULTURE_CMD${NC}"
echo ""

# Run vulture and capture exit code
if eval $VULTURE_CMD; then
    echo ""
    echo -e "${GREEN}✓ Vulture analysis completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}Summary:${NC}"
    echo "   • No unused code found at $CONFIDENCE% confidence level"
    echo "   • Codebase is clean and well-maintained"
    echo "   • All known false positives are properly ignored"
    echo ""
    echo -e "${CYAN}Optimization tips:${NC}"
    echo "   • Try higher confidence: ./tools/run_vulture.sh --confidence 80"
    echo "   • Sort by size: ./tools/run_vulture.sh --sort-by-size"
    echo "   • Generate whitelist: ./tools/run_vulture.sh --make-whitelist"
else
    echo ""
    echo -e "${YELLOW}⚠  Vulture found potential unused code${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "   1. Review the findings above carefully"
    echo "   2. Verify they are truly unused (not dynamically called)"
    echo "   3. Add confirmed false positives to .vulture file"
    echo "   4. Remove confirmed unused code"
    echo ""
    echo -e "${CYAN}Analysis tips:${NC}"
    echo "   • Lower confidence for more findings: ./tools/run_vulture.sh --confidence 60"
    echo "   • Verbose analysis: ./tools/run_vulture.sh --verbose"
    echo "   • Check specific methods in codebase before removing"
    echo ""
    echo -e "${YELLOW}To ignore false positives, add them to .vulture:${NC}"
    echo "   # Add method names (one per line)"
    echo "   method_name"
    echo "   another_method"
fi

echo ""
echo -e "${BLUE}Quick reference:${NC}"
echo "   ./tools/run_vulture.sh                    # Standard analysis (70% confidence)"
echo "   ./tools/run_vulture.sh --confidence 80    # Stricter analysis"
echo "   ./tools/run_vulture.sh --sort-by-size     # Sort by code size"
echo "   ./tools/run_vulture.sh --make-whitelist   # Generate whitelist format"
echo "   ./tools/run_vulture.sh --verbose          # Detailed analysis output" 
