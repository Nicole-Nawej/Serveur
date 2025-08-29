from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
import json
import datetime
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

clients = {}  # {'raspberry': sid, 'flutter': sid}

stats = {
    "raspberry_messages": 0,
    "flutter_messages": 0,
    "last_battery": None,
    "last_battery_time": None,
    "last_latitude": None,
    "last_longitude": None,
    "last_gps_time": None,
    "last_altitude": None,
    "last_altitude_time": None,
    "last_speed": None,
    "last_speed_time": None,
    "last_flight_mode": None,
    "last_flight_mode_time": None,
    "last_flutter_latitude": None,
    "last_flutter_longitude": None,
    "last_flutter_gps_time": None,
    "start_latitude": None,
    "start_longitude": None,
    "start_gps_time": None,
    "raspberry_to_flutter": [],
    "flutter_to_raspberry": [],
    "mission_state": "idle",
    "last_command": None,
    "signal_loss_mode": "return_home",
    "flutter_sent": [],
    "raspberry_sent": [],
}

def save_stats():
    with open("stats.json", "w") as f:
        json.dump(stats, f)

# Dashboard HTML minimal (adapte-le selon tes besoins)
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard Serveur Drone</title>
    <meta http-equiv="refresh" content="2">
    <style>
        body { font-family: Arial; margin: 40px; }
        h1 { color: #2c3e50; }
        table { border-collapse: collapse; margin-top: 10px; background: #fff; }
        td, th { border: 1px solid #ccc; padding: 8px 16px; }
        th { background: #e9ecef; text-align: left; }
        .none { color: #888; font-style: italic; }
        .value { font-weight: bold; color: #1a7f37; }
    </style>
</head>
<body>
    <h1>Dashboard Serveur Drone</h1>
    <h2>Statistiques</h2>
    <table>
        <tr><th>Messages Raspberry</th><td>{{ stats['raspberry_messages'] }}</td></tr>
        <tr><th>Messages Flutter</th><td>{{ stats['flutter_messages'] }}</td></tr>
        <tr><th>Dernier niveau batterie</th><td>{{ stats['last_battery'] or "?" }}</td></tr>
        <tr><th>Dernier GPS Raspberry</th>
            <td>
                {% if stats['last_latitude'] and stats['last_longitude'] %}
                    Lat: {{ stats['last_latitude'] }}, Lon: {{ stats['last_longitude'] }}
                {% else %}
                    <span class="none">Aucune donnée</span>
                {% endif %}
            </td>
        </tr>
        <tr><th>Dernier GPS Flutter</th>
            <td>
                {% if stats['last_flutter_latitude'] and stats['last_flutter_longitude'] %}
                    Lat: {{ stats['last_flutter_latitude'] }}, Lon: {{ stats['last_flutter_longitude'] }}
                {% else %}
                    <span class="none">Aucune donnée</span>
                {% endif %}
            </td>
        </tr>
        <tr><th>Mission State</th><td>{{ stats['mission_state'] }}</td></tr>
        <tr><th>Signal Loss Mode</th><td>{{ stats['signal_loss_mode'] }}</td></tr>
        <tr><th>Raspberry connectée</th>
            <td>{{ "Oui" if clients.get("raspberry") else "Non" }}</td>
        </tr>
        <tr><th>Flutter connectée</th>
            <td>{{ "Oui" if clients.get("flutter") else "Non" }}</td>
        </tr>
    </table>
    <h2>Historique Raspberry → Flutter</h2>
    <table>
        <tr><th>Date/Heure</th><th>Données</th></tr>
        {% for msg in stats.get('raspberry_to_flutter', []) %}
        <tr>
            <td>{{ msg.timestamp }}</td>
            <td><pre>{{ msg.data | tojson(indent=2) }}</pre></td>
        </tr>
        {% else %}
        <tr><td colspan="2" class="none">Aucun message</td></tr>
        {% endfor %}
    </table>
    <h2>Historique Flutter → Raspberry</h2>
    <table>
        <tr><th>Date/Heure</th><th>Données</th></tr>
        {% for msg in stats.get('flutter_to_raspberry', []) %}
        <tr>
            <td>{{ msg.timestamp }}</td>
            <td><pre>{{ msg.data | tojson(indent=2) }}</pre></td>
        </tr>
        {% else %}
        <tr><td colspan="2" class="none">Aucun message</td></tr>
        {% endfor %}
    </table>
    <h2>Messages envoyés par l'application (Flutter)</h2>
    <table>
        <tr><th>Date/Heure</th><th>Données</th></tr>
        {% for msg in stats.get('flutter_sent', []) %}
        <tr>
            <td>{{ msg.timestamp }}</td>
            <td><pre>{{ msg.data | tojson(indent=2) }}</pre></td>
        </tr>
        {% else %}
        <tr><td colspan="2" class="none">Aucun message</td></tr>
        {% endfor %}
    </table>

    <h2>Messages envoyés par la Raspberry</h2>
    <table>
        <tr><th>Date/Heure</th><th>Données</th></tr>
        {% for msg in stats.get('raspberry_sent', []) %}
        <tr>
            <td>{{ msg.timestamp }}</td>
            <td><pre>{{ msg.data | tojson(indent=2) }}</pre></td>
        </tr>
        {% else %}
        <tr><td colspan="2" class="none">Aucun message</td></tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(TEMPLATE, stats=stats, clients=clients)

# WebSocket: identification
@socketio.on('identify')
def handle_identify(data):
    client_type = data.get("type")
    if client_type not in ["raspberry", "flutter"]:
        emit("error", {"message": "Unknown client type"})
        return
    clients[client_type] = request.sid
    emit("registered", {
        "status": "ok",
        "message": f"{client_type} registered",
        "signal_loss_mode": stats.get("signal_loss_mode", "return_home")
    })
    if client_type == "raspberry" and "flutter" in clients:
        socketio.emit("drone_connected", {"drone_connected": True}, room=clients["flutter"])

# WebSocket: gestion des messages
@socketio.on('message')
def handle_message(data):
    # Trouve le type du client qui envoie
    client_type = None
    for k, v in clients.items():
        if v == request.sid:
            client_type = k
            break
    if not client_type:
        emit("error", {"message": "Client not identified"})
        return

    action = data.get("action")
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Gestion Raspberry
    if client_type == "raspberry":
        stats["raspberry_messages"] += 1
        if action == "battery":
            stats["last_battery"] = data.get("value")
            stats["last_battery_time"] = now
        if action == "gps":
            stats["last_latitude"] = data.get("latitude")
            stats["last_longitude"] = data.get("longitude")
            stats["last_gps_time"] = now
            if stats["start_latitude"] is None and stats["start_longitude"] is None:
                stats["start_latitude"] = data.get("latitude")
                stats["start_longitude"] = data.get("longitude")
                stats["start_gps_time"] = now
        if action == "altitude":
            stats["last_altitude"] = data.get("value")
            stats["last_altitude_time"] = now
        if action == "speed":
            stats["last_speed"] = data.get("value")
            stats["last_speed_time"] = now
        if action == "flight_mode":
            stats["last_flight_mode"] = data.get("value")
            stats["last_flight_mode_time"] = now
        save_stats()

    # Gestion Flutter
    elif client_type == "flutter":
        stats["flutter_messages"] += 1
        if action == "command":
            command = data.get("command")
            if command == "set_signal_loss_mode":
                mode = data.get("mode", "return_home")
                stats["signal_loss_mode"] = mode
                save_stats()
                print(f"Mode de perte de signal changé: {mode}")
                return
            stats["last_command"] = command
            if command == "pause":
                stats["mission_state"] = "paused"
            elif command == "resume":
                stats["mission_state"] = "running"
            elif command == "stop":
                stats["mission_state"] = "stopped"
            elif command == "return_home":
                stats["mission_state"] = "returning_home"
            elif command == "hover":
                stats["mission_state"] = "hovering"
            save_stats()
            print(f"Commande reçue: {command}, nouvel état: {stats['mission_state']}")
        if action == "gps":
            stats["last_flutter_latitude"] = data.get("latitude")
            stats["last_flutter_longitude"] = data.get("longitude")
            stats["last_flutter_gps_time"] = now
        save_stats()

    # Relais des messages
    target = "flutter" if client_type == "raspberry" else "raspberry"
    if target in clients:
        entry = {
            "timestamp": now,
            "data": data
        }
        if client_type == "raspberry":
            stats["raspberry_to_flutter"].append(entry)
            stats["raspberry_to_flutter"] = stats["raspberry_to_flutter"][-10:]
        else:
            stats["flutter_to_raspberry"].append(entry)
            stats["flutter_to_raspberry"] = stats["flutter_to_raspberry"][-10:]
        save_stats()
        socketio.emit("message", data, room=clients[target])
    else:
        emit("error", {"message": f"{target} not connected"})

    # Ajoute à l'historique des messages envoyés
    entry = {
        "timestamp": now,
        "data": data
    }
    if client_type == "raspberry":
        stats["raspberry_sent"].append(entry)
        stats["raspberry_sent"] = stats["raspberry_sent"][-10:]
    elif client_type == "flutter":
        stats["flutter_sent"].append(entry)
        stats["flutter_sent"] = stats["flutter_sent"][-10:]
    save_stats()

@socketio.on('disconnect')
def handle_disconnect():
    for k, v in list(clients.items()):
        if v == request.sid:
            del clients[k]
            print(f"{k} déconnecté.")
            break

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)