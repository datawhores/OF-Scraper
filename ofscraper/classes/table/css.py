Widgets = """
    Sidebar.-hidden {
        display: none;
    }
    
    /* Forces inputs to take full width of the sidebar grid */
    Widget {
        column-span: 4;
        row-span: 2;
    }
    
    Screen {
        layers: sidebar;
        overflow-y: hidden;
        overflow-x: hidden;
    }
    
    Button {
        height: 3;
        margin: 0 1; 
    }

    /* ========================================= */
    /* NEW TABS ROW                              */
    /* ========================================= */
    #tabs_row {
        height: 3;
        margin-top: 1;
        margin-bottom: 1;
    }

    /* ========================================= */
    /* 4-COLUMN HEADER STYLING                   */
    /* ========================================= */
    #header_top_row {
        height: auto; 
        min-height: 8; 
        layout: horizontal;
        margin-bottom: 0;
    }

    #trackers_column, #page_info_column, #toggles_column, #instructions_column {
        width: 1fr; 
        height: 100%;
        content-align: left top;
    }

    #instructions_column {
        width: 1.2fr;
        padding-left: 1;
    }

    .header_divider {
        height: 100%;
        margin: 0 1;
    }
    
    #table_instructions {
        text-align: left;
        width: 100%;
    }

    Rule {
        margin: 0;
    }

    #button_row {
        height: 3;
        margin-top: 1;
        margin-bottom: 1;
    }
"""

Table = """
/* Tell the switcher and page to strictly fill remaining space */
    ContentSwitcher {
        height: 1fr;
    }
    
    #table_page {
        height: 100%;
        width: 100%;
    }

    #table_main {
        height: 100%; 
        min-height: 20;
    }
    #data_table {
        margin-top: 0;
        height: 1fr;
        min-height: 20; 
    }

    #table_main {
        height: 1fr; 
        min-height: 20;
    }

    #table_info_header {
        height: auto;
        margin-bottom: 1;
    }

    .table_info {
        width: 1fr;
        padding: 0 2;
    }
"""

Options = """
    /* ========================================= */
    /* RESTORED ORIGINAL SIDEBAR SETTINGS        */
    /* ========================================= */
    #options_sidebar, #page_option_sidebar, #download_option_sidebar {
        width: 45%;
        dock: left;
        layer: sidebar;
        overflow-y: scroll;
        overflow-x: scroll;
        height: 100vh;
    }

    #main_options {
        height: 150;
        layout: grid;
        grid-size: 4 60;
        margin-top: 2;
    }

    #page_option {
        height: 120;
        layout: grid;
        grid-size: 4 50;
        margin-top: 2;
    }
"""

CSS = (
    """
    #post_id, #media_id {
        column-span: 2;
    }
    """
    + Widgets
    + Table
    + Options
)