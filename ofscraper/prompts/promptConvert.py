import functools
from InquirerPy import inquirer
from InquirerPy.separator import Separator


import ofscraper.prompts.keybindings as keybindings

def getMultiSection(fuzzy=False,*args,**kwargs):
    prompt=None
    if fuzzy:
        prompt=inquirer.fuzzy(
        *args,
        marker="\u25c9 ",
            marker_pl="\u25cb ",
            keybindings= keybindings.fuzzy,
        
        **kwargs
        )
    else:
        prompt=inquirer.select(
        *args,
            keybindings= keybindings.select,
        
        **kwargs
        )

    @prompt.register_kb("c-d")
    def _handle_toggle_all_false(event):
          for choice in prompt.content_control._filtered_choices:
            raw_choice = prompt.content_control.choices[choice["index"]]
            if isinstance(raw_choice["value"], Separator):
                continue
            raw_choice["enabled"] = False

    
    return prompt


def checkbox(*args,**kwargs):
    return inquirer.checkbox(
      *args,**kwargs
    )
def input_prompt(*args,**kwargs):
    return inquirer.text(
      *args,**kwargs
    )


def confirm_prompt(*args,**kwargs):
    return inquirer.confirm(
      *args,**kwargs
    )

def getType(input_type):
    if input_type=="checkbox":
        return checkbox
    elif input_type=="list":
        return functools.partial(getMultiSection,fuzzy=False)
    elif input_type=="input":
        return input_prompt
    
    elif input_type=="confirm":
        return confirm_prompt

def batchConverterHelper(ele):
     ele_type=ele.pop("type")
     name=ele.pop("name")
     obj=getType(ele_type)(**ele)
     return (name,obj.execute())
     
        
def batchConverter(*args):
    outDict={}
    outDict.update(list(map(lambda x:batchConverterHelper(x),args)))
    return outDict
  
    
        
    



