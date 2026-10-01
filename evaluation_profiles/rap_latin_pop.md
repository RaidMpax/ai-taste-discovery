# V2 Offline Recommendation Evaluation

Generated: 2026-09-29T23:48+08:00
Catalogue: 530 accepted albums
Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
Favorite albums: The Pinkprint, Un verano sin ti, MOTOMAMI
Seed aggregation: `mean_of_l2_normalized_seed_vectors_then_l2_normalize`

## Ablation summary

| Method | Results | Mean taste similarity | Mean pairwise distance | Unique lead artists | Top artist share | Overlap with embedding-only |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding_only | 9 | 0.852 | 0.256 | 6 | 0.333 | 1.000 |
| embedding_plus_tags | 9 | 0.848 | 0.254 | 7 | 0.222 | 0.778 |
| full_ranking | 9 | 0.788 | 0.309 | 7 | 0.222 | 0.556 |

## Full-ranking tier separation

Mean profile cosine similarity by displayed tier: Safe 0.866, Explore 0.834, Wildcard 0.664.

## Results to inspect manually

### embedding_only

- 1. Bad Bunny — *DeBÍ TiRAR MáS FOToS*; score 0.870, embedding 0.870, bridge tags: dembow, latin, reggaeton
- 2. Nicki Minaj — *Pink Friday 2*; score 0.865, embedding 0.865, bridge tags: hip hop, hip-hop, rap, rnb
- 3. Bad Bunny — *YHLQMDLG*; score 0.862, embedding 0.862, bridge tags: hip-hop, latin, latin pop, reggaeton
- 4. Tainy — *DATA*; score 0.862, embedding 0.862, bridge tags: alternative rnb, reggaeton
- 5. Kali Uchis — *ORQUÍDEAS*; score 0.860, embedding 0.860, bridge tags: latin, latin pop, reggaeton
- 6. Kali Uchis — *Sin miedo (del amor y otros demonios) ∞*; score 0.842, embedding 0.842, bridge tags: latin, latin pop, reggaeton
- 7. Bad Bunny — *X 100PRE*; score 0.836, embedding 0.836, bridge tags: reggaeton
- 8. FLO — *Access All Areas*; score 0.835, embedding 0.835, bridge tags: hip-hop, pop
- 9. ROSALÍA — *EL MAL QUERER*; score 0.833, embedding 0.833, bridge tags: alternative rnb, art pop, experimental

### embedding_plus_tags

- 1. Bad Bunny — *DeBÍ TiRAR MáS FOToS*; score 0.892, embedding 0.870, bridge tags: dembow, latin, reggaeton
- 2. Bad Bunny — *YHLQMDLG*; score 0.884, embedding 0.862, bridge tags: hip-hop, latin, latin pop, reggaeton
- 3. Nicki Minaj — *Pink Friday 2*; score 0.881, embedding 0.865, bridge tags: hip hop, hip-hop, rap, rnb
- 4. Kali Uchis — *ORQUÍDEAS*; score 0.863, embedding 0.860, bridge tags: latin, latin pop, reggaeton
- 5. ROSALÍA — *EL MAL QUERER*; score 0.858, embedding 0.833, bridge tags: alternative rnb, art pop, experimental
- 6. Kali Uchis — *Sin miedo (del amor y otros demonios) ∞*; score 0.848, embedding 0.842, bridge tags: latin, latin pop, reggaeton
- 7. Tainy — *DATA*; score 0.829, embedding 0.862, bridge tags: alternative rnb, reggaeton
- 8. Future — *HNDRXX*; score 0.827, embedding 0.827, bridge tags: 2010s, hip-hop, rap
- 9. KAROL G — *MAÑANA SERÁ BONITO*; score 0.824, embedding 0.816, bridge tags: latin, latin pop, reggaeton

### full_ranking

- 1. Bad Bunny — *DeBÍ TiRAR MáS FOToS* / Safe; score 0.892, embedding 0.870, bridge tags: dembow, latin, reggaeton
- 2. Bad Bunny — *YHLQMDLG* / Safe; score 0.884, embedding 0.862, bridge tags: hip-hop, latin, latin pop, reggaeton
- 3. Nicki Minaj — *Pink Friday 2* / Safe; score 0.881, embedding 0.865, bridge tags: hip hop, hip-hop, rap, rnb
- 1. Megan Thee Stallion — *MEGAN* / Explore; score 0.838, embedding 0.804, bridge tags: hip hop, hip-hop, rap
- 2. Tainy — *DATA* / Explore; score 0.835, embedding 0.862, bridge tags: alternative rnb, reggaeton
- 3. FLO — *Access All Areas* / Explore; score 0.823, embedding 0.835, bridge tags: hip-hop, pop
- 1. Lil’ Kim — *Hard Core* / Wildcard; score 0.663, embedding 0.688, bridge tags: hip hop, hip-hop, rap, rnb
- 2. Kendrick Lamar — *good kid, m.A.A.d city* / Wildcard; score 0.655, embedding 0.635, bridge tags: 2010s, hip hop, hip-hop, rap
- 3. Kendrick Lamar — *DAMN.* / Wildcard; score 0.649, embedding 0.668, bridge tags: hip hop, hip-hop, rap

## Reading this report

These are ranking diagnostics, not evidence of user preference or recommendation accuracy. Review the listed albums manually and use Taste Battle feedback for future exploratory analysis.

When reviewing results, check for wrong album matches, seed albums reappearing, repetitive lead artists, tier mismatches, and weak or forced tag bridges. More pairwise feedback is needed before drawing conclusions about user preference.
