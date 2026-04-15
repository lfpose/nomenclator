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
