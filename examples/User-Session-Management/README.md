
# Project Overview
This is a Flask-based application that demonstrates user session management using Redis.
It supports login/logout tracking, session metadata storage, admin monitoring, and cache handling.

Users can:
- Log in with a username, app name, and session type
- Submit additional profile data (email, department)
- View session history (on the form page)

Admins can:
- View all logs and cache
- Search user sessions
- Perform manual session logout
- Monitor all active/inactive sessions via the dashboard

How Redis Is Used
--------------------
1. **Session Data Storage**
   - Key: `session:<session_id>`
   - Type: Hash
   - Stores: username, app, type, IP, user-agent, login/logout time, status, etc.

2. **User-to-Session Mapping**
   - Key: `user:sessions:<username>`
   - Type: List
   - Stores ordered list of all session_ids for a user

3. **Active Session Tracking**
   - Key: `user:active_sessions:<username>`
   - Type: Set
   - Stores all currently active sessions per user

4. **Event Logs**
   - Key: `event:logs`
   - Type: List
   - Appends a string log for each login and logout event

5. **Session Data Caching**
   - Key: `cache:session:<session_id>`
   - Type: String (Expires after 1 hour)
   - Value: Compact string representation of session metadata for quick access

How to Run
-------------
1. Install dependencies:
```
    pip install flask redis
```
2. Ensure Redis is running on:
   Host: 127.0.0.1
   Port: 21084

   To start Redis:
```
   redis-server redis.conf
```
3. Run the Flask app:
```
   python app.py
```
4. Access the app in your browser:
```
   http://localhost:21090
```
5. (Optional) To view Redis server logs:
```
   redis-cli -p 21084 monitor
```
Test Credentials
-------------------
For user login:
- Any username + app name + type (web, mobile, api)

For admin login:
- Username: admin
- Password: 12345

Admin Features
-----------------
- View full session dashboard (active/inactive)
- Search by username to see all session history
- View event logs (login/logout)
- View session cache
- Manual logout by session ID
- Return to home with one click

Key Highlights
-----------------
- Session data is persisted in Redis.
- Admin can monitor and control all activity.
- Cached user sessions speed up analytics.
- Easy to extend and plug into production systems.
