from flask import Flask, render_template_string
import json

# On crée une application Flask, qui va servir une page web pour afficher les statistiques du serveur WebSocket.
app = Flask(__name__)

# Ceci est le code HTML de la page web, avec du style et des blocs pour afficher les statistiques.
# On utilise la syntaxe Jinja2 ({{ ... }}, {% ... %}) pour insérer dynamiquement les valeurs Python dans la page.
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Statistiques Serveur Drone</title>
    <!-- La page se rafraîchit automatiquement toutes les 2 secondes -->
    <meta http-equiv="refresh" content="2">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa; }
        h1 { color: #2c3e50; }
        h2 { color: #1a7f37; margin-top: 40px; }
        table { border-collapse: collapse; margin-top: 10px; background: #fff; }
        td, th { border: 1px solid #ccc; padding: 12px 20px; font-size: 1.1em; }
        th { background: #e9ecef; text-align: left; }
        .none { color: #888; font-style: italic; }
        .value { font-weight: bold; color: #1a7f37; }
    </style>
</head>
<body>
    <h1>Statistiques du Serveur Drone</h1>

    <!-- Section pour les infos du Raspberry Pi -->
    <h2>Raspberry Pi</h2>
    <table>
        <tr>
            <th>Messages reçus</th>
            <td class="value">{{ stats['raspberry_messages'] }}</td>
        </tr>
        <tr>
            <th>Dernier niveau batterie</th>
            <td>
                {% if stats['last_battery'] is not none %}
                    <span class="value">{{ stats['last_battery'] }} %</span><br>
                    <small>Reçu le {{ stats['last_battery_time'] or "?" }}</small>
                {% else %}
                    <span class="none">Aucune donnée</span>
                {% endif %}
            </td>
        </tr>
        <tr>
            <th>Dernier GPS</th>
            <td>
                {% if stats['last_latitude'] is not none and stats['last_longitude'] is not none %}
                    <span class="value">Lat: {{ stats['last_latitude'] }}, Lon: {{ stats['last_longitude'] }}</span><br>
                    <small>Reçu le {{ stats['last_gps_time'] or "?" }}</small>
                {% else %}
                    <span class="none">Aucune donnée</span>
                {% endif %}
            </td>
        </tr>
        <tr>
            <th>Dernière altitude</th>
            <td>
                {% if stats['last_altitude'] is not none %}
                    <span class="value">{{ stats['last_altitude'] }} m</span><br>
                    <small>Reçu le {{ stats['last_altitude_time'] or "?" }}</small>
                {% else %}
                    <span class="none">Aucune donnée</span>
                {% endif %}
            </td>
        </tr>
        <tr>
            <th>Dernière vitesse</th>
            <td>
                {% if stats['last_speed'] is not none %}
                    <span class="value">{{ stats['last_speed'] }} m/s</span><br>
                    <small>Reçu le {{ stats['last_speed_time'] or "?" }}</small>
                {% else %}
                    <span class="none">Aucune donnée</span>
                {% endif %}
            </td>
        </tr>
        <tr>
            <th>Dernier mode de vol</th>
            <td>
                {% if stats['last_flight_mode'] is not none %}
                    <span class="value">{{ stats['last_flight_mode'] }}</span><br>
                    <small>Reçu le {{ stats['last_flight_mode_time'] or "?" }}</small>
                {% else %}
                    <span class="none">Aucune donnée</span>
                {% endif %}
            </td>
        </tr>
        <tr>
            <th>Coordonnées de départ</th>
            <td>
                {% if stats['start_latitude'] is not none and stats['start_longitude'] is not none %}
                    <span class="value">Lat: {{ stats['start_latitude'] }}, Lon: {{ stats['start_longitude'] }}</span><br>
                    <small>Reçu le {{ stats['start_gps_time'] or "?" }}</small>
                {% else %}
                    <span class="none">Aucune donnée</span>
                {% endif %}
            </td>
        </tr>
    </table>

    <!-- Section pour les infos de l'application Flutter -->
    <h2>Application Flutter</h2>
    <table>
        <tr>
            <th>Messages reçus</th>
            <td class="value">{{ stats['flutter_messages'] }}</td>
        </tr>
        <tr>
            <th>Dernier GPS envoyé</th>
            <td>
                {% if stats['last_flutter_latitude'] is not none and stats['last_flutter_longitude'] is not none %}
                    <span class="value">Lat: {{ stats['last_flutter_latitude'] }}, Lon: {{ stats['last_flutter_longitude'] }}</span><br>
                    <small>Envoyé le {{ stats['last_flutter_gps_time'] or "?" }}</small>
                {% else %}
                    <span class="none">Aucune donnée</span>
                {% endif %}
            </td>
        </tr>
    </table>

    <!-- Historique des messages Raspberry -> Flutter -->
    <h2>Messages de la Raspberry vers l'application</h2>
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

    <!-- Historique des messages Flutter -> Raspberry -->
    <h2>Messages de l'application vers la Raspberry</h2>
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

    <p style="margin-top:20px;color:#555;"><i>La page se rafraîchit toutes les 2 secondes.<br>
    Les valeurs s'affichent en vert lorsqu'elles sont reçues.</i></p>
</body>
</html>
"""

def get_stats():
    """
    Cette fonction lit le fichier stats.json (créé par le serveur WebSocket)
    et retourne les statistiques sous forme de dictionnaire Python.
    Si le fichier n'existe pas ou qu'il y a une erreur, elle retourne un dictionnaire vide.
    """
    try:
        with open("stats.json", "r") as f:
            return json.load(f)
    except Exception:
        return {}

@app.route("/")
def index():
    """
    Cette fonction est appelée quand on accède à la page principale ("/").
    Elle affiche la page HTML avec les statistiques actuelles.
    """
    return render_template_string(TEMPLATE, stats=get_stats())

if __name__ == "__main__":
    # Si ce fichier est lancé directement, on démarre le serveur web Flask sur le port 5000.
    # Le mode debug permet de voir les erreurs plus facilement pendant le développement.
    app.run(port=5000, debug=True)