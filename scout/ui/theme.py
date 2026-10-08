"""Scout Terminal V2 — Color System & Theme tokens."""

from rich.theme import Theme

# Consistent blue-green visual identity
THEME_COLORS = {
    # Core brand colors
    "primary": "#42E8D5",        # Luminous turquoise/cyan (primary accent)
    "secondary": "#14B8A6",      # Bluish green/teal (secondary accent)
    "teal": "#0D9488",           # Deep teal
    "ice": "#7DD3FC",            # Ice blue (supporting color)
    "glow": "#DDFBFF",           # Luminous white-cyan highlight
    "bg": "#080E14",             # Near-black with subtle blue undertones
    "panel": "#0F1D27",          # Deep surface
    "border": "#16384C",         # Subtle cyan separator
    
    # Typography & Hierarchy
    "text": "#F8FAFC",           # Soft white (main text)
    "text_muted": "#94A3B8",     # Muted blue-grey (secondary text)
    "dim": "#64748B",            # Muted slate (dividers / subtle metadata)
    
    # State Indicators
    "success": "#34D399",        # Mint (success)
    "warning": "#FBBF24",        # Amber (warning / safety confirmation)
    "error": "#F87171",          # Muted coral (errors)
    
    # Aliases for backward compatibility
    "accent": "#DDFBFF",
    "core_glow": "#42E8D5",
}

scout_theme = Theme({
    "primary": THEME_COLORS["primary"],
    "secondary": THEME_COLORS["secondary"],
    "teal": THEME_COLORS["teal"],
    "ice": THEME_COLORS["ice"],
    "glow": THEME_COLORS["glow"],
    "accent": THEME_COLORS["accent"],
    "text": THEME_COLORS["text"],
    "text_muted": THEME_COLORS["text_muted"],
    "dim": THEME_COLORS["dim"],
    "border": THEME_COLORS["border"],
    "success": THEME_COLORS["success"],
    "warning": THEME_COLORS["warning"],
    "error": THEME_COLORS["error"],
    "info": THEME_COLORS["ice"],
})
