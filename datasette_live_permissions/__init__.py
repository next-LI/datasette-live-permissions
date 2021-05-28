import json
import os
import re
import sqlite3

import sqlite_utils
from datasette import hookimpl, database as ds_database
from datasette.utils.asgi import Response, Forbidden


DB_NAME="live_permissions"
DEFAULT_DBPATH="."


# used to check all required tables exist and for table specified
# in the CRUD endpoint
KNOWN_TABLES = [
    "users", "groups", "group-membership", "actions_resources", "permissions"
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
        database["users"].create_index([
            "lookup", "value",
        ], unique=True)
        database["users"].insert({
            "id": 1,
            "description": "Root account",
            "lookup": "actor.id",
            "value": "root",
        }, pk="id", replace=True)
        database["users"].insert({
            "id": 2,
            "description": "Unauthenticated users",
            "lookup": "actor",
            "value": None,
        }, pk="id", replace=True)

    if "groups" not in table_names:
        database["groups"].create({
            "id": int,
            "name": str,
        }, pk="id")
        database["groups"].insert({
            "id": 1,
            "name": "Auto-added users",
        }, pk="id", replace=True)
        database["groups"].create_index([
            "name",
        ], unique=True)

    if "group-membership" not in table_names:
        database["group-membership"].create({
            "group_id": int,
            "user_id": int,
        }, pk=("group_id", "user_id"))
        database["group-membership"].insert({
            "user_id": 1,
            "group_id": 1,
        }, pk=("group_id", "user_id"), replace=True)

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
        }, pk="id", not_null=[
            "actions_resources_id",
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


def get_lookups(db):
    # TODO: replace with a separate lookup table
    return db.execute(
        "select lookup from users where lookup != 'actor' group by lookup;"
    ).fetchall()


def bootstrap_and_fetch_users(db, actor):
    """
    This method does two things: it looks for users relevant to a permission check
    based on the actor provided by Datasette in this request. If users can't be found,
    one will be created so that it's easier for end users to manage permissions (since
    Datasette has no "users" table).

    Note that this also returns the "everyone" user regardless of if logged-in
    users are also found. This simplifies permission checks on the perms table.
    """
    users = db["users"]
    relevant_users = []
    # unauthenticated user (get or create)
    data = {"lookup": "actor", "value": actor}
    query = (
        "select id from [users] "
        "where lookup = :lookup and value is null"
    )
    results = db.execute(query, data).fetchall()
    if not len(results):
        users.insert(data, pk="id", replace=True)
    else:
        relevant_users += results

    # we have a logged-in user, use the lookups in our DB to
    # find possible matches
    if actor is not None:
        lookups = get_lookups(db)
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
            if value:
                lookup_values[lookup] = value
            lookup_clauses.append("(lookup = ? and value = ?)")
            lookup_args.append(value)
        where_conditions = " or ".join(lookup_clauses)
        query = f"select id from [users] where {where_conditions}"
        results = db.execute(query, lookup_args).fetchall()
        if not len(results):
            # github auth check, add it if we don't have it added already
            if "gh_email" in actor and "actor.gh_email" not in lookup_values:
                lookup_values["actor.gh_email"] = actor.get("gh_email")
            for lookup, value in lookup_values.items():
                users.insert({
                    "lookup": lookup,
                    "value": value,
                }, pk="id", replace=True)
                # just do the first one for now, people can
                # figure out other ways to do lookups from
                # the examples
                break
        else:
            relevant_users += results

    return relevant_users


def bootstrap_and_fetch_actions_resources(db, action, resource):
    ar = db["actions_resources"]

    relevant_actions = []
    if action:
        data = {"action": action}
        query = "select id from actions_resources where action = :action"
        relevant_actions = db.execute(query, data).fetchall()
        if not len(relevant_actions):
            ar.insert(data, pk="id", replace=True)

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
        # we could rely on
        elif isinstance(resource, (tuple, list)) and len(resource) == 2:
            resource_primary, resource_secondary = resource

            # do a primary only query first
            data = {"action": action, "resource_primary": resource_primary}
            resource_primary_cond = "is null"
            if resource:
                resource_primary_cond = "= :resource_primary"
            query = (
                "select id from actions_resources "
                f"where action = :action and resource_primary {resource_primary_cond}"
            )
            results = db.execute(query, data).fetchall()
            if len(results):
                relevant_actions += results

            # then do a primary w/ secondary check
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
                # only do the insert here for primary w/ secondary
                # (and not above) because this one is user-initiated
                ar.insert(data, pk="id", replace=True)
            else:
                relevant_actions += results

        # TODO: figure out a better way to store more complex resources. one
        # idea is to have a table that expresses more complex lookups, similar
        # to my plans with users. For now, just serialize the resource and
        # leave it at that
        else:
            return None

    return relevant_actions or None


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
    ])
    perms = [p for p in db["permissions"].rows_where(cond)]
    for perm in perms:
        return True


# TODO: on permission requested: lookup permission in DB
#   1) found: return result
#   2) not: add permission to DB
# TODO: permission lookup routine (looks permission and user)
#   if not found: lookup user -> groups -> permission (join?)
@hookimpl
def permission_allowed(actor, action, resource):
    async def inner_permission_allowed():
        db = get_db()
        authed_users = bootstrap_and_fetch_users(db, actor)
        relevant_actions = bootstrap_and_fetch_actions_resources(db, action, resource)
        return check_permission(actor, action, resource, db, authed_users, relevant_actions)

    return inner_permission_allowed


@hookimpl
def register_routes():
    return [
        (r"^/-/live-permissions/(?P<table>.*)/(?P<id>.*)/?$", perms_crud),
    ]


async def perms_crud(scope, receive, datasette, request):
    table = request.url_vars["table"]
    obj_id = request.url_vars["id"]
    next = request.args.get("next", f"/live_permissions/{table}")

    if not await datasette.permission_allowed(
        request.actor, "live-permissions-edit", default=False
    ):
        raise Forbidden("Permission denied")

    assert table and obj_id, "Invalid URL"
    assert request.method in ["POST", "DELETE"], "Bad method"
    assert table in KNOWN_TABLES, "Bad table name provided"
    assert obj_id == "new" or re.match(r"[0-9]+", obj_id), "Bad id provided"

    db = get_db(datasette=datasette)
    # POST is just dual update/create (depending on if id=="new")
    if request.method == "POST":
        formdata = await request.post_vars()

        if "csrftoken" in formdata:
            del formdata["csrftoken"]

        pk = "id"
        if table == "group-membership":
            pk = ("group_id", "user_id")
        db[table].insert(
            formdata, pk=pk, alter=False, replace=True
        )
        return Response.redirect(next)

    elif request.method == "DELETE":
        db[table].delete(obj_id)
        return Response.redirect(next)
