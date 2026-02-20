# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ottoneu Draft Assistant — a Streamlit web app for Ottoneu fantasy baseball auction drafts. Combines 7 data files (4 pitcher, 3 hitter CSVs from FanGraphs/Ottoneu) into a SQLite database and provides a real-time draft tracker with filtering, sorting, and best-available identification.

## Tech Stack

- Python 3.11+ with Streamlit
- SQLite for local draft state
- pandas for data processing
- openpyxl for Excel file reading

## Project Structure

- `app.py` — Streamlit entry point
- `data/` — CSV/XLSX loading (`load.py`), merging (`merge.py`), position parsing (`positions.py`)
- `db/` — SQLite schema (`schema.py`), connection (`connection.py`), queries (`queries.py`), init script (`init_db.py`)
- `ui/` — Streamlit views: `hitters_view.py`, `pitchers_view.py`, `draft_log.py`, `sidebar.py`, `settings.py`

Source data files live in the parent directory: `../` (relative to project root).

## Commands

```bash
# Install dependencies
pip install streamlit pandas openpyxl

# Initialize/rebuild the database
python3 db/init_db.py

# Run the app
streamlit run app.py
```

## Key Conventions

- Player `name` is the natural key across all source files
- Source CSVs use BOM encoding (`utf-8-sig`); `hitters_fantasy.csv` is actually XLSX
- Column names are SQL-friendly (e.g., `k_per_9`, `hr_per_fb`, `wrc_plus`)
- Draft state (is_drafted, draft_price) stored in SQLite alongside stats

## Data Context

- **Current source data is historical** (past season stats), not projections
- **Dynasty league**: salary data represents keeper salaries for currently owned players
- Keeper salaries are biased downward (players are only kept if owner deems them below market value) — do NOT use as training data for price prediction
- Projection data must be sourced separately from historical stats
