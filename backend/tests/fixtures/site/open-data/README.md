# AirStack open data

Facts from products' own pages and public registries, one JSON line per fact, released each month as `airstack-<YYYY-MM>.jsonl.gz`.
Each fact is a short quote with its source link and the day the page was read, so anyone can check it.

## Licence

- AirStack's compilation (the records, their selection and arrangement) is under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  Credit "AirStack (https://airstack.bot)" and keep each fact's source link.
- Quotes belong to their publishers. Each is at most 25 words and is included only to show where a fact comes from. Text quoted from
  Wikipedia or another Wikimedia project is under CC BY-SA 4.0; each line's `licence` says which applies.
- Product ids that start with `Q` are Wikidata items. Those ids and their names come from [Wikidata](https://www.wikidata.org/), under CC0.
- Product names are trademarks of their owners. A publisher can ask for a quote to be removed by opening an issue at
  https://github.com/OttObottr/airstack/issues.

## Fields

| Field | What it holds |
|---|---|
| `id` | AirStack's product id |
| `name` | The product's name |
| `metric` | What the fact is about, such as `what_it_does`, `platforms`, `integrations` or `free_plan` |
| `value` | The value read from the quote: text, a list, true or false, or a number |
| `quote` | The page's own words, at most 25 words |
| `url` | The page the quote is on |
| `read` | The day AirStack read that page (YYYY-MM-DD) |
| `licence` | The licence note for this line |

Left out: the stored page text, prices, and every fact from a page whose robots.txt is closed to AirStackBot, and every fact from
the hosts whose terms AirStack has recorded as barring automated reading. A page that closes later is removed from earlier releases too.

## How it is built

`backend/tools/build_feed.py` reads `chain-data.json`, the evidence file the site serves, and writes this month's release and this file.
It makes no model call and no network request, and the same input gives the same bytes. The release for a month is the last build in it.

## Releases

| Release | Facts | Products | New since the previous release | Gone since the previous release |
|---|---|---|---|---|
| `airstack-2026-11.jsonl.gz` | 26 | 5 | 26 | 0 |
