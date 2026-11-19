# Presentation Plan — Multi-Vector ANN Search

**Paper:** *Breaking the Single-Reference-Vector Barrier in Approximate Nearest Neighbor Search*
Jiadong Xie, Jeffrey Liang, Siyi Teng, Jeffrey Xu Yu, Yingfan Liu — WWW '26

**Format:** 15 minutes. Target **13:30 talking + 1:30 slack / questions**.
**Audience:** data-engineering students who know basic ANN but not this paper.
**Narrative:** one query vector is not enough → naive fix is broken → reformulate as a
single score → reuse the existing graph → seed it properly → 10× faster.

---

## 1. Run sheet

| # | Time | Slide | Message | Visual |
|---|------|-------|---------|--------|
| 1 | 0:00–0:30 | Title | Multi-vector search: one query vector is not enough | decorative all/any motif |
| 2 | 0:30–2:00 | Why multi-vector? | 3 real stories: fair flat, logo dedup, diverse recs | 3 cards |
| 3 | 2:00–3:30 | Background | ANN = grow a ball; graph search = walk downhill | 2-panel diagram |
| 4 | 3:30–5:30 | The two new queries | **all-𝑘** = intersection, **any-𝑘** = union | 2-panel geometry |
| 5 | 5:30–7:00 | Worked example | A is nobody's nearest neighbour, yet it is the all-1 NN | 4-step build + table |
| 6 | 7:00–8:30 | Why the obvious fix fails | 𝑚 searches + merge is wrong or wasteful; 𝑘′ is unknowable | verdict table |
| 7 | 8:30–10:30 | **Core idea** | score = balloon capture time: max (all) / min (any) | animated GIF |
| 8 | 10:30–11:15 | Why graphs still work | score is 1-Lipschitz → reuse HNSW unchanged | cone diagram |
| 9 | 11:15–12:15 | Wrinkle 1 (all-𝑘) | start at the MEB centre, not the centroid | MEB vs centroid |
| 10 | 12:15–13:00 | Wrinkle 2 (any-𝑘) | answers can be disconnected → seed every region | disconnected demo |
| 11 | 13:00–14:15 | Results | ~10× QPS at equal recall, 5 datasets | QPS–recall + speedup |
| 12 | 14:15–15:00 | Conclusion + Q&A | reformulate, prove, seed; limits | takeaways |

> Slides 5 and 6 were split from the original single "worked example" slide:
> the geometry and the baseline failure need separate beats to land in 15 minutes.

---

## 2. Slide-by-slide content

### 1 · Title (30 s)
- Title, authors, venue, presenter placeholder.
- Spoken thesis: *"Existing vector databases accept one reference vector. This paper makes
  all-of and any-of multi-vector queries first-class — and 10× faster — by reformulating
  them as a single distance score."*

### 2 · Why multi-vector? (90 s)
Three cards, one line each:
1. **Fair apartment** — two offices, one flat; minimise the *worst* commute. → all-of.
2. **Logo dedup** — five rotated/cropped copies; find the original near *all* of them. → all-of.
3. **Diverse recommendations** — "more like *any* of my last three clicks". → any-of.

Takeaway bar: production systems squash these into one vector (concatenate/average).
Averaging "jazz" and "death metal" gives a meaningless midpoint.

### 3 · Background (90 s)
- 𝑘-NN: grow a ball around 𝑞 until it holds 𝑘 points; score = distance.
- Graph ANN: start at a node, step to a neighbour with a smaller distance.
- **Why it works:** nearby points have similar distances → the score landscape has no cliffs.
  (Plant this; it is reused verbatim on slide 8.)

### 4 · The two new queries (120 s)
| | all-𝑘 | any-𝑘 |
|---|---|---|
| Meaning | similar to **every** 𝑞ᵢ | similar to **at least one** 𝑞ᵢ |
| Geometry | **intersection** of 𝑚 balls | **union** of 𝑚 balls |
| Rank of 𝑢 | maxᵢ δ(𝑞ᵢ,𝑢) | minᵢ δ(𝑞ᵢ,𝑢) |

Say explicitly: **𝑚 = number of query vectors, 𝑘 = number of results.**
20-second aside: Recipe dataset — daikon+pork (all) vs burger+coffee (any).

### 5 · Worked example (90 s)
`q1=(0,0)`, `q2=(10,0)`, `A=(5,0)`, `B=(0,1)`, `C=(10,1)`, `D=(5,5)`.

| point | →q1 | →q2 | max | min |
|---|---|---|---|---|
| A | 5 | 5 | **5.00** | 5.00 |
| D | 7.07 | 7.07 | **7.07** | 7.07 |
| B | 1 | 10.05 | 10.05 | **1.00** |
| C | 10.05 | 1 | 10.05 | **1.00** |

- all-2 = {A, D}; any-2 = {B, C}.
- **A is nobody's nearest neighbour** (B is q1's, C is q2's) yet A is the all-1 NN.
  It lives in the valley between the queries where no single-vector search goes.
- Same point A is #1 for all and #3 for any → genuinely different query, not a tweak.

### 6 · Why the obvious fix fails (90 s)
Baseline = run 𝑘′-ANN per query vector, merge, rank the pool.
- 𝑘′=2 for all-2 → pool {A,B,C} → **wrong**; D is 3rd for *both* queries.
- 𝑘′=3 → correct, but 50% more work per query.
- any-2 with 𝑘′=1 → correct, and *less* work than 𝑘′=2.
→ optimal 𝑘′ is unknown in advance and varies by semantics **and** by query vector.
Milvus doubles 𝑘′ until stable: correct, but repeated searches. This is the inefficiency
the paper removes.

### 7 · Core idea (120 s) — the best slide
Animated balloons, both panels inflating in sync:
- all-𝑘: a point is captured by the **last** balloon → **max** distance.
- any-𝑘: captured by the **first** balloon → **min** distance.
→ both problems become ordinary top-𝑘 ranking. No 𝑘′ anywhere.
The same point can be #1 for all and #3 for any.

### 8 · Why graphs still work (45 s)
|r̂(u) − r̂(v)| ≤ δ(u,v) — close points have close scores (1-Lipschitz).
So the downhill walk still converges, and **the existing HNSW index is reused unchanged**;
only the distance function changes. Same time/space complexity as beam search. No proof.

### 9 · Wrinkle 1 — where to start for all-𝑘 (60 s)
- Best compromise = minimise the **max** distance = centre of the **minimum enclosing ball**.
- 1 office at (0,0), 9 at (4,4): centroid (3.6,3.6) → worst commute **5.09**;
  MEB centre (2,2) → **2.83**. Minimise the max ≠ average.
- Pipeline: MEB centre → ordinary 1-NN search → seed radius search.
  Cost O(m²d + m^3.5), once per query.
- Credibility: the authors show the centroid baseline is *worse* than doing nothing clever.

### 10 · Wrinkle 2 — disconnected any-𝑘 (45 s)
q1=(0,0), q2=(100,0), A near q1, B near q2. any-2 = {A,B}, 100 apart.
Walking from A toward B makes the min-distance **increase** (50 at the midpoint) →
no downhill path, so the walk never leaves A.
Fix: seed the queue with the 1-NN of **each** 𝑞ᵢ. Same search, better start.

### 11 · Results (75 s)
- Up to **~10× QPS at equal recall**, consistent over 5 datasets (1M–2M vectors, 128–2048 dims).
- RadiusSearch+ wins most at **high recall**: the seeding cost is fixed, so it amortises.
- Honest caveat: plain RadiusSearch can *lose* to Milvus on any-𝑘 — direct evidence for the
  disconnected-region argument, and the reason for the two-stage version.

### 12 · Conclusion (45 s)
1. **Reformulate** — all/any-𝑘 = top-𝑘 by max/min distance; kills the 𝑘′ knob.
2. **Prove** — the score is Lipschitz, so existing graph indexes work as-is.
3. **Seed** — MEB centre (all), one seed per query (any); that is where the speed comes from.
Limits: RadiusSearch+ is graph-specific; guarantees need LMG (O(n²d) build); recall is empirical.

---

## 3. Assets to produce

| Asset | Used on | Notes |
|---|---|---|
| `figures/fig_title.png` | 1 | decorative all/any motif |
| `figures/fig_background.png` | 3 | ball growth + greedy graph walk |
| `figures/fig_all_any.png` | 4 | intersection vs union, shaded |
| `figures/fig_example_build.png` | 5 | 4-step build of the 2D example |
| `figures/fig_balloon.gif` | 7 | **highest value asset** — synced inflation |
| `figures/fig_balloon_frames.png` | 7 backup | static 2×3 strip if GIF cannot play |
| `figures/fig_lipschitz.png` | 8 | slope-±1 cone |
| `figures/fig_meb.png` | 9 | centroid vs MEB + worst-commute bars |
| `figures/fig_disconnected.png` | 10 | two clusters + score hump |
| `figures/fig_qps_recall.png` | 11 | schematic, redrawn from paper trends |
| `figures/fig_qps_bar.png` | 11 | schematic speedup |

All charts are **redrawn schematics** from the paper's reported trends, not digitised data;
this is stated in the slide footnotes.

---

## 4. Timing contingencies

- **Running long (−2 min):** drop the Recipe aside (4), the centroid counterexample (9),
  and one of the two charts (11).
- **Running short (+1 min):** add the "vary 𝑚 from 2 to 20" scaling result, or the
  cosine / inner-product extension.
- Rehearse slides 5–7 to the second; the rest can flex.

## 5. Likely questions

1. **Why not average/concatenate the queries?** Averaging is only right for balanced query
   distributions; for any-𝑘 it lands in empty space. Concatenation changes the metric and
   needs a new index.
2. **Is recall guaranteed?** No. Exact guarantees need LMG with O(n²d) build; stated future work.
3. **New index needed?** No — same HNSW, only the distance function changes.
4. **Isn't the MEB expensive?** O(m²d + m^3.5) once per query; >50% of runtime only at small
   beam widths (low recall). At useful recall it amortises.
5. **Scaling in 𝑚?** Distance evaluation is O(md); runtime grows sublinearly in 𝑚 up to 𝑚=20,
   because seeding is fixed and the graph walk dominates.

---

## 6. Deliverables & status

- [x] Plan catalogued in this file
- [ ] Figures generated (`figures/make_figures.py` → PNG/GIF)
- [ ] Slide deck (`build_deck.py` → `MultiVector_ANN_Slides.pptx`, 16:9)
- [ ] Speaker notes (`SPEAKER_NOTES.md`, generated from the deck notes)
- [ ] PDF preview (`MultiVector_ANN_Slides.pdf`) for checking layout
