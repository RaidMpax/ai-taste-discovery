# V2 Offline Recommendation Evaluation

Generated: 2026-09-29T23:48+08:00
Catalogue: 530 accepted albums
Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
Favorite albums: BRAT, HIT ME HARD AND SOFT, 30
Seed aggregation: `mean_of_l2_normalized_seed_vectors_then_l2_normalize`

## Ablation summary

| Method | Results | Mean taste similarity | Mean pairwise distance | Unique lead artists | Top artist share | Overlap with embedding-only |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding_only | 9 | 0.845 | 0.222 | 9 | 0.111 | 1.000 |
| embedding_plus_tags | 9 | 0.835 | 0.235 | 7 | 0.333 | 0.556 |
| full_ranking | 9 | 0.788 | 0.338 | 7 | 0.222 | 0.333 |

## Full-ranking tier separation

Mean profile cosine similarity by displayed tier: Safe 0.845, Explore 0.828, Wildcard 0.692.

## Results to inspect manually

### embedding_only

- 1. Charli xcx — *how i’m feeling now*; score 0.857, embedding 0.857, bridge tags: bubblegum bass, electronic, electropop, hyperpop, pop
- 2. Billie Eilish — *Happier Than Ever*; score 0.852, embedding 0.852, bridge tags: alt-pop, peter, pop
- 3. aespa — *MY WORLD*; score 0.852, embedding 0.852, bridge tags: dance-pop, electropop
- 4. ARTMS — *<Dall>*; score 0.846, embedding 0.846, bridge tags: pop, rnb
- 5. 이달의 소녀 — *[+ +]*; score 0.844, embedding 0.844, bridge tags: dance-pop, electropop
- 6. Robyn — *Sexistential*; score 0.839, embedding 0.839, bridge tags: dance-pop, electropop, pop
- 7. underscores — *Wallsocket*; score 0.839, embedding 0.839, bridge tags: electronic, electropop, pop
- 8. That Kid — *Superstar*; score 0.839, embedding 0.839, bridge tags: bubblegum bass, electronic, electropop, hyperpop, pop
- 9. Mitski — *Puberty 2*; score 0.837, embedding 0.837, bridge tags: art pop, singer-songwriter

### embedding_plus_tags

- 1. Charli xcx — *how i’m feeling now*; score 0.877, embedding 0.857, bridge tags: bubblegum bass, electronic, electropop, hyperpop, pop
- 2. Billie Eilish — *Happier Than Ever*; score 0.865, embedding 0.852, bridge tags: alt-pop, peter, pop
- 3. Charli xcx — *Pop 2*; score 0.859, embedding 0.826, bridge tags: bubblegum bass, electronic, electropop, hyperpop, pop
- 4. Charli xcx — *Charli*; score 0.853, embedding 0.811, bridge tags: bubblegum bass, electronic, electropop, hyperpop, pop
- 5. That Kid — *Superstar*; score 0.853, embedding 0.839, bridge tags: bubblegum bass, electronic, electropop, hyperpop, pop
- 6. underscores — *Wallsocket*; score 0.852, embedding 0.839, bridge tags: electronic, electropop, pop
- 7. Robyn — *Sexistential*; score 0.849, embedding 0.839, bridge tags: dance-pop, electropop, pop
- 8. Dorian Electra — *Flamboyant*; score 0.846, embedding 0.829, bridge tags: bubblegum bass, dance-pop, electronic, electropop, hyperpop
- 9. Ninajirachi — *I Love My Computer*; score 0.843, embedding 0.822, bridge tags: bubblegum bass, edm, electro house, electronic, electropop, pop

### full_ranking

- 1. Charli xcx — *how i’m feeling now* / Safe; score 0.877, embedding 0.857, bridge tags: bubblegum bass, electronic, electropop, hyperpop, pop
- 2. Billie Eilish — *Happier Than Ever* / Safe; score 0.865, embedding 0.852, bridge tags: alt-pop, peter, pop
- 3. Charli xcx — *Pop 2* / Safe; score 0.859, embedding 0.826, bridge tags: bubblegum bass, electronic, electropop, hyperpop, pop
- 1. underscores — *Wallsocket* / Explore; score 0.873, embedding 0.839, bridge tags: electronic, electropop, pop
- 2. underscores — *fishmonger* / Explore; score 0.859, embedding 0.828, bridge tags: electronic, hyperpop, pop
- 3. A. G. Cook — *Britpop* / Explore; score 0.858, embedding 0.816, bridge tags: bubblegum bass, electronic, pop
- 1. Yellow Magic Orchestra — *Solid State Survivor* / Wildcard; score 0.669, embedding 0.676, bridge tags: electronic, electropop, pop
- 2. Taylor Swift — *THE TORTURED POETS DEPARTMENT* / Wildcard; score 0.662, embedding 0.690, bridge tags: aoty, pop, singer-songwriter
- 3. Beyoncé — *BEYONCÉ* / Wildcard; score 0.647, embedding 0.709, bridge tags: pop, rnb, soul

## Reading this report

These are ranking diagnostics, not evidence of user preference or recommendation accuracy. Review the listed albums manually and use Taste Battle feedback for future exploratory analysis.

When reviewing results, check for wrong album matches, seed albums reappearing, repetitive lead artists, tier mismatches, and weak or forced tag bridges. More pairwise feedback is needed before drawing conclusions about user preference.
