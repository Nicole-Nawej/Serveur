import asyncio
import websockets
import json
import datetime
import threading

# Dictionnaire pour stocker les clients connectés (raspberry et flutter)
clients = {}

# Liste des actions autorisées que le serveur peut traiter
ALLOWED_ACTIONS = {"battery", "gps", "altitude", "speed", "command"}

# Dictionnaire pour stocker des statistiques et les dernières valeurs reçues
stats = {
    "raspberry_messages": 0,         # Nombre de messages reçus du Raspberry Pi
    "flutter_messages": 0,           # Nombre de messages reçus de Flutter
    "last_battery": None,            # Dernier niveau de batterie reçu
    "last_battery_time": None,       # Date/heure du dernier niveau de batterie
    "last_latitude": None,           # Dernière latitude reçue du Raspberry Pi
    "last_longitude": None,          # Dernière longitude reçue du Raspberry Pi
    "last_gps_time": None,           # Date/heure de la dernière position GPS
    "last_altitude": None,           # Dernière altitude reçue
    "last_altitude_time": None,      # Date/heure de la dernière altitude
    "last_speed": None,              # Dernière vitesse reçue
    "last_speed_time": None,         # Date/heure de la dernière vitesse
    "last_flight_mode": None,        # Dernier mode de vol reçu
    "last_flight_mode_time": None,   # Date/heure du dernier mode de vol
    "last_flutter_latitude": None,   # Dernière latitude reçue de Flutter
    "last_flutter_longitude": None,  # Dernière longitude reçue de Flutter
    "last_flutter_gps_time": None,   # Date/heure de la dernière position GPS de Flutter
    "start_latitude": None,          # Latitude de départ (première reçue)
    "start_longitude": None,         # Longitude de départ (première reçue)
    "start_gps_time": None,           # Date/heure de la première position GPS
    "raspberry_to_flutter": [],       # Historique des messages relayés Raspberry -> Flutter
    "flutter_to_raspberry": [],        # Historique des messages relayés Flutter -> Raspberry
    "mission_state": "idle",          # idle, running, paused, stopped, returning_home, hovering
    "last_command": None              # Dernière commande reçue (pause, resume, stop, return_home, hover)
}

# Mode à appliquer en cas de perte de signal (par défaut)
stats["signal_loss_mode"] = "return_home"

def save_stats():
    """
    Sauvegarde les statistiques dans un fichier JSON.
    Cela permet de garder une trace des données même si le serveur redémarre.
    """
    with open("stats.json", "w") as f:
        json.dump(stats, f)

async def handler(websocket):
    """
    Fonction principale qui gère la connexion d'un client (raspberry ou flutter).
    Elle identifie le client, traite ses messages, et fait le relais entre les deux.
    """
    # Identification du client à la connexion
    try:
        ident_msg = await websocket.recv()  # Attend le premier message du client
        ident_data = json.loads(ident_msg)  # Décode le message JSON
        client_type = ident_data.get("type")  # Doit être "raspberry" ou "flutter"
        if client_type not in ["raspberry", "flutter"]:
            # Si le type n'est pas reconnu, on envoie une erreur et on arrête
            await websocket.send(json.dumps({"status": "error", "message": "Unknown client type"}))
            return
        # On enregistre le client dans le dictionnaire
        clients[client_type] = websocket

        # Si le Raspberry vient de se connecter et que Flutter est déjà là, on informe Flutter
        if client_type == "raspberry" and "flutter" in clients:
            await clients["flutter"].send(json.dumps({"drone_connected": True}))

        # On confirme au client qu'il est bien enregistré
        await websocket.send(json.dumps({
            "status": "ok",
            "message": f"{client_type} registered",
            "signal_loss_mode": stats.get("signal_loss_mode", "return_home")
        }))
    except Exception as e:
        # En cas d'erreur lors de l'identification, on envoie une erreur
        await websocket.send(json.dumps({"status": "error", "message": str(e)}))
        return

    # Boucle principale pour recevoir et traiter les messages du client
    try:
        async for message in websocket:
            print(f"[{datetime.datetime.now()}] Message reçu de {client_type}: {message}")
            try:
                data = json.loads(message)  # On décode le message JSON
                action = data.get("action") # On récupère l'action demandée
                if action not in ALLOWED_ACTIONS:
                    # Si l'action n'est pas autorisée, on envoie une erreur
                    await websocket.send(json.dumps({"status": "error", "message": "Unknown action"}))
                    continue

                # Traitement spécifique selon le type de client
                if client_type == "raspberry":
                    stats["raspberry_messages"] += 1
                    # Le Raspberry ne peut envoyer que certaines actions
                    if action not in {"battery", "gps", "altitude", "speed"}:
                        await websocket.send(json.dumps({"status": "error", "message": "Action not allowed for raspberry"}))
                        continue
                    # Mise à jour des statistiques selon l'action
                    if action == "battery":
                        stats["last_battery"] = data.get("value")
                        stats["last_battery_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        print(f"Stat: Batterie mise à jour: {stats['last_battery']}%")
                    if action == "gps" and client_type == "raspberry":
                        stats["last_latitude"] = data.get("latitude")
                        stats["last_longitude"] = data.get("longitude")
                        stats["last_gps_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        # Si c'est la première position, on la garde comme point de départ
                        if stats["start_latitude"] is None and stats["start_longitude"] is None:
                            stats["start_latitude"] = data.get("latitude")
                            stats["start_longitude"] = data.get("longitude")
                            stats["start_gps_time"] = stats["last_gps_time"]
                        print(f"Stat: GPS mis à jour: {stats['last_latitude']}, {stats['last_longitude']}")
                    if action == "altitude" and client_type == "raspberry":
                        stats["last_altitude"] = data.get("value")
                        stats["last_altitude_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if action == "speed" and client_type == "raspberry":
                        stats["last_speed"] = data.get("value")
                        stats["last_speed_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if action == "flight_mode" and client_type == "raspberry":
                        stats["last_flight_mode"] = data.get("value")
                        stats["last_flight_mode_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    # On ajoute la date de réception au message
                    data["received_at"] = datetime.datetime.now().isoformat()
                    save_stats()  # On sauvegarde les statistiques

                elif client_type == "flutter":
                    stats["flutter_messages"] += 1
                    # Flutter peut envoyer des commandes ou sa position GPS
                    if action not in {"command", "gps"}:
                        await websocket.send(json.dumps({"status": "error", "message": "Action not allowed for flutter"}))
                        continue
                    if action == "command":
                        command = data.get("command")
                        # Gestion du changement de mode de perte de signal
                        if command == "set_signal_loss_mode":
                            mode = data.get("mode", "return_home")
                            stats["signal_loss_mode"] = mode
                            save_stats()
                            print(f"Mode de perte de signal changé: {mode}")
                            continue
                        # Gestion classique des commandes de mission
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
                    if action == "gps" and client_type == "flutter":
                        stats["last_flutter_latitude"] = data.get("latitude")
                        stats["last_flutter_longitude"] = data.get("longitude")
                        stats["last_flutter_gps_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        print(f"Stat: GPS Flutter mis à jour: {stats['last_flutter_latitude']}, {stats['last_flutter_longitude']}")
                        data["handled_by"] = "server"
                    save_stats()  # On sauvegarde les statistiques

                # On transmet le message à l'autre client s'il est connecté
                target = "flutter" if client_type == "raspberry" else "raspberry"
                if target in clients:
                    # On ajoute le message à l'historique selon le sens
                    if client_type == "raspberry":
                        stats["raspberry_to_flutter"].append({
                            "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                            "data": data
                        })
                        # On limite l'historique à 10 messages pour éviter un fichier trop gros
                        stats["raspberry_to_flutter"] = stats["raspberry_to_flutter"][-10:]
                    else:
                        stats["flutter_to_raspberry"].append({
                            "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                            "data": data
                        })
                        stats["flutter_to_raspberry"] = stats["flutter_to_raspberry"][-10:]
                    save_stats()
                    await clients[target].send(json.dumps(data))
                else:
                    # Si l'autre client n'est pas connecté, on informe l'expéditeur
                    await websocket.send(json.dumps({"status": "error", "message": f"{target} not connected"}))
            except json.JSONDecodeError:
                # Si le message n'est pas du JSON valide, on envoie une erreur
                await websocket.send(json.dumps({"status": "error", "message": "Invalid JSON"}))
    finally:
        # Quand le client se déconnecte, on le retire de la liste
        if client_type in clients and clients[client_type] == websocket:
            del clients[client_type]
        print(f"{client_type} déconnecté. Statistiques actuelles: {stats}")

async def main():
    """
    Fonction qui démarre le serveur WebSocket sur le port 8765.
    Elle attend des connexions de clients en boucle.
    """
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("Serveur WebSocket démarré sur ws://0.0.0.0:8765")
        await asyncio.Future()  # Le serveur tourne en continu

if __name__ == "__main__":
    # Point d'entrée du script : on lance le serveur
    asyncio.run(main())

