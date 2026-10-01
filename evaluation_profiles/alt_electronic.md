# V2 Offline Recommendation Evaluation

Generated: 2026-09-29T23:48+08:00
Catalogue: 530 accepted albums
Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
Favorite albums: OK Computer, Homogenic, Untrue
Seed aggregation: `mean_of_l2_normalized_seed_vectors_then_l2_normalize`

## Ablation summary

| Method | Results | Mean taste similarity | Mean pairwise distance | Unique lead artists | Top artist share | Overlap with embedding-only |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding_only | 9 | 0.819 | 0.290 | 8 | 0.222 | 1.000 |
| embedding_plus_tags | 9 | 0.816 | 0.304 | 7 | 0.222 | 0.778 |
| full_ranking | 9 | 0.774 | 0.358 | 8 | 0.222 | 0.444 |

## Full-ranking tier separation

Mean profile cosine similarity by displayed tier: Safe 0.830, Explore 0.802, Wildcard 0.690.

## Results to inspect manually

### embedding_only

- 1. Radiohead — *Kid A*; score 0.850, embedding 0.850, bridge tags: alternative, alternative rock, art rock, electronic, experimental, rock
- 2. Björk — *Post*; score 0.828, embedding 0.828, bridge tags: 90s, alternative, art pop, electronic, experimental, trip-hop
- 3. Portishead — *Dummy*; score 0.828, embedding 0.828, bridge tags: 90s, electronic, trip-hop
- 4. ML Buch — *Suntub*; score 0.814, embedding 0.814, bridge tags: experimental
- 5. Björk — *Vespertine*; score 0.813, embedding 0.813, bridge tags: alternative, art pop, electronic, electronica, experimental
- 6. Aphex Twin — *Selected Ambient Works 85–92*; score 0.812, embedding 0.812, bridge tags: 90s, electronic, electronica, experimental
- 7. Burial — *Kindred*; score 0.811, embedding 0.811, bridge tags: ambient, dubstep, electronic, future garage
- 8. Overmono — *Good Lies*; score 0.811, embedding 0.811, bridge tags: ambient, electronic, uk garage
- 9. Four Tet — *Three*; score 0.810, embedding 0.810, bridge tags: ambient, electronic

### embedding_plus_tags

- 1. Radiohead — *Kid A*; score 0.874, embedding 0.850, bridge tags: alternative, alternative rock, art rock, electronic, experimental, rock
- 2. Björk — *Post*; score 0.848, embedding 0.828, bridge tags: 90s, alternative, art pop, electronic, experimental, trip-hop
- 3. Björk — *Vespertine*; score 0.837, embedding 0.813, bridge tags: alternative, art pop, electronic, electronica, experimental
- 4. Burial — *Kindred*; score 0.835, embedding 0.811, bridge tags: ambient, dubstep, electronic, future garage
- 5. Portishead — *Dummy*; score 0.830, embedding 0.828, bridge tags: 90s, electronic, trip-hop
- 6. Radiohead — *In Rainbows*; score 0.825, embedding 0.795, bridge tags: alternative, alternative rock, art rock, electronic, rock
- 7. Overmono — *Good Lies*; score 0.822, embedding 0.811, bridge tags: ambient, electronic, uk garage
- 8. Aphex Twin — *Selected Ambient Works 85–92*; score 0.816, embedding 0.812, bridge tags: 90s, electronic, electronica, experimental
- 9. underscores — *Wallsocket*; score 0.811, embedding 0.801, bridge tags: alternative, alternative rock, electronic, rock

### full_ranking

- 1. Radiohead — *Kid A* / Safe; score 0.874, embedding 0.850, bridge tags: alternative, alternative rock, art rock, electronic, experimental, rock
- 2. Björk — *Post* / Safe; score 0.848, embedding 0.828, bridge tags: 90s, alternative, art pop, electronic, experimental, trip-hop
- 3. Björk — *Vespertine* / Safe; score 0.837, embedding 0.813, bridge tags: alternative, art pop, electronic, electronica, experimental
- 1. Overmono — *Good Lies* / Explore; score 0.848, embedding 0.811, bridge tags: ambient, electronic, uk garage
- 2. Daft Punk — *Homework* / Explore; score 0.830, embedding 0.798, bridge tags: 90s, electronic, electronica
- 3. Eartheater — *Powders* / Explore; score 0.819, embedding 0.798, bridge tags: art pop, electronic, trip-hop
- 1. Kraftwerk — *Trans Europa Express* / Wildcard; score 0.658, embedding 0.683, bridge tags: electronic, electronica, experimental
- 2. Yeah Yeah Yeahs — *It’s Blitz!* / Wildcard; score 0.654, embedding 0.694, bridge tags: alternative, alternative rock, electronic, rock
- 3. Madonna — *Ray of Light* / Wildcard; score 0.653, embedding 0.692, bridge tags: 90s, art pop, electronic, trip-hop

## Reading this report

These are ranking diagnostics, not evidence of user preference or recommendation accuracy. Review the listed albums manually and use Taste Battle feedback for future exploratory analysis.

When reviewing results, check for wrong album matches, seed albums reappearing, repetitive lead artists, tier mismatches, and weak or forced tag bridges. More pairwise feedback is needed before drawing conclusions about user preference.
