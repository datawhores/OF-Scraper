Widgets = """
    Sidebar.-hidden {
        display: none;
    }
    
    Sidebar Widget {
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

    #tabs_row {
        height: 3;
        margin-top: 1;
        margin-bottom: 1;
    }

    /* ========================================= */
    /* HEADER & PAGINATION STYLING               */
    /* ========================================= */
    .header_top_row {
        height: auto; 
        layout: horizontal;
        margin-bottom: 0;
    }

    .trackers_column, .page_info_column, .toggles_column, .info_column, .instructions_column {
        width: 1fr; 
        height: auto;
        content-align: left top;
    }

    .instructions_column {
        width: 1.2fr;
        padding-left: 1;
    }
    
    .header_divider {
        height: 100%;
        margin: 0 1;
    }
    
    Rule {
        margin: 0;
    }

    /* ========================================= */
    /* INLINE PAGINATION                         */
    /* ========================================= */
    .pagination_row {
        height: 4;           
        min-height: 4;       
        max-height: 4;       
        layout: horizontal;
        align: left middle;
        margin-top: 1; 
        margin-bottom: 0;
        width: 100%;
    }
    
    .page_btn {
        width: auto;
        min-width: 3;
        height: 3;           
        margin: 0 1;
    }

    .page_btn:disabled {
        display: none; 
    }
    
    .page_label {
        width: auto; 
        height: 3;          
        margin: 0 2;
        content-align: center middle;
    }
    
    .mini_label {
        width: auto;
        height: 3;
        content-align: center middle;
        margin-left: 2;
        color: #888888; 
    }

    .page_input_small {
        width: 10;
        max-width: 10;
        margin: 0 1;
    }

    .page_input {
        width: 10;
        max-width: 12;
        margin: 0 1;
    }

    .pagination_gap {
        width: 4; 
    }
"""

Table = """
    ContentSwitcher {
        height: 1fr;
    }
    
    /* 1. Page Ceiling: Prevents headers from scrolling off-screen */
    #table_page, #cart_page {
        height: 1fr; 
        width: 100%;
        layout: vertical;
        overflow: hidden; 
    }

    /* 2. Container: Using 1fr here allows it to expand to fill the page,
       while padding-bottom: 1 protects the horizontal scrollbar. */
    #table_main, #cart_table_main {
        height: 1fr;
        width: 100%;
        padding-bottom: 1; 
    }
    
    /* 3. The Table: height: auto allows it to be small when empty.
       margin: 1 adds a clean buffer around the grid. */
    #data_table, #cart_data_table {
        margin: 1;
        height: auto; 
        width: 100%;
    }
"""

Options = """
    #options_sidebar, #download_option_sidebar {
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