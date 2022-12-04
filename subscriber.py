from flask import Flask, request, jsonify
import threading
import json
import requests
import socket
import sys  

host_name = "0.0.0.0"
flask_port = 4000
id = '1.1.1.1:1010' 
app = Flask(__name__)

leader_url = '0.0.0.0:2000'
zookeeper_url = '0.0.0.0:1000'

@app.route("/", methods=['GET'])
def home():
  return "Home"


# for dev to call
@app.route("/new_subscription", methods=['POST'])
def new_subscription():
  msg = json.loads(request.data)
 
  obj = {"subscriber_id" : id,
        "publisher_name" : msg['publisher_name']}
  call_zookeeper()
  response = requests.post('http://' + leader_url + "/subscribe", json = obj)
  return response.json()


# receive msg data from node
@app.route("/send_to_subscriber", methods=['POST'])
def send_to_subscriber():
  msg = json.loads(request.data)
  print('Yayyyy! message received')
  print(msg)
  response = {"status":"success"}
  return jsonify(response)

def call_zookeeper():
  global mode_leader, leader_url
  response = requests.get('http://' + zookeeper_url + '/leader')
  r = response.json()
  leader_url = r['leader']


if __name__ == "__main__":
  if len(sys.argv) > 1:
    flask_port = sys.argv[1] # eg. 3000
    if len(sys.argv) > 2:
      zookeeper_url = sys.argv[2]

  call_zookeeper()
  
  threading.Thread(target=lambda: app.run(
    host=host_name, port=flask_port, debug=True, use_reloader=False, threaded=True)
                   ).start()
  
  host_name = socket.gethostname()
  host_ip = socket.gethostbyname(host_name)
  
  id = host_ip + ":" + flask_port

