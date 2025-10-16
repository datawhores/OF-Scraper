import logging
import shutil
from ofscraper.managers.model import ModelManager
import ofscraper.utils.settings as settings
import ofscraper.utils.profiles.data as data
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.config.config as config_
import ofscraper.utils.profiles.data as profile_data
import ofscraper.utils.of_env.of_env as of_env


log = logging.getLogger("shared")

class ProfileManager:
    def __init__(self):
        self.model_managers = {}

    def switch_profile(self, new_profile_name: str, permanent: bool = False):
        """
        Changes the active profile.

        Args:
            new_profile_name (str): The name of the profile to switch to.
            permanent (bool): If True, changes the default profile in the config file.
                            If False, changes the profile for the current session only.
        """
        # Use your get_active_profile to check against the true active profile
        if not new_profile_name or new_profile_name == profile_data.get_active_profile():
            return
        args = settings.get_args()
        if permanent:
            log.info(f"Permanently switching default profile to '{new_profile_name}'...")
            # 1. Update the persistent config file
            config_.update_config(of_env.getattr("mainProfile"), new_profile_name)
            args.profile = None
        else:
            log.info(f"Temporarily switching active profile to '{new_profile_name}' for this session...")
            args.profile = new_profile_name
        settings.update_args(args)
        log.info(f"[green]✅ Active profile is now '{new_profile_name}'[/green]")   

    def delete_profile(self, profile_name: str):
        if profile_name == self.active_profile:
            log.error(f"Cannot delete the active profile ('{profile_name}').")
            return

        if profile_name in self.model_managers:
            self.model_managers.pop(profile_name)

        profile_path = common_paths.get_config_home() / profile_name
        if profile_path.exists():
            log.info(f"Removing profile directory: {profile_path}")
            shutil.rmtree(profile_path)
        
        log.info(f"[green]Successfully deleted profile '{profile_name}'[/green]")
    def rename_profile(self, old_name: str, new_name: str):
        """
        Safely renames a profile, updating the filesystem, in-memory state,
        and persistent config. This is the single source of truth for this action.
        """
        log=logging.getLogger("shared")
        if old_name == new_name:
            log.info("Names are the same. No action needed.")
            return
        config_folder = common_paths.get_config_home()
        old_folder = config_folder / old_name
        new_folder = config_folder / new_name

        if new_folder.exists():
            log.error(f"Cannot rename. A folder for '{new_name}' already exists.")
            return
        if old_folder.exists():
            log.info(f"Renaming profile '{old_name}' to '{new_name}'...")

            # --- 2. Update Filesystem ---
            try:
                shutil.move(str(old_folder), str(new_folder))
                log.debug(f"Moved profile folder to '{new_folder}'")
            except Exception as e:
                log.error(f"Failed to rename profile folder: {e}")
                return # Stop the process if the file operation fails
        else:
            new_folder.mkdir(parents=True,exist_ok=True)

        if old_name in self.model_managers:
            log.debug(f"Moving ModelManager instance from '{old_name}' to '{new_name}'.")
            self.model_managers[new_name] = self.model_managers.pop(old_name)

        if self.config_profile == old_name:
            log.info(f"Default config profile was '{old_name}', updating to '{new_name}'.")
            config_.update_config("main_profile", new_name) # Updates the main config file
        if not self.config_profile==old_name and self.active_profile==old_name:
            log.info(f"Active config profile was '{old_name}', updating to '{new_name}'.")
            args=settings.get_args()
            args.profile=new_name
            settings.update_args(args)
        log.info(f"[green]Successfully renamed profile '{old_name}' to '{new_name}'[/green]")
    
    @property
    def current_model_manager(self) -> ModelManager:
        """
        Gets the ModelManager for the currently active profile.
        If a manager for this profile doesn't exist, it creates one.
        """
        # Check if we've already created a manager for this profile
        self._add_profile_helper()
        # Return the manager for the active profile
        return self.model_managers[self.active_profile]
    
    @property
    def active_profile(self) -> str:
        """
        Returns the current active profile by always checking get_active_profile
        """
        return data.get_active_profile()
    
    @property
    def config_profile(self) -> str:
        """
        Returns the current config profile by always checking get_current_config_proifle.
        """
        return data.get_current_config_profile()
    
    def _add_profile_helper(self):
        profile=self.active_profile
        if profile not in self.model_managers:
            log.info(f"Creating new ModelManager for profile: '{profile}'")
            self.model_managers[profile] = ModelManager()
            