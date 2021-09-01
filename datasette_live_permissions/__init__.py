import json
import os
import re
import sqlite3

import sqlite_utils
from datasette import hookimpl, database as ds_database
from datasette.utils.asgi import Response, Forbidden


DB_NAME="live_permissions"
DEFAULT_DBPATH="."
BLOCKED_DB_ACTIONS = [
    "live_permissions", "live_config",
    "_internal", "_memory",
]


# used to check all required tables exist and for table specified
# in the CRUD endpoint
KNOWN_TABLES = [
    "users", "groups", "group_membership", "actions_resources", "permissions"
]


def get_db_path(datasette):
    config = datasette.plugin_config("datasette-live-permissions") or {}
    default_db_path = config.get("db_path", DEFAULT_DBPATH)
    return os.path.join(default_db_path, f"{DB_NAME}.db")


def get_db(datasette):
    """
    Returns a sqlite_utils.Database, not datasette.Database, but a datasette
    Database can be got through datasette.databases[DB_NAME] after this runs.
    """
    # this will create the DB if not exists
    database_path = get_db_path(datasette)
    conn = sqlite3.connect(database_path)
    db = sqlite_utils.Database(conn)
    # just make it show up in the DBs list
    if datasette and not (DB_NAME in datasette.databases):
        datasette.add_database(
            ds_database.Database(datasette, path=database_path, is_mutable=True),
            name=DB_NAME,
        )
    return db


def make_query(preamble, key_values):
    """
    Takes a beginning query and dict, where they keys are column names
    and the values are the values in need of querying and return a query
    where "is null" is used in place where None values are encountered.

    E.g., make_query("select * from tbl where", {"action": "greet", "person": None})

    Returns: "select * from tbl where action = :action and person is null"
    """
    query_parts = []
    for key, value in key_values.items():
        if value is None:
            query_parts.append(f"{key} is null")
        else:
            query_parts.append(f"{key} = :{key}")
    query_conditionals = " and ".join(query_parts)
    return f"{preamble} {query_conditionals}"


def setup_default_permissions(datasette):
    db = get_db(datasette)
    ar_tbl = db["actions_resources"]
    users = db["users"]
    groups = db["groups"]

    # NOTE: If these aren't already created then they won't
    # be assigned any permissions
    anyone="lookup='actor' and value is null"
    grp_is_admin="name='Admins'"
    grp_is_survey_admin="name='Survey Admins'"
    grp_is_config_admin="name='Config Admins'"
    grp_is_perms_admin="name='Permission Admins'"

    # A list of datasette-provided defaults. Some of these fields are
    # just informational, like description and default. For each here,
    # we'll add it to the actions-resources DB to bootstrap. If one of
    # these items has "set_to" then the query will be executed and
    # the resulting users will be given access in the permissions table.
    default_ars = [{
        "action": "view-instance",
        "allow_users": anyone,
    }, {
        # Actor is allowed to view all databases
        # default: allow
        "action": "view-database",
        "allow_groups": grp_is_admin,
    }, {
        # Actor is allowed to view all tables
        # default: allow
        "action": "view-table",
        "allow_groups": grp_is_admin,
    }, {
        # Actor is allowed to run arbitrary SQL queries against databases
        # default: allow
        "action": "execute-sql",
        "allow_groups": grp_is_admin,
    }, {
        # Actor is allowed to download all databases",
        # default: allow
        "action": "view-database-download",
        "allow_groups": grp_is_admin,
    }, {
        # Controls if the various debug pages are displayed in the
        # navigation menu.
        # "default": "deny",
        "action": "debug-menu",
        "allow_groups": grp_is_admin,
    }, {
        # Allow people to import new CSVs!
        "action": "csv-importer",
        "allow_groups": grp_is_admin,
    }, {
        # Allow to view permissions database
        "action": "view-database",
        "resource_primary": "live_permissions",
        "allow_groups": " or ".join([grp_is_admin, grp_is_perms_admin]),
    }, {
        # Allow to view permissions database tables
        "action": "view-table",
        "resource_primary": "live_permissions",
        "allow_groups": " or ".join([grp_is_admin, grp_is_perms_admin]),
    }, {
        # Allow to execute SQL against permissions database
        "action": "execute-sql",
        "resource_primary": "live_permissions",
        "allow_groups": " or ".join([grp_is_admin, grp_is_perms_admin]),
    }, {
        # allow to edit permissions
        "action": "live-permissions-edit",
        "allow_groups": " or ".join([grp_is_admin, grp_is_perms_admin]),
    }, {
        # Actor is allowed to view the /-/permissions debug page.
        # default: deny,
        "action": "permissions-debug",
        "allow_groups": " or ".join([grp_is_admin, grp_is_perms_admin]),
    },{
        # Ability to view and edit global configuration
        "action": "live-config",
        "allow_groups": " or ".join([grp_is_admin, grp_is_config_admin]),
    }, {
        # Can see the list of surveys
        "action": "surveys-list",
        "allow_groups": " or ".join([grp_is_admin, grp_is_survey_admin]),
    }, {
        "action": "surveys-create",
        "allow_groups": " or ".join([grp_is_admin, grp_is_survey_admin]),
    }, {
        "action": "surveys-delete",
        "allow_groups": " or ".join([grp_is_admin, grp_is_survey_admin]),
    }, {
        "action": "surveys-edit",
        "allow_groups": " or ".join([grp_is_admin, grp_is_survey_admin]),
    }, {
        # Can view the survey response form
        "action": "surveys-view",
        "allow_users": anyone,
        "allow_groups": grp_is_survey_admin,
    }, {
        # Can respond to survey response form
        "action": "surveys-respond",
        "allow_users": anyone,
        "allow_groups": grp_is_survey_admin,
    }]
    # create convenience view-table/db functions for available dbs
    if datasette:
        for db_name in datasette.databases:
            grp_db = f"DB Access: {db_name}"
            groups.insert({
                "name": grp_db,
            }, pk="id", replace=True)

            allow_grps = " or ".join([
                f"name='{grp_db}'", grp_is_admin
            ])
            default_ars.append({
                "action": "view-database",
                "resource_primary": db_name,
                "allow_groups": allow_grps,
            })
            default_ars.append({
                "action": "view-table",
                "resource_primary": db_name,
                "allow_groups": allow_grps,
            })
            default_ars.append({
                "action": "live-config",
                "resource_primary": db_name,
                "allow_groups": allow_grps,
            })

    for default_ar in default_ars:
        ar_data = {
            "action": default_ar["action"],
            "resource_primary": default_ar.get("resource_primary")
        }
        result = ar_tbl.insert(ar_data, pk="id", replace=True)

        if "allow_users" not in default_ar and "allow_groups" not in default_ar:
            continue

        if default_ar.get("allow_users"):
            for u in users.rows_where(default_ar.get("allow_users")):
                for ar in ar_tbl.rows_where(make_query("", ar_data), ar_data):
                    db["permissions"].insert({
                        "actions_resources_id": ar["id"],
                        "user_id": u["id"],
                    }, replace=True)

        if default_ar.get("allow_groups"):
            for g in groups.rows_where(default_ar.get("allow_groups")):
                for ar in ar_tbl.rows_where(make_query("", ar_data), ar_data):
                    db["permissions"].insert({
                        "actions_resources_id": ar["id"],
                        "group_id": g["id"],
                    }, replace=True)


def add_user(database, user_dict):
    """
    Add a user by a provided user_dict lookup and also add them
    to the auto-added users group.
    """
    users_tbl = database["users"]
    users_tbl.insert(user_dict, pk="id", replace=True)
    query = make_query("", user_dict)
    uid = None
    for u in users_tbl.rows_where(query, user_dict, limit=1):
        uid = u["id"]
    if uid is not None:
        database["group_membership"].insert({
            "user_id": uid,
            "group_id": 1,
        }, pk=("group_id", "user_id"), replace=True)


def have_live_config_plugin(datasette):
    """
    Checks to see if we have the datasette-live-config plugin
    installed. If so, we can integrate with it.
    """
    if not datasette:
        return
    for plugin in datasette._plugins():
        if plugin.get("name") == "datasette-live-config":
            return True
    return False


def create_tables(datasette):
    """
    Bootstrap all the tables and default users, groups and permissions.
    """
    database = get_db(datasette)
    table_names = database.table_names()

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
            "description": "Anybody (authed or not)",
            "lookup": "actor",
            "value": None,
        }, pk="id", replace=True)

    if "groups" not in table_names:
        database["groups"].create({
            "id": int,
            "name": str,
        }, pk="id")
        database["groups"].create_index([
            "name",
        ], unique=True)
        database["groups"].insert({
            "id": 1,
            "name": "Auto-added users",
        }, pk="id", replace=True)
        database["groups"].insert({
            "name": "Admins",
        }, pk="id", replace=True)
        database["groups"].insert({
            "name": 'Permission Admins'
        }, pk="id", replace=True)
        # TODO: check for surveys plugin
        database["groups"].insert({
            "name": 'Survey Admins',
        }, pk="id", replace=True)
        # TODO: check for config plugin
        database["groups"].insert({
            "name": 'Config Admins'
        }, pk="id", replace=True)

    if "group_membership" not in table_names:
        database["group_membership"].create({
            "group_id": int,
            "user_id": int,
        }, pk=("group_id", "user_id"), foreign_keys=(
            ("user_id", "users", "id"),
            ("group_id", "groups", "id"),
        ))
        database["group_membership"].insert({
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
        setup_default_permissions(datasette)

    if have_live_config_plugin(datasette) and "__metadata" not in table_names:
        database["__metadata"].insert({
            "key": "tables",
            "value": json.dumps({
                "groups": {
                    "hidden": False,
                    "label_column": "name"
                },
                "users": {
                    "hidden": False,
                    "label_column": "value"
                },
                "actions_resources": {
                    "hidden": False,
                    "label_column": "action"
                },
                "__metadata": {
                    "hidden": True
                }
            })
        }, pk="key", alter=True, replace=False)


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
        create_tables(datasette)
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
            # github auth plugin support
            if actor.get("gh_email"):
                add_user(db, {
                    "lookup": "actor.gh_email",
                    "value": actor.get("gh_email"),
                })
            else:
                for lookup, value in lookup_values.items():
                    add_user(db, {
                        "lookup": lookup,
                        "value": value,
                    })
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
        query = (
            "select id from actions_resources where action = :action "
            "and resource_primary is null and resource_secondary is null"
        )
        relevant_actions = db.execute(query, data).fetchall()
        if not len(relevant_actions):
            ar.insert(data, pk="id", replace=True)

    if resource and action:
        if isinstance(resource, str):
            data = {"action": action, "resource_primary": resource}
            query = make_query("select id from actions_resources where", data)
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
            data = {
                "action": action,
                "resource_primary": resource_primary,
                "resource_secondary": None
            }
            query = make_query("select id from actions_resources where", data)
            results = db.execute(query, data).fetchall()
            if len(results):
                relevant_actions += results

            # then do a primary w/ secondary check
            data = {
                "action": action,
                "resource_primary": resource_primary,
                "resource_secondary": resource_secondary
            }
            query = make_query("select id from actions_resources where", data)
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


def check_permission(actor, action, resource, db, authed_users, relevant_actions):
    user_ids = ",".join([
        str(a[0]) for a in authed_users or []
    ])
    group_ids = ",".join(set([
        str(g["group_id"]) for g in db["group_membership"].rows_where(
            f"user_id in ({user_ids})"
        )
    ]))
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
    if actor and actor.get("id") == "root":
        return True
    return False


# TODO: on permission requested: lookup permission in DB
#   1) found: return result
#   2) not: add permission to DB
# TODO: permission lookup routine (looks permission and user)
#   if not found: lookup user -> groups -> permission (join?)
@hookimpl
def permission_allowed(datasette, actor, action, resource):
    async def inner_permission_allowed():
        db = get_db(datasette)
        authed_users = bootstrap_and_fetch_users(db, actor)
        relevant_actions = bootstrap_and_fetch_actions_resources(
            db, action, resource
        )
        return check_permission(
            actor, action, resource, db, authed_users, relevant_actions
        )

    return inner_permission_allowed


@hookimpl
def menu_links(datasette, actor):
    async def inner():
        if not await datasette.permission_allowed(
            actor, "live-permissions-edit", default=False
        ):
            return
        return [{
            "href": datasette.urls.path(f"/{DB_NAME}"),
            "label": "Permissions"
        }]
    return inner


@hookimpl
def database_actions(datasette, actor, database):
    async def inner_database_actions():
        # don't let people do these unsupported things
        if database in BLOCKED_DB_ACTIONS:
            return
        allowed = await datasette.permission_allowed(
            actor, "live-permissions-edit", database, default=False
        )
        if allowed:
            return [{
                "href": datasette.urls.path(f"/-/live-permissions/db/manage/{database}"),
                "label": "Manage permissions",
            }]
    return inner_database_actions


@hookimpl
def register_routes():
    return [
        (r"^/-/live-permissions/db/manage/(?P<database>.*)/?$", manage_db_group),
        (r"^/-/live-permissions/(?P<table>.*)/(?P<id>.*)/?$", perms_crud),
    ]


async def perms_crud(scope, receive, datasette, request):
    table = request.url_vars["table"]
    default_next = datasette.urls.path(f"/live_permissions/{table}")
    next = request.args.get("next", default_next)
    obj_id = request.url_vars["id"]

    if not await datasette.permission_allowed(
        request.actor, "live-permissions-edit", default=False
    ):
        raise Forbidden("Permission denied")

    assert table and obj_id, "Invalid URL"
    assert request.method in ["POST", "DELETE"], "Bad method"
    assert table in KNOWN_TABLES, "Bad table name provided"

    db = get_db(datasette)
    # POST is just dual update/create (depending on if id=="new")
    if request.method == "POST":
        formdata = await request.post_vars()

        if "csrftoken" in formdata:
            del formdata["csrftoken"]

        pk = "id"
        if table == "group_membership":
            pk = ("group_id", "user_id")
        db[table].insert(
            formdata, pk=pk, alter=False, replace=False
        )
        return Response.redirect(next)

    elif request.method == "DELETE":
        try:
            obj_id = int(obj_id)
        except ValueError:
            obj_id = tuple(int(i) for i in obj_id.split(","))
        db[table].delete(obj_id)
        return Response.text('', status=204)

    else:
        raise NotImplementedError("Bad HTTP method!")


async def manage_db_group(scope, receive, datasette, request):
    db_name = request.url_vars["database"]
    if not await datasette.permission_allowed(
        request.actor, "live-permissions-edit", db_name, default=False
    ):
        raise Forbidden("Permission denied")

    db = get_db(datasette)

    group_id = None
    results = db["groups"].rows_where("name=?", [f"DB Access: {db_name}"])
    for row in results:
        group_id = row["id"]
        break

    assert db_name in datasette.databases, "Non-existant database!"

    if not group_id and db_name not in BLOCKED_DB_ACTIONS:
        db["groups"].insert({
            "name": f"DB Access: {db_name}",
        }, pk="id", replace=True)
        return await manage_db_group(scope, receive, datasette, request)

    if request.method in ["POST", "DELETE"]:
        formdata = await request.post_vars()
        user_id = formdata["user_id"]

        if request.method == "POST":
            db["group_membership"].insert({
                "group_id": group_id,
                "user_id": user_id,
            }, replace=True)
        elif request.method == "DELETE":
            db["group_membership"].delete((group_id, user_id))
            return Response.text('', status=204)
        else:
            raise NotImplementedError(f"Bad method: {request.method}")

    perms_query = """
        select distinct user_id as id, lookup, value, description
        from group_membership join users
        on group_membership.user_id = users.id
        where group_membership.group_id=?
    """
    users = db.execute(perms_query, (group_id,))
    return Response.html(
        await datasette.render_template(
            "database_management.html", {
                "database": db_name,
                "users": users,
            }, request=request
        )
    )
