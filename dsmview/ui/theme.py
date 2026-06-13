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

Header {{
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
}}

.panel > .panel-title {{
    color: {BORDER_TITLE};
    text-style: bold;
}}

.meter-cpu Bar > .bar--bar {{
    color: {CPU_BAR};
}}

.meter-mem Bar > .bar--bar {{
    color: {MEM_BAR};
}}

.meter-disk Bar > .bar--bar {{
    color: {DISK_BAR};
}}

.severity-error {{
    color: {LOG_ERROR};
}}

.severity-warn {{
    color: {LOG_WARN};
}}

.severity-info {{
    color: {LOG_INFO};
}}

.severity-security {{
    color: {LOG_SECURITY};
}}

.svc-running {{
    color: {OK};
}}

.svc-stopped {{
    color: {STOPPED};
}}

DataTable {{
    background: {BG};
    color: {BORDER_TITLE};
}}

DataTable > .datatable--header {{
    background: {BG};
    color: {BORDER_TITLE};
    text-style: bold;
}}

DataTable > .datatable--cursor {{
    background: {BORDER};
    color: {BG};
}}

#dashboard-grid {{
    layout: grid;
    grid-size: 2 3;
    grid-columns: 1fr 1fr;
    grid-rows: 1fr 1fr auto;
    grid-gutter: 0;
}}

#cpu-panel, #mem-panel, #storage-panel, #net-panel, #services-row, #logs-row {{
    height: 100%;
    width: 100%;
}}

#services-row, #logs-row {{
    column-span: 2;
}}

ConfirmDialog {{
    align: center middle;
}}

ConfirmDialog > #dialog {{
    width: 60;
    height: 9;
    background: {BG};
    border: round {WARNING};
    padding: 1 2;
}}

ConfirmDialog #dialog-title {{
    color: {WARNING};
    text-style: bold;
}}
"""
