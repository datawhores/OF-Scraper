LIVE_CSS = """
Screen {
    layout: vertical;
    overflow-x: hidden;
    overflow-y: hidden;
}

#telemetry_bar {
    height: auto;
    layout: horizontal;
    padding: 0 1;
    background: $surface;
    border-bottom: solid $primary;
}

.telemetry_col {
    width: 1fr;
    height: auto;
    padding: 0 1;
}

#action_bar {
    height: auto;
    layout: vertical;
    padding: 0 1;
    margin-top: 1;
    margin-bottom: 0;
}

.action_row {
    height: auto;
    layout: horizontal;
    margin-bottom: 0;
}

#action_row_1 {
    margin-bottom: 1;
}

#action_bar Button {
    margin: 0 1 0 0;
}

#add_user_bar, #search_bar {
    height: auto;
    layout: horizontal;
    margin-top: 1;
}

#add_user_bar.-hidden, #search_bar.-hidden {
    display: none;
}

#add_user_input, #search_input {
    width: 1fr;
    margin-right: 1;
}

#streams_container {
    height: 1fr;
    width: 100%;
    layout: vertical;
    padding: 0 1;
    margin-top: 1;
}

#streams_table {
    height: 1fr;
    width: 100%;
}

#bottom_split {
    height: 14;
    min-height: 8;
    width: 100%;
    layout: horizontal;
    border-top: solid $primary;
}

.pane_box {
    width: 1fr;
    height: 100%;
    layout: vertical;
    padding: 0 1;
}

#chat_pane {
    border-left: solid $panel;
}

.pane_title {
    height: 1;
    color: $text-muted;
    text-style: bold;
}

#live_console, #live_chat_log {
    height: 1fr;
    width: 100%;
}

#keybind_footer {
    height: 1;
    width: 100%;
    padding: 0 1;
    background: $surface;
    color: $text-muted;
}
"""
