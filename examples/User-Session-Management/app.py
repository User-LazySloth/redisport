import uuid
import time
from flask import Flask, request, jsonify, render_template, render_template_string, redirect, url_for, session
import redis
import os

app = Flask(__name__)
app.secret_key = 'super-secret'
r = redis.Redis(host='127.0.0.1', port=21084, decode_responses=True)

# HTML Templates are now moved to the 'templates' folder using Jinja2 rendering

@app.route("/")
def index():
    return render_template("home.html")

@app.route("/start-login", methods=["POST"])
def start_login():
    username = request.form['username']
    appname = request.form['app']
    session_type = request.form['type']
    session_id = str(uuid.uuid4())
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    ip = request.remote_addr
    agent = request.headers.get('User-Agent', 'unknown')

    r.hset(f"session:{session_id}", mapping={
        "user": username,
        "app": appname,
        "status": "active",
        "login_time": timestamp,
        "ip": ip,
        "agent": agent,
        "type": session_type
    })

    r.rpush(f"user:sessions:{username}", session_id)
    r.sadd(f"user:active_sessions:{username}", session_id)
    r.rpush("event:logs", f"{timestamp} - LOGIN - {username} from {appname} via {session_type} ({ip}) [{session_id}]")

    all_sessions = r.lrange(f"user:sessions:{username}", 0, -1)
    history = []
    for sid in all_sessions:
        d = r.hgetall(f"session:{sid}")
        d["session_id"] = sid
        history.append(d)

    return render_template("form.html", username=username, app=appname, type=session_type, session_id=session_id, history=history)

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    appname = request.form["app"]
    session_type = request.form["type"]
    email = request.form.get("email", "")
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    department = request.form.get("department", "")
    session_id = request.form["session_id"]

    r.hset(f"session:{session_id}", mapping={
        "email": email,
        "department": department
    })
    r.setex(f"cache:session:{session_id}", 3600, f"{username}|{appname}|{session_type}|{timestamp}|{email}|{department}")

    return render_template("submitted.html", username=username, session_id=session_id)

@app.route("/logout", methods=["POST"])
def logout():
    username = request.form["username"]
    session_id = request.form["session_id"]
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    if r.exists(f"session:{session_id}"):
        r.hset(f"session:{session_id}", mapping={
            "status": "logged_out",
            "logout_time": timestamp
        })
        r.srem(f"user:active_sessions:{username}", session_id)
        r.rpush("event:logs", f"{timestamp} - LOGOUT - {username} [{session_id}]")
        return render_template("logout.html", user=username, sid=session_id)
    return jsonify({"error": "Session not found"}), 404

@app.route("/admin-login", methods=["POST"])
def admin_login():
    username = request.form["username"]
    password = request.form["password"]
    if username == "admin" and password == "123456":
        return render_template("admin_tools.html")
    return "Access denied", 403

@app.route("/admin-tools")
def admin_tools():
    return render_template("admin_tools.html")

@app.route("/logs")
def logs():
    logs = r.lrange("event:logs", 0, -1)
    return render_template_string("""
    <div style="padding: 20px; font-family: monospace;">
        <h3>📜 Event Logs</h3>
        <pre>{{logs}}</pre>
        <a href="/admin-tools">⬅️ Back</a>
    </div>
    """, logs="\n".join(logs))

@app.route("/cache")
def cache():
    keys = r.keys("cache:session:*")
    cache_data = {k: r.get(k) for k in keys}
    return render_template("cache.html", cache_data=cache_data)


@app.route("/status/user")
def status_user():
    username = request.args.get("username")
    all_sessions = r.lrange(f"user:sessions:{username}", 0, -1)
    active = list(r.smembers(f"user:active_sessions:{username}"))
    details = [r.hgetall(f"session:{sid}") for sid in all_sessions]

    output_lines = [f"User: {username}", f"Active Sessions: {active}", "", "All Sessions:\n"]

    for sid, data in zip(all_sessions, details):
        output_lines.append(f"Session ID: {sid}")
        for k in sorted(data.keys()):
            value = data[k]
            output_lines.append(f"  {k:<15}: {value}")
        output_lines.append("-" * 40)

    return render_template_string("""
    <div style="padding: 20px; font-family: monospace;">
        <h3>📌 User Session Status</h3>
        <pre>{{ logs }}</pre>
        <a href="/admin-tools">⬅️ Back</a>
    </div>
    """, logs="\n".join(output_lines))


@app.route("/admin")
def admin():
    import collections
    from datetime import datetime

    only_active = request.args.get("active") == "1"
    all_keys = r.keys("user:sessions:*")
    users = sorted([k.split(":" )[-1] for k in all_keys])
    user_data = collections.OrderedDict()

    for user in users:
        sessions = r.lrange(f"user:sessions:{user}", 0, -1)
        session_details = []

        for sid in sessions:
            data = r.hgetall(f"session:{sid}")
            if only_active and data.get("status") != "active":
                continue

            data["session_id"] = sid
            if "login_time" in data:
                try:
                    dt = datetime.strptime(data["login_time"], "%Y-%m-%d %H:%M:%S")
                    data["expires_at"] = datetime.fromtimestamp(dt.timestamp() + 3600).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    data["expires_at"] = "-"
            else:
                data["expires_at"] = "-"

            session_details.append(data)

        if session_details:
            user_data[user] = session_details

    return render_template("admin_dashboard.html", user_data=user_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=21090, debug=True)