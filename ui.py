import streamlit as st
from main import graph
import time
import json
from fpdf import FPDF

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="AI Essay Writer",
    page_icon="📝",
    layout="wide",
)

# -----------------------------
# Custom CSS
# -----------------------------
st.markdown("""
<style>
div.block-container { padding: 2rem 4rem; }
h1, h2, h3, h4 { color: #1F2937; font-family: "Segoe UI", sans-serif; }
.stButton>button { background-color: #2563EB; color: white; font-weight: 600; border-radius: 6px; padding: 0.5rem 1.2rem; font-size: 1rem; }
.stButton>button:hover { background-color: #1D4ED8; }
.stProgress > div > div > div > div { background-color: #2563EB; }

/* Expander Header */
div[data-testid="stExpander"] > button {
    background-color: #2563EB !important;
    color: white !important;
    font-weight: 600;
    border-radius: 6px;
    padding: 0.5rem 1rem;
}

/* Expander Content */
div[data-testid="stExpander"] > div {
    background-color: #F3F4F6 !important;
    border-radius: 6px;
    padding: 1rem;
}

textarea { border-radius: 6px; padding: 0.5rem; border: 1px solid #D1D5DB; font-family: "Segoe UI", sans-serif; }
code, pre { background-color: #F9FAFB; border-radius: 6px; padding: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Header Section
# -----------------------------
st.title("AI Essay Writer Assistant")
st.markdown("Generate structured, well-formatted essays with sources.")
st.divider()

# -----------------------------
# Input Section
# -----------------------------
with st.container():
    st.subheader("Enter Your Essay Topic")
    topic_col, revision_col = st.columns([3, 1])
    with topic_col:
        task = st.text_area(
            "Your topic here...",
            placeholder="Example: The impact of AI on education",
            height=120
        )
    with revision_col:
        max_revisions = st.slider(
            "Refinement Rounds", 1, 5, 2
        )
    run_button = st.button("Generate Essay")

# -----------------------------
# Workflow Execution
# -----------------------------
if run_button:
    if not task.strip():
        st.warning("Please enter a topic first.")
        st.stop()

    st.info("Running AI essay workflow... this may take a minute.")

    # Placeholders
    progress_bar = st.progress(0)
    progress_text = st.empty()
    workflow_container = st.container()
    essay_output = ""
    collected_sources = []

    thread = {"configurable": {"thread_id": "ui-thread"}}
    state = {
        "task": task,
        "max_revisions": max_revisions,
        "revision_number": 1,
        "plan": "",
        "draft": "",
        "critique": "",
        "content": [],
        "sources": []
    }

    # Step definitions
    step_names = {
        "planner": "Planning Essay Outline",
        "research_plan": "Researching Background Information",
        "generate": "Writing / Improving Draft",
        "reflect": "Critiquing Draft",
        "research_critique": "Additional Research"
    }

    step_count = 0
    total_steps = 6

    # Stream LangGraph workflow
    for s in graph.stream(state, thread):
        for node, value in s.items():
            step_count += 1
            label = step_names.get(node, node)
            progress_text.markdown(f"**{label}...**")
            progress_bar.progress(min(step_count / total_steps, 1.0))
            time.sleep(0.2)

            # Show intermediate step in expander
            with workflow_container:
                with st.expander(f"{label}", expanded=False):
                    st.markdown(f"```json\n{json.dumps(value, indent=2)}\n```")

            # Capture draft & sources
            if "draft" in value:
                essay_output = value["draft"]
            if "sources" in value:
                collected_sources.extend(value["sources"])

    # Complete
    progress_bar.progress(1.0)
    st.success("Essay generation completed!")

    # -----------------------------
    # Final Essay Display
    # -----------------------------
    st.markdown("## Final Essay")
    st.markdown(essay_output, unsafe_allow_html=True)

    # -----------------------------
    # Sources Display
    # -----------------------------
    if collected_sources:
        st.markdown("## Sources")
        # Deduplicate by URL
        unique_sources = {s.get("url", f"source_{i}"): s for i, s in enumerate(collected_sources)}.values()

        for src in unique_sources:
            if not isinstance(src, dict):
                continue
            url = src.get("url", "Unknown Source")
            title = src.get("title", None)
            snippet = src.get("content", "")
            snippet_clean = " ".join(snippet.split())
            snippet_preview = snippet_clean[:150] + "..." if len(snippet_clean) > 150 else snippet_clean

            if title:
                st.markdown(f"- **[{title}]({url})** — {snippet_preview}")
            else:
                st.markdown(f"- {url} — {snippet_preview}")

    # -----------------------------
    # Download PDF Button
    # -----------------------------
    if essay_output:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)
        for line in essay_output.split("\n"):
            pdf.multi_cell(0, 8, line)

        # Convert PDF to bytes
        pdf_bytes = pdf.output(dest='S').encode('latin1')

        st.download_button(
            label="Download Essay as PDF",
            data=pdf_bytes,
            file_name="essay.pdf",
            mime="application/pdf"
        )

else:
    st.info("Enter a topic and click Generate Essay to begin.")
