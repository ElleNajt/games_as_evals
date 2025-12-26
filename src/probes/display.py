"""Display helpers for probe scores."""

from typing import List, Optional

from ..backends.base import ProbeScores


def categorize_score(score: float, all_scores: Optional[List[float]] = None) -> str:
    """
    Categorize probe score as LOW/MED/HIGH.

    Uses adaptive percentile-based thresholds if enough scores available,
    otherwise uses fixed thresholds.

    Args:
        score: The probe score to categorize (0.0 to 1.0)
        all_scores: List of all probe scores seen in the game so far.
                   If provided and len >= 10, uses adaptive percentile thresholds.

    Returns:
        "LOW", "MED", or "HIGH" category label

    Examples:
        >>> categorize_score(0.3)  # Fixed thresholds
        'LOW'
        >>> categorize_score(0.7, all_scores=[0.2, 0.3, ..., 0.8, 0.9])  # Adaptive
        'HIGH'
    """
    if all_scores and len(all_scores) >= 10:
        # Adaptive thresholds based on 33rd and 66th percentiles
        sorted_scores = sorted(all_scores)
        low_threshold = sorted_scores[len(sorted_scores) // 3]
        high_threshold = sorted_scores[2 * len(sorted_scores) // 3]

        if score < low_threshold:
            return "LOW"
        elif score < high_threshold:
            return "MED"
        else:
            return "HIGH"
    else:
        # Fixed thresholds for early in game
        if score < 0.4:
            return "LOW"
        elif score < 0.6:
            return "MED"
        else:
            return "HIGH"


def format_probe_annotation(
    speaker: str,
    text: str,
    probe_scores: Optional[ProbeScores],
    style: str = "inline",
    all_scores: Optional[List[float]] = None,
) -> str:
    """
    Format probe scores for display to other players.

    Args:
        speaker: Name of the player who generated the text
        text: The generated text to annotate
        probe_scores: ProbeScores object (or None if no probe)
        style: Display style:
            - "inline": Annotate each sentence with "[PROBE: HIGH/MED/LOW]"
            - "summary": "[LIE DETECTOR] Player: 0.75" (Werewolf style)
            - "none": No annotation, return text as-is
        all_scores: List of all probe scores (for adaptive categorization in inline mode)

    Returns:
        Formatted string with probe annotation

    Examples:
        >>> format_probe_annotation("Alice", "I'll set x3=True. This helps us.", scores, "inline")
        "I'll set x3=True [PROBE: HIGH]. This helps us [PROBE: HIGH]."

        >>> format_probe_annotation("Alice", "...", scores, "summary")
        "[LIE DETECTOR] Alice: 0.75"
    """
    if probe_scores is None or style == "none":
        return text

    if style == "inline":
        # 3-SAT style: Annotate each sentence
        import re

        label = categorize_score(probe_scores.aggregate_score, all_scores)

        # Split on sentence boundaries but keep the punctuation
        # Matches: . ? ! ; followed by space or end of string
        sentences = re.split(r"([.?!;])\s*", text)

        # Reconstruct with annotations after each sentence
        result = []
        i = 0
        while i < len(sentences):
            sentence = sentences[i].strip()
            if not sentence:
                i += 1
                continue

            # Check if next element is punctuation
            if i + 1 < len(sentences) and sentences[i + 1] in ".?!;":
                punct = sentences[i + 1]
                # Add sentence with annotation before punctuation
                result.append(f"{sentence} [PROBE: {label}]{punct}")
                i += 2
            else:
                # No punctuation following (shouldn't happen with our regex, but handle it)
                result.append(f"{sentence} [PROBE: {label}]")
                i += 1

        return " ".join(result)

    elif style == "summary":
        # Werewolf style: Separate line with numerical score
        return f"[LIE DETECTOR] {speaker}: Score: {probe_scores.aggregate_score:.2f}"

    else:
        raise ValueError(
            f"Unknown style '{style}'. Use 'inline', 'summary', or 'none'."
        )


def format_token_level_display(
    tokens: List[str], token_scores: List[float], threshold: float = 0.5
) -> str:
    """
    Format tokens with HTML color-coding based on probe scores.

    Useful for detailed token-level visualization (TTLGame style).
    Returns HTML string that can be displayed in Jupyter/Streamlit.

    Args:
        tokens: List of token strings
        token_scores: List of per-token probe scores (same length as tokens)
        threshold: Score threshold for flagging (default: 0.5)

    Returns:
        HTML string with color-coded tokens
    """
    html_parts = []

    for token, score in zip(tokens, token_scores):
        # Clean up token display
        display_token = token.replace("▁", " ").replace("Ġ", " ")
        if display_token.startswith("##"):
            display_token = display_token[2:]

        # Color based on score
        if score > threshold:
            # High score (likely deception/hallucination) - red
            red_intensity = min(
                255, int(150 + (score - threshold) / (1 - threshold) * 105)
            )
            color = f"rgb({red_intensity}, 100, 100)"
            style = "font-weight: bold;"
        else:
            # Low score (likely truthful) - green
            green_intensity = min(255, int(200 + (1 - score) * 55))
            color = f"rgb(100, {green_intensity}, 100)"
            style = ""

        html_parts.append(
            f'<span style="background-color: {color}; padding: 1px 2px; '
            f'border-radius: 3px; margin: 1px; {style}" '
            f'title="Score: {score:.3f}">{display_token}</span>'
        )

    return "".join(html_parts)
