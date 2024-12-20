CSS = """
    Screen {
       layers: sidebar;
       overflow: hidden;
    }
    .table_info,Static{
    max-width:45;
    width:30vw;
    min-width:20;
    }


    #options_sidebar, #page_option_sidebar{
        width: 45%;
        dock: left;
        layer: sidebar;
        overflow-y:scroll;
        overflow-x:scroll;
        height: 100%;

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

#buttons{
height:15vh;
}
 
    Sidebar.-hidden {
        display: none;
    }

    #data_table {
    margin-bottom:2;
    height:95vh;
    width:100vw;
    }


    #data_table_holder {
         overflow-x:scroll;
        overflow-y:scroll;
        width:80%;
        height:80%;
    }

    Widget {
    column-span:4;
    row-span:2;
    }
    NumField {
    column-span:3;
    }

SelectField,DateField,TimeField {
    row-span:3;
    }

    SelectField{
    column-span:2;
    }

    MediaField {
    column-span:3;
    row-span:3;
    }
   

    ResponseField {
    column-span:4;
    row-span:4;
    }
   
    #other_posts_with_media{
    column-span:1;
    }
    #Post_Media_Count{
    column-span:1;
    }
    #table_main{
    height:6fr;
    }

    """