"""Theme presets, the Custom theme, and the interface CSS built from every Look and Colors setting.

Every rule a setting controls lives here (one provider), so GTK's provider priority can't let a static rule win
over, or lose to, a setting. Order matters: later rules here override earlier ones of equal specificity.
"""
from gi.repository import Gio

from settings import RANGES, is_font_family, is_hex_color

LABELS = {"dusk": "Dusk", "pine": "Pine", "plum": "Plum", "tide": "Tide", "graphite": "Graphite",
          "midnight": "Midnight (true black)", "custom": "Custom (your own colors)"}
GROUP_COLOR_KEYS = {"Development": "color_development", "Social": "color_social", "Research": "color_research",
                    "Media": "color_media", "Other": "color_other"}
# Colors for the user's own tab groups, in order
USER_GROUP_COLORS = ("#f5b83d", "#5ec27a", "#e26d5c", "#62a8f0", "#d07fd8", "#c9c25a")


def _p(window, view, fg, popover, dialog, private, sky_top, sky_bottom):
    return {"window": window, "view": view, "fg": fg, "popover": popover, "dialog": dialog, "private": private,
            "sky_top": sky_top, "sky_bottom": sky_bottom}


GRAPHITE_LIGHT = _p("#ececee", "#ffffff", "#1c1c1f", "#ffffff", "#f6f6f7", "#e9e2f5", "#dcdce0", "#f5f5f7")
PRESETS = {
    "dusk": {True: _p("#161a31", "#1f2442", "#e6e9f5", "#232949", "#1c2140", "#261b40", "#11152d", "#2b2e5c"),
             False: _p("#e4e9f4", "#ffffff", "#1a1f3d", "#ffffff", "#f3f5fb", "#e9e0f6", "#b9d0f1", "#eef3fb")},
    "pine": {True: _p("#121c19", "#1a2723", "#e3efe9", "#1f2e29", "#18241f", "#221a33", "#0d1714", "#23392f"),
             False: _p("#e3ede8", "#ffffff", "#15261f", "#ffffff", "#f2f7f4", "#ebe3f5", "#c4dfd2", "#f0f6f2")},
    "plum": {True: _p("#1d1424", "#281c31", "#efe5f3", "#2e2138", "#241a2c", "#2a1840", "#170f1d", "#3a2547"),
             False: _p("#efe6f2", "#ffffff", "#2a1733", "#ffffff", "#f8f2fa", "#e6dcf6", "#e2cfe9", "#f8f3fa")},
    "tide": {True: _p("#0f1d24", "#16303a", "#e1f0f4", "#1a3642", "#132830", "#22193c", "#0a161c", "#1d4250"),
             False: _p("#dfedf1", "#ffffff", "#10262e", "#ffffff", "#eff7f9", "#e7e0f6", "#bfe0ea", "#eef7f9")},
    "graphite": {True: _p("#18181a", "#222225", "#e8e8ea", "#29292d", "#1f1f22", "#241d33", "#141416", "#2c2c31"),
                 False: GRAPHITE_LIGHT},
    "midnight": {True: _p("#000000", "#0a0a0a", "#f2f2f2", "#141414", "#0c0c0c", "#140d22", "#000000", "#101018"),
                 False: GRAPHITE_LIGHT},
}


def clamp(key, value):
    lo, hi = RANGES[key]
    return max(lo, min(hi, value))


def luminance(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def rgba(hex_color, alpha):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def _color(s, key):
    from settings import DEFAULTS
    return s[key] if is_hex_color(s[key]) else DEFAULTS[key]


def custom_is_dark(s):
    return luminance(_color(s, "custom_window")) < 0.5


def palette(s, dark):
    """The palette in use. A Custom theme has one palette whatever the light/dark setting: its window color decides."""
    if s["theme_preset"] != "custom":
        return PRESETS.get(s["theme_preset"], PRESETS["dusk"])[dark]
    window, view, popover = _color(s, "custom_window"), _color(s, "custom_view"), _color(s, "custom_popover")
    fg = s["custom_text"] if is_hex_color(s["custom_text"]) else ("#ecedf3" if custom_is_dark(s) else "#1b1d27")
    return _p(window, view, fg, popover, popover, f"color-mix(in srgb, {window} 75%, #7a4dd8)", window, view)


def font_css(description):
    """CSS for a Pango font description like "Inter Bold 11", or "" when unset or unsafe."""
    if not description:
        return ""
    from gi.repository import Pango
    font = Pango.FontDescription.from_string(description)
    family = font.get_family()
    if not is_font_family(family or ""):
        return ""
    size = font.get_size() / Pango.SCALE
    return f'font-family: "{family}";' + (f" font-size: {size:g}pt;" if size else "")


def image_uri(path):
    """A file:// URI for CSS url(): percent-encoded, so quotes or brackets in the path can't end the string."""
    return Gio.File.new_for_path(path).get_uri()


def chrome_css(s, dark, image_ok):
    """The window background behind the toolbar and tab panel: color, gradient or image, with transparency.

    Alpha goes only on window.kite's own background, never into --window-bg-color: Adwaita derives popovers and
    dialogs from that, and they'd turn see-through too.
    """
    p = palette(s, dark)
    window = p["window"]
    alpha = clamp("chrome_opacity", s["chrome_opacity"]) / 100
    layers = []
    if s["chrome_background"] == "gradient":
        layers.append(f"linear-gradient(160deg, {rgba(window, alpha)}, {rgba(_color(s, 'chrome_gradient'), alpha)})")
    elif s["chrome_background"] == "image" and image_ok:
        dim = rgba(window, clamp("chrome_dim", s["chrome_dim"]) / 100)
        layers += [f"linear-gradient({dim}, {dim})", f'url("{image_uri(s["chrome_image"])}")']
    image = ", ".join(layers) or "none"
    private = rgba(p["private"], alpha) if is_hex_color(p["private"]) else p["private"]  # Custom: a color-mix()
    return (f"window.kite {{ background-color: {rgba(window, alpha)}; background-image: {image};"
            f" background-size: cover; background-position: center; }}"
            f" window.kite.private {{ background-color: {private}; }}")


def interface_css(s, dark, accent, accent_fg):
    p = palette(s, dark)
    text_accent = accent if dark else f"color-mix(in srgb, {accent} 60%, black)"
    r = clamp("roundness", s["roundness"])
    gap = clamp("card_gap", s["card_gap"])
    border = clamp("card_border", s["card_border"])
    shadow = ", 0 2px 8px rgba(0, 0, 0, .18)" if s["card_shadow"] else ""
    card_shadow = f"0 0 0 {border}px alpha(currentColor, .09){shadow}" if border or shadow else "none"
    style = s["active_tab_style"]
    active = {
        "bar": ("background-color: alpha(currentColor, .11); box-shadow: inset 3px 0 var(--accent-bg-color);",
                "box-shadow: inset 0 -2px var(--accent-bg-color);"),
        "fill": ("background-color: var(--accent-bg-color); color: var(--accent-fg-color); box-shadow: none;", ""),
        "underline": ("background-color: transparent; box-shadow: inset 0 -2px var(--accent-bg-color);", ""),
        "outline": ("background-color: alpha(currentColor, .05); box-shadow: inset 0 0 0 2px var(--accent-bg-color);", ""),
    }[style]
    # Adjacent f-strings join before a trailing "if", so the optional rule is built on its own.
    horizontal = f" .tabs-horizontal .tabstrip .tab.active {{ {active[1]} }}" if active[1] else ""
    return (
        f":root {{ --window-bg-color: {p['window']}; --window-fg-color: {p['fg']};"
        f" --headerbar-bg-color: {p['window']}; --headerbar-fg-color: {p['fg']};"
        f" --view-bg-color: {p['view']}; --view-fg-color: {p['fg']};"
        f" --popover-bg-color: {p['popover']}; --popover-fg-color: {p['fg']};"
        f" --dialog-bg-color: {p['dialog']}; --dialog-fg-color: {p['fg']};"
        f" --sidebar-bg-color: {p['window']}; --sidebar-fg-color: {p['fg']};"
        f" --accent-bg-color: {accent}; --accent-fg-color: {accent_fg}; --accent-color: {text_accent}; }}"
        # Same provider as :root so specificity, not provider priority, lets private windows win.
        f" window.private {{ --window-bg-color: {p['private']}; --headerbar-bg-color: {p['private']};"
        f" --sidebar-bg-color: {p['private']}; }}"
        f" window.kite {{ {font_css(s['ui_font'])} }}"
        f" window.kite headerbar {{ min-height: {clamp('toolbar_height', s['toolbar_height'])}px; }}"
        f" .omnibox {{ border-radius: {r * 3}px; }}"
        f" .tabstrip .tab, .newtab, .pin-tile {{ border-radius: {max(0, r - 4)}px; }}"
        f" .findbar {{ border-radius: {r}px; }}"
        # The page card: base, then the tab panel's side, then full screen, so each later rule wins.
        f" .webcard {{ border-radius: {r}px; margin: 0 {gap}px {gap}px {gap}px; box-shadow: {card_shadow}; }}"
        f" window.vertical-layout .webcard {{ margin: 0 {gap}px {gap}px 0; }}"
        f" window.vertical-layout.panel-end .webcard {{ margin: 0 0 {gap}px {gap}px; }}"
        f" window.fullscreen .webcard {{ margin: 0; border-radius: 0; box-shadow: none; }}"
        f" .tabstrip .tab.active {{ {active[0]} }}"
    ) + horizontal + " " + group_css(s)


def group_css(s):
    """Tab group dot colors (built-in groups by setting, the user's groups by position)."""
    dots = [f".dot.pinned {{ background-color: var(--accent-bg-color); }}"]
    dots += [f".dot.g-{name.lower()} {{ background-color: {_color(s, key)}; }}" for name, key in GROUP_COLOR_KEYS.items()]
    dots += [f".dot.user-{i} {{ background-color: {c}; }}" for i, c in enumerate(USER_GROUP_COLORS)]
    return " ".join(dots)
