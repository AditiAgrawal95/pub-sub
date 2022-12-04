from flask import Flask, request, jsonify
import threading
import json
import requests
import socket
import sys  

host_name = "0.0.0.0"
flask_port = 1000
app = Flask(__name__)

leader_url = '172.31.128.20:2000'


@app.route("/", methods=['GET'])
def home():
  return "Home"


@app.route("/leader", methods=['GET'])
def leader():
  global leader_url
  print(leader_url)
  obj = {"leader" : leader_url}
  return jsonify(obj)

@app.route("/update_leader", methods=['POST'])
def update_leader():
  global leader_url
  msg = json.loads(request.data)
  leader_url = msg["new_leader_url"]
  print('Updated leader: ' + str(leader_url))
  response = {"status":"success"}
  return jsonify(response)


if __name__ == "__main__":
  if len(sys.argv) > 1:
    flask_port = sys.argv[1] # eg. 1000
    if len(sys.argv) > 2:
      leader_url = sys.argv[2]

  if len(sys.argv) < 3:
    host_ip = socket.gethostbyname(socket.gethostname())
    leader_url = host_ip + ':2000'
  
  threading.Thread(target=lambda: app.run(
    host=host_name, port=flask_port, debug=True, use_reloader=False, threaded=True)
                   ).start()
  
