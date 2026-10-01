# V2 Offline Recommendation Evaluation

Generated: 2026-09-29T22:19+08:00
Catalogue: 530 accepted albums
Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
Favorite albums: OK Computer
Seed aggregation: `mean_of_l2_normalized_seed_vectors_then_l2_normalize`

## Ablation summary

| Method | Results | Mean taste similarity | Mean pairwise distance | Unique lead artists | Top artist share | Overlap with embedding-only |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding_only | 9 | 0.787 | 0.259 | 8 | 0.222 | 1.000 |
| embedding_plus_tags | 9 | 0.776 | 0.288 | 7 | 0.222 | 0.556 |
| full_ranking | 9 | 0.738 | 0.333 | 8 | 0.222 | 0.556 |

## Full-ranking tier separation

Mean profile cosine similarity by displayed tier: Safe 0.831, Explore 0.755, Wildcard 0.628.

## Results to inspect manually

### embedding_only

- 1. Radiohead — *Kid A*; score 0.897, embedding 0.897, bridge tags: alternative, alternative rock, art rock, electronic, experimental, rock
- 2. Radiohead — *In Rainbows*; score 0.842, embedding 0.842, bridge tags: alternative, alternative rock, art rock, electronic, rock
- 3. The 1975 — *The 1975*; score 0.788, embedding 0.788, bridge tags: none
- 4. ML Buch — *Suntub*; score 0.768, embedding 0.768, bridge tags: experimental
- 5. 椎名林檎 — *無罪モラトリアム*; score 0.762, embedding 0.762, bridge tags: 90s, alternative rock, rock
- 6. Marina and the Diamonds — *FROOT*; score 0.760, embedding 0.760, bridge tags: alternative
- 7. Pixies — *Doolittle*; score 0.758, embedding 0.758, bridge tags: alternative, alternative rock, rock
- 8. underscores — *Wallsocket*; score 0.753, embedding 0.753, bridge tags: alternative, alternative rock, electronic, rock
- 9. Daft Punk — *Homework*; score 0.751, embedding 0.751, bridge tags: 90s, electronic

### embedding_plus_tags

- 1. Radiohead — *Kid A*; score 0.908, embedding 0.897, bridge tags: alternative, alternative rock, art rock, electronic, experimental, rock
- 2. Radiohead — *In Rainbows*; score 0.858, embedding 0.842, bridge tags: alternative, alternative rock, art rock, electronic, rock
- 3. 椎名林檎 — *無罪モラトリアム*; score 0.786, embedding 0.762, bridge tags: 90s, alternative rock, rock
- 4. Pixies — *Doolittle*; score 0.782, embedding 0.758, bridge tags: alternative, alternative rock, rock
- 5. underscores — *Wallsocket*; score 0.778, embedding 0.753, bridge tags: alternative, alternative rock, electronic, rock
- 6. Brian Eno — *Another Green World*; score 0.773, embedding 0.748, bridge tags: art rock, electronic, experimental, rock
- 7. The Strokes — *Is This It*; score 0.771, embedding 0.745, bridge tags: alternative, alternative rock, rock
- 8. Björk — *Homogenic*; score 0.770, embedding 0.744, bridge tags: 90s, alternative, electronic, experimental
- 9. underscores — *fishmonger*; score 0.760, embedding 0.734, bridge tags: alternative, alternative rock, electronic, rock

### full_ranking

- 1. Radiohead — *Kid A* / Safe; score 0.908, embedding 0.897, bridge tags: alternative, alternative rock, art rock, electronic, experimental, rock
- 2. Radiohead — *In Rainbows* / Safe; score 0.858, embedding 0.842, bridge tags: alternative, alternative rock, art rock, electronic, rock
- 3. underscores — *Wallsocket* / Safe; score 0.778, embedding 0.753, bridge tags: alternative, alternative rock, electronic, rock
- 1. 椎名林檎 — *無罪モラトリアム* / Explore; score 0.819, embedding 0.762, bridge tags: 90s, alternative rock, rock
- 2. Pixies — *Doolittle* / Explore; score 0.814, embedding 0.758, bridge tags: alternative, alternative rock, rock
- 3. The Strokes — *Is This It* / Explore; score 0.805, embedding 0.745, bridge tags: alternative, alternative rock, rock
- 1. St. Vincent — *All Born Screaming* / Wildcard; score 0.642, embedding 0.613, bridge tags: alternative rock, art rock, rock
- 2. Lana Del Rey — *Ultraviolence* / Wildcard; score 0.562, embedding 0.635, bridge tags: alternative, rock
- 3. Ravyn Lenae — *Hypnos* / Wildcard; score 0.562, embedding 0.635, bridge tags: alternative, electronic

## Reading this report

These are ranking diagnostics, not evidence of user preference or recommendation accuracy. Review the listed albums manually and use Taste Battle feedback for future exploratory analysis.

When reviewing results, check for wrong album matches, seed albums reappearing, repetitive lead artists, tier mismatches, and weak or forced tag bridges. More pairwise feedback is needed before drawing conclusions about user preference.
