# Album Matching Exceptions Audit

This audit records the manual review of the 20 album rows that the conservative
MusicBrainz matcher did not accept automatically. It is intentionally separate
from SQLite ingestion: no database records are created by this review.

## Outcome

- 19 original exception rows have a verified MusicBrainz release-group MBID.
- 1 row was an editorial error: `Isabella Lovestory — Amor Intro` names a track,
  not an album. It was replaced with `Isabella Lovestory — Vanity` (2025,
  Album), release-group MBID `7ccbf18c-541c-45d1-8cb6-8afffc9b8d9e`.
- All 20 reviewed decisions are recorded in `album_mbid_overrides.json`.
- Overrides are explicit evidence, not permission to weaken the global matching
  thresholds.

## Reviewed aliases and incomplete browse results

| Requested artist | Requested title | MusicBrainz canonical title | Release-group MBID | Decision |
| --- | --- | --- | --- | --- |
| Miley Cyrus | Plastic Hearts | Plastic Hearts | `0663bcbd-e202-4aeb-b003-6d49f0a4d152` | Accept |
| Miley Cyrus | Something Beautiful | Something Beautiful | `a2ba3c58-0d5d-43b3-81aa-d0a72e9e262b` | Accept |
| LOONA | [X X] | [+ +] (aka [× ×]) | `5e725997-55dc-4f9c-b8e6-7762f021ba17` | Accept as EP; canonical first year 2018 |
| Kraftwerk | The Man-Machine | Die Mensch·Maschine | `d147e89b-90ca-35b6-9f7b-3e34b8edf63f` | Accept |
| Ryuichi Sakamoto | Thousand Knives of Ryuichi Sakamoto | 千のナイフ | `e47e1a1f-5060-3ec2-9444-f93c2212ec49` | Accept |
| CA7RIEL & Paco Amoroso | BAÑO MARÍA | Baño María | `4c358d1f-aa05-443c-8fe8-4500d5c2b4c9` | Accept |
| 梅艷芳 | 似水流年 | 梅艷芳 (later issues titled 似水流年) | `8d121c9d-f67c-3bce-828d-1df52635b08e` | Accept |
| Elephant Gym | Underwater | 水底 | `14165569-4114-43ca-b040-140898f5855d` | Accept |
| Fiona Apple | When the Pawn… | Full 90-word canonical title | `3d3ff0b9-5858-33f3-9d67-8ba5977899a8` | Accept |
| David Bowie | Blackstar | ★ | `1fd18f5b-9a92-41fd-a590-da6b5cc60d85` | Accept |
| Prince | Sign o' the Times | Sign “☮︎” the Times | `90718403-7634-3786-84bf-2053a7bd4f4c` | Accept album, not same-name single |

## Reviewed type or year differences

| Artist | Title | MusicBrainz classification | Release-group MBID | Decision |
| --- | --- | --- | --- | --- |
| ARTMS | <Club Icarus> | EP, 2025 | `46b396ea-dee3-4c62-b8db-2bd84bc70b08` | Accept; correct editorial type |
| Red Velvet | The ReVe Festival: Finale | Album + Compilation, 2019 | `2b1d5578-60d7-4a6c-9cfb-fedf72924641` | Accept as reviewed repackage |
| COBRAH | SUCCUBUS | Album, 2023 | `58c43a7b-cd9e-4bc3-b521-68b74de798ff` | Accept; correct editorial type |
| Kim Petras | Clarity | Album + Mixtape/Street, 2019 | `dbe2ef7a-c16d-4469-ade6-57f49ff3b6e5` | Accept album-length project, not title-track single |
| That Kid | Superstar | Album + Mixtape/Street, 2022 | `cb12f6df-8008-4fc6-a9e0-022413a8a8e3` | Accept; correct editorial year from 2024 to 2022 |
| Kraftwerk | Trans-Europe Express | Trans Europa Express, Album, 1977 | `33101a28-ae05-3a69-873c-684e336fe2df` | Accept |
| Madvillain | Madvillainy | Album, first-release metadata 2002 | `ab570ccb-b06b-3746-8147-4903163ba895` | Accept; preserve MusicBrainz canonical year and note common 2004 date |
| Feid | FERXXOCALIPSIS | Album, 2023 | `2080236e-64c7-4a47-8d03-08c7aeba4f58` | Accept; correct editorial type |

## Editorial replacement

| Existing row | Problem | Replacement | Release-group MBID |
| --- | --- | --- | --- |
| Isabella Lovestory — Amor Intro (2022) | `Amor Intro` is a track on *Amor Hardcore*, and that album currently has no usable MusicBrainz release group in the matching result. | Isabella Lovestory — Vanity (2025, Album) | `7ccbf18c-541c-45d1-8cb6-8afffc9b8d9e` |

## Required matcher behavior

The matcher should load the override file by normalized `(requested_artist,
requested_title)`, fetch the referenced release group from MusicBrainz, and
validate its artist credit before accepting it. An override must never silently
accept an unknown or mistyped MBID. The final report should distinguish:

- automatic exact matches;
- manually reviewed overrides;
- editorial replacements;
- unresolved coverage gaps.
