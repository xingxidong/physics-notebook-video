"""Compatibility for v0.10.0 native scenes rebuilt from handwriting timelines."""


def add_manim_layer(scene, page):
    """Handwriting timelines already include all formulas in the pen layer."""
    if any(event.get('render_kind') == 'tex' for event in page['strokes']):
        raise ValueError('Rebuild this timeline to generate handwritten formulas.')
