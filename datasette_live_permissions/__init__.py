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

    # TODO: create some defaults
    # actions resources:
    # - view-instance
    # - view-database
    # maybe create some sane defaults?
    # users:
    # - unauthenticated user
    # - root user
    # - if github plugin installed, an example gh_email?
    # permissions:
    # - view-instance to unauthenticated?

    # TODO: user lookup -> use a lookup table! then
    # we can use the lookup table to actually perform
    # the lookups on the users in a request
    if "users" not in table_names:
        database["users"].create({
            "id": int,
            "description": str,
            "lookup": str,
            "value": str,
        }, not_null=[
            "lookup"
        ], pk="id")

    # We need a lookup "through" table here
    # if "groups" not in table_names:
    #     database["groups"].create({
    #         "id": int,
    #         "user_id": int,
    #     }, pk="id", foreign_keys=(
    #         ("user_id", "users", "id"),
    #     ))
    # if "groups" not in table_names:
    #     database["groups"].lookup({
    #         "user_id": int
    #     })

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


def user_lookup(actor, lookup_str):
    """
    Apply a lookup string, as stored in the users table, to a
    given actor, for use in performing user permission checks.

    E.g. if we have an actor: `{id: "root"}` and lookup string:
        `actor.id` calling this function will return "root".
    """
    if not lookup_str or not lookup_str.startswith("actor"):
        return None
    value = None
    for lookup in lookup_str.split("."):
        if lookup == "actor":
            value = actor
            continue
        if lookup not in value:
            return None
        else:
            value = value[lookup]
    return value


def flat_ids(rows):
    return ",".join([str(r["id"]) for r in rows])


# TODO: allow people to create groups
# groups can have users
# resources must have actions
# permissions can have users and groups and action and resource and allow/deny

def check_permission(actor, action, resource, db, authed_users, relevant_actions):
    # TODO: find groups
    group_ids = ""
    user_ids = ",".join([
        str(a[0]) for a in authed_users or []
    ])
    ar_ids = ",".join([
        str(a[0]) for a in relevant_actions or []
    ])

    cond = " and ".join([
        f"actions_resources_id in ({ar_ids})",
        f"(user_id in ({user_ids}) or group_id in ({group_ids}))",
        "allow=true",
    ])
    print("cond", cond)
    perms = [p for p in db["permissions"].rows_where(cond)]
    print("perms", perms)

    for perm in perms:
        print("Access granted")
        return True
    print("Access denied")
    return False


def get_lookups(db):
    # TODO: replace with a separate lookup table
    return db.execute(
        "select lookup from users where lookup != 'actor' group by lookup;"
    ).fetchall()


def bootstrap_fetch_user(db, actor):
    users = db["users"]
    if actor is None:
        data = {"lookup": "actor", "value": actor}
        query = (
            "select id from [users] "
            "where lookup = :lookup and value is null"
        )
        results = db.execute(query, data).fetchall()
        print(query, data, "results", results)
        if not len(results):
            users.insert(data, pk="id", replace=True)

    # we have a logged-in user, use the lookups in our DB to
    # find possible matches
    else:
        lookups = get_lookups(db)
        print("lookups", lookups)
        # this could probably be cleaned up significantly, but basically
        # we just want to build the query and also fetch the user ID(s??)
        # for the matching user
        lookup_values = {}
        lookup_clauses = []
        lookup_args = []
        for row in lookups:
            lookup = row[0]
            lookup_args.append(lookup)
            value = user_lookup(actor, lookup)
            lookup_values[lookup] = value
            lookup_clauses.append("(lookup = ? and value = ?)")
            lookup_args.append(value)
        print("lookup_clauses", lookup_clauses)
        print("lookup_args", lookup_args)
        where_conditions = " or ".join(lookup_clauses)
        query = f"select id from [users] where {where_conditions}"
        print("query", query)
        results = db.execute(query, lookup_args).fetchall()
        if not len(results):
            for lookup, value in lookup_values.items():
                if not value: continue
                users.insert({
                    "lookup": lookup,
                    "value": value,
                }, pk="id", replace=True)
                # just do the first one for now, people can
                # figure out other ways to do lookups from
                # the examples
        else:
            return results
    return []


def bootstrap_fetch_actions_resources(db, action, resource):
    ar = db["actions_resources"]

    relevant_actions = []
    if action:
        data = {"action": action}
        query = "select id from actions_resources where action = :action"
        relevant_actions = db.execute(query, data).fetchall()
        if not len(relevant_actions):
            # we won't consider newly added actions for check below
            ar.insert(data, pk="id", replace=True).m2m(
                "groups", lookup={
                    "name": "Auto-added users"
                }
            )

    if resource and action:
        if isinstance(resource, str):
            data = {"action": action, "resource_primary": resource}
            resource_primary_cond = "is null"
            if resource:
                resource_primary_cond = "= :resource_primary"
            query = (
                "select id from actions_resources "
                f"where action = :action and resource_primary {resource_primary_cond}"
            )
            results = db.execute(query, data).fetchall()
            if not len(results):
                ar.insert(data, pk="id", replace=True)
            else:
                relevant_actions += results
        # NOTE: we probably don't need this since resources always have actions
        elif isinstance(resource, (tuple, list)) and len(resource) == 2:
            resource_primary, resource_secondary = resource
            data = {"action": action,
                    "resource_primary": resource_primary,
                    "resource_secondary": resource_secondary}
            resource_primary_cond = "is_null"
            if resource_primary:
                resource_primary_cond = "= :resource_primary"
            resource_secondary_cond = "is null"
            if resource_secondary:
                resource_secondary_cond = "= :resource_secondary"
            query = (
                "select id from actions_resources "
                "where action = :action and "
                f"resource_primary {resource_primary_cond} and "
                f"resource_secondary {resource_secondary_cond}"
            )
            results = db.execute(query, data).fetchall()
            if not len(results):
                ar.insert(data, pk="id", replace=True)
            else:
                relevant_actions += results
        # TODO: figure out a better way to store more complex resources. one
        # idea is to have a table that expresses more complex lookups, similar
        # to my plans with users. For now, just serialize the resource and
        # leave it at that
        else:
            print(f"Unrecognized data type for resource: '{resource}'")
            # data = {"action": action, "resource": json.dumps(resource)}
            return None

    return relevant_actions


# TODO: on permission requested: lookup permission in DB
#   1) found: return result
#   2) not: add permission to DB
# TODO: permission lookup routine (looks permission and user)
#   if not found: lookup user -> groups -> permission (join?)
@hookimpl
def permission_allowed(actor, action, resource):
    async def inner_permission_allowed():
        db = get_db()

        authed_users = bootstrap_fetch_user(db, actor)
        print("authed_users", authed_users)

        relevant_actions = bootstrap_fetch_actions_resources(db, action, resource)
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
        # TODO: something like this...
        # actor_groups = get_groups(actor.id) # select * from groups where user_id=user_id;
        return check_permission(actor, action, resource, db, authed_users, relevant_actions)

    return inner_permission_allowed
