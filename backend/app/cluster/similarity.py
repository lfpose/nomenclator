import numpy as np
from rapidfuzz import process, fuzz


def len_ratio(a: str, b: str) -> float:
    """Return the length ratio between two strings.
    
    The ratio is computed as min(len(a), len(b)) / max(len(a), len(b)).
    Returns 0.0 if either string is empty.
    
    Args:
        a: First string
        b: Second string
    
    Returns:
        Float between 0.0 and 1.0 representing the length ratio
    """
    if not a or not b:
        return 0.0
    la, lb = len(a), len(b)
    return min(la, lb) / max(la, lb)


def compute_similarity(
    strings: list[str], score_cutoff: int = 0
) -> np.ndarray:
    """Compute the token_set_ratio similarity matrix for a list of strings.
    
    Args:
        strings: List of normalized strings to compare
        score_cutoff: Minimum similarity score to compute (default 0)
    
    Returns:
        NxN numpy array of similarity scores (0-100)
    """
    return process.cdist(
        strings,
        strings,
        scorer=fuzz.token_set_ratio,
        processor=None,  # strings are already normalized
        score_cutoff=score_cutoff,
        dtype=np.uint8,
    )
