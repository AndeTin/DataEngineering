/*
 * esort.c - 外部排序 (External Merge Sort) 命令列工具
 *
 *   用法：esort [options] FileName
 *     -c              不分大小寫排序 (strcasecmp)
 *     -m <size>       最大記憶體用量 (MB)，預設 100
 *     -r              反向排序 (遞減)
 *     -n              數值排序 (atoi)
 *     -l              長度優先排序 (strlen)
 *     -o <file>       輸出檔案（預設 stdout，-o - 亦為 stdout）
 *
 * 實作要點
 *   1. 單一 Comparator（cmp_strings）同時供 qsort() 與 Min-Heap 使用。
 *   2. 階段一：以 Arena（固定大小區塊、永不搬移）+ char** 指標陣列組成
 *      「Buffer Pool」，精確計算「字串內容 + sizeof(char*)」的記憶體用量，
 *      一旦逼近 -m 上限就停止讀取，把目前這批輸出成一個 run 暫存檔。
 *   3. 階段二：Min-Heap 多路合併；若 run 數超過 fanin（受 FOPEN_MAX 限制，
 *      上限 512，並依記憶體預算自動縮小），自動執行多輪合併。
 *   4. -o 與輸入為同一檔案時，先寫入暫存輸出檔，完成後再覆蓋原檔。
 *   5. 結束前關閉所有 FILE*、free 所有 malloc、unlink 所有暫存檔。
 *
 * 編譯：gcc -std=c11 -Wall -Wextra -O2 -o esort esort.c
 */

#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <getopt.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>     /* strcasecmp() */
#include <sys/stat.h>
#include <unistd.h>      /* unlink(), mkstemp() */

/* ------------------------------------------------------------------ */
/* 常數定義                                                            */
/* ------------------------------------------------------------------ */

/** 單行最大長度（含 NUL 結尾空間）；超出部分會被截斷 */
#define MAX_LINE_LENGTH       4096

/** -m 未指定時的預設記憶體上限 (MB) */
#define DEFAULT_MEM_MB        100

/** 單輪合併的最大路數：作業系統同時開檔數 (FOPEN_MAX) 的保守上限 */
#ifndef MAX_MERGE_FANIN
#define MAX_MERGE_FANIN       512
#endif

/** Arena 區塊大小：區塊永不搬移，故既有指標不會失效 */
#define ARENA_BLOCK_SIZE      (64u * 1024u)

/** 讀取 / 寫出緩衝區大小 */
#define IO_BUF_SIZE           (64u * 1024u)

/** 合併階段：每個 run 檔的讀取緩衝區大小 */
#define RUN_READER_BUF_SIZE   (8u * 1024u)

/** 階段一最小預算：至少要能放得下一行資料與指標陣列 */
#define MIN_CHUNK_BUDGET      (MAX_LINE_LENGTH + 256 * sizeof(char *))

/** 暫存檔樣板 */
#define TMP_RUN_TEMPLATE      "/tmp/esort_run_XXXXXX"
#define TMP_OUT_TEMPLATE      "/tmp/esort_out_XXXXXX"

/* ------------------------------------------------------------------ */
/* 錯誤處理                                                            */
/* ------------------------------------------------------------------ */

static char g_errbuf[512];

static void err_set(const char *fmt, ...)
{
    va_list ap;

    va_start(ap, fmt);
    vsnprintf(g_errbuf, sizeof g_errbuf, fmt, ap);
    va_end(ap);
}

/** 設定錯誤訊息並附加 strerror(errno) */
static void err_set_errno(const char *fmt, ...)
{
    char msg[320];
    int  saved = errno;
    va_list ap;

    va_start(ap, fmt);
    vsnprintf(msg, sizeof msg, fmt, ap);
    va_end(ap);

    snprintf(g_errbuf, sizeof g_errbuf, "%s: %s", msg, strerror(saved));
}

static void err_report(const char *prog)
{
    if (g_errbuf[0] != '\0')
        fprintf(stderr, "%s: %s\n", prog, g_errbuf);
}

/* ------------------------------------------------------------------ */
/* 排序選項與核心 Comparator                                            */
/* ------------------------------------------------------------------ */

typedef struct {
    int fold_case;   /* -c：不分大小寫 */
    int reverse;     /* -r：遞減排序 */
    int numeric;     /* -n：數值排序 */
    int by_length;   /* -l：長度優先 */
} SortOpts;

/*
 * qsort() 沒有 context 參數可比擬，因此排序選項採檔案作用域變數。
 * 本程式為單執行緒設計。
 */
static SortOpts g_opts = { 0, 0, 0, 0 };

/*
 * 統一比較函式，判斷順序：
 *   1. -l：先比較 strlen(a) 與 strlen(b)。長度不同即以此為準；
 *          長度相同則繼續往下比較。
 *   2. -n：比較 atoi(a) 與 atoi(b)（以 < / > 判斷，避免相減造成整數溢位）；
 *          數值相同再以字典序（-c 決定 strcasecmp / strcmp）做次要比較。
 *      未啟用 -n：-c 用 strcasecmp()，否則用 strcmp()。
 *   3. -r：把結果乘以 -1，反轉遞增 / 遞減方向。
 *
 * 回傳值只需保證符號正確（<0 / 0 / >0），不特定 -1 與 +1。
 */
static int cmp_strings(const char *a, const char *b)
{
    int result = 0;

    /* (1) 長度優先 */
    if (g_opts.by_length) {
        size_t la = strlen(a);
        size_t lb = strlen(b);

        if (la < lb)
            result = -1;
        else if (la > lb)
            result = 1;
    }

    /* (2) 數值序 或 字典序 */
    if (result == 0) {
        if (g_opts.numeric) {
            int na = atoi(a);
            int nb = atoi(b);

            if (na < nb)
                result = -1;
            else if (na > nb)
                result = 1;
            else
                result = g_opts.fold_case ? strcasecmp(a, b) : strcmp(a, b);
        } else {
            result = g_opts.fold_case ? strcasecmp(a, b) : strcmp(a, b);
        }
    }

    /* (3) 反向排序 */
    if (g_opts.reverse)
        result = -result;

    return result;
}

/** qsort() 的比較函式：元素是 char*，需多一層解參考 */
static int cmp_qsort(const void *pa, const void *pb)
{
    const char *a = *(const char *const *)pa;
    const char *b = *(const char *const *)pb;

    return cmp_strings(a, b);
}

/* ------------------------------------------------------------------ */
/* LineReader：以 fread() 預讀的高效行讀取器                           */
/* ------------------------------------------------------------------ */

typedef struct {
    FILE  *fp;
    char  *buf;
    size_t cap;      /* buf 容量 */
    size_t len;      /* buf 中有效位元組數 */
    size_t pos;      /* 目前消費到哪裡 */
} LineReader;

static int lr_init(LineReader *lr, FILE *fp, size_t cap)
{
    lr->fp  = fp;
    lr->cap = cap;
    lr->len = 0;
    lr->pos = 0;
    lr->buf = malloc(cap);

    if (lr->buf == NULL) {
        err_set("out of memory (input buffer, %zu bytes)", cap);
        return -1;
    }
    return 0;
}

static void lr_destroy(LineReader *lr)
{
    free(lr->buf);
    lr->buf = NULL;
    lr->cap = lr->len = lr->pos = 0;
}

/*
 * 讀取下一行到 dst（移除行尾 "\r\n" 或 "\n"，補上 '\0'）。
 * 回傳： 1 = 讀到一行；0 = EOF；-1 = I/O 錯誤。
 * 超過 dstcap-1 的內容會被截斷，但仍會把整行自來源消耗掉，
 * 因此不會影響後續行的對齊。
 */
static int lr_next(LineReader *lr, char *dst, size_t dstcap, size_t *out_len)
{
    size_t n = 0;
    int    got_any = 0;

    if (dstcap < 2) {
        err_set("internal error: destination line buffer too small");
        return -1;
    }

    for (;;) {
        char  *base;
        char  *nl;
        size_t avail, take, i;

        /* 緩衝區已用盡 → refill */
        if (lr->pos >= lr->len) {
            lr->len = fread(lr->buf, 1, lr->cap, lr->fp);
            lr->pos = 0;
            if (lr->len == 0) {
                if (ferror(lr->fp)) {
                    err_set_errno("read error");
                    return -1;
                }
                break;                  /* EOF */
            }
        }

        base  = lr->buf + lr->pos;
        avail = lr->len - lr->pos;
        nl    = memchr(base, '\n', avail);
        take  = nl ? (size_t)(nl - base) : avail;

        for (i = 0; i < take; i++) {
            if (n + 1 < dstcap)        /* 保留一個位元組給 '\0' */
                dst[n++] = base[i];
            got_any = 1;               /* 超長行：內容截斷，但仍算讀到一行 */
        }

        lr->pos += take;

        if (nl != NULL) {
            lr->pos++;                 /* 吃掉 '\n' */
            got_any = 1;
            break;
        }
    }

    /* 去掉 Windows 慣用的 '\r' */
    if (n > 0 && dst[n - 1] == '\r')
        n--;

    dst[n]   = '\0';
    *out_len = n;

    if (!got_any)
        return 0;                      /* 純 EOF，沒有任何資料 */

    return 1;
}

/* ------------------------------------------------------------------ */
/* LineWriter：輸出緩衝寫入器（輸出時補回 '\n'）                       */
/* ------------------------------------------------------------------ */

typedef struct {
    FILE  *fp;
    char  *buf;
    size_t cap;
    size_t len;
} LineWriter;

static int lw_init(LineWriter *w, FILE *fp, size_t cap)
{
    w->fp  = fp;
    w->cap = cap;
    w->len = 0;
    w->buf = malloc(cap);

    if (w->buf == NULL) {
        err_set("out of memory (output buffer, %zu bytes)", cap);
        return -1;
    }
    return 0;
}

static int lw_flush(LineWriter *w)
{
    size_t n = w->len;

    if (n == 0)
        return 0;

    w->len = 0;
    if (fwrite(w->buf, 1, n, w->fp) != n) {
        err_set_errno("write error");
        return -1;
    }
    return 0;
}

/** 寫出一行（自動補回 '\n'） */
static int lw_put(LineWriter *w, const char *s)
{
    size_t n = strlen(s);

    /* 行長度超過緩衝區 → 先清空緩衝區再直接寫出 */
    if (n + 1 > w->cap) {
        if (lw_flush(w) != 0)
            return -1;
        if (fwrite(s, 1, n, w->fp) != n || fputc('\n', w->fp) == EOF) {
            err_set_errno("write error");
            return -1;
        }
        return 0;
    }

    if (w->len + n + 1 > w->cap && lw_flush(w) != 0)
        return -1;

    memcpy(w->buf + w->len, s, n);
    w->len += n;
    w->buf[w->len++] = '\n';

    return 0;
}

static void lw_destroy(LineWriter *w)
{
    free(w->buf);
    w->buf = NULL;
    w->cap = w->len = 0;
}

/** 把 lines[0..n) 依序寫到 out（供「單一批次直接輸出」使用） */
static int lw_put_all(LineWriter *lw, FILE *out, char *const *lines, size_t n)
{
    size_t i;

    if (lw_init(lw, out, IO_BUF_SIZE) != 0)
        return -1;

    for (i = 0; i < n; i++) {
        if (lw_put(lw, lines[i]) != 0)
            return -1;
    }

    return lw_flush(lw);
}

/* ------------------------------------------------------------------ */
/* Arena：固定大小區塊的記憶體池（區塊永不搬移，故指標保持有效）       */
/* ------------------------------------------------------------------ */

typedef struct ArenaBlock {
    struct ArenaBlock *next;
    size_t size;                   /* data 的可用位元組數 */
    size_t used;                   /* 已使用位元組數 */
    char   data[1];                /* 實際配置 sizeof(ArenaBlock) + size */
} ArenaBlock;

typedef struct {
    ArenaBlock *head;              /* 所有區塊（由 head 串成鏈） */
    ArenaBlock *cur;               /* 目前寫入中的區塊 */
    size_t      arena_bytes;       /* Arena 實際佔用位元組總數 */
    char      **lines;             /* 指標陣列 */
    size_t      nlines;            /* 目前批次的行數 */
    size_t      lines_cap;         /* 指標陣列容量 */
    size_t      budget;            /* arena_bytes + lines_cap*sizeof(char*) 上限 */
} Chunk;

static void chunk_init(Chunk *c, size_t budget)
{
    c->head        = NULL;
    c->cur         = NULL;
    c->arena_bytes = 0;
    c->lines       = NULL;
    c->nlines      = 0;
    c->lines_cap   = 0;
    c->budget      = budget;
}

/** 釋放所有 Arena 區塊（保留指標陣列供下一批重用，避免反覆配置） */
static void chunk_drop_arena(Chunk *c)
{
    ArenaBlock *b = c->head;

    while (b != NULL) {
        ArenaBlock *next = b->next;
        free(b);
        b = next;
    }
    c->head        = NULL;
    c->cur         = NULL;
    c->arena_bytes = 0;
}

static void chunk_destroy(Chunk *c)
{
    chunk_drop_arena(c);
    free(c->lines);
    c->lines     = NULL;
    c->lines_cap = 0;
    c->nlines    = 0;
}

/** 清空內容，準備接收下一批資料 */
static void chunk_reset(Chunk *c)
{
    chunk_drop_arena(c);
    c->nlines = 0;
}

/** 指標陣列下一次擴充後的容量 */
static size_t chunk_next_cap(const Chunk *c)
{
    size_t cap = (c->lines_cap != 0) ? c->lines_cap : 128;

    while (cap <= c->nlines)
        cap *= 2;

    return cap;
}

/*
 * 目前 Chunk 已配置、且必須持續存在的位元組總數。
 * = Arena 所有區塊的實際配置量 + 指標陣列容量（每個指標 sizeof(char *)）。
 * chunk_alloc() 的每一次配置檢查都以此式為準，確保總和不超過 budget。
 */
#define CHUNK_USED(c) ((c)->arena_bytes + (c)->lines_cap * sizeof(char *))

/*
 * 為長度 need（含 NUL）的字串配置空間，並將指標存入指標陣列。
 * 精確檢查「已配置位元組（CHUNK_USED）+ 本次需求」是否仍在 budget 內，
 * 因此動態配置的陣列與字串緩衝區總和不會超過 -m 指定的上限。
 *
 * 成功回傳字串空間；超出預算或配置失敗回傳 NULL。
 */
static char *chunk_alloc(Chunk *c, size_t need)
{
    ArenaBlock *b;
    size_t block_size;
    char  *p;

    if (need == 0)
        need = 1;                    /* 空字串仍需要 NUL */

    /* 1. 指標陣列容量不足時先擴充，擴充量本身也要計入預算 */
    if (c->nlines >= c->lines_cap) {
        size_t newcap = chunk_next_cap(c);
        size_t grow   = (newcap - c->lines_cap) * sizeof(char *);

        if (CHUNK_USED(c) + grow + need > c->budget)
            return NULL;

        {
            char **nl = realloc(c->lines, newcap * sizeof(char *));

            if (nl == NULL)
                return NULL;
            c->lines     = nl;
            c->lines_cap = newcap;
        }
    }

    /* 2. 嚴格檢查字串本身的空間 */
    if (CHUNK_USED(c) + need > c->budget)
        return NULL;

    /* 3. 取得 Arena 空間：目前區塊剩餘不足就換一塊新區塊 */
    b = c->cur;
    if (b == NULL || b->used + need > b->size) {
        block_size = (need > ARENA_BLOCK_SIZE) ? need : ARENA_BLOCK_SIZE;

        /* 預算不足以配置一個完整區塊時，退而求其次只配置 need 大小；
         * 兩次檢查都包含指標陣列，確保 CHUNK_USED(c) 永不超過 budget。 */
        if (CHUNK_USED(c) + block_size > c->budget) {
            block_size = need;
            if (CHUNK_USED(c) + block_size > c->budget)
                return NULL;
        }

        b = malloc(sizeof(ArenaBlock) + block_size);
        if (b == NULL)
            return NULL;

        b->size = block_size;
        b->used = 0;
        b->next = NULL;

        if (c->cur != NULL)
            c->cur->next = b;
        else
            c->head = b;

        c->cur = b;
        c->arena_bytes += block_size;
    }

    p = b->data + b->used;
    b->used += need;
    c->lines[c->nlines++] = p;

    return p;
}

/* ------------------------------------------------------------------ */
/* 暫存檔清單                                                          */
/* ------------------------------------------------------------------ */

typedef struct {
    char  **paths;
    size_t  n;
    size_t  cap;
} PathList;

static void pathlist_init(PathList *l)
{
    l->paths = NULL;
    l->n     = 0;
    l->cap   = 0;
}

/** 把 path 的「指標」登錄進清單（path 的記憶體所有權轉移給清單） */
static int pathlist_push(PathList *l, char *path)
{
    if (l->n == l->cap) {
        size_t newcap = (l->cap != 0) ? l->cap * 2 : 16;
        char **np     = realloc(l->paths, newcap * sizeof(char *));

        if (np == NULL) {
            err_set("out of memory (path list)");
            return -1;
        }
        l->paths = np;
        l->cap    = newcap;
    }
    l->paths[l->n++] = path;
    return 0;
}

/** unlink 並釋放清單中所有暫存檔 */
static void pathlist_cleanup(PathList *l)
{
    size_t i;

    for (i = 0; i < l->n; i++) {
        if (l->paths[i] != NULL) {
            (void)unlink(l->paths[i]);
            free(l->paths[i]);
        }
    }
    free(l->paths);
    pathlist_init(l);
}

/** 建立新的暫存檔：回傳已開啟的 FILE*，檔案路徑寫入 *path_out */
static FILE *tmp_file_new(PathList *l, const char *tmpl, char **path_out)
{
    size_t tlen = strlen(tmpl) + 1;
    char  *path;
    int    fd;
    FILE  *fp;

    path = malloc(tlen);
    if (path == NULL) {
        err_set("out of memory (temp file path)");
        return NULL;
    }
    memcpy(path, tmpl, tlen);

    fd = mkstemp(path);
    if (fd < 0) {
        err_set_errno("cannot create temp file (%s)", tmpl);
        free(path);
        return NULL;
    }

    fp = fdopen(fd, "w");
    if (fp == NULL) {
        err_set_errno("fdopen");
        (void)close(fd);
        (void)unlink(path);
        free(path);
        return NULL;
    }

    if (pathlist_push(l, path) != 0) {
        fclose(fp);
        (void)unlink(path);
        free(path);
        return NULL;
    }

    *path_out = path;
    return fp;
}

/*
 * 把 chunk 的內容寫成一個 run 暫存檔，並把路徑登錄到 runs（所有權歸 runs，
 * 之後由 pathlist_cleanup() 負責 unlink）。回傳 0 成功、-1 失敗。
 *
 * 抽成獨立函式，讓階段一主迴圈不需要任何 goto 標籤跳躍。
 */
static int write_run_file(PathList *runs, char *const *lines, size_t n)
{
    char      *path = NULL;
    FILE      *rfp;
    LineWriter lw;
    int        rc = -1;

    memset(&lw, 0, sizeof lw);

    rfp = tmp_file_new(runs, TMP_RUN_TEMPLATE, &path);
    if (rfp == NULL)
        return -1;

    if (lw_put_all(&lw, rfp, lines, n) != 0)
        goto out;                    /* lw_put_all 已設定錯誤訊息 */

    if (fflush(rfp) != 0) {
        err_set_errno("cannot flush run file: %s", path);
        goto out;
    }

    if (fclose(rfp) != 0) {
        rfp = NULL;
        err_set_errno("cannot close run file: %s", path);
        goto out;
    }
    rfp = NULL;
    rc  = 0;

out:
    lw_destroy(&lw);
    if (rfp != NULL)
        (void)fclose(rfp);           /* 只有失敗路徑才會走到這裡 */

    return rc;
}

/* ------------------------------------------------------------------ */
/* Min-Heap（最小堆積），與 qsort() 共用 cmp_strings()                 */
/* ------------------------------------------------------------------ */

typedef struct {
    const char *line;   /* 指向該 run 的行緩衝區 */
    int         run;    /* 來源 run 索引 */
} HeapItem;

static int cmp_heap(const void *pa, const void *pb)
{
    const HeapItem *a = pa;
    const HeapItem *b = pb;

    return cmp_strings(a->line, b->line);
}

static void heap_sift_down(HeapItem *h, size_t root, size_t n)
{
    for (;;) {
        size_t   child = 2 * root + 1;
        HeapItem t;

        if (child >= n)
            break;

        /* 選較小的子節點 */
        if (child + 1 < n && cmp_heap(&h[child], &h[child + 1]) > 0)
            child++;

        if (cmp_heap(&h[root], &h[child]) <= 0)
            break;

        t        = h[root];
        h[root]  = h[child];
        h[child] = t;
        root     = child;
    }
}

/*
 * 由後往前 bottom-up 建堆，O(n)。
 * 初始填入所有 run 的第一行時一次建堆，比逐筆 push（O(n log n)）划算；
 * 合併階段則一律使用 heap_replace_top()，因此不再需要 sift_up。
 */
static void heap_init(HeapItem *h, size_t n)
{
    size_t i;

    for (i = n / 2; i > 0; i--)
        heap_sift_down(h, i - 1, n);
}

/*
 * 直接覆寫堆頂（取代成同一個 run 的下一行），堆的大小不變。
 *
 * 這是「heap_pop() + heap_push()」的等價最佳化：取出堆頂後，下一個要放進堆的
 * 元素必定來自「同一個 run」，整個堆中只有堆頂一個位置改變，
 * 因此只要一趟 sift_down 即可重新平衡，省掉原本 sift_down + sift_up 兩趟比較。
 *
 * 前置條件：n > 0。
 */
static void heap_set_top(HeapItem *h, size_t n, HeapItem it)
{
    h[0] = it;
    heap_sift_down(h, 0, n);
}

/** 取出堆頂（最小元素）並移除，堆大小減一；回傳被取出的元素 */
static HeapItem heap_remove_top(HeapItem *h, size_t *n)
{
    HeapItem top = h[0];

    (*n)--;
    if (*n > 0) {
        h[0] = h[*n];
        heap_sift_down(h, 0, *n);
    }
    return top;
}

/* ------------------------------------------------------------------ */
/* 階段二：K-way Merge                                                 */
/* ------------------------------------------------------------------ */

typedef struct {
    LineReader lr;
    char      *line;     /* 存放該 run 目前讀到的一行 */
    int        opened;   /* lr.lr.fp 是否有效 */
} MergeRun;

/*
 * 把 n 個已排序的 run 檔多路合併，結果寫入 out。
 * 所有 run 都同時開啟，每個 run 先讀第一行放入 Min-Heap；
 * 迴圈中取堆頂輸出，再從同一個 run 補下一行，直到所有 run 讀完。
 * 回傳 0 成功，-1 失敗（錯誤訊息寫入 g_errbuf）。
 */
static int merge_runs(char **in_paths, size_t n, FILE *out)
{
    MergeRun  *runs = NULL;
    HeapItem  *heap = NULL;
    LineWriter lw;
    size_t     hsize = 0;
    size_t     i;
    int        rc = -1;
    int        lw_ready = 0;

    memset(&lw, 0, sizeof lw);

    runs = calloc(n, sizeof *runs);
    heap = malloc(n * sizeof *heap);
    if (runs == NULL || heap == NULL) {
        err_set("out of memory (merge: %zu runs)", n);
        goto done;
    }

    /* 開啟所有 run 檔，並把每個 run 的第一行放進 heap */
    for (i = 0; i < n; i++) {
        FILE   *fp = fopen(in_paths[i], "rb");
        size_t  len;
        int     r;

        if (fp == NULL) {
            err_set_errno("cannot open run file: %s", in_paths[i]);
            goto done;
        }
        runs[i].opened = 1;

        if (lr_init(&runs[i].lr, fp, RUN_READER_BUF_SIZE) != 0)
            goto done;

        runs[i].line = malloc(MAX_LINE_LENGTH);
        if (runs[i].line == NULL) {
            err_set("out of memory (merge line buffer)");
            goto done;
        }

        r = lr_next(&runs[i].lr, runs[i].line, MAX_LINE_LENGTH, &len);
        if (r < 0)
            goto done;

        if (r == 1) {                     /* r == 0：空 run，略過 */
            HeapItem it;
            it.line = runs[i].line;
            it.run  = (int)i;
            heap[hsize++] = it;
        }
    }

    /* bottom-up 建立 Min-Heap（O(n)） */
    if (hsize > 1)
        heap_init(heap, hsize);

    if (lw_init(&lw, out, IO_BUF_SIZE) != 0)
        goto done;
    lw_ready = 1;

    /* 主迴圈：堆頂輸出後，直接用「同一個 run 的下一行」取代堆頂 */
    while (hsize > 0) {
        HeapItem  top = heap[0];
        MergeRun *run = &runs[top.run];
        size_t    len;
        int       r;

        if (lw_put(&lw, top.line) != 0)
            goto done;

        /*
         * 重要：run->line 正是 top.line 所在的緩衝區，
         * 必須先把堆頂輸出出去，才能覆寫該緩衝區。
         */
        r = lr_next(&run->lr, run->line, MAX_LINE_LENGTH, &len);
        if (r < 0)
            goto done;

        if (r == 1) {
            /* 此 run 還有下一行：覆寫堆頂 + 一次 sift_down（堆大小不變） */
            HeapItem it;
            it.line = run->line;
            it.run  = top.run;
            heap_set_top(heap, hsize, it);
        } else {
            /* 此 run 已讀完：直接移除堆頂 */
            (void)heap_remove_top(heap, &hsize);
        }
    }

    if (lw_flush(&lw) != 0)
        goto done;

    rc = 0;

done:
    if (lw_ready) {
        if (lw_flush(&lw) != 0 && rc == 0)
            rc = -1;
        lw_destroy(&lw);
    }

    if (runs != NULL) {
        for (i = 0; i < n; i++) {
            free(runs[i].line);
            if (runs[i].opened) {
                lr_destroy(&runs[i].lr);
                if (runs[i].lr.fp != NULL)
                    (void)fclose(runs[i].lr.fp);
            }
        }
        free(runs);
    }
    free(heap);

    return rc;
}

/* ------------------------------------------------------------------ */
/* 輔助函式                                                            */
/* ------------------------------------------------------------------ */

/** 判斷兩個路徑是否指向同一個檔案（先比字串，再比 dev/ino） */
static int is_same_file(const char *a, const char *b)
{
    struct stat sa, sb;

    if (strcmp(a, b) == 0)
        return 1;

    if (stat(a, &sa) != 0 || stat(b, &sb) != 0)
        return 0;

    return (sa.st_dev == sb.st_dev) && (sa.st_ino == sb.st_ino);
}

/** 把 src 的內容覆蓋寫入 dst（用於 -o 與輸入同檔的情況） */
static int copy_file_over(const char *src, const char *dst)
{
    FILE *in  = NULL;
    FILE *out = NULL;
    char *buf = NULL;
    int   rc  = -1;

    in = fopen(src, "rb");
    if (in == NULL) {
        err_set_errno("cannot reopen temp output: %s", src);
        goto done;
    }

    out = fopen(dst, "wb");
    if (out == NULL) {
        err_set_errno("cannot overwrite output file: %s", dst);
        goto done;
    }

    buf = malloc(IO_BUF_SIZE);
    if (buf == NULL) {
        err_set("out of memory (copy buffer)");
        goto done;
    }

    for (;;) {
        size_t n = fread(buf, 1, IO_BUF_SIZE, in);

        if (n == 0)
            break;

        if (fwrite(buf, 1, n, out) != n) {
            err_set_errno("write error while overwriting %s", dst);
            goto done;
        }
    }

    if (ferror(in)) {
        err_set_errno("read error: %s", src);
        goto done;
    }

    if (fclose(out) != 0) {
        out = NULL;
        err_set_errno("close error: %s", dst);
        goto done;
    }
    out = NULL;
    rc  = 0;

done:
    free(buf);
    if (in != NULL)
        (void)fclose(in);
    if (out != NULL)
        (void)fclose(out);
    return rc;
}

/**
 * 解析 -m 參數。
 * 先以 strtol() 檢查數值範圍（避免 atoi() 溢位屬於未定義行為），
 * 再依規格用 atoi() 取得整數 MB 值。
 */
static int parse_mem_mb(const char *arg, int *out_mb)
{
    char *end = NULL;
    long  val;

    errno = 0;
    val = strtol(arg, &end, 10);

    if (end == arg || (end != NULL && *end != '\0')) {
        err_set("invalid memory size: '%s' (expect an integer number of MB)", arg);
        return -1;
    }

    if (val < 1 || val > 1048576L) {      /* 1 MB ~ 1 TB，避免後續乘以 1024*1024 溢位 */
        err_set("invalid memory size: '%s' (must be 1..1048576)", arg);
        return -1;
    }

    *out_mb = atoi(arg);                  /* MB */
    return 0;
}

/** 依記憶體預算決定單輪合併路數（同時受 FOPEN_MAX 上限 512 限制） */
static size_t calc_fanin(size_t mem_limit)
{
    size_t per_run = sizeof(MergeRun) + RUN_READER_BUF_SIZE
                   + MAX_LINE_LENGTH + sizeof(HeapItem);
    size_t avail   = mem_limit / 2;               /* 合併階段最多用一半預算 */
    size_t fanin;

    if (avail > 2 * IO_BUF_SIZE)
        fanin = (avail - 2 * IO_BUF_SIZE) / per_run;
    else
        fanin = 2;

    if (fanin > MAX_MERGE_FANIN)
        fanin = MAX_MERGE_FANIN;
    if (fanin < 2)
        fanin = 2;

    return fanin;
}

/** 合併階段要預留的記憶體量 */
static size_t merge_reserve_of(size_t fanin)
{
    size_t per_run = sizeof(MergeRun) + RUN_READER_BUF_SIZE
                   + MAX_LINE_LENGTH + sizeof(HeapItem);

    return fanin * per_run + 2 * IO_BUF_SIZE;
}

/* ------------------------------------------------------------------ */
/* 主流程                                                              */
/* ------------------------------------------------------------------ */

static void usage(FILE *fp, const char *prog)
{
    fprintf(fp,
        "Usage: %s [options] FileName\n"
        "\n"
        "Options:\n"
        "  -c            case-insensitive sort (strcasecmp)\n"
        "  -m <size>     max memory usage in MB (default: %d)\n"
        "  -r            reverse sort (decreasing order)\n"
        "  -n            numeric sort (atoi)\n"
        "  -l            sort by length first (strlen)\n"
        "  -o <file>     output file (default: stdout)\n"
        "  -h            show this help\n"
        "\n"
        "Example:\n"
        "  %s -n -r data.txt -o sorted.txt\n",
        prog, DEFAULT_MEM_MB, prog);
}

int main(int argc, char **argv)
{
    static struct option long_opts[] = {
        { "case-insensitive", no_argument,       NULL, 'c' },
        { "memory",           required_argument, NULL, 'm' },
        { "reverse",          no_argument,       NULL, 'r' },
        { "numeric",          no_argument,       NULL, 'n' },
        { "length",           no_argument,       NULL, 'l' },
        { "output",           required_argument, NULL, 'o' },
        { "help",             no_argument,       NULL, 'h' },
        { NULL,               0,                 NULL, 0   }
    };

    int         opt_mb     = DEFAULT_MEM_MB;
    const char *out_path   = NULL;
    const char *in_path    = NULL;
    FILE       *fin        = NULL;
    FILE       *fout       = NULL;
    char       *tmp_out_path = NULL;
    int         same_file_io   = 0;
    int         rc         = EXIT_FAILURE;

    /* 記憶體預算 */
    size_t mem_limit, fanin, merge_reserve, chunk_budget;

    /* 執行狀態 */
    LineReader  lr;
    int         lr_ready    = 0;
    LineWriter  lw;
    int         lw_ready    = 0;
    Chunk       chunk;
    int         chunk_ready = 0;
    PathList    runs;                /* 目前待合併的 run 暫存檔 */
    PathList    tmpout;              /* -o 同檔時的中繼輸出檔 */

    char        stage[MAX_LINE_LENGTH];
    /* chunk 滿載時暫存、下一批要補上的那一行 */
    char        pending[MAX_LINE_LENGTH];
    size_t      pending_len  = 0;
    int         have_pending = 0;

    memset(&lr, 0, sizeof lr);
    memset(&lw, 0, sizeof lw);
    memset(&chunk, 0, sizeof chunk);
    pathlist_init(&runs);
    pathlist_init(&tmpout);

    /* ---------------- 1. 解析命令列（getopt_long） ---------------- */
    opterr = 0;                       /* 自行輸出錯誤訊息 */

    for (;;) {
        int c = getopt_long(argc, argv, "cm:rnlo:h", long_opts, NULL);

        if (c == -1)
            break;

        switch (c) {
        case 'c':
            g_opts.fold_case = 1;
            break;
        case 'r':
            g_opts.reverse = 1;
            break;
        case 'n':
            g_opts.numeric = 1;
            break;
        case 'l':
            g_opts.by_length = 1;
            break;
        case 'm':
            if (parse_mem_mb(optarg, &opt_mb) != 0) {
                err_report(argv[0]);
                goto cleanup;
            }
            break;
        case 'o':
            out_path = optarg;
            break;
        case 'h':
            usage(stdout, argv[0]);
            rc = EXIT_SUCCESS;
            goto cleanup;
        case '?':
        default:
            if (optopt == 'm' || optopt == 'o')
                fprintf(stderr, "%s: option -%c requires an argument\n",
                        argv[0], optopt);
            else if (optopt != 0)
                fprintf(stderr, "%s: unknown option -%c\n", argv[0], optopt);
            else
                fprintf(stderr, "%s: unknown option %s\n",
                        argv[0], argv[optind - 1]);
            usage(stderr, argv[0]);
            goto cleanup;
        }
    }

    if (optind >= argc) {
        fprintf(stderr, "%s: missing input file name\n\n", argv[0]);
        usage(stderr, argv[0]);
        goto cleanup;
    }

    in_path = argv[optind];

    if (out_path != NULL && strcmp(out_path, "-") == 0)
        out_path = NULL;              /* -o - 代表 stdout */

    /* ---------------- 2. 計算記憶體預算 ---------------- */
    mem_limit = (size_t)opt_mb * 1024u * 1024u;   /* MB -> Bytes */

    /*
     * 預算分配：merge_reserve 給合併階段（每個 run 的讀取緩衝區、行緩衝區
     * 與 heap 欄位），剩下的全部給階段一的 in-memory chunk。
     */
    fanin = calc_fanin(mem_limit);

    merge_reserve = merge_reserve_of(fanin);
    if (merge_reserve > mem_limit / 2)
        merge_reserve = mem_limit / 2;

    chunk_budget = (mem_limit > merge_reserve) ? (mem_limit - merge_reserve) : 0;
    if (chunk_budget < MIN_CHUNK_BUDGET)
        chunk_budget = (mem_limit < MIN_CHUNK_BUDGET) ? mem_limit : MIN_CHUNK_BUDGET;

    /* ---------------- 3. 開啟輸入 / 輸出 ---------------- */
    fin = fopen(in_path, "rb");
    if (fin == NULL) {
        fprintf(stderr, "%s: cannot open input file %s: %s\n",
                argv[0], in_path, strerror(errno));
        goto cleanup;
    }

    if (out_path != NULL) {
        /* -o 與輸入為同一檔案 → 先寫暫存輸出檔，之後再覆蓋原檔 */
        same_file_io = is_same_file(out_path, in_path);

        if (same_file_io) {
            fout = tmp_file_new(&tmpout, TMP_OUT_TEMPLATE, &tmp_out_path);
            if (fout == NULL) {
                err_report(argv[0]);
                goto cleanup;
            }
        } else {
            fout = fopen(out_path, "wb");
            if (fout == NULL) {
                fprintf(stderr, "%s: cannot open output file %s: %s\n",
                        argv[0], out_path, strerror(errno));
                goto cleanup;
            }
        }
    } else {
        fout = stdout;
    }

    if (lr_init(&lr, fin, IO_BUF_SIZE) != 0) {
        err_report(argv[0]);
        goto cleanup;
    }
    lr_ready = 1;

    chunk_init(&chunk, chunk_budget);
    chunk_ready = 1;

    /* ================================================================
     * 階段一：分塊讀取 + 內部排序 (Run Generation)
     * ================================================================ */
    for (;;) {
        int    eof_reached = 0;
        size_t len;

        chunk_reset(&chunk);

        /*
         * 3-0. 先補上上一個 chunk 滿載時「讀出來卻放不下」的那一行，
         *      避免它在記憶體不足而被丟棄（每個 chunk 邊界會少一行）。
         */
        if (have_pending) {
            char *dst = chunk_alloc(&chunk, pending_len + 1);

            if (dst == NULL) {          /* 理論上不會發生：預算至少可容納一行 */
                fprintf(stderr, "%s: memory limit too small (%d MB) to hold a "
                                "single line\n", argv[0], opt_mb);
                goto cleanup;
            }
            memcpy(dst, pending, pending_len + 1);
            have_pending = 0;
        }

        /* 3-1. 盡量塞滿這個 chunk，直到記憶體預算用完或讀到 EOF */
        for (;;) {
            char *dst;
            int   r = lr_next(&lr, stage, sizeof stage, &len);

            if (r < 0) {
                err_report(argv[0]);
                goto cleanup;
            }

            if (r == 0) {             /* EOF */
                eof_reached = 1;
                break;
            }

            /* 配置失敗 = 記憶體已滿，這個 run 到此為止；
             * 但這一行必須保留給下一個 chunk，不能丟棄。 */
            dst = chunk_alloc(&chunk, len + 1);
            if (dst == NULL) {
                memcpy(pending, stage, len + 1);
                pending_len  = len;
                have_pending = 1;
                break;
            }

            memcpy(dst, stage, len + 1);   /* 包含結尾的 '\0' */
        }

        if (chunk.nlines == 0) {
            if (eof_reached)
                break;                 /* 輸入檔是空的，沒有任何資料 */
            fprintf(stderr,
                    "%s: memory limit too small (%d MB) to hold a single line\n",
                    argv[0], opt_mb);
            goto cleanup;
        }

        /* 3-2. 這個 chunk 做內部排序 */
        qsort(chunk.lines, chunk.nlines, sizeof(char *), cmp_qsort);

        /* 3-3. 整份輸入都在記憶體內（只產生一個批次）→ 直接輸出，不落地暫存檔 */
        if (runs.n == 0 && eof_reached) {
            size_t k;

            if (lw_init(&lw, fout, IO_BUF_SIZE) != 0) {
                err_report(argv[0]);
                goto cleanup;
            }
            lw_ready = 1;

            for (k = 0; k < chunk.nlines; k++) {
                if (lw_put(&lw, chunk.lines[k]) != 0) {
                    err_report(argv[0]);
                    goto cleanup;
                }
            }

            if (lw_flush(&lw) != 0) {
                err_report(argv[0]);
                goto cleanup;
            }
            break;
        }

        /* 3-4. 否則輸出成一個 run 暫存檔 */
        if (write_run_file(&runs, chunk.lines, chunk.nlines) != 0) {
            err_report(argv[0]);
            goto cleanup;
        }
        /* 暫存檔路徑已登錄到 runs，最後會在 cleanup 階段 unlink */

        if (eof_reached)
            break;
    }

    /* ================================================================
     * 階段二：多輪 K-way Merge
     * ================================================================ */

    if (runs.n > 0) {
        /* 2-1. 多輪合併：run 數超過 fanin 時，先併成較少的 run 檔 */
        while (runs.n > fanin) {
            PathList src;
            size_t   i;

            /* 把目前的 run 清單搬給 src，runs 改作下一輪的輸出清單 */
            src.paths = runs.paths;
            src.n     = runs.n;
            src.cap   = runs.n;
            pathlist_init(&runs);

            for (i = 0; i < src.n; i += fanin) {
                size_t cnt   = (src.n - i < fanin) ? (src.n - i) : fanin;
                char  *mpath = NULL;
                FILE  *mfp;

                mfp = tmp_file_new(&runs, TMP_RUN_TEMPLATE, &mpath);
                if (mfp == NULL) {
                    err_report(argv[0]);
                    goto merge_fail;
                }

                if (merge_runs(&src.paths[i], cnt, mfp) != 0) {
                    fprintf(stderr, "%s: merge failed: %s\n", argv[0], g_errbuf);
                    (void)fclose(mfp);
                    goto merge_fail;
                }

                if (fflush(mfp) != 0 || fclose(mfp) != 0) {
                    fprintf(stderr, "%s: cannot close run file %s: %s\n",
                            argv[0], mpath, strerror(errno));
                    goto merge_fail;
                }
            }

            /* 這一輪的來源 run 已無用處：unlink 並釋放 */
            pathlist_cleanup(&src);
            continue;

        merge_fail:
            pathlist_cleanup(&src);
            goto cleanup;
        }

        /* 2-2. 最後一輪：直接寫入目標輸出 */
        if (merge_runs(runs.paths, runs.n, fout) != 0) {
            fprintf(stderr, "%s: merge failed: %s\n", argv[0], g_errbuf);
            goto cleanup;
        }
    }

    /* ---------------- 4. 收尾 ---------------- */
    if (lw_ready) {
        if (lw_flush(&lw) != 0) {
            err_report(argv[0]);
            goto cleanup;
        }
        lw_destroy(&lw);
        lw_ready = 0;
    }

    if (fflush(fout) != 0) {
        fprintf(stderr, "%s: cannot flush output: %s\n", argv[0], strerror(errno));
        goto cleanup;
    }

    if (fout != stdout) {
        if (fclose(fout) != 0) {
            fout = NULL;
            fprintf(stderr, "%s: cannot close output: %s\n", argv[0], strerror(errno));
            goto cleanup;
        }
        fout = NULL;
    }

    /* -o 與輸入同檔：此時才覆蓋原檔（邊讀邊寫會毀損原始資料） */
    if (same_file_io) {
        if (copy_file_over(tmp_out_path, out_path) != 0) {
            err_report(argv[0]);
            goto cleanup;
        }
    }

    rc = EXIT_SUCCESS;

cleanup:
    /* 關閉所有檔案指標 */
    if (lw_ready)
        lw_destroy(&lw);
    if (lr_ready) {
        lr_destroy(&lr);
        if (fin != NULL) {
            (void)fclose(fin);
            fin = NULL;
        }
    }
    if (fout != NULL && fout != stdout) {
        (void)fclose(fout);
        fout = NULL;
    }

    /* 釋放所有 malloc */
    if (chunk_ready)
        chunk_destroy(&chunk);

    /* 清除所有暫存檔 */
    pathlist_cleanup(&runs);
    pathlist_cleanup(&tmpout);

    return rc;
}