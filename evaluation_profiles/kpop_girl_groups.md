# V2 Offline Recommendation Evaluation

Generated: 2026-09-29T23:49+08:00
Catalogue: 530 accepted albums
Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
Favorite albums: <Club Icarus>, IVE EMPATHY, BORN PINK
Seed aggregation: `mean_of_l2_normalized_seed_vectors_then_l2_normalize`

## Ablation summary

| Method | Results | Mean taste similarity | Mean pairwise distance | Unique lead artists | Top artist share | Overlap with embedding-only |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding_only | 9 | 0.873 | 0.210 | 9 | 0.111 | 1.000 |
| embedding_plus_tags | 9 | 0.871 | 0.211 | 9 | 0.111 | 0.889 |
| full_ranking | 9 | 0.812 | 0.316 | 9 | 0.111 | 0.444 |

## Full-ranking tier separation

Mean profile cosine similarity by displayed tier: Safe 0.896, Explore 0.841, Wildcard 0.700.

## Results to inspect manually

### embedding_only

- 1. IVE — *I’ve IVE*; score 0.929, embedding 0.929, bridge tags: dance-pop, k-pop, korean, kpop
- 2. BLACKPINK — *THE ALBUM*; score 0.882, embedding 0.882, bridge tags: dance-pop, k-pop, korean, kpop, pop, pop rap, trap
- 3. aespa — *MY WORLD*; score 0.882, embedding 0.882, bridge tags: dance-pop, k-pop
- 4. KISS OF LIFE — *Born to be XX*; score 0.876, embedding 0.876, bridge tags: k-pop, korean, kpop
- 5. f5ve — *SEQUENCE 01*; score 0.872, embedding 0.872, bridge tags: dance-pop, pop
- 6. 2NE1 — *To Anyone*; score 0.856, embedding 0.856, bridge tags: k-pop, korean, kpop, pop
- 7. LE SSERAFIM — *ANTIFRAGILE*; score 0.856, embedding 0.856, bridge tags: k-pop, korean, kpop
- 8. (G)I‐DLE — *I NEVER DIE*; score 0.855, embedding 0.855, bridge tags: k-pop, korean, kpop
- 9. ARTMS — *<Dall>*; score 0.852, embedding 0.852, bridge tags: dance-pop, k-pop, loona, synthpop

### embedding_plus_tags

- 1. IVE — *I’ve IVE*; score 0.918, embedding 0.929, bridge tags: dance-pop, k-pop, korean, kpop
- 2. BLACKPINK — *THE ALBUM*; score 0.895, embedding 0.882, bridge tags: dance-pop, k-pop, korean, kpop, pop, pop rap, trap
- 3. KISS OF LIFE — *Born to be XX*; score 0.880, embedding 0.876, bridge tags: k-pop, korean, kpop
- 4. ARTMS — *<Dall>*; score 0.873, embedding 0.852, bridge tags: dance-pop, k-pop, loona, synthpop
- 5. (G)I‐DLE — *I NEVER DIE*; score 0.864, embedding 0.855, bridge tags: k-pop, korean, kpop
- 6. LE SSERAFIM — *ANTIFRAGILE*; score 0.860, embedding 0.856, bridge tags: k-pop, korean, kpop
- 7. 2NE1 — *To Anyone*; score 0.858, embedding 0.856, bridge tags: k-pop, korean, kpop, pop
- 8. aespa — *MY WORLD*; score 0.856, embedding 0.882, bridge tags: dance-pop, k-pop
- 9. 이달의 소녀 — *[12:00]*; score 0.852, embedding 0.847, bridge tags: k-pop, kpop, loona, synthpop

### full_ranking

- 1. IVE — *I’ve IVE* / Safe; score 0.918, embedding 0.929, bridge tags: dance-pop, k-pop, korean, kpop
- 2. BLACKPINK — *THE ALBUM* / Safe; score 0.895, embedding 0.882, bridge tags: dance-pop, k-pop, korean, kpop, pop, pop rap, trap
- 3. KISS OF LIFE — *Born to be XX* / Safe; score 0.880, embedding 0.876, bridge tags: k-pop, korean, kpop
- 1. LE SSERAFIM — *ANTIFRAGILE* / Explore; score 0.879, embedding 0.856, bridge tags: k-pop, korean, kpop
- 2. IU — *Palette* / Explore; score 0.869, embedding 0.840, bridge tags: k-pop, korean, kpop
- 3. f(x) — *Pink Tape* / Explore; score 0.862, embedding 0.827, bridge tags: k-pop, korean, kpop
- 1. Kendrick Lamar — *DAMN.* / Wildcard; score 0.668, embedding 0.695, bridge tags: pop rap, trap, trap rap
- 2. Doja Cat — *Hot Pink* / Wildcard; score 0.641, embedding 0.690, bridge tags: pop, pop rap, trap
- 3. ROSALÍA — *LUX* / Wildcard; score 0.589, embedding 0.714, bridge tags: art pop, experimental

## Reading this report

These are ranking diagnostics, not evidence of user preference or recommendation accuracy. Review the listed albums manually and use Taste Battle feedback for future exploratory analysis.

When reviewing results, check for wrong album matches, seed albums reappearing, repetitive lead artists, tier mismatches, and weak or forced tag bridges. More pairwise feedback is needed before drawing conclusions about user preference.
