# Source business metadata: SV_DWH_KPI_MOIS_GROUPE

These instructions and verified queries are preserved for review. They are not executed by Power BI.

## sql_generation

- COUNTRY_CODE contains entity codes: KE, KM, KSI, LOCA (French specialties), DE, DK, ES, IT, PL, PT (international). No 'FR' code. - 'France' without specialty → COUNTRY_CODE IN ('KE','KM','KSI','LOCA')
- RATIO METRICS (tariff_index, occupancy_rate, rotation, failure_rate, control_rate, unavailability_rate, objective_turnover_rate) are NOT additive. Grand total = recompute from SUM(base_measures), NOT from AVG of ratios. - OBJECTIVES vs ACTUALS are on DIFFERENT rows (sparse model): - OBJECTIVE_TURNOVER (KPI_OBJ_CA_FAMILLE_DEV) is stored on rows where FAMILY_CODE_2 is populated (not 'ND') but RACINE_CODE='ND'. - Objectives are defined at BRANCH x FAMILY_CODE_2 x MONTH granularity ONLY. There is NO finer breakdown (no FAMILY_CODE_3, no RACINE_CODE level). Do NOT attempt to filter objectives by FAMILY_CODE_3 or RACINE_CODE. - Objectives cover TOTAL turnover (rental + services), not just rental. - To compute achievement rates, you MUST use separate CTEs or subqueries with DIFFERENT WHERE clauses: - Actuals CTE: SUM(turnover) with NO filter on family_code_2 or racine_code (sum ALL rows for the period/country/branch) - Objectives CTE: SUM(objective_turnover) WHERE family_code_2 <> 'ND' AND racine_code = 'ND' - Then JOIN the two CTEs and divide: actuals / objectives ❌ NEVER apply the objective filters (family_code_2 <> 'ND' AND racine_code = 'ND') to queries selecting turnover - this will exclude most actual revenue data!- When user asks 'objective' or 'target' or 'budget' → use OBJECTIVE_TURNOVER (always at FAMILY_CODE_2 level). - When user asks 'taux d'atteinte' or 'achievement rate' → use OBJECTIVE_TURNOVER_RATE metric. - FAMILY_CODE_1 labels: do NOT hardcode family names in SQL output. ALWAYS join to V_FAMILLE_GROUPE_N1 on FAMILY_CODE_1 = CODE_FAMILLE_GROUPE_1 to get the label in the user's language. For filtering by family name (e.g. 'Terrassement', 'Élévation'), join V_FAMILLE_GROUPE_N1 and filter on the appropriate label column. - CRITICAL: 'Other Specialties' or 'Autres Spécialités' = FAMILY_CODE_1 = 'G' ONLY. Do NOT use NOT IN ('A','B','C','D','E','F') or any catch-all logic. Non-rental codes (90, 51, 53, 54, X, N, ND, Z) are NOT part of 'Other Specialties'.
- ROTATION FORMULA (MANDATORY): Rotation = 12 × SUM(KPI_CA_LOCATION_HT_DEV) / SUM(KPI_STKQTETOT_VI_DEV). The denominator MUST be STOCK_TOTAL (KPI_STKQTETOT_VI_DEV), NOT stock in rental (KPI_STKQTELOU_VI_DEV). Using stock in rental gives a value ~2x too high. The result is a coefficient (e.g. 0.22 = 22%). Multiply by 100 only if displaying as percentage. For LTM rotation: SUM(KPI_CA_LOCATION_LTM_HT_DEV) / SUM(KPI_STKQTETOT_VI_LTM_DEV). Always use the pre-defined metrics ROTATION_12_MONTHS_EQUIVALENT or ROTATION_LTM. - CURRENCY & MULTI-COUNTRY QUERIES: All monetary columns (_DEV suffix) are in LOCAL currency (EUR for DE/ES/IT/KE/KM/KSI/LOCA, DKK for DK, PLN for PL). When a query involves MULTIPLE countries, ALWAYS convert to EUR. Join DWHP.INTER.DWH_PAYS p ON p.PAYCOD = k.PAYCOD AND p.LNGCOD = '002', then join DWHP.INTER.DWH_DEVISE d ON d.PAYCOD = k.PAYCOD AND d.CODE_DEVISE_ORIGINE = p.CODE_DEVISE AND d.CODE_DEVISE_DESTINATION = 'EUR' AND d.TYPE_CONVERSION = 'Annuel'. Then use SUM(monetary_column * d.TAUX) for EUR values. For EUR countries d.TAUX = 1.0 so no impact. Non-monetary KPIs (quantities, rates, percentages) do NOT need conversion. Label columns '(EUR)'. - FAMILY LABELS (MULTILINGUAL - 3 LEVELS): Three dimension tables provide family labels at each hierarchy level: - V_FAMILLE_GROUPE_N1: level 1 labels (gamme). Joined on FAMILY_CODE_1. Always available, even for objectives.
- V_FAMILLE_GROUPE_N2: level 2 labels (sous-famille). Joined on FAMILY_CODE_1 + FAMILY_CODE_2. Always available, even for objectives. - V_FAMILLE_GROUPE_N3: level 3 labels (sous-sous-famille). Joined on FAMILY_CODE_1 + FAMILY_CODE_2 + FAMILY_CODE_3. NOT available for objectives (FAMILY_CODE_3='ND'). Use the label columns matching the user question language: - French: FAMILY_LABEL_FR_1 / _2 / _3 - English: FAMILY_LABEL_EN_1 / _2 / _3 - German: FAMILY_LABEL_DE_1 / _2 / _3 - Spanish: FAMILY_LABEL_ES_1 / _2 / _3 - Italian: FAMILY_LABEL_IT_1 / _2 / _3 - Polish: FAMILY_LABEL_PL_1 / _2 / _3 - Portuguese: FAMILY_LABEL_PT_1 / _2 / _3 - Danish: FAMILY_LABEL_DA_1 / _2 / _3 When showing family data, ALWAYS include both the code (FAMILY_CODE_n) and the label (FAMILY_LABEL_{LANG}_n) in the appropriate language. Default to French labels if language cannot be determined. - FAMILY_CODE columns exist ONLY on DWH_KPI_MOIS_GROUPE. V_PRODUCT does NOT carry family codes. - PRODUCT NAMES (MULTILINGUAL): Product names are available in 8 languages via V_PRODUCT_LIB (joined on RACINE_CODE = PRODUCT_CODE). Language selection rules: 1. If the user explicitly requests a specific language for the label (e.g. 'show me the product name in German', 'give me the label in Italian'), use that requested language regardless of the question language. 2. Otherwise, use the column matching the user question language. 3. Default to English (PRODUCT_NAME_EN) if the language cannot be determined. Available columns: French=PRODUCT_NAME_FR, English=PRODUCT_NAME_EN, German=PRODUCT_NAME_DE, Spanish=PRODUCT_NAME_ES, Italian=PRODUCT_NAME_IT, Polish=PRODUCT_NAME_PL, Portuguese=PRODUCT_NAME_PT, Danish=PRODUCT_NAME_DA. When showing product data, ALWAYS include both the RACINE_CODE and the product name in the appropriate language.
- LTM METRICS ARE SEMI-ADDITIVE: KPI_CA_LOCATION_LTM_HT_DEV and KPI_STKQTETOT_VI_LTM_DEV already contain rolling 12-month totals and are POINT-IN-TIME values. NEVER SUM them across multiple months — this double-counts. When a user asks for an LTM indicator for a year or period, filter on the LAST YEAR_MONTH of that period only. Examples: CA LTM 2025 means WHERE YEAR_MONTH = '202512'. CA LTM Q1 2025 means WHERE YEAR_MONTH = '202503'. Rotation LTM mars 2025 means WHERE YEAR_MONTH = '202503'. This applies to metrics TOTAL_TURNOVER_RENTAL_LTM, ROTATION_LTM, and fact TURNOVER_RENTAL_LTM.

## question_categorization

- If user asks for stock or occupancy rate without specifying unit, ask: IV or quantity?
- IV/valued/euros → STOCK_IV or OCCUPANCY_RATE_IV
- quantity/units/qty → STOCK_QTY or OCCUPANCY_RATE
- If user asks 'objectif' or 'budget' → use OBJECTIVE_TURNOVER (granularity: branch x FN2 x month)

## Verified queries

### "Stock en quantite ELE18E Italie 2025"

**Question:** Quel est le stock en quantité de l'ELE18E en Italie sur l'année 2025 ?

```sql
SELECT SUM(k.stock_qty) / NULLIF(COUNT(DISTINCT k.year_month), 0) AS stock_qty_2025 FROM dwh_kpi_mois_groupe AS k WHERE k.country_code = 'IT' AND k.racine_code = 'ELE18E' AND k.year_month >= '202501' AND k.year_month <= '202512'
```

### "Index tarifaire Pologne familles ABDEFG jan-mai 2026"

**Question:** Donnes moi l'index tarifaire de la Pologne uniquement pour les familles A, B, D, E, F et G, de janvier a mai 2026 ?

```sql
WITH base_metrics AS ( SELECT family_code_1, SUM(stock_rental_vi) AS stock_rental_vi_sum, SUM(turnover_rental_tariff_index) AS tariff_index_sum FROM dwh_kpi_mois_groupe
WHERE country_code = 'PL' AND year_month >= '202601' AND year_month <= '202605' AND family_code_1 IN ('A', 'B', 'D', 'E', 'F', 'G') GROUP BY family_code_1 ), family_metrics AS ( SELECT family_code_1, ROUND( (1000 * tariff_index_sum) / NULLIF(NULLIF(stock_rental_vi_sum, 0), 0), 2 ) AS tariff_index, stock_rental_vi_sum, tariff_index_sum
FROM base_metrics ) SELECT family_code_1, tariff_index FROM family_metrics UNION ALL SELECT 'TOTAL' AS family_code_1, ROUND( (1000 * SUM(tariff_index_sum)) / NULLIF(NULLIF(SUM(stock_rental_vi_sum), 0), 0), 2 ) AS tariff_index FROM family_metrics ORDER BY CASE WHEN family_code_1 = 'TOTAL' THEN 1 ELSE 0 END, family_code_1
```

### "CA par famille de niveau 2"

**Question:** Quel est le CA par famille de niveau 2 ?

```sql
SELECT k.family_code_1, f1.family_label_fr_1, k.family_code_2, f2.family_label_fr_2, SUM(k.turnover) AS total_turnover FROM dwh_kpi_mois_groupe AS k JOIN v_famille_groupe_n1 AS f1 ON k.family_code_1 = f1.code_famille_groupe_1 JOIN v_famille_groupe_n2 AS f2 ON k.family_code_1 = f2.code_famille_groupe_1 AND k.family_code_2 = f2.code_famille_groupe_2
WHERE k.family_code_2 <> 'ND' GROUP BY k.family_code_1, f1.family_label_fr_1, k.family_code_2, f2.family_label_fr_2 ORDER BY k.family_code_1, k.family_code_2
```

### "Quel est le CA et l'objectif de la pologne en juillet 2026 ?"

**Question:** Quel est le CA et l'objectif de la pologne en juillet 2026 ?

```sql
SELECT * FROM SEMANTIC_VIEW( DWHP.GROUPE.SV_DWH_KPI_MOIS_GROUPE METRICS SUM(dwh_kpi_mois_groupe.turnover) AS total_turnover, SUM(dwh_kpi_mois_groupe.objective_turnover) AS total_objective DIMENSIONS dwh_kpi_mois_groupe.country_code, dwh_kpi_mois_groupe.year_month WHERE dwh_kpi_mois_groupe.country_code = 'PL' AND dwh_kpi_mois_groupe.year_month = '202607' )
/* Generated by Cortex Analyst (request_id: a3eae648-d6a1-44ae-b6bd-6516385f7e4e) */
```
