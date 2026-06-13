"""btop-inspired color scheme for dsmview."""

BG = "#1a1a2e"
BORDER = "#454580"
BORDER_TITLE = "#a9b1d6"

CPU_BAR = "#e06c75"
MEM_BAR = "#98c379"
DISK_BAR = "#e5c07b"
NET_UP = "#61afef"
NET_DOWN = "#c678dd"

LOG_ERROR = "#e06c75"
LOG_WARN = "#e5c07b"
LOG_INFO = "#98c379"
LOG_SECURITY = "#c678dd"

OK = "#98c379"
WARNING = "#e5c07b"
CRITICAL = "#e06c75"
STOPPED = "#545862"


CSS = f"""
Screen {{
    background: {BG};
    color: {BORDER_TITLE};
}}

Footer {{
    background: {BG};
    color: {BORDER_TITLE};
}}

TabbedContent {{
    background: {BG};
}}

Tabs {{
    background: {BG};
}}

Tab {{
    background: {BG};
    color: {BORDER_TITLE};
}}

Tab.-active {{
    color: {OK};
    text-style: bold;
}}

#topbar {{
    height: 1;
    background: {BG};
    color: {BORDER_TITLE};
    content-align: left middle;
    padding: 0 1;
}}

.panel {{
    border: round {BORDER};
    background: {BG};
    color: {BORDER_TITLE};
    padding: 0 1;
    margin-bottom: 1;
    height: auto;
}}

.panel > Static.panel-title {{
    color: {BORDER_TITLE};
    text-style: bold;
    height: 1;
}}

#net-graphs {{
    height: 5;
}}

DataTable {{
    background: {BG};
    color: {BORDER_TITLE};
    height: auto;
}}

DataTable > .datatable--header {{
    background: {BG};
    color: {BORDER_TITLE};
    text-style: bold;
}}
"""
