def stars(rating: int | None) -> str:
    """Renders a rating as filled/empty star characters, e.g. "★★★☆☆"."""
    if rating is None:
        return "未評価"
    n = max(0, min(5, rating))
    return "★" * n + "☆" * (5 - n)
