Widgets = """
    Sidebar.-hidden {
        display: none;
    }
    Screen {
        layers: sidebar;
        overflow: hidden;
    }
    Button {
        height: 3;
        margin: 0 1; 
    }
    
    /* The flexible header section */
    #header_top_row {
        height: auto; 
        min-height: 7;
        margin-bottom: 0;
        layout: horizontal; 
    }
    
    /* Three equal columns */
    #trackers_column, #page_info_column, #instructions_column {
        width: 1fr; 
        height: 100%;
    }
    
    /* Center columns vertically */
    #trackers_column, #page_info_column {
        content-align: left middle;
    }

    #instructions_column {
        content-align: left top;
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
    #data_table {
        margin-top: 0;
        height: 1fr;
        min-height: 20; 
    }

    #table_main {
        height: 1fr; 
        min-height: 20;
    }
"""

Options = """
    #options_sidebar, #page_option_sidebar, #download_option_sidebar {
        width: 45%;
        dock: left;
        layer: sidebar;
        overflow-y: auto; 
        overflow-x: hidden;
        height: 100vh;
    }

    #main_options {
        height: auto; 
        layout: grid;
        grid-size: 4 60;
        margin-top: 1;
    }

    #page_option {
        height: auto;
        layout: grid;
        grid-size: 4 50;
        margin-top: 1;
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