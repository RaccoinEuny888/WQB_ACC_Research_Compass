# GA 設定的兩個提醒

> 來源：`[L] 強勢基因: Trade off between diversity and quality`（TW77745 原文；YW42946、KK82709 回覆）。
> 用在 `/templatize` 印出 GA 指令時，給使用者看 ga_config 該注意什麼。

## 1. `bcorr_threshold`＝每代的 correlation reduction

GA 朝全局最優收斂時，會跳過很多「局部最優」，而局部最優對多樣性貢獻不小。解法是每一代結束時用 correlation 做 cluster，同一 cluster 只留表現最好的——這樣跟主流不同、但表現也不同的 alpha 不會在演化中被遺忘。
open machine 的 `ga_config` 裡 `bcorr_threshold`（預設 0.7）就是這個門檻：越低越強調多樣性、越高越強調單支成績。

## 2. 被強勢基因排擠的優良基因，切出來另跑

GA 初期常有一些不錯的基因被超強基因排擠掉。想保留它們，把這些基因切出來另外開一條 GA（例如把被排擠的 operator 或欄位固定住再跑一次），既保留基因也能提高 yield rate。
對應到我們的流程：同一張卡的 template 若某個基因位的選項從第 2 代起就沒再出現過，值得把它固定成單一選項另開一條研究線（研究名稱仍用 `<card_id>_<slug2>`，羅盤會連回同一張卡）。
