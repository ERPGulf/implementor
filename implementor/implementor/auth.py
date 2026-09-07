import base64
import io
import json
import os
from base64 import b64encode

import frappe
import requests
from frappe import _
from pyqrcode import create as qr_create
from werkzeug.wrappers import Response
import frappe


def is_admin(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or "System Manager" or "Project Manager" in frappe.get_roles(user)


def get_task_permission_query_conditions(user=None):
    user = user or frappe.session.user
    if is_admin(user):
        return ""
    u = frappe.db.escape(user)
    return f"""(
        `tabTask`.`owner` = {u}
        OR `tabTask`.`custom_assigned_by` = {u}
        OR `tabTask`.`custom_division_lead` = {u}
        OR `tabTask`.`completed_by` = {u}
    )"""
def has_task_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if is_admin(user):
        return True
    return user in {doc.owner, doc.custom_assigned_by, doc.custom_division_lead}

# ---------------- PROJECT (read-only, derived from Task + ToDo) ----------------

def get_project_permission_query_conditions(user=None):
    user = user or frappe.session.user
    if is_admin(user):
        return ""
    u = frappe.db.escape(user)
    return f"""(
        `tabProject`.`name` in (
            select distinct `project` from `tabTask`
            where `tabTask`.`project` is not null
            and (
                `tabTask`.`owner` = {u}
                or `tabTask`.`custom_assigned_by` = {u}
                or `tabTask`.`custom_division_lead` = {u}
                OR `tabTask`.`completed_by` = {u}
            )
        )
        or `tabProject`.`name` in (
            select distinct `reference_name` from `tabToDo`
            where `tabToDo`.`reference_type` = 'Project'
            and (
                `tabToDo`.`allocated_to` = {u}
                or `tabToDo`.`assigned_by` = {u}
            )
        )
    )"""

def has_project_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if is_admin(user):
        return True

    if permission_type and permission_type != "read":
        return False  # non-admins never get write/create/delete on Project

    via_task = frappe.get_all(
        "Task",
        filters={"project": doc.name},
        or_filters=[
            ["owner", "=", user],
            ["custom_assigned_by", "=", user],
            ["custom_division_lead", "=", user],
            ["completed_by", "=", user],
        ],
        limit=1,
    )
    if via_task:
        return True

    via_todo = frappe.get_all(
        "ToDo",
        filters={"reference_type": "Project", "reference_name": doc.name},
        or_filters=[
            ["allocated_to", "=", user],
            ["assigned_by", "=", user],
        ],
        limit=1,
    )
    return bool(via_todo)
def get_todo_permission_query_conditions(user=None):
    user = user or frappe.session.user
    if is_admin(user):
        return ""
    u = frappe.db.escape(user)
    return f"""(
        `tabToDo`.`owner` = {u}
        OR `tabToDo`.`assigned_by` = {u}
        OR `tabToDo`.`allocated_to` = {u}
    )"""
def has_todo_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if is_admin(user):
        return True
    return user in {doc.allocated_to, doc.assigned_by}



AUTH_ERROR = _("Authentication failed")
def log_activity(subject, status, user=None):
    """Write a debug entry to Activity Log, swallowing any insert errors."""
    try:
        frappe.get_doc({
            "doctype": "Activity Log",
            "subject": subject,
            "user": user or "Guest",
            "full_name": user or "Guest",
            "status": status,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as log_err:
        frappe.log_error(f"Activity Log insert failed: {log_err}", "generate_token_secure: Activity Log Error")


def whoami():
    """
    Get current session user.

    Returns:
        Current session username or raises error
    """
    try:
        return frappe.session.user
    except Exception:
        frappe.throw(AUTH_ERROR)


@frappe.whitelist(allow_guest=True)
def generate_token_secure(api_key, api_secret, app_key):
    # NOTE: api_secret is a password. Do not log it in plaintext.
    frappe.log_error(
        "generate_token_secure: Function Call",
        f"[generate_token_secure] Called with username: {api_key}",
    )

    log_activity(
        subject=f"[DEBUG] generate_token_secure called | username: {api_key}",
        status="",
        user=api_key,
    )

    try:
        try:
            app_key = base64.b64decode(app_key).decode("utf-8")
        except Exception as e:
            frappe.log_error(
                "generate_token_secure: Decode Error",
                f"[generate_token_secure] Base64 decode failed | username: {api_key} | error: {str(e)}",
            )
            log_activity(
                subject=f"[DEBUG] Base64 decode failed | username: {api_key} | error: {str(e)}",
                status="Failed",
                user=api_key,
            )
            return Response(
                json.dumps({"message": "Security Parameters are not valid", "user_count": 0}),
                status=401,
                mimetype="application/json",
            )

        client = frappe.db.get_value(
            "OAuth Client",
            {"app_name": app_key},
            ["name", "client_id", "client_secret", "user"],
            as_dict=True,
        )

        if not client:
            frappe.log_error(
                "generate_token_secure: OAuth Client Missing",
                f"[generate_token_secure] OAuth client not found | app_key: {app_key} | username: {api_key}",
            )
            log_activity(
                subject=f"[DEBUG] OAuth client not found | app_key: {app_key} | username: {api_key}",
                status="Failed",
                user=api_key,
            )
            return Response(
                json.dumps({"message": "Security Parameters are not valid", "user_count": 0}),
                status=401,
                mimetype="application/json",
            )

        client_id = client.client_id
        client_secret = client.client_secret

        url = frappe.local.conf.host_name + "/api/method/frappe.integrations.oauth2.get_token"

        payload = {
            "username": api_key,
            "password": api_secret,
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=payload, headers=headers)

        if response.status_code == 200:
            result_data = response.json()

            log_activity(
                subject=f"[DEBUG] Token generated successfully | username: {api_key}",
                status="Success",
                user=api_key,
            )

            return Response(
                json.dumps({"data": result_data}),
                status=200,
                mimetype="application/json",
            )
        else:
            frappe.log_error(
                "generate_token_secure: Token Request Failed",
                f"[generate_token_secure] Token request failed | username: {api_key} | HTTP {response.status_code} | response: {response.text}",
            )
            log_activity(
                subject=f"[DEBUG] Token request failed | username: {api_key} | HTTP {response.status_code}",
                status="Failed",
                user=api_key,
            )
            return Response(
                response.text,
                status=401,
                mimetype="application/json",
            )

    except Exception as e:
        frappe.log_error(
            "generate_token_secure: Exception",
            f"[generate_token_secure] Unhandled exception | username: {api_key} | error: {str(e)}",
        )
        log_activity(
            subject=f"[DEBUG] Unhandled exception | username: {api_key} | error: {str(e)}",
            status="Failed",
            user=api_key,
        )
        return Response(
            json.dumps({"message": str(e), "user_count": 0}),
            status=500,
            mimetype="application/json",
        )

@frappe.whitelist(allow_guest=False)
def create_refresh_token(refresh_token):
    """
    Create a new access token using a refresh token.

    Args:
        refresh_token: Refresh token string

    Returns:
        Response with new token data or error message
    """
    url = f"{frappe.local.conf.host_name}/api/method/frappe.integrations.oauth2.get_token"

    payload = f"grant_type=refresh_token&refresh_token={refresh_token}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        response = requests.post(url, headers=headers, data=payload)

        if response.status_code == 200:
            try:
                message_json = response.json()
                new_message = {
                    "access_token": message_json["access_token"],
                    "expires_in": message_json["expires_in"],
                    "token_type": message_json["token_type"],
                    "scope": message_json["scope"],
                    "refresh_token": message_json["refresh_token"],
                }

                return Response(
                    json.dumps({"data": new_message}),
                    status=200,
                    mimetype="application/json",
                )
            except (json.JSONDecodeError, KeyError) as e:
                return Response(
                    json.dumps({"data": f"Error decoding JSON: {e}"}),
                    status=401,
                    mimetype="application/json",
                )
        else:
            return Response(
                json.dumps({"data": response.text}),
                status=401,
                mimetype="application/json",
            )
    except Exception as e:
        return Response(
            json.dumps({"data": f"Error: {str(e)}"}),
            status=500,
            mimetype="application/json",
        )


def create_qr_code(doc, method):
    """Create QR Code after inserting Employee"""
    if not hasattr(doc, 'custom_qr_code'):
        return

    fields = frappe.get_meta('Employee').fields
    auth_client_name = frappe.db.get_value("OAuth Client", {}, "name")
    if auth_client_name:
        auth_client = frappe.get_doc("OAuth Client", auth_client_name)
    else:
        frappe.throw("No OAuth Client found")
    app_name = auth_client.app_name
    if not app_name:
        frappe.throw(_('App name missing in OAuth Client'))

    app_key = base64.b64encode(app_name.encode()).decode("utf-8")

    for field in fields:
        if field.fieldname == 'custom_qr_code' and field.fieldtype == 'Attach Image':

            company_name = frappe.db.get_value('Company', doc.company, 'company_name')
            if not company_name:
                frappe.throw(_('Company name missing for {} in the company document'.format(doc.company)))

            if not doc.name:
                frappe.throw(_('Employee code missing in the document'))

            if not doc.first_name:
                frappe.throw(_('First name missing for {} in the document'.format(doc.name)))

            last_name = doc.last_name if doc.last_name else ""

            if not doc.user_id:
                frappe.throw(_('User ID missing for {} in the document'.format(doc.name)))

            if not frappe.local.conf.host_name:
                frappe.throw(_('API URL (host_name) is missing in site config'))

            if not app_key:
                frappe.throw(_('App key could not be generated'))

            cleaned = (
                f"Company: {company_name}"
                f" Employee_Code: {doc.name}"
                f" Full_Name: {doc.first_name}  {last_name}"
                f" Photo: {doc.custom_photo_}"
                f" User_id: {doc.user_id}"
                f" API: {frappe.local.conf.host_name}"
                f" App_key: {app_key}"
            )

            base64_string = b64encode(cleaned.encode()).decode()

            qr_image = io.BytesIO()
            url = qr_create(base64_string, error='L')
            url.png(qr_image, scale=2, quiet_zone=1)

            filename = f"QR-CODE-{doc.name}.png".replace(os.path.sep, "__")

            for old_file in frappe.get_all("File", filters={"file_name": filename}, pluck="name"):
                frappe.delete_doc("File", old_file, ignore_permissions=True, delete_permanently=True)

            _file = frappe.get_doc({
                "doctype": "File",
                "file_name": filename,
                "content": qr_image.getvalue(),
                "is_private": 0
            })

            _file.save()

            doc.db_set('custom_qr_code', _file.file_url)
            doc.notify_update()

            break

def delete_qr_code_file(doc, method):
    """Delete QR Code on deleted sales invoice"""


    if hasattr(doc, 'custom_qr_code'):
        if doc.get('custom_qr_code'):
            file_doc = frappe.get_list('File', {
                'file_url': doc.custom_qr_code,
                'attached_to_doctype': doc.doctype,
                'attached_to_name': doc.name
            })
            if len(file_doc):
                frappe.delete_doc('File', file_doc[0].name)
from frappe.utils import today
# @frappe.whitelist()
# def send_daily_task_summary():
#     frappe.get_all("Task",)