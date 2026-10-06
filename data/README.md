# data/

| folder | committed? | contents |
|---|---|---|
| `raw/` | no | CFPB archive exports `CCDB_Export_*.zip` (~1.3 GB zipped) and cached Yahoo price JSON; rebuilt by `make pipeline` |
| `interim/` | no | `cfpb.duckdb`, the filtered complaints for the 10-company universe plus topic weights (~1 GB) |
| `processed/` | yes | small derived tables: quarterly volume (`q_volume.csv`), topic shares (`q_topics.csv`), template shares (`q_templates.csv`), weekly counts (`weekly_volume.csv`), the signal/return panel (`signal_panel.csv`), topic top terms and a few example narratives, and the archive-vs-API validation |

The complaint data is public domain (CC0). Narratives were redacted by the CFPB before publication (names, dates and account numbers appear as `XXXX`).
