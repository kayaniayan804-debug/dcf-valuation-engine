Streamlit app standards:
- Single app.py unless a split is cleaner. Include requirements.txt + README.
- layout="wide", sidebar for inputs, st.metric cards on top, Plotly charts (plotly_dark).
- Cache data with @st.cache_data(ttl=3600). Handle API errors with st.error.
- API keys from st.secrets, never hardcoded.
- Comment code for a beginner. Add a "How this works" expander explaining the finance concepts.
