# Speaker notes — Multi-Vector ANN Search

Generated from the deck's notes pane. Timing in brackets.

## 01 · Title

[0:00–0:30]  Opening.

Good morning. Vector databases today take one reference vector per query. This paper makes the query a *set* of vectors — 'similar to all of these' or 'similar to any of these' — and makes it about ten times faster than the obvious approach.

In the next 15 minutes: why anyone wants that, the problem with the obvious fix, the one idea that solves it, and the results. The whole paper is in six words: max for all, min for any. I'll unpack that.

## 02 · Why would a query need more than one vector?

[0:30–2:00]  Three stories, 30 seconds each.

1. Two people, two offices. You want a flat that is a fair compromise for both — formally, the flat with the best *worst* commute. That's 'similar to all of the reference points'.

2. Logo deduplication. You have five rotated or cropped copies of a logo and want the original. The original should be near *all* of them.

3. Recommendations. 'More like any of my last three clicks' — deliberately broad, to avoid a filter bubble.

Now the punchline: every production system forces you to squash those vectors into one — concatenate or average. Averaging 'jazz' and 'death metal' gives a vector in the meaningless middle. That is the barrier in the title.

## 03 · Two things you already know — and one to remember

[2:00–3:30]  Keep this short; it is scaffolding.

Ordinary k-NN: put a ball around the query, grow it until it holds k points. The score of a point is just its distance.

Graph indexes like HNSW: start at some node and repeatedly step to a neighbour that is closer to the query. That works because nearby points have similar distances — the score landscape has no cliffs. Remember that sentence; it comes back in five minutes and it is the reason this whole approach is legal.

## 04 · Two new query types: all-k and any-k

[3:30–5:30]  The definition slide — go slowly.

Give the query m vectors. Two natural semantics.

ALL-k: similar to every q_i. Geometrically, the intersection of m balls. Ranking a database vector: its maximum distance to the query set.

ANY-k: similar to at least one q_i. The union of the balls. Ranking: the minimum distance.

Emphasise: m is the number of query vectors, k is the number of results. Students mix these up.

Concrete example from the paper's Recipe dataset: find a recipe with both daikon and pork (all), versus a recipe like a burger or a coffee (any). The all result genuinely combines the inputs; the any result resembles one of them.

## 05 · A four-point example you can do in your head

[5:30–7:00]  Build the picture step by step.

Two query points, q1 at the origin and q2 at (10,0). Four database points. A sits exactly between them. D is the compromise above. B and C are each close to one query.

Compute the two columns: max and min distance. Rank by max: A (5), D (7.07), then B and C (10.05). So all-2 is {A, D}. Rank by min: B and C at 1, then A, then D. So any-2 is {B, C}.

Now the key observation. A is nobody's nearest neighbour — B is q1's nearest, C is q2's. Yet A is the all-1 NN. It lives in the valley between the queries, where no single-vector search ever goes. That is the whole difficulty in one picture.

## 06 · Why the obvious fix fails

[7:00–8:30]  The baseline everyone would write first.

Run a k'-ANN search per query vector, merge the pools, rank the pool by max or min.

For all-2 with k'=2: q1 returns B and A, q2 returns C and A. The pool is {A,B,C} — wrong. D is third for *both* queries, so it never enters the pool. You needed k'=3.

With k'=3 it is correct, but you paid 50% more work per query. And for any-2, k'=1 already gives the right answer — less work than k'=2. So the optimal k' is unknown in advance, and it differs by semantics and by query vector.

Milvus patches this by doubling k' until the result set stops changing: correct, but repeated searches. That is exactly the inefficiency this paper removes.

## 07 · Score = the moment a point gets captured

[8:30–10:30]  This is the heart of the talk. Let the GIF play; talk over it.

Put a balloon on every query vector and inflate them all at exactly the same rate. A point's score is the moment it gets captured.

For all-k, the point must be inside every balloon, so it is captured by the LAST one — that is the maximum distance.

For any-k, the first balloon is enough — the minimum distance.

That is it. Both problems become ordinary top-k ranking with a different score. No k' anywhere. And notice that the same point can be first for all and third for any: these are genuinely different queries, not a cosmetic tweak.

If the animation does not play, use the three-frame strip on the backup slide.

## 08 · Why the graph still works: the score has no cliffs

[10:30–11:15]  Anticipate the objection before it is asked.

'Max and min are not distances — why should graph search still be valid?'

Because the score is 1-Lipschitz: if two points are close, their scores differ by at most their distance. Geometrically, the score can only move inside a cone of slope plus or minus one. That is exactly the 'no cliffs' property from the background slide.

Consequence one: the downhill walk still converges. Consequence two: neighbours of a good point are likely good too. So we reuse the existing HNSW index unchanged — only the distance function changes. Same time and space complexity as beam search.

## 09 · Where to start for all-k: minimise the MAX

[11:15–12:15]  First engineering wrinkle.

Graph search is a downhill walk, so the start matters. For all-k the naive start is the centroid of the queries. Wrong.

The best compromise minimises the *maximum* distance — that is the centre of the minimum enclosing ball, not the average. Concrete: one office at the origin and nine at (4,4). The centroid gives the lone office a 5.09 commute. The MEB centre gives 2.83. Minimise the max, don't average.

The authors also show the centroid baseline is worse than doing nothing clever, because it starts off the HNSW entry point and breaks the hierarchy.

Pipeline: compute the MEB centre, run an ordinary 1-NN search with it, hand that node to the radius search. Cost is O(m squared d plus m to the 3.5), once per query.

## 10 · Why any-k needs more than one starting point

[12:15–13:00]  Second wrinkle, specific to any-k.

The answer can live in disconnected regions. Two query points 100 apart, A near one and B near the other. any-2 is {A,B} — two points 100 apart.

Now start a walk at A and try to reach B. The min-distance gets *worse* as you move: 50 at the midpoint. There is no downhill path, so the walk never leaves A. A single descent can only find one region.

Fix: seed the queue with the 1-NN of every query vector, so the search starts inside all the relevant regions at once. Same search, better starting points. That is the two-stage method.

## 11 · Up to ~10× the QPS at the same recall

[13:00–14:15]  Do not read the axes; read the gap.

Five real datasets, one to two million vectors, 128 to 2048 dimensions. Every method uses the same HNSW index, EF 400, M 32, single thread, k=10, m=5 by default.

Up to about ten times the QPS at equal recall, consistently across datasets.

RadiusSearch+ wins most at high recall, because the seeding cost is fixed and amortises — at low recall it can be slightly worse than plain RadiusSearch.

Honest caveat the authors report: plain RadiusSearch can lose to Milvus on any-k. That is exactly the disconnected-region problem we just saw, and the reason the two-stage version exists.

Both charts are schematics of the reported trends; exact curves are in the paper.

## 12 · Change the distance, not the index

[14:15–15:00]  Close on the three ideas, then the limits.

One: reformulate. all/any-k is just top-k by max or min distance. That kills the k' knob and turns m searches into one.

Two: prove. The score is 1-Lipschitz, so existing graph indexes work as-is.

Three: seed. MEB centre for all-k, one seed per query for any-k. That is where the speed comes from.

Limits, stated honestly: the fast variant is specific to graph indexes; exact guarantees need an index with quadratic build cost; and recall is empirical, not guaranteed. But as a systems idea it is clean: change the distance, not the index.

Then: 'Max for all, min for any.' Questions.

## 13 · Questions

Happy to take questions.

Backup slides follow: the formal definitions and theorems, the dataset table, the time breakdown, and a complexity summary.

Short answers ready: averaging is only right for balanced queries; recall is not guaranteed; no new index is needed; the MEB is amortised at useful recall; runtime grows sublinearly in m.

## 14 · Formal definitions and the two key theorems

Use only if asked for rigor.

Theorem 4.1 says the all-radius is the maximum distance and the any-radius is the minimum — which is why ranking by radius is exactly ranking by capture time.

Theorem 4.2 is the Lipschitz bound that licenses graph search. The appendix also proves that the merge baseline is correct for any-k with exact per-vector search, and for all-k only when the final set is contained in every per-vector result set.

## 15 · Datasets and experimental setup

Five datasets spanning image, audio and text. All methods share one HNSW index, EF 400, M 32. k=10, m=5 by default, 1000 queries, single thread. Metrics are QPS and recall@k against exact ground truth.

## 16 · Time breakdown, scaling, and other metrics

Time breakdown: for all-k the MEB phase can exceed half the runtime at small beam widths, i.e. low recall. That is why RadiusSearch+ looks worse than plain RadiusSearch at low recall and better at high recall. For any-k the m one-NN searches are the fixed first-stage cost.

Scaling: runtime grows sublinearly in m up to 20.

Other metrics: with normalised embeddings, inner product, cosine and Euclidean are equivalent; for non-normalised inner product the authors adjust a small portion of HNSW edges. RadiusSearch+ stays consistent.

## 17 · Complexity summary

Per distance evaluation: m-d for the radius, d for the Euclidean seed. One-off MEB: m squared d plus m to the 3.5. The graph walk itself is the same as beam search. That is the whole cost story.
