import  ofscraper.runner.manager as manager
import ofscraper.utils.actions as actions
from ofscraper.commands.managers.db import DBManager




def db():
    actions.select_areas()
    for model in manager.Manager.model_manager.getselected_usernames(rescan=False):
        db_manager = DBManager(model.name, model.id)
        db_manager.print_media()

