# V2 Album Selection

Status: editorial selection in progress. The product owner delegated unresolved
album-level choices to the accepted defaults in `EDITORIAL_DECISIONS.md`. No V2
albums have been ingested yet.

## Goal

Build a catalogue of approximately 500 albums from the 282-artist slate in
`DATASET_SELECTION.md`.

The catalogue should feel broad enough for discovery while retaining a clear
editorial point of view. It should not become a collection of complete
discographies or a popularity chart.

## Original 280 + 220 planning model

The first planning pass gives every candidate artist one core release. It then
allocates 220 additional slots to artists who need more releases to represent a
genuinely different period, sound, or role in the product.

This originally produced an exact planning budget of 500:

- 280 baseline releases;
- 220 additional releases;
- 500 planned releases in total.

This remains a planning model, not a reason to accept a weak release. The
accepted target is now a range of approximately 480-530 releases. Seed-only
coverage counts inside that total.

## Current accepted progress

| Completed branch | Artists | Accepted releases |
| --- | ---: | ---: |
| Contemporary pop and alt-pop | 25 | 74 |
| Breakout and new-generation pop | 24 | 35 |
| K-pop girl groups and female soloists | 27 | 54 |
| Hyperpop and internet pop | 19 | 31 |
| Contemporary indie and alternative | 30 | 60 |
| Left-field art pop | 15 | 26 |
| Electronic | 19 | 38 |
| R&B and soul | 13 | 32 |
| Rap and hip-hop | 36 | 61 |
| Latin and Spanish-language | 20 | 26 |
| Selective Asian and global | 15 | 29 |
| Canonical taste anchors | 26 | 42 |
| Modern pop canon and cult favourites | 13 | 22 |
| **Completed total** | **282** | **530** |

All 282 artist targets are now represented. The untrimmed Batch 4 defaults
would have produced 552 releases, so the final balance audit returned 22
secondary catalog slots while preserving every artist and all explicit
product-owner keep decisions. The final accepted total is 530 releases.

## Proposed category allocation

| Branch | Artists | Baseline | Extra slots | Planned releases |
| --- | ---: | ---: | ---: | ---: |
| Contemporary pop and alt-pop | 25 | 25 | 30 | 55 |
| Contemporary indie and alternative | 30 | 30 | 18 | 48 |
| Canonical taste anchors | 26 | 26 | 36 | 62 |
| Modern pop canon and cult favourites | 13 | 13 | 13 | 26 |
| R&B and neo-soul | 13 | 13 | 12 | 25 |
| Rap and hip-hop | 34 | 34 | 24 | 58 |
| Electronic and club-adjacent | 19 | 19 | 15 | 34 |
| K-pop girl groups and female soloists | 27 | 27 | 25 | 52 |
| Breakout and new-generation pop | 24 | 24 | 3 | 27 |
| Hyperpop, internet pop, and new electronic pop | 19 | 19 | 11 | 30 |
| Left-field pop and art-pop discoveries | 15 | 15 | 8 | 23 |
| Latin and Spanish-language expansion | 20 | 20 | 12 | 32 |
| Selective Asian and global extension | 15 | 15 | 13 | 28 |
| **Total** | **280** | **280** | **220** | **500** |

## Why the allocation is shaped this way

- The catalogue remains centred on contemporary culture rather than being
  dominated by historical canon.
- Canonical artists receive enough room to show distinct eras, but only 62 of
  the 500 slots belong to that branch.
- Rap receives its own substantial allocation instead of being treated as a
  small extension of R&B.
- K-pop retains meaningful depth after all boy groups were removed.
- Hyperpop, left-field pop, and Spanish-language music have enough density to
  produce real recommendation paths rather than isolated novelty picks.
- The breakout branch stays broad: most new artists receive one current,
  culturally relevant release instead of premature discography depth.

## Per-artist release rules

### Usually one release

- breakout and very new artists;
- artists with only one clearly relevant project;
- cult or regional additions included to open a discovery path;
- artists whose catalogue is culturally visible but uneven.

### Usually two releases

- established contemporary artists with two meaningfully different strong
  projects;
- K-pop artists where an album and a substantial mini album represent distinct
  eras;
- rap, electronic, Latin, and indie artists with both an accessible entry point
  and a more adventurous project.

### Usually two or three releases

- canonical artists whose eras cannot be represented honestly by one album;
- a small number of contemporary artists with several genuinely central works.

### Discography-coverage exceptions

Some artists should not have a hard three-release ceiling. For artists with a
large and highly engaged fanbase, different albums can represent meaningfully
different user tastes even when not every album is an editorial priority.

Taylor Swift is the clearest example: a fan may reasonably choose any of her
main studio albums as a seed. Restricting the input catalogue to three albums
would erase useful preference information before recommendation even begins.

An expanded artist allocation is allowed when:

- users are likely to search for several different studio albums;
- those albums represent distinguishable eras or taste signals;
- the extra albums materially improve seed selection;
- the catalogue still excludes deluxe, remastered, live, and duplicate editions.

This exception is based on product usefulness, not fame alone. It will apply to
a small reviewed set of artists rather than every established act.

## Two album roles

The same catalogue supports two different jobs, so album selection should store
two separate eligibility decisions.

### Seed eligible

The album may be selected by a user as one of their favourites. Coverage should
be relatively broad for artists whose fans identify strongly with different
eras or albums.

### Recommendation eligible

The album may appear as a recommendation. This remains more selective so that
large discographies do not dominate rankings or introduce weak recommendations.

An album can therefore be:

- eligible for both seed selection and recommendation;
- seed eligible but not recommendation eligible;
- excluded from both.

Recommendation eligibility remains a deterministic catalogue field. Gemini
does not decide it.

## Release eligibility

Prefer:

- studio albums;
- artistically substantial EPs or K-pop mini albums;
- the original release group rather than a later deluxe or remaster;
- releases that add a distinct recommendation signal to the catalogue.

Exclude by default:

- singles;
- greatest-hits and routine compilations;
- deluxe, anniversary, and remastered duplicates;
- live, remix, demo, karaoke, and instrumental variants;
- weak early releases included only because the artist later became famous.

## Selection evidence

Each proposed release should eventually contain:

- artist and release title;
- MusicBrainz artist MBID and release-group MBID;
- primary release year;
- branch;
- proposed artist slot number, such as `1 of 2`;
- seed eligibility;
- recommendation eligibility;
- a short inclusion reason;
- confidence: `accept`, `review`, or `reject`;
- matching notes when MusicBrainz identity is uncertain.

Critical reception and popularity may help discover candidates, but neither is
an automatic acceptance rule. The final decision is editorial and album-level.

## Review sequence

To keep the review manageable, concrete album titles will be proposed in four
batches rather than as one 500-row wall:

1. contemporary pop, breakout pop, K-pop, and hyperpop;
2. indie, left-field pop, electronic, and R&B;
3. rap, Latin/Spanish-language, and Asian/global;
4. canonical and modern-pop canon, followed by a balance audit.

After all four batches:

- count releases by artist, branch, decade, and region;
- inspect duplicate releases and alternate editions;
- check whether any artist is overrepresented;
- reserve uncertain MusicBrainz matches for manual review;
- approve the final manifest before database ingestion.

Album-level selection and the first global balance audit are now complete.
Canonical MusicBrainz matching remains the required gate before ingestion.

## Resolved policy decisions

- The final total may land between approximately 480 and 530 releases.
- Strong EPs and mixtapes count inside the same total as albums.
- K-pop remains female-only in this V2 slate.
- Kanye West and Drake remain eligible under selective catalog allocations.
- Taylor Swift receives broad era-level seed coverage; other large catalogs are
  curated unless a separate product reason justifies broader seed coverage.
- Controversy alone does not automatically exclude an artist; release quality,
  product usefulness, and deterministic eligibility rules still apply.
