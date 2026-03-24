# Ottoneu Draft Assistant

A Streamlit web app for Ottoneu fantasy baseball auction drafts. Combines multiple data sources (FanGraphs stats, projections, expert rankings, Ottoneu ownership data) into a unified SQLite database and provides a real-time draft tracker with filtering, sorting, tagging, and roster planning.

## Key Concepts

### Ottoneu Fantasy Baseball

Ottoneu is a dynasty fantasy baseball format where teams acquire players through auction drafts. Each team has a fixed salary budget ($400), and players are kept year-over-year at their acquired salary. This tool helps identify value during the draft by comparing projected performance against auction prices.

### Data Sources

The app merges 7+ data files per player type to build a complete player profile:

- **Fantasy stats** — FanGraphs historical stats (points, games, plate appearances / innings pitched)
- **Advanced stats** — Batted ball data, plate discipline, and advanced metrics (wRC+, Stuff+, etc.)
- **Projections** — Forward-looking stat projections (prefixed with `proj_`)
- **Position universe** — Ottoneu average values export providing current positions, team ownership, salary, and roster percentages (authoritative source for ownership data)
- **Expert rankings** — Positional rankings from multiple experts
- **Player info** — MLB team and age data
- **Historical draft results** — Past auction prices used to train price prediction models

### Dollar Values & Surplus

The app calculates dollar values from projected stats using configurable league settings (number of teams, budget, hitter/pitcher budget split). **Surplus value** (projected dollar value minus acquisition cost) is the core metric for identifying draft bargains.

### Keeper Salary Bias

In dynasty leagues, keeper salaries skew low because owners only retain players they consider below market value. The app accounts for this distinction — keeper salaries are displayed but not used as training data for price predictions.

## Functionality

### Draft Tracker

The main interface provides tabbed views for **Hitters** and **Pitchers**, each displaying an interactive data table with:

- **Search** — Filter players by name with a quick-clear button
- **Position filters** — Show only specific positions (supports multi-position eligibility)
- **Availability indicators** — Color-coded status showing available (green), drafted (blue), or kept (gray) players
- **Percentile indicators** — Emoji-based rankings (green/yellow/red) showing how each player's stats compare to the full player pool
- **Stat range filters** — Min/max sliders for key stats (fpts, dollar value, wRC+, ERA, K/9, etc.)
- **Column group selection** — Toggle visibility of stat categories (Player Info, Rankings, Fantasy, Basic Stats, Projections, Advanced)
- **Drafting** — Click a player row to open a draft dialog, enter the price, and log the pick
- **Tagging** — Mark players as Target, Avoid, or Injury with color-coded labels

### Roster Planning

The Roster tab provides:

- **Budget dashboard** — Remaining budget, salary committed, roster spots left, dollars per open spot
- **Roster grid** — Pre-defined slot structure (C, 1B, 2B, SS, 3B, MI, OF, Util, SP, RP, Bench) with player assignments
- **Position targets** — Per-position wishlists with player names and roles (Starter, Bench, Prospect)

### Draft Log

Tracks all draft actions in reverse chronological order with:

- Player name, type (hitter/pitcher), projected salary, draft price, and computed value
- Summary metrics (total drafted, total spent, average value)
- Undo button to revert the last pick

### Settings

- **League configuration** — Adjust number of teams, budget, hitter budget percentage, and roster sizes to recalculate dollar values
- **Position data upload** — Upload a fresh Ottoneu average values CSV to sync positions, teams, salaries, and ownership percentages
- **Price model training** — Train an ML model on historical draft results to generate price predictions and identify model-flagged targets
- **Database rebuild** — Reload all source data while preserving user data (tags, roster plan, position targets)

## Technical Components

### Architecture

```
app.py                  # Streamlit entry point, tab routing, sidebar integration
data/
  load.py               # CSV/XLSX loading, column normalization, name cleaning
  merge.py              # Multi-source DataFrame merging, deduplication, pruning
  positions.py          # Ottoneu position universe parser
db/
  connection.py         # SQLite connection factory (WAL mode)
  schema.py             # DDL for all tables (draft_log, roster_plan, player_tags, etc.)
  queries.py            # Parameterized query builder, draft/undo logic, roster sync
  init_db.py            # ETL pipeline: load → merge → valuate → populate DB
ui/
  hitters_view.py       # Hitter table rendering with styling and interactions
  pitchers_view.py      # Pitcher table rendering (parallel structure to hitters)
  draft_log.py          # Draft history display with undo
  roster_view.py        # Roster planning grid and budget dashboard
  sidebar.py            # Shared filter/sort controls
  settings.py           # League config, data upload, model training
valuation/              # Dollar value calculation and price prediction model
```

### Data Pipeline

1. **Load** — Source CSVs are read with BOM encoding support and XLSX auto-detection (via magic bytes). Column names are normalized to SQL-friendly formats. Player names are cleaned (accent removal, suffix stripping).
2. **Merge** — DataFrames are outer-joined on player name. Position CSV values take priority for ownership data. Players with no projections, no historical stats, and low ownership (≤5%) are pruned.
3. **Valuate** — Projected stats are converted to dollar values based on league settings. Historical prices optionally train a price prediction model.
4. **Store** — Final DataFrames are written to SQLite via pandas `to_sql`. Draft state columns (`is_drafted`, `draft_price`, `is_keeper`) are initialized empty.

### Database

SQLite with WAL mode for concurrency across Streamlit sessions. Key tables:

| Table | Purpose |
|---|---|
| `hitters` / `pitchers` | Full player stats and draft state |
| `draft_log` | Chronological record of all draft picks |
| `valuation_config` | League settings for dollar value calculation |
| `roster_plan` | Pre-seeded roster slots with player assignments |
| `player_tags` | User annotations (target, avoid, injury) |
| `model_targets` | ML-identified value opportunities |
| `position_targets` | Per-position draft wishlists |
| `historical_prices` | Past season auction results |

### Query Layer

`queries.py` builds parameterized SQL with dynamic WHERE clauses for position, availability, stat ranges, and tags. Sort columns are validated against table schema to prevent injection. NULLs are sorted last via `ORDER BY col IS NULL, col`.

## Setup

### 1. Clone and install

```bash
git clone https://github.com/<your-username>/ottoneu-draft-assistant.git
cd ottoneu-draft-assistant
pip install -r requirements.txt
```

Or install as a package: `pip install -e .`

### 2. Prepare data files

The app expects source data files in the **parent directory** of the project by default. You can override this by setting the `OTTONEU_DATA_DIR` environment variable (see `.env.example`).

#### Required files (FanGraphs exports)

Export these from FanGraphs leaderboards as CSV:

| File | Source |
|---|---|
| `hitters_advanced.csv` | FanGraphs → Leaders → Hitters → Advanced |
| `hitters_batted_ball.csv` | FanGraphs → Leaders → Hitters → Batted Ball |
| `hitters_fantasy.csv` | FanGraphs → Leaders → Hitters → Fantasy (may export as XLSX — handled automatically) |
| `pitchers_advanced.csv` | FanGraphs → Leaders → Pitchers → Advanced |
| `pitchers_batted_ball.csv` | FanGraphs → Leaders → Pitchers → Batted Ball |
| `pitchers_fantasy.csv` | FanGraphs → Leaders → Pitchers → Fantasy |
| `pitchers_modeling.csv` | FanGraphs → Leaders → Pitchers → Pitch Type / Modeling |

#### Optional files (for full functionality)

| File | Source | Enables |
|---|---|---|
| `proj_hitters.csv` | FanGraphs or projection system export | Dollar values, surplus calculations |
| `proj_pitchers.csv` | FanGraphs or projection system export | Dollar values, surplus calculations |
| `hitter_positions.csv` | Ottoneu → Average Values → Export CSV | Ownership, salary, positions (authoritative) |
| `pitcher_positions.csv` | Ottoneu → Average Values → Export CSV | Ownership, salary, positions (authoritative) |
| `expert_rankings.xlsx` | Custom — sheets per position (C, 1B, MI, 3B, OF, SP, RP) | Expert ranking columns |
| `player_info.xlsx` | Custom — columns: Name, Team, Age | MLB team and age data |
| `draft_results.csv` | Ottoneu draft export — columns: Year, Team Name, PlayerID, Player Name, Price | Price model training |
| `hitter_statcast.csv` | Baseball Savant export | StatCast metrics |

### 3. Run the app

```bash
streamlit run app.py
```

The database builds automatically on first launch. No manual init step needed.

### 4. Configure

Once the app is running, go to the **Settings** tab to:

1. **Set your team name** — enables the "Show my team" filter to highlight your owned players
2. **Adjust league settings** — number of teams, budget, hitter/pitcher split, roster sizes
3. **Upload position data** — upload a fresh Ottoneu average values CSV at any time
4. **Train price model** — if you loaded historical draft results

### Custom data directory

To use a different directory for data files:

```bash
export OTTONEU_DATA_DIR=/path/to/your/data
streamlit run app.py
```

Or copy `.env.example` to `.env` and set the path there.
