import asyncio
import websockets
import json
import datetime
import os

clients = {}
ALLOWED_ACTIONS = {"battery", "gps", "altitude", "speed", "command"}

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
    "signal_loss_mode": "return_home"
}

def save_stats():
    with open("stats.json", "w") as f:
        json.dump(stats, f)

async def handler(websocket):
    try:
        ident_msg = await websocket.recv()
        ident_data = json.loads(ident_msg)
        client_type = ident_data.get("type")
        if client_type not in ["raspberry", "flutter"]:
            await websocket.send(json.dumps({"status": "error", "message": "Unknown client type"}))
            return
        clients[client_type] = websocket
        if client_type == "raspberry" and "flutter" in clients:
            await clients["flutter"].send(json.dumps({"drone_connected": True}))

        await websocket.send(json.dumps({
            "status": "ok",
            "message": f"{client_type} registered",
            "signal_loss_mode": stats.get("signal_loss_mode", "return_home")
        }))
    except Exception as e:
        await websocket.send(json.dumps({"status": "error", "message": str(e)}))
        return

    try:
        async for message in websocket:
            print(f"[{datetime.datetime.now()}] Message reçu de {client_type}: {message}")
            try:
                data = json.loads(message)
                action = data.get("action")
                if action not in ALLOWED_ACTIONS:
                    await websocket.send(json.dumps({"status": "error", "message": "Unknown action"}))
                    continue

                if client_type == "raspberry":
                    stats["raspberry_messages"] += 1
                    if action not in {"battery", "gps", "altitude", "speed"}:
                        await websocket.send(json.dumps({"status": "error", "message": "Action not allowed for raspberry"}))
                        continue
                    if action == "battery":
                        stats["last_battery"] = data.get("value")
                        stats["last_battery_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if action == "gps":
                        stats["last_latitude"] = data.get("latitude")
                        stats["last_longitude"] = data.get("longitude")
                        stats["last_gps_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        if stats["start_latitude"] is None and stats["start_longitude"] is None:
                            stats["start_latitude"] = data.get("latitude")
                            stats["start_longitude"] = data.get("longitude")
                            stats["start_gps_time"] = stats["last_gps_time"]
                    if action == "altitude":
                        stats["last_altitude"] = data.get("value")
                        stats["last_altitude_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if action == "speed":
                        stats["last_speed"] = data.get("value")
                        stats["last_speed_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if action == "flight_mode":
                        stats["last_flight_mode"] = data.get("value")
                        stats["last_flight_mode_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    data["received_at"] = datetime.datetime.now().isoformat()
                    save_stats()

                elif client_type == "flutter":
                    stats["flutter_messages"] += 1
                    if action not in {"command", "gps"}:
                        await websocket.send(json.dumps({"status": "error", "message": "Action not allowed for flutter"}))
                        continue
                    if action == "command":
                        command = data.get("command")
                        if command == "set_signal_loss_mode":
                            mode = data.get("mode", "return_home")
                            stats["signal_loss_mode"] = mode
                            save_stats()
                            print(f"Mode de perte de signal changé: {mode}")
                            continue
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
                        stats["last_flutter_gps_time"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        data["handled_by"] = "server"
                    save_stats()

                target = "flutter" if client_type == "raspberry" else "raspberry"
                if target in clients:
                    entry = {
                        "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "data": data
                    }
                    if client_type == "raspberry":
                        stats["raspberry_to_flutter"].append(entry)
                        stats["raspberry_to_flutter"] = stats["raspberry_to_flutter"][-10:]
                    else:
                        stats["flutter_to_raspberry"].append(entry)
                        stats["flutter_to_raspberry"] = stats["flutter_to_raspberry"][-10:]
                    save_stats()
                    await clients[target].send(json.dumps(data))
                else:
                    await websocket.send(json.dumps({"status": "error", "message": f"{target} not connected"}))
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"status": "error", "message": "Invalid JSON"}))
    finally:
        if client_type in clients and clients[client_type] == websocket:
            del clients[client_type]
        print(f"{client_type} déconnecté. Statistiques actuelles: {stats}")

async def main():
    port = int(os.environ.get("PORT", 8765))  # Utilisé par Render
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"Serveur WebSocket démarré sur ws://0.0.0.0:{port}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())