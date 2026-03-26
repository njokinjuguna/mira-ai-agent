from typing import Any, Dict, List, Optional, TypedDict

class MiraState(TypedDict, total=False):
    session_id: str
    query: str
    lang: str

    intent: str  # search | select | sketch_generation | follow_up_cost | showroom | unsupported

    last_search_results: List[Dict[str, Any]]  # indexed results
    selected_index: Optional[int]
    selected_sketch: Optional[Dict[str, Any]]

    message: str
    results: List[Dict[str, Any]]
