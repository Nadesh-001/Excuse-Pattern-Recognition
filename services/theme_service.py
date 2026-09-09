
def get_theme_css(theme_name='light'):
    """
    Returns the CSS variables for the selected theme.
    """
    themes = {
        'light': """
            :root {
                --bg-main: #f8fafc;
                --bg-card: #ffffff;
                --bg-hover: #f1f5f9;
                
                /* Typography Palette */
                --text-main: #0f172a;       /* Primary text */
                --text-bold: #0f172a;       /* Headings */
                --text-secondary: #334155;  /* Secondary / Labels */
                --text-muted: #64748b;      /* Hints / Placeholders */
                --text-disabled: #94a3b8;   /* Disabled */
                
                /* Status Colors */
                --color-error: #dc2626;
                --color-success: #16a34a;
                --color-link: #2563eb;
                
                /* Brand */
                --primary: #3b82f6;
                --primary-dark: #1d4ed8;
                --primary-gradient: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                
                --border-color: #e5e7eb;
                --border-light: #f1f5f9;
                --shadow-light: rgba(0,0,0,0.05);
                --shadow-hover: rgba(0,0,0,0.1);
            }
        """,
        'dark': """
            :root {
                --bg-main: #0f172a;
                --bg-card: #1e293b;
                --bg-hover: #334155;
                --text-main: #e2e8f0;
                --text-bold: #f8fafc;
                --text-secondary: #94a3b8;
                --text-faint: #64748b;
                --primary: #60a5fa;
                --primary-dark: #3b82f6;
                --primary-gradient: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
                --border-color: #334155;
                --border-light: #1e293b;
                --shadow-light: rgba(0,0,0,0.4);
                --shadow-hover: rgba(0,0,0,0.6);
            }
        """
    }
    return themes.get(theme_name, themes['light'])

def get_logo_path(theme_name='light'):
    """Returns the logo path for the selected theme."""
    if theme_name == 'dark':
        return "assets/logo_dark.png" # Assuming you'll create/upload this or use inverted filter
    return "assets/logo_light.png"
