import streamlit as st
from typing import Dict, Any

def initialize_session_state():
    """Initialize session state variables."""
    if 'extraction_results' not in st.session_state:
        st.session_state.extraction_results = None
    if 'analyzed_results' not in st.session_state:
        st.session_state.analyzed_results = None
    if 'analyzed_df' not in st.session_state:
        st.session_state.analyzed_df = None
    if 'history' not in st.session_state:
        st.session_state.history = []

def get_app_configuration() -> Dict[str, Any]:
    """Get application configuration from sidebar."""
    with st.sidebar:
        with st.expander("⚙️ Configuration"):
            config = {
                "MAX_WORKERS": st.slider("Max workers", 1, 20, 10, 
                                       key="global_workers"),
                "TIMEOUT": st.slider("Timeout (seconds)", 1, 15, 5, 
                                   key="global_timeout"),
                "CHUNK_SIZE": st.slider("Batch size", 10, 100, 50, 
                                      key="global_chunk_size")
            }
            
            st.markdown("---")
            test_mode = st.checkbox("🧪 Enable test mode", False, 
                                  key="global_test_mode")
            if test_mode:
                config["TEST_SIZE"] = st.number_input(
                    "Number of URLs to test",
                    min_value=1,
                    max_value=1000,
                    value=10,
                    help="Limit the number of URLs to process for testing",
                    key="global_test_size"
                )
            else:
                config["TEST_SIZE"] = None
                
            config["TEST_MODE"] = test_mode
            
            return config
