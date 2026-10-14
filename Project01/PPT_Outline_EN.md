# esort Project Report — Slide Outline & Speaker Notes (English)

> **Occasion**: classroom presentation  **Length**: 10–15 minutes  **Deck**: 17 slides + 2 appendix
> **Audience**: instructor + classmates
> **Through-line**: *When the data does not fit in memory, how do we make "the sort is correct" and "the memory limit is honoured" hold at the same time?*
> Every design decision answers the same question: **"What breaks if I do it this way, and how do I prove it won't?"**

---

## Timing Overview

| Section | Slides | Seconds |
|---------|--------|---------|
| Opening | 1–3 | 115s |
| Architecture & five design ideas | 4–10 | 390s |
| Validation & performance | 11–15 | 275s |
| Wrap-up | 16–17 | 65s |
| **Total** | **17 slides** | **845s ≈ 14:05** |

> Per-slide timings assume a natural delivery pace of ~150 words/minute, pauses included.
> Speaking faster will land you around 12–13 minutes, still comfortably inside the window.

> **On-the-fly compression plan** (apply in order if you run long):
> ① Skip slide 16 "Limitations" (−40s) → ② On slide 14 keep only the memory-leak bug (−25s) → ③ Merge slide 5 into slide 4 in one sentence (−35s) → ④ Reduce slide 11 to a single sentence (−35s).
> The first three bring you to about **12:15**; all four give **11:40**.
> Rule of thumb for cutting live: **if you pass 9 minutes by the end of slide 10, drop slides 11 and 12** — those numbers are all in the written report anyway.

---

## 1. Title

**Time**: 30 s  **Visual**: project title, course, presenter, date

> Good morning. My project is **esort — an external sort with a hard memory ceiling**.
> It is a command-line tool written in C that sorts files far larger than the memory it is allowed to use: 1,413 lines, compiled with zero warnings. I'll cover the architecture, five design decisions worth talking about, and four bugs I actually found while verifying it.

**Key takeaway**: this is a memory-bounded external sort.

---

## 2. Motivation: why external sorting exists

**Time**: 45 s  **Visual**: memory vs. data size

> Let's start with why. Algorithms like `qsort()` carry one assumption: the entire dataset must fit in memory. In practice we routinely handle log files and transaction dumps measured in tens of gigabytes, so that assumption simply does not hold.
>
> External sorting solves this with **sort in memory, spill to disk, then merge**. The complexity splits in two: if memory holds M records out of N total, and we merge k runs at a time, internal sorting costs O(N/M × M log M), while the I/O cost is **O(N log_k N)**. The base of that logarithm is what matters — the larger k is, the fewer times we read and write temporary files.
>
> That single observation drives two of the main design decisions: **how large to make k**, and **how to pay for a large k in memory**.

**Key takeaway**: the bottleneck of external sort is I/O count, and I/O count is set by the merge fan-in k.

---

## 3. Goals and constraints

**Time**: 40 s  **Visual**: option table + hard constraints

> The specification required six command-line options: `-c` case-insensitive, `-m` memory limit, `-r` reverse, `-n` numeric, `-l` length-first, and `-o` output file.
>
> Beyond the features, there are five hard constraints:
>
> 1. **Memory must never exceed `-m`** — not approximately, strictly.
> 2. It must implement a **two-phase external sort**.
> 3. The number of runs may exceed the OS file-descriptor limit, so **multi-pass merging** is required.
> 4. **`-o` must not damage the input file**, which may be the same file.
> 5. Every resource must be released before exit.
>
> Each of the five design ideas later in this talk answers exactly one of these.

**Key takeaway**: the constraints drive the design.

---

## 4. System architecture

**Time**: 50 s  **Visual**: two-stage flow diagram with the memory budget split

> The architecture is the classic two-phase external merge sort.
>
> **Phase one** repeats three steps: read as much as fits into the in-memory pool, sort that batch with `qsort()`, and write the result out as one run file. **Phase two** merges every run into a single ordered stream using a **Min-Heap**. If there are more runs than we can keep open at once, we merge groups first and run another pass.
>
> Note the memory bar at the bottom of the diagram — that is the core of the whole program. The total budget is `-m`; we **subtract what phase two is guaranteed to need**, and only what remains goes to the phase-one pool. Why that order matters, I'll cover in slide 8.

**Key takeaway**: two phases, with the memory budget reserved for the merge phase up front.

---

## 5. The five design ideas at a glance

**Time**: 35 s  **Visual**: five numbered cards

> Before the details, here are the five ideas I want to highlight:
>
> 1. **One shared comparator** — internal sorting and external merging cannot disagree.
> 2. **An arena memory pool** — fixed-size blocks chained together, so pointers never dangle.
> 3. **Budget split and a derived fan-in** — makes `-m` a real ceiling.
> 4. **Min-Heap merging with root replacement** — one sift-down per line.
> 5. **Resource-safety details** — same-file output, temp naming, over-long lines.
>
> Each one maps to one of the five constraints I just listed.

**Key takeaway**: five ideas, five constraints.

---

## 6. Idea 1: one shared comparator

**Time**: 55 s  **Visual**: `cmp_strings()` code (L133)

> The first idea is to write the comparison logic **exactly once**.
>
> My program compares in two places: `qsort()` inside phase one, and the Min-Heap in phase two. The classic mistake is writing the comparison twice, so that **phase one sorts lexicographically while phase two merges numerically**. The result is silently wrong, and because the data volume is huge, the symptom looks like "it's mostly sorted" — which is very hard to notice.
>
> So both paths call the same `cmp_strings()`; only the outermost interface differs: `qsort()` receives a `char**` so it needs one extra dereference, while the heap receives a `HeapItem` and uses the pointer inside it. The decision order is identical: compare length under `-l`, then numeric value under `-n`, then fall back to dictionary order — chosen by `-c` — and finally negate under `-r`.
>
> One detail: for `-n` I compare with `<` and `>` rather than subtracting, because `atoi()` returns `int` and subtracting two large values overflows.

**Key takeaway**: one comparison function for both phases, which makes an inconsistent result structurally impossible.

---

## 7. Idea 2: the arena memory pool

**Time**: 75 s  **Visual**: block-chain diagram + `CHUNK_USED` code (L450)

> The second idea is the memory pool, and this is the part I think is most worth explaining.
>
> The obvious approach is one large `char` buffer plus a `char**` of pointers. The problem is growth: the only way to grow the pointer array is `realloc()`, which may move the whole block. That invalidates every pointer at once, and during the move both the old and new copies exist, so **peak memory doubles**.
>
> Instead I use **fixed 64 KB blocks chained together, never moved**. Once a block is full, the next one is allocated. So a line's pointer stays valid from the moment it is written until the batch is sorted, and peak memory is fully under my control — because I decide how large a block is.
>
> Top right is the budget check. `CHUNK_USED()` adds up the arena bytes actually allocated plus the pointer array capacity times `sizeof(char*)`. Why count the pointers? Because the specification says dynamically allocated arrays count toward the limit, and the array capacity grows as a power of two, so it gets expensive as the batch grows.

**Key takeaway**: fixed-size chained blocks — pointers never dangle, peak memory never doubles, and the budget counts the pointer array too.

---

## 8. Idea 3: splitting the budget and deriving k

**Time**: 70 s  **Visual**: `calc_fanin()` (L983) + a table of `-m` vs. k

> The third idea is **how to split the budget, and how to choose k**.
>
> First, the split. During merging, every run is open simultaneously, and each needs a read buffer and a line buffer. That memory must be **reserved before phase one even finishes** — otherwise we read the whole file and only then discover there is not enough left to merge.
>
> So I deduct the merge reserve first and give phase one whatever remains.
>
> Here is the subtle part: the common approach is to hard-code k at 512. But 512 runs, each with an 8 KB read buffer and a 4 KB line buffer, is about 6 MB by itself. If a user passes `-m 1`, that simply does not fit.
>
> So I **derive k from the memory budget** and cap it at 512. In practice `-m 100` yields k = 512, and `-m 1` drops to 31 automatically. Small-memory users get a working program instead of a crash — the tool degrades into multi-pass merging.

**Key takeaway**: reserve for the merge first, and derive k from `-m` rather than hard-coding it.

---

## 9. Idea 4: Min-Heap merging with root replacement

**Time**: 55 s  **Visual**: merge loop (L819)

> The fourth idea is inside the merge loop. The textbook version pops the root, writes it out, then pushes a new item back — pop needs a sift-down and push needs a sift-up, so two heap passes per line.
>
> But there is a property to exploit: **the element we take out and the element we put back always come from the same run**. So only one position in the entire heap changes. I can overwrite the root directly and do a single sift-down — semantically identical, minus one sift-up.
>
> Measured, this cuts comparator calls by **8 to 11 percent**, and runs about 3 to 4 percent faster. To be honest, that is less than the "nearly half" I originally expected: the sift-up after a push usually stops at the first level, because the new element is typically already larger than its parent. The real value is that the worst case drops from two passes to one, and the deeper the heap, the more it helps.

**Key takeaway**: root replacement halves the heap work per line.

---

## 10. Idea 5: resource-safety details

**Time**: 50 s  **Visual**: three case cards

> The fifth idea is a collection of small details, but each one silently corrupts results if you get it wrong.
>
> **First, the output file may be the input file.** Opening it for writing destroys data that has not been read yet. So I compare the path strings and then `stat()` the `st_dev` and `st_ino`; if it is the same file, I write to a temporary file first and overwrite the original only after everything completes.
>
> **Second, temp file names must not be invented by hand.** A shared `/tmp` has races, so `mkstemp()` lets the kernel guarantee uniqueness.
>
> **Third, input edge cases**: a final line with no newline, Windows `\r\n`, and lines longer than 4,096 bytes. The rule for long lines is truncate but still count them as one line — the line count must never drift, or the whole output is wrong.

**Key takeaway**: same-file output, safe temp naming, and over-long lines — all three corrupt results silently if mishandled.

---

## 11. Relationship to sort, and complexity

**Time**: 50 s  **Visual**: comparison table

> How does this relate to the system `sort`?
>
> **Similar**: GNU coreutils `sort` also performs external merge sorting, spilling to disk and merging in multiple passes when memory is insufficient — the same algorithm.
>
> **Different**: GNU sort uses memory opportunistically, whereas `-m` here is a **hard ceiling** the user specifies precisely. And when memory is tight, k shrinks automatically and the tool falls back to multi-pass merging, which makes the behaviour more predictable.
>
> **In practice**: on my 75 MB, 1.5-million-line test file, `-m 8` finishes in 1.06 s while `-m 100` takes 1.67 s. More memory is slower here. The reason is that a bigger in-memory batch hurts `qsort()` cache locality, and the final write is sequential I/O — so the time saved by writing fewer temp files does not pay for itself.

**Key takeaway**: same algorithm family as GNU sort, but a hard memory ceiling — and more memory is not always faster.

---

## 12. Performance measurements

**Time**: 40 s  **Visual**: measurement table

> These are the measurements, on 75 MB and 1.5 million lines with numeric sort.
>
> **Memory** is the table that best proves the budget is honoured: with `-m 100` peak RSS is 98.8 MB, with `-m 16` it is 12.1 MB, and with `-m 4` it is only 5.6 MB. Memory really is tracking `-m`. The extra 1.5 to 2 MB is the program image and libc overhead, not my buffers.
>
> **Speed**: `-m 4` takes 0.97 s, `-m 8` 1.06 s, `-m 100` 1.67 s — consistent with the I/O-bound analysis from the complexity slide.
>
> **Optimization**: the root-replacement change removes 8 to 11 percent of comparator calls and runs 3 to 4 percent faster.

**Key takeaway**: `-m` genuinely constrains memory, and this tool is I/O bound — more memory is not always better.

---

## 13. Debugging case study I: dropped lines and an inverted heap condition

**Time**: 70 s  **Visual**: symptom / diagnosis / fix for each bug

> Next I want to talk about the bugs I found during verification, because I think this says more about engineering practice than the successes do.
>
> **Bug one: dropped lines.** With `-m 1` forcing multiple runs, the output was shorter than the input — by exactly **one line per run**. When `chunk_alloc()` returned NULL I broke out of the read loop, but that line had *already been consumed* from the input file; it simply had not been placed in the pool, so I was discarding it. The fix was a `pending` buffer that holds that line and installs it as the first line of the next chunk.
>
> **Bug two: an inverted heap condition.** The symptom was output that looked "mostly sorted" but was not. The diagnosis was the interesting part: I was not sure whether the fault was in phase one or phase two, so I copied **all nine run files out and checked each one**. Every run was internally sorted, which proved the bug had to be in the merge layer. The cause was a sift-up exit condition written as `<= 0` when it should have been `>= 0`, so new elements never floated up.

**Key takeaway**: diagnose by bisecting first, then confirm with a tool.

---

## 14. Debugging case study II: what the tools caught

**Time**: 60 s  **Visual**: sanitiser output (redacted)

> These two were found by tooling, not by staring at the output.
>
> **Bug three: a memory leak.** Every run file allocated a 64 KB output buffer that was never freed. The program was functionally perfect and leaked only a little, which is exactly the kind of bug that is invisible by eye. ASAN reported 589,824 bytes in 9 objects — exactly nine runs times 64 KB.
>
> **Bug four: one I introduced myself while refactoring.** When optimising the heap I wrote a single function responsible for both "replace the root" and "remove the root", then called it twice in one iteration. The second call drove the heap size from zero to `SIZE_MAX` and ran a sift-down far out of bounds — ASAN caught it as a double free.
>
> The lesson for me was: **tests have to travel with the refactor.** After every change I re-ran the full differential suite, and that is what revealed that the previous version had broken too. Unit tests alone would not have caught it.

**Key takeaway**: leaks and out-of-bounds access are found by tools; always re-run the full suite after refactoring.

---

## 15. Testing methodology

**Time**: 55 s  **Visual**: test matrix + pass rate

> Finally, how I tested this.
>
> I did not use "it does not crash" as the pass criterion. I wrote a **Python reference implementation** that follows the comparison order in the specification directly, using `cmp_to_key`, and then compared the output of the C program **line by line**.
>
> The matrix is **16 flag combinations × 3 memory limits × 6 data profiles — 288 cases**. The profiles cover plain words, pure numbers, mixed text with spaces, 4,000-character lines, an empty file, and a single-line file. All 288 pass now.
>
> The real value of this approach is that it catches errors **only external sorting can produce**. The dropped-line bug, for instance, never happens if the file is small enough to fit in a single run. The single most effective criterion I used is that **`-m 1` and `-m 100` must produce byte-identical output.**

**Key takeaway**: 288 differential cases, and `-m 1` ≡ `-m 100` is the sharpest single check.

---

## 16. Limitations and possible improvements

**Time**: 40 s  **Visual**: bullet list

> A short critique. There are limitations I know about and chose not to address:
>
> 1. **No parallelism** — merging runs could be threaded, at the cost of locking complexity.
> 2. **No stdin input** — files only.
> 3. **Temp files survive SIGKILL or a crash** — `atexit()` or a signal handler would help, though SIGKILL itself cannot be caught.
> 4. **Truncating long lines is silent** — a warning would be better.
>
> These are not oversights; I evaluated them and prioritised correctness within the time available.

**Key takeaway**: knowing the limits, and why you traded them away, is part of the engineering.

---

## 17. Conclusion

**Time**: 25 s  **Visual**: three-word summary

> Three points to close on. **First, it keeps its promises** — `-m` means what it says, and the measured peak RSS proves it. **Second, it is correct** — both phases share one comparator, and the memory budget counts even the pointer array. **Third, it is verifiable** — 288 differential cases plus sanitizers caught bugs I did not anticipate at all.
>
> Thank you — I am happy to take questions.

**Key takeaway**: keeps its promises, correct, verifiable.

---

## Appendix A1: Constants and option cross-reference

**Time**: reference only (not presented)  **Visual**: two tables

> These two pages are reference material; they stay on screen at the end for reference.
> The left table lists the program's constants and what each one means. The right table maps each of the six options to the function that implements it and the line number. If anyone wants to trace where a parameter is handled, this is the fastest way to point at it.

**Key takeaway**: every option can be located in under a minute.

| Constant | Value | Meaning |
|---|---|---|
| `MAX_LINE_LENGTH` | 4096 | maximum line length (from spec) |
| `DEFAULT_MEM_MB` | 100 | default for `-m` |
| `MAX_MERGE_FANIN` | 512 | max merge fan-in (FOPEN_MAX bound) |
| `ARENA_BLOCK_SIZE` | 64 KB | arena block size |
| `IO_BUF_SIZE` | 64 KB | read / write buffer |
| `RUN_READER_BUF_SIZE` | 8 KB | per-run read buffer |
| `MIN_CHUNK_BUDGET` | 4096 + 256×8 | guarantees one line + 256 ptrs |

| Option | Function | Line |
|---|---|---|
| `-c` | `strcasecmp()` | L161 |
| `-n` | `atoi()` | L151 |
| `-l` | `strlen()` | L139 |
| `-r` | negate result | L167 |
| `-m` | `atoi()` → bytes | L960 |
| `-o` | `fopen()` / `is_same_file()` | L1160 / L882 |

---

## Appendix A2: Q&A preparation

**Time**: reference only (flip to it during questions)  **Visual**: Q&A table

> This is a prepared question-and-answer sheet, kept on screen once the talk ends.
> These seven questions are the ones I expect from the instructor or my classmates. The second one — why 512 — is worth calling out, because that number can simply be changed in the constant definition.

**Key takeaway**: the major design decisions are tunable parameters, not magic numbers.

| Likely question | Answer |
|---|---|
| Why not `getline()`? | A hand-written `lr_next()` strips `\r\n` while reading, truncates over-long lines, and avoids per-line allocation; `memchr` scanning is faster than reading char by char. |
| Why is k 512? | A conservative value for `FOPEN_MAX` / `ulimit -n`, and the balance point between memory and I/O count. Tunable via `MAX_MERGE_FANIN`. |
| Is memory really O(1)? | It depends on `-m`: with `-m` fixed, memory is independent of file size — but the **disk** space needed for temporary files is O(N). |
| Do the results need to be stable? | No. `qsort()` does not guarantee stability; test data uses unique values to avoid ambiguity. |
| How is the input protected? | `stat()` compares `st_dev` / `st_ino`; if identical, write to a temporary output first and overwrite afterwards. |
| Does multi-pass merging blow up temp files? | Each round unlinks its source runs immediately, so peak temp space stays O(N). |
| What if `-m` cannot even hold one line? | `MIN_CHUNK_BUDGET` guarantees room for one line plus 256 pointers; otherwise a clear error is printed and a non-zero status returned. |