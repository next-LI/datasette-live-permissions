from datasette.app import Datasette
import pytest
import os

import sqlite3
import sqlite_utils
import datasette_live_permissions


# @pytest.mark.asyncio
# async def test_plugin_is_installed():
#     datasette = Datasette([], memory=True)
#     response = await datasette.client.get("/-/plugins.json")
#     assert response.status_code == 200
#     installed_plugins = {p["name"] for p in response.json()}
#     print("installed_plugins", installed_plugins)
#     assert "datasette-live-permissions" in installed_plugins


@pytest.mark.asyncio
async def test_can_create_db():
    datasette = Datasette([], memory=True)
    db1 = datasette_live_permissions.get_db(datasette)
    assert db1 is not None
    db2 = datasette.get_database("live_permissions")
    assert db2 is not None


@pytest.mark.asyncio
async def test_can_create_tables():
    datasette = Datasette([], memory=True)
    datasette_live_permissions.get_db(datasette)
    database_path = os.path.join(datasette_live_permissions.DEFAULT_DBPATH,
                                 f"{datasette_live_permissions.DB_NAME}.db")
    db = sqlite_utils.Database(sqlite3.connect(database_path))
    datasette_live_permissions.create_tables()
    for table in datasette_live_permissions.KNOWN_TABLES:
        print(f"{table} in tables?")
        assert table in db.table_names()
