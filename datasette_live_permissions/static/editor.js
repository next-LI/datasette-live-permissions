async function doDelete(url_path, body) {
  const csrf_els = $("input[name='csrftoken']");
  if (!csrf_els || !csrf_els[0]) return;
  const csrftoken = csrf_els[0].value;

  const opts = {
    method: 'DELETE',
    headers: {
      "x-csrftoken": csrftoken,
    },
  };
  if (body) {
    opts.headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=UTF-8';
    opts.body = new URLSearchParams(body);
  }

  const response = await fetch(url_path, opts);
  return response;
}

function lastPathPart() {
  const parts = document.location.pathname.split("/").filter(x=>x);
  return parts[parts.length-1];
}

async function deleteItem(e) {
  const parentEl = $(e.target.parentElement);
  const cols = parentEl.find("td.type-pk");
  if (!cols || !cols[0]) return;

  const objId = cols[0].innerText.trim();
  const table = lastPathPart();
  const url_path = `/-/live-permissions/${table}/${objId}`;

  const response = await doDelete(url_path);
  if (response.status === 204) document.location.reload();
}

async function deleteItemDB(e) {
  const parentEl = $(e.target.parentElement);
  const cols = parentEl.find("td");
  if (!cols || !cols[0]) return;

  const objId = cols[0].innerText.trim();
  const db_name = lastPathPart();
  const url_path = `/-/live-permissions/db/manage/${db_name}`;

  const response = await doDelete(url_path, {
    user_id: objId
  });
  if (response.status === 204) document.location = document.location.href;
}

function addTrashCans() {
  $(".rows-and-columns thead tr").append("<th>delete</th>");
  $(".rows-and-columns tbody tr").append("<td class='delete-item'>🗑️</td>");
  $('.delete-item').on("click", deleteItem);
  $('.delete-item-db').on("click", deleteItemDB);
}

function s2_data(type, params) {
  switch(type) {
    case 'action-resource':
      return {
        action__contains: params.term,
        _shape: 'array',
        _size: 'max',
      };
    case 'user':
      return {
        value__contains: params.term,
        _shape: 'array',
        _size: 'max',
      };
    case 'group':
      return {
        name__contains: params.term,
        _shape: 'array',
        _size: 'max',
      };
  }
}

function s2_process(type, data) {
  switch(type) {
    case 'action-resource':
      return {
        results: data.map((rec) => {
          let text = rec.action;
          if (rec.resource_primary) {
            text += `: ${rec.resource_primary}`;
          }
          if (rec.resource_secondary) {
            text += `, ${rec.resource_secondary}`;
          }
          return {id: rec.id, text};
        }),
      };
    case 'user':
      return {
        results: data.map((rec) => {
          let text = `${rec.lookup} => ${rec.value}`;
          if (rec.description) {
            text += ` (${rec.description})`;
          }
          return {id: rec.id, text: text};
        }),
      };
    case 'group':
      return {
        results: data.map((rec) => {
          return {id: rec.id, text: rec.name};
        }),
      };
  }
}

function setup() {
  $('#actions-resources-id').select2({
    placeholder: 'Select an action',
    ajax: {
      url: '/live_permissions/actions_resources.json',
      dataType: 'json',
      data: s2_data.bind(this, 'action-resource'),
      processResults: s2_process.bind(this, 'action-resource')
    }
  });

  $('#user-id').select2({
    placeholder: 'Select a user',
    ajax: {
      url: '/live_permissions/users.json',
      dataType: 'json',
      data: s2_data.bind(this, 'user'),
      processResults: s2_process.bind(this, 'user')
    }
  });

  $('#group-id').select2({
    placeholder: 'Select a group',
    ajax: {
      url: '/live_permissions/groups.json',
      dataType: 'json',
      data: s2_data.bind(this, 'group'),
      processResults: s2_process.bind(this, 'group'),
    }
  });

  addTrashCans();
}

$(document).ready(setup);
