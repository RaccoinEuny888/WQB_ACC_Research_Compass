GA Template 設計：將 Alpha 拆成四個可管理模組
在 GA template 設計上，我不希望 alpha expression 只是隨機堆疊 operators。為了讓 search space 更可控、可解釋，也更容易擴張，我將一個 alpha 的生成過程拆成四個主要模組：資料清洗、訊號提取、時序平滑與組內處理，並且我會將單一模組依照功能分成不同 subgroup，而不是讓 GA 任意選擇所有 operator。

Raw Data
  → 資料清洗 Data Cleaning
  → 訊號提取 Signal Extraction
  → 時序平滑 Signal Smoothing
  → 組內處理 Group Operation
  → Final Alpha
資料清洗 Data Cleaning
資料清洗是整個 pipeline 的第一步，目標是將原始 data field 轉換成適合後續建模與比較的輸入。對 GLB region 來說，這一步特別重要，因為原始資料可能同時包含 missing value、不同更新頻率、不同國家 coverage 差異、不同幣值單位，以及公司規模造成的 scale effect。

missing value handling
backfill / group_backfill
除以 cap / assets / sales
winsorization
rank / zscore preprocessing
abnormal value replacement
訊號提取 Signal Extraction
訊號提取的目標，是從處理後的資料中抽取具有經濟意義的 alpha feature。這一步可以是 level signal、change signal、spread signal、freshness signal，也可以是 volatility、entropy 或 acceleration 類型的轉換。

除了 Brain 內建 operators，我也額外設計多種 custom operators，例如 spread、difference、gap、acceleration、entropy delta 等。這些 operators 可以增加 alpha expression 的多樣性，同時保留明確的 signal transformation 意義。

時序平滑 Signal Smoothing
時序平滑模組主要用來控制 signal noise 與 turnover。較快的 smoothing 可以保留近期資訊，但可能導致 turnover 偏高；較慢的 smoothing 可以提升穩定性，但也可能稀釋 signal。

組內處理 Group Operation
組內處理是 GLB alpha 中非常重要的一步。由於 GLB 包含多個國家與市場，若不做適當的 group operation，alpha 很容易變成 country bet 或 region bet。因此我會大量使用 country、industry、subindustry、sector 等 group-level transformation，讓 signal 更集中在 stock-level relative value，而不是不同國家之間的結構性差異。

Operator Subgroup 管理：避免隨機堆 operator
在每一個模組中，我都會先按照 operator 的功能建立 subgroup。例如 smoothing 類 operator 會被分成 fast smoothing、slow smoothing、decay-based、turnover-targeted 等；group operation 也會被分成 standardization、aggregation、projection、multi-factor transformation 等。這樣做的目的，是讓 GA 在搜尋時仍然保留結構，而不是把所有 operators 混在一起隨機組合。

每個 operator 會先依照功能分類，再被放入對應的 alpha template step。這種設計讓 GA search space 更可控，也讓後續分析每個 alpha 的來源更容易。

另外，我在每一個 operator subgroup 中都加入了 identity。這個 operator 代表「不做任何轉換」，目的是讓 GA 有機會跳過某些步驟。

例如某些 signal 本身已經足夠乾淨，可能不需要額外 smoothing；某些資料在前處理後已經具備良好的 cross-sectional structure，也可能不需要再做複雜轉換。加入 identity 可以避免 template 強迫 data 經過不必要的 operator。

 

Scorer設計：如何判斷 alpha 是否值得留下
相比 USA 和 EUR，GLB region 多了 subregion sharpe 的限制。這代表一個 GLB alpha 不能只在單一 universe 表現好，也必須在不同地區或子 universe 中維持一定的穩定性。
因此，如何判斷一個 alpha 是否有潛力進入下一輪 GA，成為 GLB research pipeline 中非常重要的一步。

在我的流程中，每一代 GA 完成後，我會先用一個非常嚴格的 scorer 對所有 alpha 做初步篩選。這個 scorer 不只檢查 Sharpe 和 Fitness，也包含所有 submission-related checks，例如 subuniverse sharpe、subregion sharpe、concentrated weight、robust universe sharpe 等。



除了 Brain 本身的提交門檻，我也加入了一些自訂規則，例如更低的 turnover 上限、long-short balance 等。這些規則的目的，是在 alpha 進入下一代 GA 之前先排除掉不穩定、交易成本過高或多空結構不健康的 candidate。

Self-Correlation 與 Prod-Correlation 過濾
通過 scorer 並不代表 alpha 可以直接生成下一代alpha。下一步我會進行 self-correlation 與 prod-correlation 過濾來決定下一代的parent alpha。

Self-correlation 的目的是避免同一個 research 中產生大量高度相似的 alpha；prod-correlation 則是確認 alpha 是否具有足夠的獨特性，避免與既有 production alpha 過度重疊。

 

Simulation 管理：同時最大化一般 Alpha 與 Super Alpha 的資源利用
上述流程並不只適用於 GLB region，而是我在所有 region 中都會使用的標準 research pipeline。即使只針對 GLB 進行搜尋，這套流程也已經足以每天產生大量可提交的 alpha candidates。因此，在 simulation 管理上，我的優化重點不是如何產生更多一般 alpha，而是如何更有效率地利用所有可用的 simulation slots。

一般 alpha 和 super alpha 的 simulation slots 是分開計算的，因此理論上可以同時跑滿 8 個一般 alpha simulations 與 3 個 super alpha simulations。基於這一點，我將 worker 改成可以同時處理兩種 simulation 任務的模式，使一般 alpha 與 super alpha 的資源能夠並行使用。

這樣做的好處是，即使某段時間沒有新的 regular alpha idea，也不會讓 simulation resource 閒置。我可以讓 worker 繼續執行 super alpha simulations，持續探索既有 alpha 的組合與擴張機會。換句話說，simulation management 的目標不是單純把某一類任務跑滿，而是讓 regular alpha production 與 super alpha exploration 同時維持運轉。