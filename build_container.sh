#!/usr/bin/env bash
# Build the FoodNetTrends Singularity container
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  FoodNetTrends Container Builder${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check for required tools
for cmd in singularity pixi; do
    if ! command -v "$cmd" &>/dev/null; then
        if ! module load "$cmd" 2>/dev/null; then
            echo -e "${RED}Error: '$cmd' not found. Load it with 'ml $cmd' or install it.${NC}"
            exit 1
        fi
    fi
done

# Check for def file
if [ ! -f "foodnet.def" ]; then
    echo -e "${RED}Error: foodnet.def not found. Run this from the repo root.${NC}"
    exit 1
fi

# Generate pixi lock file if missing
if [ ! -f "pixi.toml" ] || [ ! -f "pixi.lock" ]; then
    echo -e "${YELLOW}Generating pixi environment files from foodnet.yml...${NC}"
    if [ ! -f "foodnet.yml" ]; then
        echo -e "${RED}Error: foodnet.yml not found.${NC}"
        exit 1
    fi
    pixi init --import foodnet.yml
    echo -e "${GREEN}Created pixi.toml${NC}"

    echo -e "${YELLOW}Resolving dependencies (this may take a minute)...${NC}"
    pixi install
    echo -e "${GREEN}Created pixi.lock${NC}"
else
    echo -e "${GREEN}Found existing pixi.toml and pixi.lock${NC}"
fi

# Build container
SIF="foodnet.sif"
if [ -f "$SIF" ]; then
    echo ""
    echo -e "${YELLOW}Existing container found: $SIF${NC}"
    read -r -p "Rebuild? (y/n) [y]: " rebuild
    rebuild=${rebuild:-y}
    if [[ "$rebuild" != "y" ]]; then
        echo "Skipping build."
        exit 0
    fi
    FORCE="--force"
else
    FORCE=""
fi

echo ""
echo -e "${BLUE}Building container (this takes 15-20 minutes)...${NC}"
echo -e "  Base image:  ubuntu:22.04"
echo -e "  Environment: pixi (from pixi.lock)"
echo -e "  Includes:    R, brms, RStan, CmdStan, tidybayes"
echo ""

singularity build $FORCE "$SIF" foodnet.def 2>&1 | tee build.log

if [ -f "$SIF" ]; then
    SIZE=$(du -h "$SIF" | cut -f1)
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Container built successfully${NC}"
    echo -e "${GREEN}  File: $SIF ($SIZE)${NC}"
    echo -e "${GREEN}========================================${NC}"

    # Verify R packages
    echo ""
    echo -e "${BLUE}Verifying R packages...${NC}"
    singularity exec "$SIF" Rscript -e "
        pkgs <- c('brms','rstan','cmdstanr','tidybayes','HDInterval','dplyr','ggplot2','argparse','stringdist','base64enc')
        ok <- sapply(pkgs, requireNamespace, quietly=TRUE)
        cat(paste(pkgs, ifelse(ok, 'OK', 'MISSING'), sep=': '), sep='\n')
        if (!all(ok)) quit(status=1)
    " 2>/dev/null && echo -e "${GREEN}All core packages verified.${NC}" \
      || echo -e "${RED}Some packages missing — check build.log${NC}"

    # Check CmdStan
    echo ""
    echo -e "${BLUE}Checking CmdStan...${NC}"
    singularity exec "$SIF" Rscript -e "
        p <- Sys.getenv('CMDSTAN', unset='')
        if (nchar(p) > 0 && dir.exists(p)) {
            cat('CmdStan:', p, '\n')
        } else {
            cat('CmdStan: not found (cmdstanr backend unavailable)\n')
        }
    " 2>/dev/null

    echo ""
    echo -e "Build log saved to: build.log"
    echo -e "To run the pipeline: ${GREEN}./run_workflow.sh${NC}"
else
    echo ""
    echo -e "${RED}Build failed. Check build.log for details.${NC}"
    exit 1
fi
