import logging
import shutil

import ofscraper.sites as sites
import ofscraper.utils.config.config as config_
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.profiles.data as profile_data
import ofscraper.utils.settings as settings
from ofscraper.managers.model import ModelManager

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
        sites.clear_session_site()
        settings.update_args(args)
        log.info(f"[green]✅ Active profile is now '{new_profile_name}'[/green]")

    def delete_profile(self, profile_name: str):
        if profile_name == self.active_profile:
            log.error(f"Cannot delete the active profile ('{profile_name}').")
            return

        for key in [k for k in self.model_managers if k[0] == profile_name]:
            self.model_managers.pop(key)

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
                return  # Stop the process if the file operation fails
        else:
            new_folder.mkdir(parents=True, exist_ok=True)

        moved = [k for k in self.model_managers if k[0] == old_name]
        if moved:
            log.debug(f"Moving ModelManager instance from '{old_name}' to '{new_name}'.")
            for old_key in moved:
                self.model_managers[(new_name, old_key[1])] = self.model_managers.pop(old_key)

        sites.rename_session_profile(old_name, new_name)

        if self.config_profile == old_name:
            log.info(f"Default config profile was '{old_name}', updating to '{new_name}'.")
            config_.update_config("main_profile", new_name)  # Updates the main config file
        if not self.config_profile == old_name and self.active_profile == old_name:
            log.info(f"Active config profile was '{old_name}', updating to '{new_name}'.")
            args = settings.get_args()
            args.profile = new_name
            settings.update_args(args)
        log.info(f"[green]Successfully renamed profile '{old_name}' to '{new_name}'[/green]")

    def peek_model_manager(self) -> ModelManager | None:
        """Return the existing creator manager for the active profile and site, or None."""
        return self.model_managers.get((self.active_profile, sites.current_site()))

    @property
    def current_model_manager(self) -> ModelManager:
        """Get the creator manager for the active profile and site."""
        profile = self.active_profile
        site = sites.current_site()
        key = (profile, site)
        if key not in self.model_managers:
            log.info(f"Creating new ModelManager for profile: '{profile}' ({site})")
            self.model_managers[key] = ModelManager()
        return self.model_managers[key]

    @property
    def active_profile(self) -> str:
        """
        Returns the current active profile by always checking get_active_profile
        """
        return profile_data.get_active_profile()

    @property
    def config_profile(self) -> str:
        """
        Returns the current config profile by always checking get_current_config_proifle.
        """
        return profile_data.get_current_config_profile()
