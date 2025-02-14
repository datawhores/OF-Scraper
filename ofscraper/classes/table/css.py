Widgets = """
 Sidebar.-hidden {
        display: none;
    }
Widget {
    column-span:4;
    row-span:2;
    }
Screen {
       layers: sidebar;
        overflow-y:hidden;
        overflow-x:hidden;
    }

    Button{
height:3;
}
"""

Table = """
 #data_table{
    margin-bottom:4;
    margin-top:1;
    min-height:120;
    }

    #data_table_hidden {
    display:None;
    }

    #table_main{
    height:70%;
    }
    #table_header{
    height:30%;
    max-height:18;
    min-height:15;
    }
    .table_info,Static{
    max-width:45;
    width:30vw;
    min-width:20;
    }

"""

Options = """
#options_sidebar, #page_option_sidebar,#download_option_sidebar{
        width: 45%;
        dock: left;
        layer: sidebar;
        overflow-y:scroll;
        overflow-x:scroll;
        height: 100vh;

    }


    #main_options{
        height:150;
        layout: grid;
        grid-size: 4 60;
        margin-top:2;
    }

     #page_option{
        height:120;
        layout: grid;
        grid-size: 4 50;
        margin-top:2;
    }

"""

CSS = (
    """
    #post_id,#media_id{
    column-span:2;
    }
"""
    + Widgets
    + Table
    + Options
)
