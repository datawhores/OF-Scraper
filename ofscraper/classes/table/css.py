Widgets = """
    Sidebar.-hidden {
        display: none;
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
"""

Table = """
    #data_table {
        margin-top: 1;
        height: 100%;
        min-height: 20; /* Prevents the table from collapsing to 0 height */
    }

    #table_main {
        height: 100%; /* Forces the container to take up the remaining screen */
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