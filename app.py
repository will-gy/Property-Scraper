from database.update_database import ManageDatabase
from settings import get_storage_settings

manage_database = ManageDatabase(get_storage_settings().db_path)
