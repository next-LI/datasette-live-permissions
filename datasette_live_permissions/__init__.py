import json
import os
import sqlite3

import sqlite_utils
from datasette import hookimpl, database as ds_database


DB_NAME="live_permissions"
DEFAULT_DBPATH="."


# used to check all required tables exist
KNOWN_TABLES = [
    "users", "groups", "actions_resources", "permissions"
]


def get_db(datasette=None):
    """
    Returns a sqlite_utils.Database, not datasette.Database, but a datasette
    Database can be got through datasette.databases[DB_NAME] after this runs.
    """
    database_path = os.path.join(DEFAULT_DBPATH, f"{DB_NAME}.db")
    # this will create the DB if not exists
    conn = sqlite3.connect(database_path)
    db = sqlite_utils.Database(conn)
    # just make it show up in the DBs list
    if datasette and not (DB_NAME in datasette.databases):
        datasette.add_database(
            ds_database.Database(datasette, path=database_path, is_mutable=True),
            name=DB_NAME,
        )
    return db


def create_tables(datasette=None):
    database = get_db(datasette=datasette)
    table_names = database.table_names()

    if "users" not in table_names:
        database["users"].create({
            "id": int,
            "description": str,
            "lookup": str,
            "value": str,
        }, not_null=["lookup"], pk="id")

    if "groups" not in table_names:
        database["groups"].create({
            "id": int,
            "user_id": int,
        }, pk="id", foreign_keys=(
            ("user_id", "users", "id"),
        ))

    if "actions_resources" not in table_names:
        database["actions_resources"].create({
            "id": int,
            # paired with any of these
            "action": str,
            "resource_primary": str,
            "resource_secondary": str,
        }, pk="id", not_null=[
            "action",
        ])
        database["actions_resources"].create_index([
            "action", "resource_primary", "resource_secondary",
        ], unique=True)

    if "permissions" not in table_names:
        database["permissions"].create({
            "id": int,
            "actions_resources_id": int,
            "user_id": int,
            "group_id": int,
            "allow": bool,
        }, pk="id", not_null=[
            "actions_resources_id",
            "allow",
        ], foreign_keys=(
            ("user_id", "users", "id"),
            ("group_id", "groups", "id"),
            ("actions_resources_id", "actions_resources", "id"),
        ))
        # user permission search
        database["permissions"].create_index([
            "user_id",
            "actions_resources_id",
        ], unique=True)
        # group permission search
        database["permissions"].create_index([
            "group_id",
            "actions_resources_id",
        ], unique=True)


# TODO: on startup, create DB
# Permission: action, actor, resource (optional)
# Table: permissions
# Table: resources
# Table: users
# Table: groups
@hookimpl
def startup(datasette):
    async def inner():
        # db = get_or_create_db(datasette)
        create_tables(datasette=datasette)
        # table_names = await db.table_names()
        # if "groups" not in table_names:
        #     await db.execute_write_fn(build_table)
    return inner


# TODO: allow people to create groups
# groups can have users
# resources must have actions
# permissions can have users and groups and action and resource and allow/deny

# TODO: on permission requested: lookup permission in DB
#   1) found: return result
#   2) not: add permission to DB
# TODO: permission lookup routine (looks permission and user)
#   if not found: lookup user -> groups -> permission (join?)
@hookimpl
def permission_allowed(actor, action, resource):
    async def inner_permission_allowed():
        db = get_db()
        # perms = db["permissions"]
        users = db["users"]
        # groups = db["groups"]
        ar = db["actions_resources"]

        if actor and actor.id:
            data = {"lookup": "actor.id", "value": actor.id}
            query = (
                "select id from [users] "
                "where lookup = :lookup and value = :value"
            )
            results = db.execute(query, data).fetchall()
            if not len(results):
                users.insert(data, pk="id", replace=True)

        if action:
            data = {"action": action}
            query = "select id from actions_resources where action = :action"
            results = db.execute(query, data).fetchall()
            if not len(results):
                ar.insert(data, pk="id", replace=True)

        if resource and action:
            if isinstance(resource, str):
                data = {"action": action, "resource_primary": resource}
                query = (
                    "select id from actions_resources "
                    "where action = :action and resource_primary = :resource_primary"
                )
                results = db.execute(query, data).fetchall()
                if not len(results):
                    ar.insert(data, pk="id", replace=True)
            elif isinstance(resource, (tuple, list)) and len(resource) == 2:
                resource_primary, resource_secondary = resource
                data = {"action": action,
                        "resource_primary": resource_primary,
                        "resource_secondary": resource_secondary}
                query = (
                    "select id from actions_resources "
                    "where action = :action and "
                    "resource_primary = :resource_primary "
                    "and resource_secondary = :resource_secondary"
                )
                results = db.execute(query, data).fetchall()
                if not len(results):
                    ar.insert(data, pk="id", replace=True)
            # TODO: figure out a better way to store more complex resources. one
            # idea is to have a table that expresses more complex lookups, similar
            # to my plans with users. For now, just serialize the resource and
            # leave it at that
            else:
                print(f"Unrecognized data type for resource: '{resource}'")
                # data = {"action": action, "resource": json.dumps(resource)}
                return None

        # TODO: something like this...
        # actor_groups = get_groups(actor.id) # select * from groups where user_id=user_id;

        # Spitballing here ...
        # permissions = permission_found(
        #     select permission where allowed=true and ((
        #         permission_action = action

        #     ) or (
        #     ))
        # )

        # # select * from resources where id = resource;
        # trackartist IS NULL OR EXISTS(

        # # get users where user_id = actor.id and
        # actor
        # actor_groups
        # # Returning None falls back to default permissions
        # pass
    return inner_permission_allowed
