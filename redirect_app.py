from flask import Flask, request, render_template_string, redirect, session
import os
import json

app = Flask(__name__)
app.secret_key = "supersecretkey_memberbackup"

ADMIN_PASSWORD = "admin1234"
BOT_STATUS_FILE = "bot_status.json"
BOT_COMMANDS_FILE = "bot_commands.json"

# ─── OAuth Redirect Page ──────────────────────────────────────────────────────
REDIRECT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Discord Authentication - Member Backup Bot</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Segoe UI',sans-serif; background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); min-height:100vh; display:flex; align-items:center; justify-content:center; padding:20px; }
  .container { background:#1e1f22; border-radius:12px; padding:40px; max-width:500px; width:100%; box-shadow:0 20px 60px rgba(0,0,0,.3); border:1px solid rgba(255,255,255,.1); }
  .header { text-align:center; margin-bottom:30px; }
  .header h1 { color:#fff; font-size:24px; margin-bottom:8px; }
  .header p { color:#b5bac1; font-size:14px; }
  .status { padding:16px; border-radius:8px; margin-bottom:24px; display:flex; align-items:center; gap:12px; }
  .status.success { background:rgba(87,242,135,.1); border:1px solid rgba(87,242,135,.3); color:#57f287; }
  .status.error { background:rgba(237,66,69,.1); border:1px solid rgba(237,66,69,.3); color:#ed4245; }
  .code-box { background:#2c2f33; border:1px solid #40444b; border-radius:6px; padding:12px; margin-bottom:12px; word-break:break-all; font-family:'Courier New',monospace; color:#fff; font-size:14px; min-height:44px; display:flex; align-items:center; }
  .button { width:100%; padding:12px; border:none; border-radius:6px; font-size:14px; font-weight:600; cursor:pointer; transition:all .2s; text-decoration:none; display:inline-block; text-align:center; }
  .button.primary { background:#5865f2; color:#fff; margin-bottom:8px; }
  .button.primary:hover { background:#4752c4; }
  .button.secondary { background:transparent; color:#5865f2; border:1px solid #5865f2; }
  .button.secondary:hover { background:rgba(88,101,242,.1); }
  .instructions { background:rgba(88,101,242,.1); border:1px solid rgba(88,101,242,.3); border-radius:6px; padding:12px; margin-top:20px; }
  .instructions-title { color:#5865f2; font-size:12px; font-weight:600; text-transform:uppercase; margin-bottom:8px; }
  .instructions-text { color:#b5bac1; font-size:12px; line-height:1.6; }
  .instructions-text ol { margin-left:16px; }
  .instructions-text li { margin-bottom:4px; }
  label { color:#b5bac1; font-size:12px; text-transform:uppercase; letter-spacing:.5px; margin-bottom:8px; display:block; }
</style>
</head>
<body>
<div class="container">
  <div class="header"><h1>🔐 Authentication Successful</h1><p>Member Backup Bot - Discord OAuth</p></div>
  {% if code %}
  <div class="status success"><span>✅</span><span>Your account has been linked successfully!</span></div>
  <div>
    <label>Your Authentication Code</label>
    <div class="code-box" id="codeBox">{{ code }}</div>
    <button class="button primary" onclick="copyCode()">📋 Copy Code</button>
  </div>
  <div class="instructions">
    <div class="instructions-title">📝 Next Steps</div>
    <div class="instructions-text"><ol><li>Return to Discord</li><li>Use: <code style="background:#2c2f33;padding:2px 4px;border-radius:3px">!auth {{ code }}</code></li><li>Wait for confirmation ✅</li></ol></div>
  </div>
  <a href="https://discord.com/app" class="button secondary" style="margin-top:20px;">← Return to Discord</a>
  {% else %}
  <div class="status error"><span>❌</span><span>No authorization code found</span></div>
  <div class="instructions">
    <div class="instructions-title">💡 What to do</div>
    <div class="instructions-text"><ol><li>Go back to Discord</li><li>Use <code style="background:#2c2f33;padding:2px 4px;border-radius:3px">!get_token</code></li><li>Click the link and authorize</li></ol></div>
  </div>
  {% endif %}
</div>
<script>
function copyCode() {
  const code = document.getElementById('codeBox').textContent;
  navigator.clipboard.writeText(code).then(() => {
    const btn = event.target; const orig = btn.textContent;
    btn.textContent = '✅ Copied!';
    setTimeout(() => btn.textContent = orig, 2000);
  }).catch(() => alert('Copy manually: ' + code));
}
</script>
</body>
</html>
"""

# ─── Admin Panel HTML ─────────────────────────────────────────────────────────
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bot Admin Panel</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Segoe UI',sans-serif; background:#0d1117; color:#c9d1d9; min-height:100vh; }
  .sidebar { width:220px; background:#161b22; height:100vh; position:fixed; left:0; top:0; padding:20px 0; border-right:1px solid #30363d; display:flex; flex-direction:column; }
  .sidebar h2 { color:#58a6ff; text-align:center; font-size:16px; padding:0 20px 20px; border-bottom:1px solid #30363d; }
  .sidebar a { display:block; padding:12px 20px; color:#8b949e; text-decoration:none; font-size:14px; transition:all .2s; }
  .sidebar a:hover,.sidebar a.active { background:#1f6feb22; color:#58a6ff; border-left:3px solid #58a6ff; }
  .sidebar .logout { margin-top:auto; color:#f85149 !important; }
  .main { margin-left:220px; padding:30px; }
  .header { margin-bottom:30px; }
  .header h1 { font-size:24px; color:#f0f6fc; }
  .header p { color:#8b949e; font-size:14px; margin-top:5px; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:15px; margin-bottom:30px; }
  .card { background:#161b22; border:1px solid #30363d; border-radius:10px; padding:20px; }
  .card .label { font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:1px; }
  .card .value { font-size:26px; font-weight:bold; color:#f0f6fc; margin-top:8px; }
  .card .sub { font-size:11px; color:#8b949e; margin-top:4px; }
  .card.green .value { color:#3fb950; }
  .card.blue .value { color:#58a6ff; }
  .card.purple .value { color:#a5a5ff; }
  .card.yellow .value { color:#d29922; }
  .section { background:#161b22; border:1px solid #30363d; border-radius:10px; padding:20px; margin-bottom:20px; }
  .section h3 { font-size:16px; color:#f0f6fc; margin-bottom:15px; padding-bottom:10px; border-bottom:1px solid #30363d; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th { text-align:left; padding:10px; color:#8b949e; font-weight:600; border-bottom:1px solid #30363d; }
  td { padding:10px; border-bottom:1px solid #21262d; }
  tr:last-child td { border-bottom:none; }
  tr:hover td { background:#1f2937; }
  .badge { display:inline-block; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; }
  .badge.green { background:#1f4d2b; color:#3fb950; }
  .badge.blue { background:#1f3a5f; color:#58a6ff; }
  .btn { display:inline-block; padding:8px 16px; border-radius:6px; font-size:13px; font-weight:600; cursor:pointer; border:none; text-decoration:none; transition:opacity .2s; }
  .btn:hover { opacity:.8; }
  .btn-primary { background:#1f6feb; color:white; }
  .btn-danger { background:#da3633; color:white; }
  .btn-success { background:#238636; color:white; }
  .btn-secondary { background:#30363d; color:#c9d1d9; }
  .form-group { margin-bottom:15px; }
  .form-group label { display:block; font-size:13px; color:#8b949e; margin-bottom:6px; }
  .form-group select,.form-group input { width:100%; padding:8px 12px; background:#0d1117; border:1px solid #30363d; border-radius:6px; color:#c9d1d9; font-size:13px; }
  .form-group select:focus,.form-group input:focus { outline:none; border-color:#58a6ff; }
  .alert { padding:12px 16px; border-radius:6px; margin-bottom:20px; font-size:13px; }
  .alert.success { background:#1f4d2b; color:#3fb950; border:1px solid #238636; }
  .alert.error { background:#4d1f1f; color:#f85149; border:1px solid #da3633; }
  .status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
  .status-dot.online { background:#3fb950; }
  .status-dot.offline { background:#6e7681; }
  .token-text { font-family:monospace; font-size:11px; color:#8b949e; max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:block; }
  .login-wrap { display:flex; align-items:center; justify-content:center; min-height:100vh; }
  .login-box { background:#161b22; border:1px solid #30363d; border-radius:12px; padding:40px; width:360px; }
  .login-box h2 { font-size:22px; color:#f0f6fc; margin-bottom:8px; }
  .login-box p { color:#8b949e; font-size:13px; margin-bottom:25px; }
  .login-box input { width:100%; padding:10px 14px; background:#0d1117; border:1px solid #30363d; border-radius:6px; color:#c9d1d9; font-size:14px; margin-bottom:15px; }
  .login-box button { width:100%; padding:10px; background:#1f6feb; color:white; border:none; border-radius:6px; font-size:15px; font-weight:600; cursor:pointer; }
  .login-box button:hover { background:#388bfd; }
</style>
</head>
<body>
{% if not logged_in %}
<div class="login-wrap">
  <div class="login-box">
    <h2>🔐 Admin Panel</h2>
    <p>Enter your admin password to continue</p>
    {% if error %}<div class="alert error">{{ error }}</div>{% endif %}
    <form method="POST" action="/admin/login">
      <input type="password" name="password" placeholder="Password" autofocus>
      <button type="submit">Login</button>
    </form>
  </div>
</div>
{% else %}
<div class="sidebar">
  <h2>🤖 Bot Admin</h2>
  <a href="/admin" class="{{ 'active' if page=='dashboard' else '' }}">📊 Dashboard</a>
  <a href="/admin/users" class="{{ 'active' if page=='users' else '' }}">👥 Users</a>
  <a href="/admin/servers" class="{{ 'active' if page=='servers' else '' }}">🌐 Servers</a>
  <a href="/admin/status" class="{{ 'active' if page=='status' else '' }}">⚡ Set Status</a>
  <a href="/admin/logout" class="logout">🚪 Logout</a>
</div>
<div class="main">

{% if page == 'dashboard' %}
<div class="header"><h1>📊 Dashboard</h1><p>Overview of your bot</p></div>
<div class="cards">
  <div class="card green">
    <div class="label">Bot Status</div>
    <div class="value" style="font-size:18px;margin-top:10px">
      <span class="status-dot {{ 'online' if bot_ready else 'offline' }}"></span>{{ 'Online' if bot_ready else 'Offline' }}
    </div>
  </div>
  <div class="card blue">
    <div class="label">Authenticated Users</div>
    <div class="value">{{ user_count }}</div>
    <div class="sub">tokens stored</div>
  </div>
  <div class="card purple">
    <div class="label">Servers</div>
    <div class="value">{{ server_count }}</div>
    <div class="sub">bot is in</div>
  </div>
  <div class="card yellow">
    <div class="label">Ping</div>
    <div class="value">{{ latency }}ms</div>
    <div class="sub">gateway latency</div>
  </div>
</div>
<div class="section">
  <h3>Quick Actions</h3>
  <a href="/admin/users" class="btn btn-primary" style="margin-right:8px">👥 Manage Users</a>
  <a href="/admin/servers" class="btn btn-secondary" style="margin-right:8px">🌐 View Servers</a>
  <a href="/admin/status" class="btn btn-success" style="margin-right:8px">⚡ Set Status</a>
  <a href="/admin/restart" class="btn btn-danger" onclick="return confirm('Restart bot?')">🔄 Restart Bot</a>
</div>

{% elif page == 'users' %}
<div class="header"><h1>👥 Authenticated Users</h1><p>Manage stored tokens</p></div>
{% if msg %}<div class="alert {{ 'success' if msg_type=='success' else 'error' }}">{{ msg }}</div>{% endif %}
<div class="section">
  <h3>Users ({{ users|length }})</h3>
  {% if users %}
  <table>
    <tr><th>#</th><th>User ID</th><th>Access Token</th><th>Refresh Token</th><th>Action</th></tr>
    {% for u in users %}
    <tr>
      <td>{{ loop.index }}</td>
      <td><span class="badge blue">{{ u.user_id }}</span></td>
      <td><span class="token-text">{{ u.access_token }}</span></td>
      <td><span class="token-text">{{ u.refresh_token }}</span></td>
      <td>
        <form method="POST" action="/admin/users/delete" style="display:inline">
          <input type="hidden" name="user_id" value="{{ u.user_id }}">
          <button type="submit" class="btn btn-danger" onclick="return confirm('Delete?')" style="padding:4px 10px;font-size:11px">Delete</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </table>
  <br>
  <form method="POST" action="/admin/users/clear">
    <button type="submit" class="btn btn-danger" onclick="return confirm('Clear ALL tokens?')">🗑️ Clear All Tokens</button>
  </form>
  {% else %}
  <p style="color:#8b949e;text-align:center;padding:20px">No authenticated users found</p>
  {% endif %}
</div>

{% elif page == 'servers' %}
<div class="header"><h1>🌐 Servers</h1><p>All servers the bot is in</p></div>
<div class="section">
  <h3>Servers ({{ servers|length }})</h3>
  {% if servers %}
  <table>
    <tr><th>#</th><th>Server Name</th><th>Server ID</th><th>Members</th><th>Type</th></tr>
    {% for s in servers %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ s.name }}</td>
      <td><code style="font-size:11px;color:#8b949e">{{ s.id }}</code></td>
      <td>{{ s.members }}</td>
      <td>{% if s.is_main %}<span class="badge green">Main</span>{% else %}<span class="badge blue">Normal</span>{% endif %}</td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p style="color:#8b949e;text-align:center;padding:20px">No servers found. Bot may be offline.</p>
  {% endif %}
</div>

{% elif page == 'status' %}
<div class="header"><h1>⚡ Set Bot Status</h1><p>Change what the bot displays</p></div>
{% if msg %}<div class="alert {{ 'success' if msg_type=='success' else 'error' }}">{{ msg }}</div>{% endif %}
<div class="section">
  <h3>Change Activity</h3>
  <form method="POST" action="/admin/status/set">
    <div class="form-group">
      <label>Activity Type</label>
      <select name="activity_type">
        <option value="online">🟢 Online (clear activity)</option>
        <option value="playing">🎮 Playing</option>
        <option value="listening">🎵 Listening</option>
        <option value="watching">👀 Watching</option>
        <option value="streaming">📡 Streaming</option>
      </select>
    </div>
    <div class="form-group">
      <label>Activity Text (not needed for Online)</label>
      <input type="text" name="activity_text" placeholder="e.g. Member Backup">
    </div>
    <button type="submit" class="btn btn-primary">✅ Apply Status</button>
  </form>
</div>
{% endif %}

</div>
{% endif %}
</body>
</html>
"""

# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_users():
    users = []
    if os.path.exists('auths.txt'):
        with open('auths.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                if len(parts) >= 1:
                    users.append({
                        'user_id': parts[0],
                        'access_token': parts[1] if len(parts) > 1 else '',
                        'refresh_token': parts[2] if len(parts) > 2 else ''
                    })
    return users

def get_bot_status():
    if os.path.exists(BOT_STATUS_FILE):
        try:
            with open(BOT_STATUS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'ready': False, 'latency': 0, 'guilds': []}

def send_bot_command(cmd):
    with open(BOT_COMMANDS_FILE, 'w') as f:
        json.dump(cmd, f)

# ─── OAuth Routes ─────────────────────────────────────────────────────────────
@app.route('/discord-redirect.html')
@app.route('/discord-redirect')
def discord_redirect():
    code = request.args.get('code')
    error = request.args.get('error')
    if error:
        return render_template_string(REDIRECT_HTML, code=None)
    return render_template_string(REDIRECT_HTML, code=code)

@app.route('/')
def index():
    return render_template_string(REDIRECT_HTML, code=None)

# ─── Admin Routes ─────────────────────────────────────────────────────────────
@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'):
        return render_template_string(ADMIN_HTML, logged_in=False, error=None, page='login')
    status = get_bot_status()
    users = get_users()
    return render_template_string(ADMIN_HTML, logged_in=True, page='dashboard',
        bot_ready=status.get('ready', False),
        user_count=len(users),
        server_count=len(status.get('guilds', [])),
        latency=round(status.get('latency', 0) * 1000))

@app.route('/admin/login', methods=['POST'])
def admin_login():
    if request.form.get('password') == ADMIN_PASSWORD:
        session['admin'] = True
        return redirect('/admin')
    return render_template_string(ADMIN_HTML, logged_in=False, error="Wrong password!", page='login')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin')

@app.route('/admin/users')
def admin_users():
    if not session.get('admin'):
        return redirect('/admin')
    return render_template_string(ADMIN_HTML, logged_in=True, page='users', users=get_users(), msg=None, msg_type=None)

@app.route('/admin/users/delete', methods=['POST'])
def admin_delete_user():
    if not session.get('admin'):
        return redirect('/admin')
    user_id = request.form.get('user_id', '').strip()
    lines = []
    if os.path.exists('auths.txt'):
        with open('auths.txt', 'r') as f:
            lines = [l for l in f.readlines() if not l.startswith(user_id)]
    with open('auths.txt', 'w') as f:
        f.writelines(lines)
    return render_template_string(ADMIN_HTML, logged_in=True, page='users', users=get_users(),
        msg=f"User {user_id} deleted.", msg_type='success')

@app.route('/admin/users/clear', methods=['POST'])
def admin_clear_users():
    if not session.get('admin'):
        return redirect('/admin')
    with open('auths.txt', 'w') as f:
        f.write('')
    return render_template_string(ADMIN_HTML, logged_in=True, page='users', users=[],
        msg="All tokens cleared.", msg_type='success')

@app.route('/admin/servers')
def admin_servers():
    if not session.get('admin'):
        return redirect('/admin')
    status = get_bot_status()
    return render_template_string(ADMIN_HTML, logged_in=True, page='servers',
        servers=status.get('guilds', []))

@app.route('/admin/status')
def admin_status_page():
    if not session.get('admin'):
        return redirect('/admin')
    return render_template_string(ADMIN_HTML, logged_in=True, page='status', msg=None, msg_type=None)

@app.route('/admin/status/set', methods=['POST'])
def admin_set_status():
    if not session.get('admin'):
        return redirect('/admin')
    activity_type = request.form.get('activity_type', 'online')
    activity_text = request.form.get('activity_text', '').strip()
    send_bot_command({'action': 'set_status', 'type': activity_type, 'text': activity_text})
    return render_template_string(ADMIN_HTML, logged_in=True, page='status',
        msg=f"Status queued: {activity_type} {activity_text}", msg_type='success')

@app.route('/admin/restart')
def admin_restart():
    if not session.get('admin'):
        return redirect('/admin')
    send_bot_command({'action': 'restart'})
    return redirect('/admin')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
