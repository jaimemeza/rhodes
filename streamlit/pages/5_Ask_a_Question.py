import json

import pandas as pd
import streamlit as st

from utils.snowflake import get_snowflake_connection, CORTEX_MODEL
from utils.queries import (
    fetch_region_year,
    fetch_pipeline_by_region,
    fetch_channel_economics,
    fetch_consultant_performance,
)

st.set_page_config(page_title="Ask a Question · Rhodes", layout="wide")

GREEN      = "#5a8c3e"
SURFACE    = "#f5f5f7"
TEXT       = "#1c1c1e"
TEXT_MUTED = "#6e6e73"

st.title("Ask a Question")
st.caption(
    "Ask anything about Rhodes Homes sales performance. "
    "Answers are grounded in data from the analytics warehouse — "
    "the model sees the actual numbers, not just general knowledge."
)

# ── Data ───────────────────────────────────────────────────────────────
conn          = get_snowflake_connection()
region_df     = fetch_region_year(conn)
pipeline_df   = fetch_pipeline_by_region(conn)
channel_df    = fetch_channel_economics(conn)
consultant_df = fetch_consultant_performance(conn)

for label, frame in [
    ("region_year", region_df),
    ("pipeline", pipeline_df),
    ("channel_economics", channel_df),
    ("consultant_performance", consultant_df),
]:
    if frame.empty:
        st.error(f"No data returned from {label}.")
        st.stop()

curr_year   = int(region_df["contract_year"].max())
curr_region = region_df[region_df["contract_year"] == curr_year]


# ── Helpers ────────────────────────────────────────────────────────────
def _pct(v, signed=False) -> str:
    try:
        val = float(v) * 100
        return f"{val:+.1f}%" if signed else f"{val:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


# ── Context builder ────────────────────────────────────────────────────
REGION_KEYS  = {
    "coastal bend", "cb", "south texas", "stx", "rio grande", "rgv",
    "decline", "declining", "drop", "region", "regional",
    "target", "attainment", "yoy", "year over year", "margin",
}
CHANNEL_KEYS = {
    "channel", "commission", "buyer", "source", "walk", "online",
    "referral", "broker", "cancel", "cancellation", "acquisition",
}
CONSULT_KEYS = {
    "consultant", "rep", "salesperson", "who", "top",
    "performer", "leaderboard", "best", "worst", "staff",
}


def build_context(question: str) -> tuple[str, str]:
    q     = question.lower()
    parts = []
    labels = []

    # Always: compact region summary
    lines = [f"REGION SUMMARY ({curr_year} YTD):"]
    for _, r in curr_region.iterrows():
        lines.append(
            f"  {r['region']}: {int(r['contracts_closed'])} closings, "
            f"YoY {_pct(r['same_period_yoy_pct'], signed=True)}, "
            f"cancel {_pct(r['cancel_rate'])}, "
            f"target attainment {_pct(r['target_attainment_ytd_pct'])} "
            f"({int(r['contracts_closed'])} of {int(r['sales_target_units'])} units)"
        )
    parts.append("\n".join(lines))
    labels.append("Region summary")

    # Always: pipeline
    pipe_lines = ["ACTIVE PIPELINE:"]
    for _, p in pipeline_df.iterrows():
        pipe_lines.append(
            f"  {p['region']}: {int(p['pipeline_contracts'])} pipeline contracts "
            f"(${p['pipeline_value']/1_000_000:.1f}M), "
            f"{int(p['closed_contracts'])} closed YTD "
            f"(${p['closed_value']/1_000_000:.1f}M revenue)"
        )
    parts.append("\n".join(pipe_lines))
    labels.append("Pipeline")

    # Region detail
    if any(k in q for k in REGION_KEYS):
        detail = [f"REGION DETAIL ({curr_year}):"]
        for _, r in curr_region.iterrows():
            detail.append(
                f"  {r['region']}: target={int(r['sales_target_units'])} units, "
                f"closed={int(r['contracts_closed'])}, "
                f"prior_year_same_period={int(r['same_period_closed_prior_year'])}, "
                f"cancel={_pct(r['cancel_rate'])}, "
                f"margin_vs_target={_pct(r['margin_attainment_delta'], signed=True)}, "
                f"avg_price=${r['avg_contract_price']/1000:.0f}k"
            )
        parts.append("\n".join(detail))
        labels.append("Region detail")

    # Channel economics
    if any(k in q for k in CHANNEL_KEYS):
        ch = channel_df.sort_values("cancel_rate", ascending=False)
        ch_lines = ["CHANNEL ECONOMICS (by cancel rate):"]
        for _, c in ch.iterrows():
            ch_lines.append(
                f"  {c['buyer_source']}: {int(c['contracts'])} contracts, "
                f"cancel {_pct(c['cancel_rate'])}, "
                f"commission {_pct(c['avg_commission_rate'])}, "
                f"revenue ${c['total_contract_value']/1_000_000:.1f}M"
            )
        parts.append("\n".join(ch_lines))
        labels.append("Channel economics")

    # Consultant leaderboard
    if any(k in q for k in CONSULT_KEYS):
        top10 = consultant_df.head(10)
        cons_lines = [f"TOP 10 CONSULTANTS (by total closings):"]
        for _, c in top10.iterrows():
            cons_lines.append(
                f"  {c['sales_consultant']}: {int(c['closed_contracts'])} total, "
                f"{int(c['closed_current_year'])} in {curr_year}, "
                f"cancel {_pct(c['cancel_rate'])}, "
                f"{int(c['regions_worked'])} region(s)"
            )
        parts.append("\n".join(cons_lines))
        labels.append("Consultants")

    return "\n\n".join(parts), " + ".join(labels)


# ── Cortex caller ──────────────────────────────────────────────────────
def ask_cortex(question: str, context: str) -> str:
    system = (
        "You are a data analyst for Rhodes Homes, a residential home builder "
        "in South Texas. Answer the user's question using ONLY the provided "
        "data context. Be concise, cite specific numbers, and flag clearly if "
        "the data does not support the question."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user",
         "content": f"DATA CONTEXT:\n{context}\n\nQUESTION: {question}"},
    ]
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, PARSE_JSON(?))",
            (CORTEX_MODEL, json.dumps(messages)),
        )
        row = cur.fetchone()
        if not row:
            return "No response received from the model."
        raw = row[0]
        if isinstance(raw, str):
            try:
                return json.loads(raw)["choices"][0]["message"]["content"]
            except Exception:
                return raw
        return str(raw)
    except Exception as exc:
        return f"Cortex error: {exc}"
    finally:
        cur.close()


# ── Suggested questions ────────────────────────────────────────────────
SUGGESTIONS = [
    "Which region is on track to hit its annual target?",
    "Which acquisition channel has the best quality vs. commission cost?",
    "Who are the top 3 consultants by YTD closings?",
    "Why is Coastal Bend underperforming compared to last year?",
    "What does the pipeline look like going into Q4?",
    "Which channel should we reconsider based on cancel rate and cost?",
]

st.markdown(
    f'<div style="font-size:13px; color:{TEXT_MUTED}; '
    f'margin-bottom:8px;">Suggested questions</div>',
    unsafe_allow_html=True,
)
sug_cols = st.columns(3)
triggered = None
for i, s in enumerate(SUGGESTIONS):
    with sug_cols[i % 3]:
        if st.button(s, use_container_width=True, key=f"sug_{i}"):
            triggered = s

st.divider()

# ── Free-text input ────────────────────────────────────────────────────
custom = st.text_area(
    "Or type your own question",
    height=80,
    placeholder="e.g. Which region has improved the most year over year?",
)
ask_clicked = st.button("Ask →", type="primary", disabled=not custom.strip())

question_to_ask = triggered or (custom.strip() if ask_clicked else None)

# ── Answer ─────────────────────────────────────────────────────────────
if question_to_ask:
    context_block, context_desc = build_context(question_to_ask)
    with st.spinner("Querying Cortex…"):
        answer = ask_cortex(question_to_ask, context_block)

    st.markdown(
        f'<div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:4px;">'
        "Question</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="background:{SURFACE}; border-radius:8px; '
        f'padding:12px 14px; font-size:15px; color:{TEXT}; '
        f'margin-bottom:16px;">{question_to_ask}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:4px;">'
        "Answer</div>",
        unsafe_allow_html=True,
    )
    st.markdown(answer)

    with st.expander(f"Data context · {context_desc}", expanded=False):
        st.code(context_block, language="text")
