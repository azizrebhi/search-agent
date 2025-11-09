import streamlit as st
from main import graph
from langchain_core.messages import HumanMessage
import time

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="🧠 AI Essay Writer",
    page_icon="🧠",
    layout="wide",
)

# -----------------------------
# Custom CSS for Modern Look
# -----------------------------
st.markdown("""
<style>
/* Main container padding */
div.block-container {
    padding: 2rem 4rem 2rem 4rem;
}

/* Header styling */
h1, h2, h3, h4 {
    color: #333333;
}

/* Buttons */
.stButton>button {
    background-color: #4CAF50;
    color: white;
    font-weight: bold;
    border-radius: 8px;
    padding: 0.5rem 1rem;
}
.stButton>button:hover {
    background-color: #45a049;
}

/* Progress bar color */
.stProgress > div > div > div > div {
    background-color: #4CAF50;
}

/* Card styling */
div[data-testid="stExpander"] {
    background-color: #f8f9fa;
    border-radius: 10px;
    padding: 1rem;
    box-shadow: 0px 3px 6px rgba(0,0,0,0.1);
}

/* Text area styling */
textarea {
    border-radius: 8px;
    padding: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Header Section
# -----------------------------
st.title("🧠 AI Essay Writer Assistant")
st.markdown(
    "Write better essays with AI. Powered by LangGraph + OpenAI + Tavily Search."
)
st.divider()

# -----------------------------
# Input Section
# -----------------------------
with st.container():
    st.subheader("📝 Enter Your Essay Topic")
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

    run_button = st.button("🚀 Generate Essay")

# -----------------------------
# Workflow Execution
# -----------------------------
if run_button:
    if not task.strip():
        st.warning("⚠️ Please enter a topic first.")
        st.stop()

    # Info Box
    st.info("🔄 Running AI essay workflow... this may take a minute.")

    # Initialize placeholders
    progress_bar = st.progress(0)
    progress_text = st.empty()
    workflow_container = st.container()
    essay_output = ""

    thread = {"configurable": {"thread_id": "ui-thread"}}
    state = {
        "task": task,
        "max_revisions": max_revisions,
        "revision_number": 1,
        "plan": "",
        "draft": "",
        "critique": "",
        "content": []
    }

    # Step definitions for display
    step_names = {
        "planner": "📘 Planning Essay Outline",
        "research_plan": "🔍 Researching Background Info",
        "generate": "✍️ Writing / Improving Draft",
        "reflect": "🧠 Critiquing Draft",
        "research_critique": "📚 Additional Research"
    }

    step_count = 0
    total_steps = 6

    # Stream LangGraph workflow
    for s in graph.stream(state, thread):
        for node, value in s.items():
            step_count += 1
            label = step_names.get(node, node)

            # Update progress
            progress_text.markdown(f"**{label}...**")
            progress_bar.progress(min(step_count / total_steps, 1.0))
            time.sleep(0.2)

            # Display step in a "card"
            with workflow_container:
                with st.expander(f"✅ {label}", expanded=True):
                    st.markdown(f"```markdown\n{str(value)}\n```")

            # Capture draft if exists
            if "draft" in value:
                essay_output = value["draft"]

    # Complete
    progress_bar.progress(1.0)
    st.success("🎉 Essay generation completed!")

    # -----------------------------
    # Final Essay Display
    # -----------------------------
    st.markdown("## 🏁 Final Essay")
    st.markdown(f"```markdown\n{essay_output}\n```")

    st.download_button(
        label="📄 Download Essay as Markdown",
        data=essay_output,
        file_name="essay.md",
        mime="text/markdown"
    )

else:
    st.info("👆 Enter a topic and click **Generate Essay** to begin.")
