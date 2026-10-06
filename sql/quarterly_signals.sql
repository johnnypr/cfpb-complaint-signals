-- Quarterly complaint signals per company.  Inputs: complaints, complaint_topics, returns.
-- Parameters are substituted by the pipeline: {volume_start}, {volume_end}, {topic_start}, {topic_end}.

-- 1) Volume and service-quality metrics from ALL complaints (narrative or not)
CREATE OR REPLACE TABLE q_volume AS
SELECT
    ticker,
    CAST(date_trunc('quarter', date_received) AS DATE)            AS quarter,
    COUNT(*)                                                      AS n_complaints,
    COUNT(narrative)                                              AS n_narratives,
    AVG(CASE WHEN narrative IS NOT NULL THEN 1.0 ELSE 0.0 END)    AS narrative_share,
    AVG(CASE WHEN timely = 'No' THEN 1.0 ELSE 0.0 END)            AS untimely_share,
    AVG(CASE WHEN product ILIKE '%credit card%' THEN 1.0 ELSE 0.0 END)            AS credit_card_share,
    AVG(CASE WHEN product ILIKE '%money transfer%' OR product ILIKE '%virtual currency%'
             THEN 1.0 ELSE 0.0 END)                                               AS money_transfer_share,
    AVG(CASE WHEN product ILIKE '%checking or savings%' THEN 1.0 ELSE 0.0 END)    AS deposit_share
FROM complaints
WHERE date_received BETWEEN DATE '{volume_start}' AND DATE '{volume_end}'
GROUP BY 1, 2;

-- 2) Growth rates with window functions (YoY compares the same quarter a year earlier)
CREATE OR REPLACE TABLE q_growth AS
SELECT
    *,
    LN(n_complaints) - LN(LAG(n_complaints, 4) OVER w)  AS vol_yoy_log,
    LN(n_complaints) - LN(LAG(n_complaints, 1) OVER w)  AS vol_qoq_log
FROM q_volume
WINDOW w AS (PARTITION BY ticker ORDER BY quarter);

-- 3) Topic mix: average topic weight of the quarter's narratives
CREATE OR REPLACE TABLE q_topics AS
SELECT
    c.ticker,
    CAST(date_trunc('quarter', c.date_received) AS DATE) AS quarter,
    t.topic,
    AVG(t.weight)  AS topic_share,
    COUNT(*)       AS n_docs
FROM complaints c
JOIN complaint_topics_long t USING (complaint_id)
WHERE c.date_received BETWEEN DATE '{topic_start}' AND DATE '{topic_end}'
GROUP BY 1, 2, 3;

-- 3b) Share of each quarter's narratives that are copy-paste templates
CREATE OR REPLACE TABLE q_templates AS
SELECT
    c.ticker,
    CAST(date_trunc('quarter', c.date_received) AS DATE) AS quarter,
    AVG(CASE WHEN d.is_template THEN 1.0 ELSE 0.0 END)  AS template_share,
    COUNT(*)                                            AS n_docs
FROM complaints c
JOIN complaint_dominant d USING (complaint_id)
WHERE c.date_received BETWEEN DATE '{topic_start}' AND DATE '{topic_end}'
GROUP BY 1, 2;

-- 3c) Weekly counts (for event case studies), split into template vs other narratives
CREATE OR REPLACE TABLE weekly_volume AS
SELECT
    c.ticker,
    CAST(date_trunc('week', c.date_received) AS DATE)       AS week,
    COUNT(*)                                                AS n_complaints,
    COUNT(*) FILTER (WHERE d.is_template)                   AS n_template
FROM complaints c
LEFT JOIN complaint_dominant d USING (complaint_id)
WHERE c.date_received BETWEEN DATE '{volume_start}' AND DATE '{volume_end}'
GROUP BY 1, 2;

-- 4) Signal panel joined to stock returns: this quarter's signal vs NEXT quarter's excess return
CREATE OR REPLACE TABLE signal_panel AS
WITH r AS (   -- leads are computed on the full return history, so the last signal quarter still gets q+1
    SELECT ticker, quarter, ret, xret,
           LEAD(xret, 1) OVER (PARTITION BY ticker ORDER BY quarter) AS xret_next_q,
           -- skip a quarter: complaints are published with a lag, so q+2 is a stricter, tradable test
           LEAD(xret, 2) OVER (PARTITION BY ticker ORDER BY quarter) AS xret_q_plus_2
    FROM returns
)
SELECT
    g.*,
    r.ret  AS ret_same_q,
    r.xret AS xret_same_q,
    r.xret_next_q,
    r.xret_q_plus_2
FROM q_growth g
LEFT JOIN r ON r.ticker = g.ticker AND r.quarter = g.quarter;
