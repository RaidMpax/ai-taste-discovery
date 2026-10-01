# V2 Final Editorial Decisions

Status: resolved on 2026-09-28. The product owner delegated the remaining
choices, so every recommended option A is accepted unless an earlier explicit
album-level decision overrides it.

## Resolution

- Apply option A to P01-P05, H01-H08, I01-I08, R01-R14, G01-G07, and C01-C13.
- Earlier explicit keep/remove decisions in batches 1A-1C take precedence.
- Do not request further taste polling during album-list construction.
- Ask the product owner only when artist identity or MusicBrainz matching is
  genuinely ambiguous.

This document contains only choices where personal taste or product positioning
materially changes the catalogue. Straightforward album selections are omitted
and will follow the existing rules automatically.

The product owner may reply with:

> Accept all defaults except H03 = B, R01 = C, C04 = A.

## A. Catalogue policy

### P01 - Final catalogue size

- **A (recommended):** treat 500 as a centre point and accept roughly 480-530.
- B: finish at exactly 500, even if good borderline projects must be removed.
- C: allow up to roughly 600 for broader seed coverage.

### P02 - Seed-only albums

- **A (recommended):** seed-only albums count inside the final catalogue total.
- B: maintain an additional seed-only extension outside the 500 recommendation
  catalogue.

### P03 - Broad fan-discography coverage

- **A (recommended):** Taylor Swift receives near-complete era coverage; other
  major artists remain curated unless a later test demonstrates missing demand.
- B: also give Beyoncé, Lana Del Rey, Lady Gaga, Ariana Grande, Rihanna, and
  similar fan-driven artists near-complete studio-album coverage.
- C: all artists remain capped to selected representative albums.

### P04 - Re-recordings and equivalent album eras

- **A (recommended):** store one canonical representative per album era and
  map alternate names later; do not ingest both an original and a Taylor's
  Version as independent taste items.
- B: ingest original and re-recorded versions separately.

### P05 - Controversy

- **A (recommended):** controversy does not automatically remove an album, but
  inclusion still requires musical and product value.
- B: exclude artists with major public controversy from the Beta catalogue.

## B. Hyperpop, internet pop, and new electronic pop

### H01 - Frost Children depth

- **A (recommended):** keep `SPEED RUN` and `SISTER`; omit `Hearth Room`.
- B: keep all three because `Hearth Room` represents a softer identity.
- C: keep only `SISTER` as the current entry point.

### H02 - Slayyyter depth

- **A (recommended):** keep `STARFUCKER` and `WOR$T GIRL IN AMERICA`; omit
  `Troubled Paradise`.
- B: keep all three studio albums.
- C: keep only `WOR$T GIRL IN AMERICA`.

### H03 - Kim Petras

- **A (recommended):** keep `Clarity` and `TURN OFF THE LIGHT`; omit
  `Feed the Beast`.
- B: keep all three.
- C: exclude Kim Petras entirely.

### H04 - Jane Remover

- **A (recommended):** keep `Frailty`, `Census Designated`, and
  `Revengeseekerz` because they represent three sharply different sounds.
- B: keep `Frailty` and `Revengeseekerz` only.
- C: keep `Revengeseekerz` only.

### H05 - Rebecca Black

- **A (recommended):** keep `Let Her Burn` and `SALVATION`.
- B: keep only `SALVATION`.
- C: exclude her from the album catalogue.

### H06 - SOPHIE's posthumous album

- **A (recommended):** keep `OIL OF EVERY PEARL'S UN-INSIDES`, but exclude the
  posthumous 2024 album `SOPHIE` from V2.
- B: keep both.

### H07 - Dorian Electra

- **A (recommended):** keep `Flamboyant` and `My Agenda`; omit `Fanfare`.
- B: keep all three.
- C: keep only `Flamboyant`.

### H08 - A. G. Cook and 100 gecs depth

- **A (recommended):** keep `Apple` and `Britpop` for A. G. Cook, plus both
  `1000 gecs` and `10,000 gecs` for 100 gecs.
- B: keep only one project per artist.

## C. Indie and alternative depth

### I01 - Arctic Monkeys

- **A (recommended):** keep `Whatever People Say I Am, That's What I'm Not`,
  `AM`, and `Tranquility Base Hotel & Casino`.
- B: replace `Tranquility Base` with `Favourite Worst Nightmare`.
- C: keep only the debut and `AM`.

### I02 - Beach House

- **A (recommended):** keep `Teen Dream`, `Bloom`, and `Depression Cherry`.
- B: also keep `Once Twice Melody`.
- C: keep only `Teen Dream` and `Depression Cherry`.

### I03 - Tame Impala

- **A (recommended):** keep `Lonerism` and `Currents`; omit `The Slow Rush`
  and 2025's `Deadbeat`.
- B: also keep `The Slow Rush`.
- C: keep all four.

### I04 - The 1975

- **A (recommended):** keep the self-titled album, `I like it when you sleep...`,
  `A Brief Inquiry into Online Relationships`, and `Being Funny in a Foreign
  Language`.
- B: keep only `I like it when you sleep...` and `A Brief Inquiry...`.
- C: add `Notes on a Conditional Form` as well.

### I05 - Paramore

- **A (recommended):** keep `Riot!`, `After Laughter`, and `This Is Why`.
- B: keep only `After Laughter` and `This Is Why`.
- C: add the self-titled album.

### I06 - Mitski fan coverage

- **A (recommended):** keep five distinct eras: `Bury Me at Makeout Creek`,
  `Puberty 2`, `Be the Cowboy`, `Laurel Hell`, and `The Land Is Inhospitable
  and So Are We`.
- B: reduce to `Puberty 2`, `Be the Cowboy`, and `The Land Is Inhospitable...`.
- C: keep her complete studio catalogue.

### I07 - Geese

- **A (recommended):** keep both `3D Country` and 2025's `Getting Killed`.
- B: keep only `Getting Killed`.

### I08 - The National

- **A (recommended):** keep `Boxer`, `High Violet`, and `Sleep Well Beast`.
- B: keep only `Boxer` and `High Violet`.
- C: add `Trouble Will Find Me`.

## D. Rap and R&B

### R01 - Kanye West

- **A (recommended):** include `The College Dropout`, `808s & Heartbreak`,
  `My Beautiful Dark Twisted Fantasy`, and `Yeezus`; do not include recent
  collaboration albums.
- B: include only `808s`, `MBDTF`, and `Yeezus`.
- C: exclude him entirely.

### R02 - Drake

- **A (recommended):** include `Take Care`, `Nothing Was the Same`, and
  `If You're Reading This It's Too Late`; omit later catalogue bloat.
- B: include `Take Care` only.
- C: exclude him entirely.

### R03 - Nicki Minaj

- **A (recommended):** keep `Pink Friday`, `The Pinkprint`, and
  `Pink Friday 2`.
- B: keep only `Pink Friday` and `The Pinkprint`.
- C: add `Roman Reloaded` as a seed-oriented pop-rap era.

### R04 - Kendrick Lamar

- **A (recommended):** keep `good kid, m.A.A.d city`, `To Pimp a Butterfly`,
  `DAMN.`, `Mr. Morale & the Big Steppers`, and `GNX`.
- B: omit `Mr. Morale`.
- C: reduce to the first three only.

### R05 - Playboi Carti

- **A (recommended):** keep `Die Lit`, `Whole Lotta Red`, and `MUSIC`.
- B: keep only `Die Lit` and `Whole Lotta Red`.
- C: keep only `MUSIC` for current popularity.

### R06 - Future

- **A (recommended):** keep `DS2`, `HNDRXX`, and `I NEVER LIKED YOU`.
- B: keep only `DS2` and `HNDRXX`.
- C: add the collaborative mixtape `Monster` as a format exception.

### R07 - Travis Scott

- **A (recommended):** keep `Rodeo`, `ASTROWORLD`, and `UTOPIA`.
- B: keep only `Rodeo` and `ASTROWORLD`.

### R08 - Tyler, the Creator

- **A (recommended):** keep `Flower Boy`, `IGOR`, `CALL ME IF YOU GET LOST`,
  and `CHROMAKOPIA`.
- B: keep `Flower Boy`, `IGOR`, and `CHROMAKOPIA`.
- C: add `Wolf` for early fan coverage.

### R09 - Cardi B

- **A (recommended):** keep both `Invasion of Privacy` and 2025's
  `AM I THE DRAMA?`.
- B: keep only `Invasion of Privacy`.

### R10 - Doja Cat

- **A (recommended):** keep `Hot Pink` and `Planet Her`; omit `Scarlet`.
- B: keep all three.
- C: keep `Planet Her` only.

### R11 - J. Cole

- **A (recommended):** keep `2014 Forest Hills Drive` only.
- B: also keep `4 Your Eyez Only`.
- C: exclude him to prioritise more distinctive rap catalogues.

### R12 - Death Grips

- **A (recommended):** keep `The Money Store` and `Bottomless Pit`.
- B: keep `The Money Store` only.
- C: exclude them as too abrasive for the Beta audience.

### R13 - Mac Miller and posthumous work

- **A (recommended):** keep `Watching Movies with the Sound Off`, `Swimming`,
  and `Circles`; do not add later archival releases.
- B: keep only `Swimming` and `Circles`.

### R14 - Rihanna depth

- **A (recommended):** keep `Good Girl Gone Bad`, `Rated R`, `Loud`, and
  `ANTI` for four clearly different eras.
- B: keep only `Rated R` and `ANTI`.
- C: give Rihanna near-complete studio coverage under policy P03.

## E. Latin, Spanish-language, Asian, and global balance

### G01 - Rosalía

- **A (recommended):** keep all four studio albums: `Los Ángeles`,
  `El Mal Querer`, `MOTOMAMI`, and 2025's `LUX`.
- B: omit `Los Ángeles` and keep the later three.

### G02 - Bad Bunny

- **A (recommended):** keep `X 100PRE`, `YHLQMDLG`, `Un Verano Sin Ti`, and
  `DeBÍ TiRAR MáS FOToS`.
- B: keep the latter three.
- C: keep only `Un Verano Sin Ti` and `DeBÍ TiRAR MáS FOToS`.

### G03 - Male Spanish-language artists

- **A (recommended):** retain selective male entries such as C. Tangana,
  Rauw Alejandro, Tainy, Feid, and CA7RIEL & Paco Amoroso because the earlier
  male-artist exclusion applied only to the unwanted Hong Kong/Taiwan lane.
- B: reduce this group to C. Tangana, Tainy, and CA7RIEL & Paco Amoroso.
- C: remove most male Spanish-language performers.

### G04 - Emerging Latin projects and EPs

- **A (recommended):** allow one core project each from AKRIILA, Isabella
  Lovestory, Judeline, Six Sex, Villano Antillano, and Young Miko even when the
  strongest format is an EP or mixtape.
- B: require a full studio album and drop artists who do not have one.

### G05 - Chinese-language female canon

- **A (recommended):** keep approximately three albums for 王菲, two for 梅艷芳,
  and two for 林憶蓮.
- B: keep only two for 王菲 and one each for 梅艷芳 and 林憶蓮.
- C: expand 王菲 to four albums.

### G06 - Japanese catalogue depth

- **A (recommended):** allocate three albums each to 宇多田ヒカル and 椎名林檎,
  two each to Fishmans, Nujabes, 青葉市子, Lamp, and Perfume, and one to Haru
  Nemuri.
- B: reduce every Japanese artist to one or two projects.
- C: expand this branch beyond the current artist slate.

### G07 - African pop coverage

- **A (recommended):** keep two Burna Boy albums and one Rema album.
- B: keep one album each.
- C: add more African artists before finalising the dataset.

## F. Canon and modern-pop canon

### C01 - Pink Floyd

- **A (recommended):** keep `The Dark Side of the Moon` and
  `Wish You Were Here` only.
- B: replace `Wish You Were Here` with `The Wall`.
- C: keep all three.

### C02 - Radiohead

- **A (recommended):** keep `OK Computer`, `Kid A`, `In Rainbows`, and
  `A Moon Shaped Pool`.
- B: keep only the first three.
- C: add `The Bends`.

### C03 - Björk

- **A (recommended):** keep `Post`, `Homogenic`, `Vespertine`, and `Vulnicura`.
- B: add `Debut`.
- C: reduce to `Homogenic` and `Vespertine`.

### C04 - Female singer-songwriter canon depth

- **A (recommended):** allocate three projects each to Kate Bush, PJ Harvey,
  Fiona Apple, and Joni Mitchell.
- B: allocate two each.
- C: allow up to four where eras are strongly distinct.

### C05 - David Bowie

- **A (recommended):** keep `The Rise and Fall of Ziggy Stardust...`, `Low`,
  `Heroes`, and `Blackstar`.
- B: omit `Heroes`.
- C: reduce to `Ziggy Stardust` and `Low`.

### C06 - Prince, Madonna, and Janet Jackson

- **A (recommended):** allocate three albums to each.
- B: allocate two to each.
- C: give Madonna four and the others three.

### C07 - Older alternative-rock depth

- **A (recommended):** generally keep two albums each for The Cure, Cocteau
  Twins, Sonic Youth, Pixies, New Order, and The Strokes; one each for Joy
  Division and The Velvet Underground.
- B: keep only one album per artist except The Cure and The Strokes.
- C: expand the older canon further.

### C08 - Britney Spears

- **A (recommended):** keep `Oops!... I Did It Again`, `In the Zone`, and
  `Blackout`.
- B: keep only `In the Zone` and `Blackout`.
- C: add the self-titled `Britney`.

### C09 - Carly Rae Jepsen

- **A (recommended):** keep `E•MO•TION`, `Dedicated`, and
  `The Loneliest Time`.
- B: keep `E•MO•TION` and `The Loneliest Time` only.
- C: add `The Loveliest Time` as a distinct companion record.

### C10 - Kesha

- **A (recommended):** keep `Animal`, `Rainbow`, `Gag Order`, and 2025's
  `. (Period)`.
- B: keep `Animal`, `Rainbow`, and `. (Period)`.
- C: keep only `Animal` and `Rainbow`.

### C11 - Robyn

- **A (recommended):** keep `Body Talk`, `Honey`, and 2026's `Sexistential`.
- B: keep `Body Talk` and `Sexistential` only.
- C: keep `Body Talk` only.

### C12 - St. Vincent

- **A (recommended):** keep `Actor`, `Strange Mercy`, `MASSEDUCTION`, and
  `All Born Screaming`.
- B: keep `Strange Mercy`, `MASSEDUCTION`, and `All Born Screaming`.
- C: reduce to `Strange Mercy` and `MASSEDUCTION`.

### C13 - Remaining modern-pop canon

- **A (recommended):** keep two each for Avril Lavigne, Christina Aguilera,
  Imogen Heap, Lily Allen, and MARINA; one each for Gwen Stefani, Nelly Furtado,
  and Sky Ferreira.
- B: reduce all of these artists to one album each.
- C: allow three each for Avril Lavigne and MARINA.

## What happens after this sheet

After the product owner answers this document once, the remaining work will not
pause branch by branch. The next deliverable will be:

1. complete album-level manifests for all remaining artists;
2. a global count and balance audit;
3. a short final exception list only for incorrect or ambiguous MusicBrainz
   matches, not further taste polling;
4. final product-owner approval before ingestion.
