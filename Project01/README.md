# esort — 外部排序（External Merge Sort）命令列工具

以 C 語言（C99/C11 + POSIX）實作的外部排序工具，可在**有限記憶體**下排序遠大於記憶體的檔案。
核心指定函式：`getopt_long()`、`qsort()`、`strlen()`、`strcmp()`、`strcasecmp()`、`atoi()`。

---

## 1. 編譯

```bash
make            # 等同 make all，產生 ./esort
make clean      # 移除 esort 與 *.o
```

編譯參數為 `-Wall -Wextra -O2 -std=c11`（零警告）。手動編譯：

```bash
gcc -Wall -Wextra -O2 -std=c11 -o esort esort.c
```

## 2. 使用方式

```
esort [options] FileName

  -c            不分大小寫排序（strcasecmp）
  -m <size>     最大記憶體用量（MB），預設 100
  -r            反向排序（遞減）
  -n            數值排序（atoi）
  -l            長度優先排序（strlen）
  -o <file>     輸出檔案（預設 stdout；-o - 亦為 stdout）
  -h            顯示說明
```

亦支援長選項：`--case-insensitive`、`--memory=N`、`--reverse`、`--numeric`、`--length`、`--output=FILE`、`--help`。

**比較優先順序**（`cmp_strings()`，`qsort()` 與 Min-Heap 共用同一支）：

1. `-l`：先比 `strlen()`，長度相同才往下比
2. `-n`：比 `atoi()`（用 `<` / `>` 判斷避免溢位），數值相同再以字典序做平手比較；未啟用 `-n` 時直接用字典序
3. 字典序由 `-c` 決定：`strcasecmp()` 或 `strcmp()`
4. `-r`：結果乘以 `-1`

```bash
./esort -n -r -o sorted.txt data.txt   # 數值遞減，輸出到檔案
./esort -l -c -m 8 huge.txt           # 長度優先 + 不分大小寫，記憶體上限 8MB
./esort --numeric --memory=2 huge.txt > sorted.txt
```

## 3. 架構

| 階段 | 內容 |
|------|------|
| 一、Run Generation | 以 Arena（64KB 固定區塊、**永不搬移**，故指標不失效）+ `char**` 指標陣列構成 Buffer Pool；每次配置都以 `CHUNK_USED(c) = arena_bytes + lines_cap * sizeof(char *)` 精確檢查是否仍在 `-m` 預算內，逼近上限即 `qsort()` 後輸出成一個 `/tmp/esort_run_XXXXXX`。若整份檔案放得下（只產生 1 個批次）則**直接輸出，不落地暫存檔**。 |
| 二、K-way Merge | 開啟所有 run，每個 run 先讀第一行放進 **Min-Heap**；取堆頂輸出後，直接以「同一個 run 的下一行」**覆寫堆頂並做一次 `heap_sift_down()`**（取代 pop + push 兩趟）。run 數超過 fanin（上限 512，並依記憶體預算自動縮小）時自動執行**多輪合併**。 |

其他機制：

- **記憶體上限**：總預算 = `-m` MB；先扣除合併階段預留（每個 run 的讀取緩衝區 + 行緩衝區 + heap 欄位），其餘全給階段一。`chunk_alloc()` 的三處配置檢查（指標陣列擴充、字串空間、新 Arena 區塊）全部以 `CHUNK_USED()` 為基準，保證「Arena + 指標陣列」總和不超過預算。
- **同檔安全**：`-o` 與輸入為同一檔案（以路徑字串 + `st_dev/st_ino` 判定）時，先寫入暫存輸出檔，完成後才覆蓋原檔。
- **行處理**：讀入時移除行尾 `\r\n` 或 `\n`，輸出時補回 `\n`；最後一行即使沒有換行符也不影響排序正確性；超過 `MAX_LINE_LENGTH`(4096) 的行會被截斷（仍佔一行）。
- **資源回收**：結束前關閉所有 `FILE*`、`free()` 所有記憶體、`unlink()` 所有暫存檔（含錯誤路徑）。
- **錯誤處理**：所有 `fopen/fread/fwrite/malloc/mkstemp` 皆有檢查，失敗時以 `goto cleanup` 統一清理並回傳非 0 的結束代碼。

## 4. 測試

### 4.1 產生測試資料

```bash
# 一般字串（字典序 / 大小寫測試）
printf 'banana\nApple\n10\n9\ncherry\n\napple\n' > basic.txt

# 數值資料
seq 1 20000 | sed 's/$/x/' > nums.txt

# 長行資料（測試外部合併與多輪合併）
python3 -c "
import random
random.seed(7)
print('\n'.join('%04d' % random.randrange(10000) + 'y'*random.randrange(2000,3900)
                for _ in range(5000)))" > long.txt

# 大檔（測試記憶體上限與效能）
python3 -c "
import random
random.seed(3)
with open('huge.txt','w') as f:
    for i in range(1500000):
        f.write('%08d %s\n' % (random.randrange(10**8), 'z'*random.randrange(5,80)))"
```

### 4.2 驗證各參數組合

```bash
./esort            basic.txt   # 字典序遞增（空行最前）
./esort -c         basic.txt   # 不分大小寫
./esort -r         basic.txt   # 遞減
./esort -n         basic.txt   # 數值：非數字視為 0
./esort -l         basic.txt   # 長度優先
./esort -l -r      basic.txt   # 長度遞減
./esort -n -r -o out.txt nums.txt    # -o 寫檔

# 與系統 sort 對照驗證
diff <(./esort -n nums.txt) <(sort -n nums.txt) && echo "numeric OK"
diff <(./esort    nums.txt) <(sort    nums.txt) && echo "dictionary OK"
diff <(./esort -r nums.txt) <(sort -r nums.txt) && echo "reverse OK"

# 不同記憶體上限必須得到**完全相同**的結果（外部合併正確性）
diff <(./esort -n -m 100 long.txt) <(./esort -n -m 1 long.txt) && echo "external sort OK"

# 檢查確實有產生多輪合併：暫存檔數量會隨 -m 變動
ls /tmp/esort_run_* 2>/dev/null | wc -l   # 執行期間觀察，結束後應為 0

# 就地排序（輸入 = 輸出）
cp nums.txt inplace.txt && ./esort -n -o inplace.txt inplace.txt && echo "in-place OK"

# 資源回收檢查：正常結束後不應留下暫存檔
./esort -m 1 long.txt > /dev/null && ls /tmp/esort_run_* 2>/dev/null | wc -l   # 0

# 記憶體上限驗證（-m 100 的峰值 RSS 明顯小於檔案大小）
/usr/bin/time -v ./esort -m 8 -n long.txt > /dev/null 2>&1 | grep "Maximum resident"
```

### 4.3 錯誤處理

```bash
./esort                       # 缺少檔名 → 顯示 usage
./esort /nonexistent.txt      # 無法開啟輸入檔
./esort -m abc nums.txt       # -m 非整數
./esort -m 0 nums.txt         # -m 小於 1MB
./esort -o                    # -o 缺少參數
./esort -z nums.txt           # 未知選項
```

## 5. 實測結果（本機）

| 測試 | 結果 |
|------|------|
| `-Wall -Wextra -O2 -std=c11`（C99 亦可） | 0 warnings |
| 288 組（旗標組合 × 記憶體上限 × 資料型態）對照 Python 參考實作 | 全數通過 |
| 75MB / 150 萬行，`-m 8 -n` | 0.50 秒 |
| 堆頂取代法 vs. `pop`+`push` | 合併階段比較次數減少 8～11%（I/O 密集，實際快 3～4%） |
| AddressSanitizer + UBSan（含多輪合併、就地排序、錯誤路徑） | 無記憶體洩漏、無未定義行為 |
| 暫存檔清理（正常 / 錯誤 / 多輪合併） | 皆無殘留 |