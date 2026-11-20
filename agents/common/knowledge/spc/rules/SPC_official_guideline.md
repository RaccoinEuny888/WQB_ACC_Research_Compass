以下為將上述 SPC 官方指南（Guideline）完整翻譯成的英文版本：

---

### **Official Guidelines for SPC (Systematic Predictions Challenge 2026)**

#### **1. Eligibility & Basic Rules**

* **Participant Status:** Participants must be engaged by WorldQuant, LLC (or its affiliates) as a research consultant or service provider (including those conditionally approved) on or before **July 7, 2026**, and must be at least 18 years of age.
* **No Long-Short Neutrality Constraint:** This competition completely removes the strict long-short neutrality constraint typically required in regular BRAIN Alpha research. Your prompt portfolio can be **long-only**, **short-only**, or a **free mix of long and short positions**.
* **Crucial Platform Limitation (No Editing or Permanent Deletion):** Once a prompt is submitted on the platform, **its text content cannot be edited, nor can it be permanently deleted**. If you lose conviction in a prompt or wish to "remove" it in the future, the only way to do so is to **reset its Prompt Weight to 0 on the submission page**.

#### **2. Portfolio & Coverage Goals**

* **Overall Goal:** By submitting multiple prompts, you are building a "Portfolio of Prompts." Your collective objective is to cover **at least 500 unique instruments (stocks)** across your entire set of prompts to ensure adequate diversification.
* **Recommended Coverage per Prompt:** Large Language Models (LLMs) operate under a limited context window. Forcing a single prompt to analyze too many stocks (e.g., 500 stocks at once) will dilute the LLM's analytical capacity and web-search efficiency.
* **The Best Practice:** It is highly recommended to **target around 50 stocks per individual prompt**. You can then easily reach the 500+ stock target by submitting multiple diverse prompts (e.g., 10 different prompts with different themes).

#### **3. Strict Output Format Specifications**

To enable daily simulated P&L tracking, the LLM prompt's final output must be a **clean, raw JSON object without any conversational filler or prose**.

* **Structure:** `{"ISIN|MIC": Confidence Score}`
* **ISIN** (International Securities Identification Number) and **MIC** (Market Identifier Code) must be used as the key, connected by a vertical bar `|`.


* **Numerical Values:** * A **positive score** (e.g., `0.060`) represents **long conviction**.
* A **negative score** (e.g., `-0.040`) represents **short conviction**.
* The absolute value represents the strength of conviction. Instruct the model to assign differentiated scores based on its analysis; **do not use an equal-weighted distribution**.


* **Format Locking Hint:** Always add a strict instruction at the end of your prompt, such as: *"Output ONLY the raw JSON object. Do not include any conversational filler, markdown formatting (like ```json), or explanatory prose."*

#### **4. Guidelines for Building Robust Prompts (Do's & Don'ts)**

* **DO:**
* **Assign a Role and Task:** Give the LLM a clear expert persona (e.g., "Forensic Accounting Analyst") and provide a highly disciplined step-by-step logical workflow.
* **Specify Web Search:** Explicitly instruct the model to search the web for current financial facts, filings, and news. Without web search, the LLM will rely on its pre-training cutoff data (prior to Q1 2026), making your signals pure noise.
* **Implement a Bull vs. Bear Gate:** Direct the model to argue both sides (the bull case and the bear case) before committing to a position, ensuring rigorous counter-argument verification.
* **Optimize Context via Pre-compiled Lists (Chain of Prompts):** You can use a separate prompt in a clean chat window to fetch the exact `ISIN|MIC` identifiers for your target universe (e.g., the top 60 names in the MSCI World index). Then, **copy and paste those identifiers directly into your final prompt**. This saves valuable tokens from being wasted on identifier mapping, letting the model spend 100% of its capacity on deep fundamental reasoning.


* **DON'T:**
* **Avoid Vague Requests:** Never use ambiguous instructions like *"find good stocks with strong earnings"* without providing specific quantitative criteria or underlying mechanisms.
* **Do Not Rely on Model Memory:** Never trust memorized historical numbers; ensure the LLM verifies facts through valid sources (like SEC filings).
* **Do Not Submit Without Testing:** Test your final prompts multiple times in clean chat windows to ensure the JSON output is perfectly structured and repeatable every single run.



#### **5. Weight Allocation Framework across Prompts**

When managing multiple submitted prompts on the platform, you must assign weights to each prompt. Rather than applying simple equal-weighting, utilize the three-factor framework ($\text{Weight} \propto \text{Edge} \times \text{Repeatability} \times \text{Diversification}$):

1. **Edge:** Allocate higher weights to prompts built on a deeply understood and solid economic thesis.
2. **Repeatability (Regime Independence):** * Prompts that are expected to deliver steady results irrespective of the economic regime should get stable, consistent weights.

* For prompts that are highly regime-dependent (e.g., thematic or sector-specific ideas), actively dial up the weight when the macro environment is favorable, and dial it down to zero or low levels when conditions worsen.

3. **Diversification (Uniqueness):** Uniqueness is key. Allocate higher weights to prompts that leverage lesser-known, non-consensus ideas to differentiate your portfolio from the crowd.

Here is the English version of those two specific sections:

### **Advanced Tip: Pre-compiled Universe List (Token-Saving Secret)**

* **The Challenge:** LLM models consume a significant amount of tokens and computing resources when they have to browse the web just to find and map out the exact `ISIN` and `MIC` identifiers for a general list of stocks.
* **The Strategy (Tip):** You can run a separate, preliminary prompt in a clean chat window first, asking the LLM to search the web and output *only* the `ISIN|MIC` identifiers for your target universe (e.g., the top 60 companies in the MSCI World Index).
* **The Action:** Once you have that list, **copy and paste those exact identifiers directly into your final prompt** as the input dataset, and instruct the model to perform the core fundamental or red-flag analysis directly on these pre-defined assets.
* **The Benefit:** This effectively saves the final prompt from wasting its context window on identifier searches, allowing the LLM to dedicate 100% of its reasoning capacity to deep investment analysis, resulting in a much more robust signal.
